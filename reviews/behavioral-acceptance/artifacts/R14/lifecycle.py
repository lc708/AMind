"""Offline lifecycle reference. SQLite is both durable state and the mock effect sink.
No network/client initialization, provider credentials, or real machines are used.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
import sqlite3


class Rejected(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def memory_access(request_tenant, record):
    reasons = []
    if not request_tenant or record.get("record_tenant") != request_tenant:
        reasons.append("tenant_mismatch")
    if record.get("expired") is not False:
        reasons.append("expired_or_missing_expiry")
    return {"allowed": not reasons, "reasons": reasons}


class Controller:
    """All entry points require an authenticated tenant from the caller, never event data."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions(
          id TEXT PRIMARY KEY, tenant TEXT NOT NULL, phase TEXT NOT NULL DEFAULT 'running',
          connected INTEGER NOT NULL DEFAULT 0, cancelled INTEGER NOT NULL DEFAULT 0,
          epoch INTEGER NOT NULL DEFAULT 0, cancel_ack INTEGER NOT NULL DEFAULT 0,
          terminal_at INTEGER, agent_id TEXT NOT NULL DEFAULT 'fixture-agent',
          agent_version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS machines(
          session TEXT PRIMARY KEY REFERENCES sessions(id), id TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS receipts(
          session TEXT REFERENCES sessions(id), id TEXT, body TEXT NOT NULL,
          decision TEXT NOT NULL, PRIMARY KEY(session,id));
        CREATE TABLE IF NOT EXISTS effects(
          session TEXT REFERENCES sessions(id), key TEXT, state TEXT NOT NULL,
          epoch INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(session,key));
        CREATE TABLE IF NOT EXISTS mock_writes(
          session TEXT, key TEXT, value TEXT, PRIMARY KEY(session,key));
        CREATE TABLE IF NOT EXISTS artifacts(
          session TEXT REFERENCES sessions(id), name TEXT, content TEXT NOT NULL,
          archived INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(session,name));
        CREATE TABLE IF NOT EXISTS archives(
          session TEXT, name TEXT, content TEXT NOT NULL, digest TEXT NOT NULL,
          PRIMARY KEY(session,name));
        """)

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def register(self, session, tenant):
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO sessions(id,tenant) VALUES (?,?)", (session, tenant))
            self._session(session, tenant)

    def _session(self, session, tenant):
        row = self.db.execute("SELECT * FROM sessions WHERE id=?", (session,)).fetchone()
        if row is None or not tenant or row["tenant"] != tenant:
            raise Rejected("unknown_or_unauthorized_session")
        return row

    def put_artifact(self, session, tenant, name, content):
        with self.transaction():
            s = self._session(session, tenant)
            if s["cancelled"] or s["terminal_at"] is not None:
                raise Rejected("artifact_write_closed")
            self.db.execute("INSERT INTO artifacts VALUES (?,?,?,0)", (session, name, content))

    def handle(self, event, tenant):
        """Trusted domain event ingress; fixture kinds are NOT provider webhook names."""
        if not isinstance(event, dict) or not all(isinstance(event.get(k), str) and event[k] for k in ("id", "session", "kind")):
            raise Rejected("invalid_event")
        sid, eid, kind = event["session"], event["id"], event["kind"]
        body = canonical(event)
        with self.transaction():
            s = self._session(sid, tenant)
            receipt = self.db.execute("SELECT * FROM receipts WHERE session=? AND id=?", (sid, eid)).fetchone()
            if receipt:
                if receipt["body"] != body:
                    raise Rejected("event_id_payload_conflict")
                return {"decision": "duplicate", "original": receipt["decision"]}
            decision = self._apply(s, event)
            self.db.execute("INSERT INTO receipts VALUES (?,?,?,?)", (sid, eid, body, decision))
            return {"decision": decision}

    def _apply(self, s, e):
        sid, kind = s["id"], e["kind"]
        if kind == "environment_connection_required":
            if s["cancelled"] or s["terminal_at"] is not None:
                return "wake_suppressed"
            machine = "mock-machine-" + sha256(sid.encode()).hexdigest()[:12]
            inserted = self.db.execute("INSERT OR IGNORE INTO machines VALUES (?,?)", (sid, machine)).rowcount
            self.db.execute("UPDATE sessions SET connected=1 WHERE id=?", (sid,))
            return "mock_machine_created" if inserted else "existing_machine_reconnected"
        if kind == "environment_disconnected":
            self.db.execute("UPDATE sessions SET connected=0 WHERE id=?", (sid,))
            return "disconnected_artifacts_retained"
        if kind == "cancel_requested":
            if s["terminal_at"] is not None and not s["cancelled"]:
                return "already_terminal"
            if not s["cancelled"]:
                self.db.execute("UPDATE sessions SET cancelled=1,epoch=epoch+1,phase='cancelling' WHERE id=?", (sid,))
                self.db.execute("UPDATE effects SET state='blocked' WHERE session=? AND state='queued'", (sid,))
            return "cancellation_fenced"
        if kind == "effect_started":
            # This is an observation, not permission to perform an effect.
            key = e.get("key")
            if not isinstance(key, str) or not key:
                raise Rejected("missing_effect_key")
            self.db.execute("INSERT INTO effects VALUES (?,?, 'observed_unknown', ?,?) ON CONFLICT(session,key) DO UPDATE SET state='observed_unknown'", (sid, key, s["epoch"], canonical({"source_event": e["id"]})))
            self.db.execute("UPDATE sessions SET phase='needs_reconciliation',terminal_at=NULL WHERE id=?", (sid,))
            return "late_effect_after_cancel_requires_reconciliation" if s["cancelled"] else "observed_effect_requires_reconciliation"
        if kind == "cancel_acknowledged":
            if not s["cancelled"]:
                raise Rejected("unsolicited_cancel_ack")
            self.db.execute("UPDATE sessions SET cancel_ack=1 WHERE id=?", (sid,))
            unknown = self.db.execute("SELECT 1 FROM effects WHERE session=? AND state IN ('observed_unknown','applied_uncompensated')", (sid,)).fetchone()
            if unknown:
                return "cancel_ack_pending_effect_reconciliation"
            self.db.execute("UPDATE sessions SET phase='cancelled',terminal_at=? WHERE id=?", (self._time(e), sid))
            return "cancelled_confirmed"
        if kind == "session_idle":
            if s["cancelled"] or s["terminal_at"] is not None or s["phase"] == "needs_reconciliation":
                return "idle_does_not_override_stop_state"
            phases = {"requires_action": "waiting_action", "budget_reached": "paused_budget", "end_turn": "awaiting_outcome", "retries_exhausted": "failed"}
            phase = phases.get(e.get("stop_reason"), "unknown_idle")
            self.db.execute("UPDATE sessions SET phase=? WHERE id=?", (phase, sid))
            if phase == "failed":
                self.db.execute("UPDATE sessions SET terminal_at=? WHERE id=?", (self._time(e), sid))
            return phase
        if kind == "outcome_verified":
            pending = self.db.execute("SELECT 1 FROM effects WHERE session=? AND state IN ('queued','observed_unknown')", (sid,)).fetchone()
            if s["cancelled"] or s["phase"] != "awaiting_outcome" or pending or e.get("passed") is not True:
                return "success_rejected"
            self.db.execute("UPDATE sessions SET phase='succeeded',terminal_at=? WHERE id=?", (self._time(e), sid))
            return "success_verified"
        raise Rejected("unknown_event_kind")

    @staticmethod
    def _time(event):
        value = event.get("at")
        if type(value) is not int or value < 0:
            raise Rejected("fixed_timestamp_required")
        return value

    def queue_effect(self, session, tenant, key, value):
        if not isinstance(key, str) or not key:
            raise Rejected("missing_effect_key")
        payload = canonical(value)
        with self.transaction():
            s = self._session(session, tenant)
            existing = self.db.execute("SELECT * FROM effects WHERE session=? AND key=?", (session, key)).fetchone()
            if existing:
                if existing["payload"] != payload:
                    raise Rejected("effect_key_payload_conflict")
                return existing["state"]
            if s["cancelled"] or s["phase"] != "running" or not s["connected"]:
                return "blocked"
            self.db.execute("INSERT INTO effects VALUES (?,?, 'queued', ?,?)", (session, key, s["epoch"], payload))
            return "queued"

    def commit_mock_effect(self, session, tenant, key):
        """Mock sink and cancellation share one transaction; do not substitute remote I/O."""
        with self.transaction():
            s = self._session(session, tenant)
            effect = self.db.execute("SELECT * FROM effects WHERE session=? AND key=?", (session, key)).fetchone()
            if not effect:
                return "not_queued"
            if effect["state"] != "queued":
                return effect["state"]
            if s["cancelled"] or s["epoch"] != effect["epoch"] or s["phase"] != "running" or not s["connected"]:
                self.db.execute("UPDATE effects SET state='blocked' WHERE session=? AND key=?", (session, key))
                return "blocked"
            self.db.execute("INSERT OR IGNORE INTO mock_writes VALUES (?,?,?)", (session, key, effect["payload"]))
            self.db.execute("UPDATE effects SET state='committed' WHERE session=? AND key=?", (session, key))
            return "committed"

    def reconcile_effect(self, session, tenant, key, result):
        # Reconciliation evidence is trusted operator/service data, never model text.
        if result not in {"confirmed_not_applied", "compensated", "applied_uncompensated"}:
            raise Rejected("invalid_reconciliation")
        with self.transaction():
            self._session(session, tenant)
            changed = self.db.execute("UPDATE effects SET state=? WHERE session=? AND key=? AND state IN ('observed_unknown','applied_uncompensated')", (result, session, key)).rowcount
            if not changed:
                raise Rejected("no_pending_reconciliation")
            if result == "applied_uncompensated":
                self.db.execute("UPDATE sessions SET phase='cancelled_with_effects' WHERE id=?", (session,))

    def archive_and_cleanup(self, session, tenant, now, retention):
        if type(now) is not int or type(retention) is not int or retention < 0:
            raise Rejected("invalid_retention")
        with self.transaction():
            s = self._session(session, tenant)
            pending = self.db.execute("SELECT 1 FROM effects WHERE session=? AND state IN ('queued','observed_unknown','applied_uncompensated')", (session,)).fetchone()
            if s["terminal_at"] is None or now < s["terminal_at"] + retention or pending:
                return "retained"
            if s["cancelled"] and not s["cancel_ack"]:
                return "retained"
            rows = self.db.execute("SELECT * FROM artifacts WHERE session=?", (session,)).fetchall()
            for row in rows:
                digest = sha256(row["content"].encode()).hexdigest()
                self.db.execute("INSERT OR REPLACE INTO archives VALUES (?,?,?,?)", (session, row["name"], row["content"], digest))
                stored = self.db.execute("SELECT * FROM archives WHERE session=? AND name=?", (session, row["name"])).fetchone()
                if sha256(stored["content"].encode()).hexdigest() != digest:
                    raise Rejected("archive_verification_failed")
            self.db.execute("DELETE FROM artifacts WHERE session=?", (session,))
            return "archived_and_cleaned_mock_workspace"

    def snapshot(self, session, tenant):
        s = dict(self._session(session, tenant))
        for table in ("machines", "effects", "mock_writes", "artifacts", "archives", "receipts"):
            s[table] = [dict(r) for r in self.db.execute(f"SELECT * FROM {table} WHERE session=? ORDER BY rowid", (session,))]
        return s

    def close(self):
        self.db.close()


def accept_webhook(raw, headers, unwrap, durable_enqueue):
    """Verify RAW bytes before enqueue; unwrap/enqueue errors must not get a 2xx ACK.
    Production injection: client.beta.webhooks.unwrap(raw.decode(), headers=headers).
    Production notification worker retrieves current resource/history, then normalizes.
    The callback must durably enqueue + dedupe by verified webhook event.id.
    """
    verified = unwrap(raw, headers)
    durable_enqueue(verified)
    return 204


def replay_with_consolidation(open_stream, list_history, handle):
    """Open buffering stream before history. Domain receipt store deduplicates overlap."""
    stream = open_stream()
    try:
        for event in list_history():
            handle(event)
        for event in stream:
            handle(event)
    finally:
        stream.close()
