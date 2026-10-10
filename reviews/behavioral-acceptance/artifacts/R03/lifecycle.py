#!/usr/bin/env python3
"""Offline, stdlib-only lifecycle coordinator. No provider client or external effects.

The SQLite transaction is the local dispatch/cancellation ordering boundary.
Reservations committed before cancellation remain in flight and need reconciliation.
"""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
import json
import math
from pathlib import Path
import sqlite3
import tempfile


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ReconciliationRequired(RuntimeError):
    pass


class Coordinator:
    TERMINAL = {"completed", "failed", "cancelled"}
    KINDS = {"environment_connection_required", "environment_connected",
             "environment_disconnected", "cancel_requested", "effect_started",
             "idle", "task_completed", "task_failed"}

    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS sessions (
            tenant TEXT, session TEXT, data TEXT NOT NULL, PRIMARY KEY(tenant,session));
          CREATE TABLE IF NOT EXISTS events (
            tenant TEXT, session TEXT, id TEXT, hash TEXT, body TEXT, result TEXT,
            PRIMARY KEY(tenant,session,id));
          CREATE TABLE IF NOT EXISTS incidents (
            tenant TEXT, session TEXT, code TEXT, detail TEXT);
          CREATE TABLE IF NOT EXISTS effects (
            tenant TEXT, session TEXT, key TEXT, hash TEXT, state TEXT,
            result TEXT, evidence TEXT, PRIMARY KEY(tenant,session,key));
          CREATE TABLE IF NOT EXISTS inbox (
            tenant TEXT, hash TEXT, body TEXT, status TEXT,
            PRIMARY KEY(tenant,hash));
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def create(self, tenant, session, *, deadline=10000):
        if not all(isinstance(x, str) and x for x in (tenant, session)):
            raise ValueError("trusted tenant and session required")
        state = dict(state="queued", cancel_requested=False, compute_id=None,
                     environment_id=None, provision_key=None, provision_count=0,
                     environment_health="unknown", reconnect_required=False,
                     event_cursor=0, environment_sequence=-1, deadline=deadline,
                     config_version="local-v1", artifacts={}, cleanup="pending",
                     completion_reported=False)
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO sessions VALUES (?,?,?)",
                            (tenant, session, canonical(state)))

    def state(self, tenant, session):
        row = self.db.execute("SELECT data FROM sessions WHERE tenant=? AND session=?",
                              (tenant, session)).fetchone()
        if row is None:
            raise PermissionError("session is not owned by trusted tenant")
        return json.loads(row[0])

    def save(self, tenant, session, state):
        self.db.execute("UPDATE sessions SET data=? WHERE tenant=? AND session=?",
                        (canonical(state), tenant, session))

    def incident(self, tenant, session, code, detail):
        self.db.execute("INSERT INTO incidents VALUES (?,?,?,?)",
                        (tenant, session, code, detail))

    def pending(self, tenant, session):
        return [dict(r) for r in self.db.execute(
            "SELECT key,state,evidence FROM effects WHERE tenant=? AND session=? AND state='unknown'",
            (tenant, session))]

    @staticmethod
    def validate_event(event):
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        for field in ("id", "session", "kind"):
            if not isinstance(event.get(field), str) or not event[field]:
                raise ValueError("invalid event " + field)
        if event["kind"] not in Coordinator.KINDS:
            raise ValueError("unsupported event kind")
        if event["kind"] == "effect_started" and (
            not isinstance(event.get("key"), str) or not event["key"]
        ):
            raise ValueError("effect observation requires key")
        if "sequence" in event and (type(event["sequence"]) is not int or event["sequence"] < 0):
            raise ValueError("invalid sequence")

    def ingest_trusted(self, tenant, event):
        """Internal worker boundary, not an unsigned HTTP endpoint.

        effect_started is a historical observation, never a dispatch instruction.
        """
        self.validate_event(event)
        session, kind = event["session"], event["kind"]
        key, fingerprint = (tenant, session, event["id"]), digest(event)
        with self.transaction():
            state = self.state(tenant, session)
            old = self.db.execute("SELECT hash,result FROM events WHERE tenant=? AND session=? AND id=?", key).fetchone()
            if old:
                if old[0] != fingerprint:
                    self.incident(tenant, session, "conflicting_event_replay", event["id"])
                    return {"status": "rejected", "reason": "conflicting_event_replay"}
                return {"status": "duplicate", "original": json.loads(old[1])}
            result = {"status": "accepted", "kind": kind}
            state["event_cursor"] += 1  # Local arrival cursor, not provider causal order.
            stale = kind.startswith("environment_") and "sequence" in event and event["sequence"] <= state["environment_sequence"]
            if stale:
                result = {"status": "ignored", "reason": "stale_environment_event"}
            elif kind == "effect_started":
                # Never erase a reported effect because it violated the dispatch gate.
                existing = self.db.execute("SELECT state FROM effects WHERE tenant=? AND session=? AND key=?",
                                           (tenant, session, event["key"])).fetchone()
                if not existing:
                    self.db.execute("INSERT INTO effects VALUES (?,?,?,?,?,NULL,NULL)",
                                    (tenant, session, event["key"], None, "unknown"))
                if state["cancel_requested"]:
                    self.incident(tenant, session, "effect_after_cancel", event["key"])
                if state["state"] in self.TERMINAL:
                    self.incident(tenant, session, "effect_after_terminal", event["key"])
                result["reconciliation_required"] = not existing or existing[0] == "unknown"
            elif state["state"] in self.TERMINAL:
                result = {"status": "ignored", "reason": "terminal_state"}
            elif kind == "cancel_requested":
                state["cancel_requested"] = True
                state["state"] = "cancelling"
            elif kind == "environment_connection_required":
                if state["cancel_requested"]:
                    result = {"status": "blocked", "reason": "cancel_requested"}
                elif state["compute_id"] is None:
                    # One durable local mock resource. No machine is actually created.
                    token = digest([tenant, session, "provision-v1"])
                    state.update(compute_id="mock-machine-" + token[:12],
                                 environment_id="mock-env-" + token[:12],
                                 provision_key=token, provision_count=1, state="provisioning")
            elif kind == "environment_disconnected":
                state["environment_health"] = "disconnected"
                state["reconnect_required"] = True
                if not state["cancel_requested"]:
                    state["state"] = "waiting_for_environment"
                # No provisioning, deletion, resubmission or success transition.
            elif kind == "environment_connected":
                state["environment_health"] = "connected"
                # Reconnect is observational: reconcile authoritative state before running.
                if state["reconnect_required"]:
                    result["requires_reconciliation"] = True
                elif not state["cancel_requested"]:
                    state["state"] = "running"
            elif kind == "idle":
                if not state["cancel_requested"]:
                    state["state"] = "waiting_for_input"
            elif kind == "task_completed":
                state["completion_reported"] = True
                result["requires_outcome_verification"] = True
            elif kind == "task_failed":
                state["state"] = "failed"
            if kind.startswith("environment_") and "sequence" in event and not stale:
                state["environment_sequence"] = event["sequence"]
            self.save(tenant, session, state)
            self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)",
                            (*key, fingerprint, canonical(event), canonical(result)))
            return result

    def dispatch(self, tenant, session, key, request, handler, *, now):
        """Only registered local mock handler is passed by application code.

        Commit a reservation atomically against cancellation before calling it.
        Any handler exception leaves an unknown outcome, never an automatic retry.
        """
        if not isinstance(key, str) or not key or not isinstance(request, dict):
            raise ValueError("nonempty key and object request required")
        if set(request) != {"operation", "value"} or request["operation"] != "mock_write" or not isinstance(request["value"], str):
            raise ValueError("only the fixed local mock_write contract is registered")
        fingerprint = digest(request)
        with self.transaction():
            state = self.state(tenant, session)
            old = self.db.execute("SELECT hash,state,result FROM effects WHERE tenant=? AND session=? AND key=?",
                                  (tenant, session, key)).fetchone()
            if old:
                if old[0] is None:
                    raise ReconciliationRequired("observed effect has no trusted request; reconcile first")
                if old[0] != fingerprint:
                    raise ValueError("idempotency key payload changed")
                if old[1] != "succeeded":
                    raise ReconciliationRequired("unknown or failed effect; no blind retry")
                return json.loads(old[2])
            if state["cancel_requested"] or state["state"] in self.TERMINAL:
                raise PermissionError("new dispatch blocked by cancellation or terminal state")
            if now >= state["deadline"]:
                raise TimeoutError("task deadline elapsed")
            if state["environment_health"] != "connected" or state["reconnect_required"]:
                raise PermissionError("environment must be connected and reconciled")
            self.db.execute("INSERT INTO effects VALUES (?,?,?,?,?,NULL,NULL)",
                            (tenant, session, key, fingerprint, "unknown"))
        result = handler(request, key)
        encoded = canonical(result)
        with self.transaction():
            self.db.execute("UPDATE effects SET state='succeeded',result=? WHERE tenant=? AND session=? AND key=?",
                            (encoded, tenant, session, key))
        return result

    def reconcile_effect(self, tenant, session, key, *, outcome, evidence, result=None):
        if outcome not in {"succeeded", "failed"} or not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("trusted external outcome evidence required")
        with self.transaction():
            self.state(tenant, session)
            changed = self.db.execute(
                "UPDATE effects SET state=?,result=?,evidence=? WHERE tenant=? AND session=? AND key=? AND state='unknown'",
                (outcome, canonical(result), evidence, tenant, session, key)).rowcount
            if changed != 1:
                raise ValueError("one unknown effect required")

    def recover(self, tenant, session, *, environment_health, snapshot_version):
        """Application adapter supplies retrieved, ownership-checked authoritative state.

        Only health is reconciled here. Effects retain their separate evidence requirement.
        """
        if environment_health not in {"connected", "disconnected"} or type(snapshot_version) is not int:
            raise ValueError("invalid authoritative snapshot")
        with self.transaction():
            state = self.state(tenant, session)
            if snapshot_version <= state["environment_sequence"]:
                raise ValueError("snapshot is not newer than known environment state")
            state.update(environment_health=environment_health,
                         environment_sequence=snapshot_version,
                         reconnect_required=environment_health != "connected")
            if state["state"] not in self.TERMINAL and not state["cancel_requested"]:
                state["state"] = "running" if environment_health == "connected" else "waiting_for_environment"
            self.save(tenant, session, state)

    def checkpoint(self, tenant, session, path):
        """Register a durable local artifact; does not imply replacement disks persist."""
        path = Path(path).resolve()
        value = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.transaction():
            state = self.state(tenant, session)
            state["artifacts"][str(path)] = value
            self.save(tenant, session, state)
        return value

    def finish(self, tenant, session, *, expected_artifact=None, expected_hash=None):
        with self.transaction():
            state = self.state(tenant, session)
            if self.pending(tenant, session):
                raise ReconciliationRequired("unknown effects prevent finalization")
            if state["state"] in self.TERMINAL:
                return state["state"]
            if state["cancel_requested"]:
                state["state"] = "cancelled"
            else:
                if not state["completion_reported"] or expected_artifact is None or expected_hash is None:
                    raise ValueError("terminal report and independently expected artifact required")
                path = str(Path(expected_artifact).resolve())
                actual = hashlib.sha256(Path(path).read_bytes()).hexdigest()
                if state["artifacts"].get(path) != expected_hash or actual != expected_hash:
                    raise ValueError("artifact outcome failed verification")
                failed = self.db.execute("SELECT 1 FROM effects WHERE tenant=? AND session=? AND state='failed'", (tenant, session)).fetchone()
                if failed:
                    raise ValueError("failed required effect prevents success")
                state["state"] = "completed"
            self.save(tenant, session, state)
            return state["state"]

    def cleanup(self, tenant, session, *, simulate_failure=False):
        """Mock teardown only; artifacts remain retained. Safe to retry after failure."""
        with self.transaction():
            state = self.state(tenant, session)
            if state["state"] not in self.TERMINAL or self.pending(tenant, session):
                raise ReconciliationRequired("terminal state and reconciled effects required")
            if state["cleanup"] == "complete":
                return "complete"
            for path, expected in state["artifacts"].items():
                if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                    raise ValueError("checkpoint is missing or changed; retain compute")
            state["cleanup"] = "retry_required" if simulate_failure else "complete"
            if not simulate_failure:
                state["environment_health"] = "disposed"
            self.save(tenant, session, state)
            return state["cleanup"]

    @staticmethod
    def sign_fixture(body, timestamp, fixture_key):
        return hmac.new(fixture_key, str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()

    def receive_webhook(self, tenant, raw_body, *, signature, timestamp, fixture_key, now):
        """Local HMAC protocol fixture, NOT a provider-compatible signature verifier.

        Verify raw bytes and freshness before durable enqueue. Worker does actual work.
        Tenant comes from trusted endpoint configuration, never body instructions.
        """
        if type(timestamp) is not int or abs(now - timestamp) > 300:
            raise PermissionError("webhook timestamp outside allowed window")
        expected = self.sign_fixture(raw_body, timestamp, fixture_key)
        if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
            raise PermissionError("invalid webhook signature")
        event = json.loads(raw_body)
        self.validate_event(event)
        fingerprint = hashlib.sha256(raw_body).hexdigest()
        with self.transaction():
            self.state(tenant, event["session"])
            inserted = self.db.execute("INSERT OR IGNORE INTO inbox VALUES (?,?,?,'queued')",
                                       (tenant, fingerprint, raw_body.decode())).rowcount
        return "queued" if inserted else "duplicate"

    def drain_webhooks(self):
        results = []
        for row in self.db.execute("SELECT tenant,hash,body FROM inbox WHERE status='queued'").fetchall():
            result = self.ingest_trusted(row[0], json.loads(row[2]))
            # Crash before this update replays through durable event deduplication.
            self.db.execute("UPDATE inbox SET status='processed' WHERE tenant=? AND hash=?", (row[0], row[1]))
            results.append(result)
        return results


def read_memory(request_tenant, record, *, now):
    """Deny tenant/TTL violations before exposing content. Read-only, no durable learning."""
    reasons = []
    if record.get("record_tenant") != request_tenant:
        reasons.append("memory_tenant_mismatch")
    expires_at = record.get("expires_at", 0)
    valid_expiry = type(expires_at) in (int, float) and math.isfinite(expires_at)
    if record.get("expired") is True or not valid_expiry or expires_at <= now:
        reasons.append("expired_memory")
    if reasons:
        return {"allowed": False, "reasons": reasons}
    if not all(record.get(k) for k in ("source", "version", "scope")) or record["scope"] != "task_data":
        return {"allowed": False, "reasons": ["invalid_memory_metadata"]}
    return {"allowed": True, "content": record.get("content"), "role": "untrusted_task_data"}


def replay(task_path, output):
    task_path, output = Path(task_path), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    raw = task_path.read_bytes()
    task = json.loads(raw)
    fixture = task["fixture"]
    tenant = fixture["memory"]["request_tenant"]
    session = fixture["events"][0]["session"]
    normalized = [dict(id="fixture-bootstrap", task_id=session, tenant_id=tenant, kind="task_started"),
                  dict(id="fixture-webhook", task_id=session, tenant_id=tenant, kind="webhook_received", signature_verified=fixture["webhook_signature_checked"]),
                  dict(id="fixture-memory", task_id=session, tenant_id=tenant, kind="memory_read", memory_tenant_id=fixture["memory"]["record_tenant"], expires_at=0, at=1)]
    for event in fixture["events"]:
        item = dict(event, task_id=event["session"], tenant_id=tenant)
        if "key" in item:
            item["idempotency_key"] = item["key"]
        normalized.append(item)
    (output / "original-normalized.jsonl").write_text("".join(canonical(e) + "\n" for e in normalized))
    with tempfile.TemporaryDirectory(prefix="replay-", dir=output) as scratch:
        app = Coordinator(Path(scratch) / "state.sqlite")
        app.create(tenant, session)
        artifact = output / "retained-notes.txt"
        artifact.write_text("Fixed local artifact: retain across disconnect and cancellation.\n")
        artifact_hash = app.checkpoint(tenant, session, artifact)
        timeline = [dict(event=event, result=app.ingest_trusted(tenant, event)) for event in fixture["events"]]
        try:
            app.dispatch(tenant, session, "new-write-after-cancel", {"operation": "mock_write", "value": "blocked"},
                         lambda request, key: (_ for _ in ()).throw(AssertionError("must never execute")), now=1)
        except PermissionError as error:
            dispatch_result = str(error)
        try:
            app.receive_webhook(tenant, canonical(fixture["events"][0]).encode(), signature=None,
                                timestamp=1000, fixture_key=b"PUBLIC-LOCAL-FIXTURE-ONLY", now=1000)
        except PermissionError as error:
            webhook_result = str(error)
        try:
            app.finish(tenant, session)
        except ReconciliationRequired as error:
            finish_result = str(error)
        report = dict(input_sha256=hashlib.sha256(raw).hexdigest(), evidence_level="local fixed fixtures; no model/provider calls",
                      normalization="Trusted fixture harness binds t1/s1; synthetic task start plus unsigned-webhook/memory facts; e1-e4 retained unchanged; expiry represented by expires_at=0, at=1.",
                      timeline=timeline, state=app.state(tenant, session),
                      incidents=[dict(r) for r in app.db.execute("SELECT * FROM incidents")],
                      unresolved_effects=app.pending(tenant, session), memory=read_memory(tenant, fixture["memory"], now=1),
                      new_dispatch=dispatch_result, unsigned_webhook=webhook_result, finalization=finish_result,
                      artifact_preserved=artifact.exists() and hashlib.sha256(artifact.read_bytes()).hexdigest() == artifact_hash)
        with sqlite3.connect(output / "state.sqlite") as saved:
            app.db.backup(saved)
        app.close()
    (output / "replay.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"evidence": str(output / "replay.json"), "state": report["state"]["state"],
                      "mock_machine_creations": report["state"]["provision_count"],
                      "unresolved_effects": len(report["unresolved_effects"]), "artifact_preserved": report["artifact_preserved"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="task.json")
    parser.add_argument("--output", default="evidence")
    args = parser.parse_args()
    replay(args.task, args.output)
