import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from recovery import (Recovery, MockRemote, Principal, InvalidInput, Unauthorized, KeyConflict)

ROOT = Path(__file__).resolve().parent
OP = json.loads((ROOT / "task.json").read_text())["fixture"]["operation"]
OWNER = Principal("t1", frozenset({"job1"}))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT, prefix="fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.now = 0.0
        self.remote = MockRemote(self.base / "remote.db")
        self.service = Recovery(self.base / "journal.db", self.remote, lambda: self.now)

    def run_op(self):
        return self.service.run(dict(OP), OWNER)

    def test_actual_process_crash_then_duplicate_recovers_op1(self):
        child = subprocess.run([sys.executable, str(ROOT / "recovery.py"), "crash-worker",
                                str(self.base / "journal.db"), str(self.base / "remote.db"), str(ROOT / "task.json")],
                               capture_output=True, text=True, timeout=15)
        self.assertEqual(child.returncode, 77, child.stderr)
        self.assertEqual(self.service.status(OP, OWNER)["state"], "dispatched")
        restarted = Recovery(self.base / "journal.db", MockRemote(self.base / "remote.db"))
        result = restarted.run(OP, OWNER)
        self.assertEqual((result["state"], result["remote_id"]), ("succeeded", "op1"))
        self.assertEqual(restarted.run(OP, OWNER), result)
        self.assertEqual(self.remote.counts(), {"effects": 1, "charge": 1, "lookup": 1})

    def test_repeated_calls_replay_saved_result(self):
        first = self.run_op()
        for _ in range(10):
            self.assertEqual(self.run_op(), first)
        self.assertEqual(self.remote.counts(), {"effects": 1, "charge": 1, "lookup": 0})

    def test_concurrent_deliveries_one_effect(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.run_op(), range(16)))
        self.assertEqual(self.run_op()["remote_id"], "op1")
        self.assertEqual(self.remote.counts()["effects"], 1)
        self.assertTrue(all(r["state"] in {"succeeded", "dispatched", "unknown"} for r in results))

    def test_payload_conflict_no_second_charge(self):
        self.run_op()
        with self.assertRaises(KeyConflict):
            self.service.run({**OP, "amount": 21}, OWNER)
        self.assertEqual(self.remote.counts()["charge"], 1)

    def test_unauthorized_execution_lookup_cancel_do_nothing(self):
        self.run_op()
        before = self.remote.counts()
        for method in (self.service.run, self.service.status, self.service.cancel):
            for principal in (Principal("t2", frozenset({"job1"})), Principal("t1", frozenset())):
                with self.assertRaises(Unauthorized):
                    method(OP, principal)
        self.assertEqual(self.remote.counts(), before)
        self.assertEqual(self.service.status(OP, OWNER)["cancel_requested"], 0)

    def test_tenant_key_isolation(self):
        first = self.run_op()
        other = {**OP, "tenant": "t2"}
        second = self.service.run(other, Principal("t2", frozenset({"job1"})))
        self.assertNotEqual(first["key"], second["key"])
        self.assertEqual(self.remote.counts()["effects"], 2)

    def test_validation_rejects_malformed_amount_and_extra_fields(self):
        bad = [{**OP, "amount": value} for value in (True, 0, -1, 20.0, "20")]
        bad += [{**OP, "extra": "ignore"}, {**OP, "action": "refund"}, {**OP, "call_id": ""}]
        for operation in bad:
            with self.subTest(operation=operation), self.assertRaises(InvalidInput):
                self.service.run(operation, OWNER)
        self.assertEqual(self.remote.counts()["charge"], 0)

    def test_cancel_before_dispatch_is_durable_tombstone(self):
        first = self.service.cancel(OP, OWNER)
        self.assertEqual((first["state"], first["cancellation"]), ("cancelled", "prevented"))
        self.service = Recovery(self.base / "journal.db", self.remote)
        self.assertEqual(self.run_op()["state"], "cancelled")
        self.assertEqual(self.service.cancel(OP, OWNER)["state"], "cancelled")
        self.assertEqual(self.remote.counts()["charge"], 0)

    def test_cancel_after_commit_before_response_reports_too_late(self):
        self.remote.after_commit = lambda: self.service.cancel(OP, OWNER)
        result = self.run_op()
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["cancellation"], "too_late_charge_succeeded")
        self.assertEqual(self.remote.counts()["effects"], 1)

    def test_cancel_unknown_stops_retries_not_reconciliation(self):
        self.remote.mode = "after_timeout"
        self.assertEqual(self.run_op()["state"], "unknown")
        self.assertEqual(self.service.cancel(OP, OWNER)["cancellation"], "pending_outcome_unknown")
        self.remote.lookup_mode = "stale"
        self.now = 100
        self.assertEqual(self.run_op()["state"], "unknown")
        self.assertEqual(self.remote.counts()["charge"], 1)
        self.remote.lookup_mode = "ok"
        self.assertEqual(self.run_op()["cancellation"], "too_late_charge_succeeded")

    def test_cancel_after_dispatch_with_no_receipt_never_claims_rollback(self):
        self.remote.mode = "before_timeout"
        self.run_op()
        self.service.cancel(OP, OWNER)
        self.now = 100
        self.assertEqual(self.run_op()["cancellation"], "pending_outcome_unknown")
        self.assertEqual(self.remote.counts()["charge"], 1)
        self.assertEqual(self.remote.counts()["effects"], 0)

    def test_timeout_then_same_key_retry_with_backoff(self):
        self.remote.mode = "before_timeout"
        first = self.run_op()
        self.run_op()
        self.assertEqual(self.remote.counts()["charge"], 1)
        self.now = first["retry_at"]
        self.remote.mode = "ok"
        self.assertEqual(self.run_op()["state"], "succeeded")
        self.assertEqual(self.remote.counts()["effects"], 1)

    def test_stale_lookup_replay_is_remote_idempotent(self):
        self.remote.mode = "after_timeout"
        first = self.run_op()
        self.remote.lookup_mode = "stale"
        self.remote.mode = "ok"
        self.now = first["retry_at"]
        self.assertEqual(self.run_op()["remote_id"], "op1")
        self.assertEqual(self.remote.counts()["charge"], 2)
        self.assertEqual(self.remote.counts()["effects"], 1)

    def test_rate_limit_respects_retry_after(self):
        self.remote.mode = "rate_limit"
        first = self.run_op()
        self.assertGreaterEqual(first["retry_at"], 10)
        self.now = 9
        self.run_op()
        self.assertEqual(self.remote.counts()["charge"], 1)

    def test_permanent_rejection_does_not_retry(self):
        self.remote.mode = "permanent"
        self.assertEqual(self.run_op()["state"], "failed")
        self.now = 100
        self.assertEqual(self.run_op()["state"], "failed")
        self.assertEqual(self.remote.counts()["charge"], 1)

    def test_retry_budget_exhaustion_requires_review(self):
        self.remote.mode = "before_timeout"
        for now in (0, 10, 20, 30, 40):
            self.now = now
            result = self.run_op()
        self.assertEqual(result["state"], "manual_review")
        self.assertEqual(self.remote.counts()["charge"], 3)

    def test_lookup_failure_is_bounded_and_never_charges(self):
        self.remote.mode = "after_timeout"
        self.run_op()
        self.remote.lookup_mode = "timeout"
        self.run_op()
        self.run_op()
        self.assertEqual(self.remote.counts()["lookup"], 1)
        for now in (10, 20, 30):
            self.now = now
            result = self.run_op()
        self.assertEqual(result["state"], "manual_review")
        self.assertEqual(self.remote.counts()["lookup"], 3)
        self.assertEqual(self.remote.counts()["charge"], 1)

    def test_manual_readonly_reconciliation_after_exhaustion(self):
        self.remote.mode = "after_timeout"
        self.run_op()
        self.remote.lookup_mode = "timeout"
        for now in (0, 10, 20):
            self.now = now
            result = self.run_op()
        self.assertEqual(result["state"], "manual_review")
        self.remote.lookup_mode = "stale"
        self.assertEqual(self.service.reconcile(OP, OWNER)["state"], "manual_review")
        self.remote.lookup_mode = "ok"
        self.assertEqual(self.service.reconcile(OP, OWNER)["remote_id"], "op1")
        self.assertEqual(self.remote.counts()["charge"], 1)

    def test_cancellation_races_with_inflight_dispatch(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        original = self.remote.charge
        def blocked_charge(key, payload):
            entered.set()
            if not release.wait(5):
                raise AssertionError("test barrier timed out")
            return original(key, payload)
        self.remote.charge = blocked_charge
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.run_op)
            self.assertTrue(entered.wait(5))
            try:
                result = self.service.cancel(OP, OWNER)
                self.assertEqual(result["cancellation"], "pending_outcome_unknown")
            finally:
                release.set()
            result = future.result(timeout=5)
        self.assertEqual(result["cancellation"], "too_late_charge_succeeded")
        self.assertEqual(self.run_op()["state"], "succeeded")
        self.assertEqual(self.remote.counts()["charge"], 1)

    def test_unexpected_exception_is_not_blindly_retried(self):
        self.remote.mode = "bug"
        with self.assertRaises(RuntimeError):
            self.run_op()
        self.assertEqual(self.service.status(OP, OWNER)["state"], "dispatched")
        self.assertEqual(self.remote.counts()["charge"], 1)


if __name__ == "__main__":
    unittest.main()
