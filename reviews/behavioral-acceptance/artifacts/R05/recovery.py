"""Offline side-effect recovery. Python standard library only; no model or network calls."""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


class InvalidInput(ValueError): pass
class Unauthorized(PermissionError): pass
class KeyConflict(ValueError): pass
class TransientRemoteError(Exception):
    def __init__(self, message="outcome unknown", retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after
class PermanentRejection(Exception): pass


@dataclass(frozen=True)
class Principal:
    tenant: str
    owned_tasks: frozenset[str]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def validate(operation, principal):
    fields = {"tenant", "task", "call_id", "action", "amount"}
    if not isinstance(operation, dict) or set(operation) != fields:
        raise InvalidInput("exact operation fields required")
    if any(type(operation[f]) is not str or not operation[f] or len(operation[f]) > 128
           for f in ("tenant", "task", "call_id", "action")):
        raise InvalidInput("nonempty bounded identifiers required")
    if operation["action"] != "charge" or type(operation["amount"]) is not int or operation["amount"] <= 0:
        raise InvalidInput("charge requires a positive integer amount in fixture units")
    if operation["tenant"] != principal.tenant or operation["task"] not in principal.owned_tasks:
        raise Unauthorized("authenticated tenant must own the task-bound invoice")
    identity = ["charge-recovery-v1", principal.tenant, operation["task"], operation["call_id"]]
    return hashlib.sha256(canonical(identity).encode()).hexdigest(), canonical(operation)


@contextmanager
def transaction(path):
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=FULL")
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


class MockRemote:
    """Durable local fixed mock. Atomic key uniqueness is an ASSUMED remote contract."""
    def __init__(self, path):
        self.path = str(path)
        self.mode = "ok"
        self.lookup_mode = "ok"
        self.after_commit = None
        with transaction(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS charges (id INTEGER PRIMARY KEY, key TEXT UNIQUE, payload TEXT NOT NULL)")
            c.execute("CREATE TABLE IF NOT EXISTS calls (kind TEXT NOT NULL)")

    def charge(self, key, payload):
        with transaction(self.path) as c:
            c.execute("INSERT INTO calls VALUES ('charge')")
        if self.mode == "before_timeout":
            raise TransientRemoteError()
        if self.mode == "rate_limit":
            raise TransientRemoteError("rate limited", retry_after=10)
        if self.mode == "permanent":
            raise PermanentRejection("declined: guaranteed no operation accepted")
        if self.mode == "bug":
            raise RuntimeError("unexpected adapter bug")
        with transaction(self.path) as c:
            row = c.execute("SELECT * FROM charges WHERE key=?", (key,)).fetchone()
            if row is not None and row["payload"] != payload:
                raise KeyConflict("remote key payload conflict")
            if row is None:
                c.execute("INSERT INTO charges(key,payload) VALUES (?,?)", (key, payload))
                row = c.execute("SELECT * FROM charges WHERE key=?", (key,)).fetchone()
            receipt = {"operation_id": f"op{row['id']}", "key": key, "payload": row["payload"]}
        if self.after_commit:
            self.after_commit()
        if self.mode == "after_timeout":
            raise TransientRemoteError()
        return receipt

    def lookup_operation(self, key):
        with transaction(self.path) as c:
            c.execute("INSERT INTO calls VALUES ('lookup')")
            row = c.execute("SELECT * FROM charges WHERE key=?", (key,)).fetchone()
        if self.lookup_mode == "timeout":
            raise TransientRemoteError("lookup unavailable")
        if self.lookup_mode == "stale":
            return None
        if row is None:
            return None
        return {"operation_id": f"op{row['id']}", "key": key, "payload": row["payload"]}

    def counts(self):
        with transaction(self.path) as c:
            return {"effects": c.execute("SELECT COUNT(*) FROM charges").fetchone()[0],
                    **{kind: c.execute("SELECT COUNT(*) FROM calls WHERE kind=?", (kind,)).fetchone()[0]
                       for kind in ("charge", "lookup")}}


class Recovery:
    TERMINAL = {"succeeded", "failed", "cancelled", "manual_review"}
    MAX_CHARGE_ATTEMPTS = 3
    MAX_LOOKUP_FAILURES = 3

    def __init__(self, path, remote, clock=lambda: 0.0):
        self.path, self.remote, self.clock = str(path), remote, clock
        with transaction(self.path) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS operations (
                key TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, remote_id TEXT,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                retry_at REAL NOT NULL DEFAULT 0, lookup_after REAL NOT NULL DEFAULT 0,
                lookup_failures INTEGER NOT NULL DEFAULT 0, error TEXT)""")
            c.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, key TEXT, event TEXT)")

    @staticmethod
    def delay(key, attempt):
        # Reproducible per-key jitter; production may inject its own clock/jitter policy.
        return min(30.0, 2 ** (attempt - 1) + int(key[:4], 16) / 65536)

    def _event(self, c, key, event):
        c.execute("INSERT INTO events(key,event) VALUES (?,?)", (key, event))

    def register(self, operation, principal):
        key, payload = validate(operation, principal)
        with transaction(self.path) as c:
            c.execute("INSERT OR IGNORE INTO operations(key,payload,state) VALUES (?,?,'ready')", (key, payload))
            row = c.execute("SELECT * FROM operations WHERE key=?", (key,)).fetchone()
            if row["payload"] != payload:
                raise KeyConflict("call identity reused with different arguments")
        return key

    def status(self, operation, principal):
        key, payload = validate(operation, principal)
        with transaction(self.path) as c:
            row = c.execute("SELECT * FROM operations WHERE key=?", (key,)).fetchone()
            if row is None:
                return None
            if row["payload"] != payload:
                raise KeyConflict("call identity reused with different arguments")
            result = dict(row)
        result.pop("payload")
        result["cancellation"] = (
            "not_requested" if not result["cancel_requested"] else
            "prevented" if result["state"] == "cancelled" else
            "too_late_charge_succeeded" if result["state"] == "succeeded" else
            "no_charge_rejected" if result["state"] == "failed" else
            "pending_outcome_unknown")
        return result

    def cancel(self, operation, principal):
        key = self.register(operation, principal)
        with transaction(self.path) as c:
            c.execute("""UPDATE operations SET cancel_requested=1,
                state=CASE WHEN state='ready' THEN 'cancelled' ELSE state END WHERE key=?""", (key,))
            self._event(c, key, "cancellation_requested")
        return self.status(operation, principal)

    def _claim(self, key):
        with transaction(self.path) as c:
            row = c.execute("SELECT * FROM operations WHERE key=?", (key,)).fetchone()
            if (row["state"] in self.TERMINAL or row["cancel_requested"] or
                    self.clock() < row["retry_at"] or row["attempts"] >= self.MAX_CHARGE_ATTEMPTS):
                return None
            attempt = row["attempts"] + 1
            c.execute("UPDATE operations SET state='dispatched',attempts=?,retry_at=?,error=NULL WHERE key=?",
                      (attempt, self.clock() + self.delay(key, attempt), key))
            self._event(c, key, f"dispatch_recorded:{attempt}")
            return attempt, row["payload"]

    def _success(self, key, payload, receipt):
        if receipt.get("key") != key or receipt.get("payload") != payload or not receipt.get("operation_id"):
            raise KeyConflict("lookup receipt does not match immutable request")
        with transaction(self.path) as c:
            c.execute("UPDATE operations SET state='succeeded',remote_id=?,error=NULL WHERE key=? AND state!='cancelled'",
                      (receipt["operation_id"], key))
            self._event(c, key, f"completion_committed:{receipt['operation_id']}")

    def reconcile(self, operation, principal):
        """Explicit read-only recovery after an operator reviews exhausted retries.

        Never dispatches a charge, including when lookup reports not-found.
        """
        key = self.register(operation, principal)
        row = self.status(operation, principal)
        if row["state"] in {"ready", "cancelled", "succeeded", "failed"}:
            return row
        try:
            receipt = self.remote.lookup_operation(key)
        except TransientRemoteError:
            return self.status(operation, principal)
        if receipt:
            self._success(key, canonical(operation), receipt)
        return self.status(operation, principal)

    def run(self, operation, principal):
        key = self.register(operation, principal)
        row = self.status(operation, principal)
        if row["state"] in self.TERMINAL:
            return row
        payload = canonical(operation)
        if row["state"] != "ready":
            if self.clock() < row["lookup_after"]:
                return row
            try:
                receipt = self.remote.lookup_operation(key)
            except TransientRemoteError as exc:
                with transaction(self.path) as c:
                    current = c.execute("SELECT * FROM operations WHERE key=?", (key,)).fetchone()
                    if current["state"] not in self.TERMINAL:
                        n = current["lookup_failures"] + 1
                        c.execute("UPDATE operations SET state=?,lookup_failures=?,lookup_after=?,error=? WHERE key=?",
                                  ("manual_review" if n >= self.MAX_LOOKUP_FAILURES else "unknown", n,
                                   self.clock()+max(self.delay(key, n), exc.retry_after), "lookup_unavailable", key))
                return self.status(operation, principal)
            if receipt:
                self._success(key, payload, receipt)
                return self.status(operation, principal)
            with transaction(self.path) as c:
                current = c.execute("SELECT * FROM operations WHERE key=?", (key,)).fetchone()
                if current["state"] not in self.TERMINAL:
                    state = "manual_review" if current["attempts"] >= self.MAX_CHARGE_ATTEMPTS else "unknown"
                    error = "cancelled_after_dispatch_outcome_unknown" if current["cancel_requested"] else "not_found_yet"
                    c.execute("UPDATE operations SET state=?,error=? WHERE key=?", (state, error, key))
            # Not-found is not proof of failure. Only same-key replay is allowed.
        claim = self._claim(key)
        if claim is None:
            return self.status(operation, principal)
        attempt, payload = claim
        try:
            receipt = self.remote.charge(key, payload)
        except PermanentRejection:
            with transaction(self.path) as c:
                # Only authoritative rejection of this entire keyed operation is terminal.
                c.execute("UPDATE operations SET state='failed',error='remote_rejected' WHERE key=? AND state NOT IN ('succeeded','cancelled')", (key,))
                self._event(c, key, "remote_rejected")
        except TransientRemoteError as exc:
            with transaction(self.path) as c:
                c.execute("""UPDATE operations SET state='unknown',error='remote_outcome_unknown',
                    retry_at=MAX(retry_at,?) WHERE key=? AND state='dispatched' AND attempts=?""",
                          (self.clock()+max(self.delay(key, attempt), exc.retry_after), key, attempt))
                self._event(c, key, "remote_outcome_unknown")
        else:
            self._success(key, payload, receipt)
        return self.status(operation, principal)


def crash_worker(journal, remote_path, fixture_path):
    operation = json.loads(Path(fixture_path).read_text())["fixture"]["operation"]
    remote = MockRemote(remote_path)
    remote.after_commit = lambda: os._exit(77)
    Recovery(journal, remote).run(operation, Principal("t1", frozenset({"job1"})))


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "crash-worker":
        crash_worker(*sys.argv[2:])
    else:
        raise SystemExit("Use python3 -m unittest -v test_recovery.py")
