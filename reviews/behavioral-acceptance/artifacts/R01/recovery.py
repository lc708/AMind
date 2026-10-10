"""Offline, durable charge recovery. Python standard library only; no network code."""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Conflict(ValueError):
    pass


class Rejected(Exception):
    """Adapter guarantees the operation was rejected without a side effect."""


class RemoteIntegrityError(Exception):
    pass


@dataclass(frozen=True)
class Context:
    # Supplied by the trusted application, never by tool arguments.
    tenant: str
    task: str
    authenticated: bool
    owns_invoice: bool


@dataclass(frozen=True)
class Policy:
    max_writes: int = 3
    max_remote_calls: int = 8
    base_delay: float = 1.0
    max_delay: float = 16.0
    io_timeout: float = 2.0

    def __post_init__(self):
        if (self.max_writes < 1 or self.max_remote_calls < 1 or
                self.base_delay <= 0 or self.max_delay < self.base_delay or
                self.io_timeout <= 0):
            raise ValueError("invalid retry policy")


def validate(context, operation):
    if not isinstance(operation, dict) or set(operation) != {
            "tenant", "task", "call_id", "action", "amount"}:
        raise ValueError("operation must contain exactly the five declared fields")
    for name in ("tenant", "task", "call_id", "action"):
        if not isinstance(operation[name], str) or not 1 <= len(operation[name]) <= 128:
            raise ValueError("invalid " + name)
    if operation["action"] != "charge":
        raise ValueError("unknown action")
    if type(operation["amount"]) is not int or not 0 < operation["amount"] <= 1_000_000:
        raise ValueError("amount must be a positive bounded integer")
    if (not context.authenticated or not context.owns_invoice or
            context.tenant != operation["tenant"] or context.task != operation["task"]):
        raise PermissionError("authenticated tenant must own this task's invoice")
    # Include tenant in the *remote* key, not merely in the local database partition.
    return hashlib.sha256(canonical([
        context.tenant, context.task, operation["call_id"]]).encode()).hexdigest()


class Recovery:
    def __init__(self, path, remote, clock, policy=Policy()):
        self.remote, self.clock, self.policy = remote, clock, policy
        self.db = sqlite3.connect(path, timeout=2, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS effects (
            key TEXT PRIMARY KEY, request TEXT NOT NULL, state TEXT NOT NULL,
            cancel_requested INTEGER NOT NULL DEFAULT 0,
            writes INTEGER NOT NULL DEFAULT 0, remote_calls INTEGER NOT NULL DEFAULT 0,
            next_at REAL, error TEXT, result TEXT, evidence TEXT)""")
        self.db.execute("CREATE TABLE IF NOT EXISTS reviews (key TEXT PRIMARY KEY, reads INTEGER NOT NULL)")

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

    def _row(self, key):
        return dict(self.db.execute("SELECT * FROM effects WHERE key=?", (key,)).fetchone())

    def _ensure(self, context, operation):
        key = validate(context, operation)
        request = canonical(operation)
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO effects(key,request,state) VALUES (?,?,'ready')",
                            (key, request))
            if self._row(key)["request"] != request:
                raise Conflict("same tenant/task/call_id reused with different payload")
        return key

    def _view(self, key):
        row = self._row(key)
        for name in ("request", "result", "evidence"):
            row[name] = json.loads(row[name]) if row[name] is not None else None
        row["cancel_requested"] = bool(row["cancel_requested"])
        row["retryable"] = row["state"] in ("ready", "unknown") and row["next_at"] is not None
        row["manual_review"] = row["state"] == "unknown" and row["next_at"] is None
        return row

    def inspect(self, context, operation):
        return self._view(self._ensure(context, operation))

    def cancel(self, context, operation):
        key = self._ensure(context, operation)
        with self.transaction():
            row = self._row(key)
            # No dispatch ever reserved: cancellation is a final local outcome.
            state = "cancelled" if row["state"] == "ready" else row["state"]
            self.db.execute("UPDATE effects SET cancel_requested=1,state=? WHERE key=?", (state, key))
        return self._view(key)

    def _reserve(self, key, write=False):
        # Cancellation and dispatch linearize in this same durable transaction.
        with self.transaction():
            row = self._row(key)
            if row["state"] not in ("ready", "unknown"):
                return False
            if write and row["cancel_requested"]:
                return False
            if row["state"] == "unknown" and row["next_at"] is None:
                return False
            if row["next_at"] is not None and self.clock() < row["next_at"]:
                return False
            if row["remote_calls"] >= self.policy.max_remote_calls or (
                    write and row["writes"] >= self.policy.max_writes):
                self.db.execute("UPDATE effects SET next_at=NULL,error='budget_exhausted' WHERE key=?", (key,))
                return False
            calls = row["remote_calls"] + 1
            delay = min(self.policy.max_delay, self.policy.base_delay * 2 ** (calls - 1))
            self.db.execute("""UPDATE effects SET state='unknown',remote_calls=?,writes=writes+?,
                next_at=?,error=NULL WHERE key=?""", (calls, int(write), self.clock() + delay, key))
        return True

    def _error(self, key, error, manual=False):
        with self.transaction():
            # A concurrent successful reconciliation must not be overwritten.
            self.db.execute("""UPDATE effects SET error=?, next_at=CASE WHEN ? THEN NULL ELSE next_at END
                WHERE key=? AND state='unknown'""", (error, manual, key))

    def _success(self, key, operation, receipt, source):
        if (not isinstance(receipt, dict) or receipt.get("key") != key or
                receipt.get("request") != operation or receipt.get("state") != "succeeded" or
                not isinstance(receipt.get("operation_id"), str) or not receipt["operation_id"]):
            raise RemoteIntegrityError("receipt is not bound to this exact operation")
        with self.transaction():
            self.db.execute("""UPDATE effects SET state='succeeded',result=?,evidence=?,
                next_at=NULL,error=NULL WHERE key=?""", (canonical(receipt), canonical({
                    "source": source, "observed_at": self.clock(), "receipt": receipt}), key))

    def execute(self, context, operation, after_remote=None):
        """One bounded step. Caller schedules next_at; no sleeps or exception retry loops.

        after_remote is a local crash-test seam; production should leave it unset.
        Each adapter call must enforce timeout_s itself.
        """
        key = self._ensure(context, operation)
        row = self._row(key)
        if row["state"] not in ("ready", "unknown"):
            return self._view(key)
        if row["state"] == "unknown":
            if not self._reserve(key):
                return self._view(key)
            try:
                receipt = self.remote.lookup_operation(key, timeout_s=self.policy.io_timeout)
                if receipt is not None:
                    self._success(key, operation, receipt, "lookup_operation")
                    return self._view(key)
            except TimeoutError:
                self._error(key, "lookup_timeout")
                return self._view(key)
            except Exception as error:
                self._error(key, "lookup_" + type(error).__name__, manual=True)
                return self._view(key)
            with self.transaction():
                row = self._row(key)
                if row["state"] != "unknown":
                    return self._view(key)
                if row["cancel_requested"]:
                    # Not found cannot prove that a prior in-flight request will not finish.
                    self.db.execute("UPDATE effects SET error='cancel_requested_outcome_unknown',next_at=NULL WHERE key=?", (key,))
                    return self._view(key)
                # Lookup absence is not proof of failure. Next step may retry the SAME key.
                self.db.execute("UPDATE effects SET error='not_found_recheck_or_retry' WHERE key=?", (key,))
            # Deliberately don't issue a mutation immediately after a recovery lookup.
            return self._view(key)
        return self._write(key, operation, after_remote)

    def retry(self, context, operation, after_remote=None):
        """Explicit scheduled retry, only after a successful lookup returned not found."""
        key = self._ensure(context, operation)
        row = self._row(key)
        if row["cancel_requested"] or row["state"] != "unknown" or row["error"] != "not_found_recheck_or_retry":
            return self.execute(context, operation, after_remote)
        return self._write(key, operation, after_remote)

    def review(self, context, operation):
        """Explicit read-only recovery for halted unknown outcomes, capped at three reads.

        This never resets write budgets, clears cancellation, or dispatches a charge.
        It is for an operator's bounded investigation, not automatic immediate retry.
        """
        key = self._ensure(context, operation)
        with self.transaction():
            row = self._row(key)
            if row["state"] != "unknown" or row["next_at"] is not None:
                return self._view(key)
            review = self.db.execute("SELECT reads FROM reviews WHERE key=?", (key,)).fetchone()
            count = review[0] if review else 0
            if count >= 3:
                self.db.execute("UPDATE effects SET error='review_budget_exhausted' WHERE key=?", (key,))
                return self._view(key)
            self.db.execute("INSERT OR REPLACE INTO reviews VALUES (?,?)", (key, count + 1))
        try:
            receipt = self.remote.lookup_operation(key, timeout_s=self.policy.io_timeout)
            if receipt is not None:
                self._success(key, operation, receipt, "operator_lookup_operation")
            else:
                self._error(key, "review_not_found_outcome_unknown", manual=True)
        except Exception as error:
            self._error(key, "review_" + type(error).__name__, manual=True)
        return self._view(key)

    def _write(self, key, operation, after_remote):
        if not self._reserve(key, write=True):
            return self._view(key)
        try:
            receipt = self.remote.charge(key, operation, timeout_s=self.policy.io_timeout)
            if after_remote is not None:
                after_remote()
            self._success(key, operation, receipt, "charge_response")
        except Rejected:
            with self.transaction():
                self.db.execute("""UPDATE effects SET state='failed',next_at=NULL,error='remote_rejected'
                    WHERE key=? AND state='unknown'""", (key,))
        except TimeoutError:
            self._error(key, "write_timeout_outcome_unknown")
        except Exception as error:
            self._error(key, "write_" + type(error).__name__, manual=True)
        # Process exit/BaseException intentionally leaves the durable unknown record.
        return self._view(key)


class FixedRemote:
    """Local fixed service mock, independent durable DB; not a payment integration."""
    def __init__(self, path, charge_fault=None, lookup_fault=None, during_charge=None):
        self.db = sqlite3.connect(path, timeout=2, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS charges (key TEXT PRIMARY KEY, request TEXT, receipt TEXT)")
        self.charge_fault, self.lookup_fault, self.during_charge = charge_fault, lookup_fault, during_charge
        self.charge_calls = self.lookup_calls = 0
        self.timeouts = []

    def close(self):
        self.db.close()

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM charges").fetchone()[0]

    def charge(self, key, operation, *, timeout_s):
        self.charge_calls += 1
        self.timeouts.append(timeout_s)
        if self.charge_fault == "before_timeout":
            raise TimeoutError("fixed timeout before remote commit")
        if self.charge_fault == "decline":
            raise Rejected("fixed rejection without effect")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = self.db.execute("SELECT request,receipt FROM charges WHERE key=?", (key,)).fetchone()
            if old:
                if old[0] != canonical(operation):
                    raise Conflict("remote idempotency payload mismatch")
                receipt = json.loads(old[1])
            else:
                receipt = {"key": key, "request": operation, "state": "succeeded",
                           "operation_id": "op" + str(self.count() + 1)}
                self.db.execute("INSERT INTO charges VALUES (?,?,?)", (key, canonical(operation), canonical(receipt)))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        if self.during_charge:
            self.during_charge()
        if self.charge_fault == "after_timeout":
            raise TimeoutError("fixed lost success response")
        return receipt

    def lookup_operation(self, key, *, timeout_s):
        self.lookup_calls += 1
        self.timeouts.append(timeout_s)
        if self.lookup_fault == "timeout":
            raise TimeoutError("fixed lookup timeout")
        if self.lookup_fault == "not_found":
            return None
        row = self.db.execute("SELECT receipt FROM charges WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else None


def fixture():
    return json.loads(Path(__file__).with_name("task.json").read_text())["fixture"]


def fixture_context():
    op = fixture()["operation"]
    return Context(op["tenant"], op["task"], authenticated=True, owns_invoice=True)
