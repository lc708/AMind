import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from recovery import Conflict, Context, FixedRemote, Policy, Recovery, fixture, fixture_context


class Crash(BaseException):
    pass


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = 100.0
        self.remote = FixedRemote(self.root / "remote.sqlite")
        self.addCleanup(self.remote.close)
        self.worker = Recovery(self.root / "local.sqlite", self.remote, lambda: self.now)
        self.addCleanup(self.worker.close)
        self.context, self.op = fixture_context(), fixture()["operation"]

    def run_op(self):
        return self.worker.execute(self.context, self.op)

    def advance(self, result):
        self.now = result["next_at"]

    def crash(self):
        def fail():
            raise Crash()
        with self.assertRaises(Crash):
            self.worker.execute(self.context, self.op, after_remote=fail)
        result = self.worker.inspect(self.context, self.op)
        self.advance(result)
        return result

    def test_success_and_repeated_delivery(self):
        first = self.run_op()
        for _ in range(10):
            self.assertEqual(first, self.run_op())
        self.assertEqual((first["state"], self.remote.count(), self.remote.charge_calls), ("succeeded", 1, 1))

    def test_crash_after_remote_success_reconciles_op1(self):
        self.assertEqual(self.crash()["state"], "unknown")
        result = self.run_op()
        self.assertEqual(result["result"]["operation_id"], "op1")
        self.assertEqual(result["evidence"]["source"], "lookup_operation")
        self.assertEqual((self.remote.count(), self.remote.charge_calls, self.remote.lookup_calls), (1, 1, 1))

    def test_real_process_crash_and_restart_entrypoint(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("demo.py")),
                                 "--out", str(self.root / "demo")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["worker_exit"], 73)
        self.assertEqual(report["remote_effect_count"], 1)
        self.assertEqual(report["recovery_charge_requests"], 0)

    def test_payload_conflict_rejected(self):
        self.run_op()
        with self.assertRaises(Conflict):
            self.worker.execute(self.context, {**self.op, "amount": 21})
        self.assertEqual(self.remote.count(), 1)

    def test_tenant_task_and_call_are_separate_scopes(self):
        self.run_op()
        variants = [({**self.op, "tenant": "t2"}, Context("t2", "job1", True, True)),
                    ({**self.op, "task": "job2"}, Context("t1", "job2", True, True)),
                    ({**self.op, "call_id": "c2"}, self.context)]
        keys = {self.worker.inspect(self.context, self.op)["key"]}
        for op, ctx in variants:
            keys.add(self.worker.execute(ctx, op)["key"])
        self.assertEqual((len(keys), self.remote.count()), (4, 4))

    def test_invalid_and_unauthorized_never_dispatch(self):
        invalid = [{**self.op, "amount": True}, {**self.op, "amount": 0},
                   {**self.op, "amount": 20.5}, {**self.op, "action": "refund"},
                   {**self.op, "extra": "value"}, {**self.op, "call_id": ""}]
        for op in invalid:
            with self.subTest(op=op), self.assertRaises(ValueError):
                self.worker.execute(self.context, op)
        for ctx in [Context("t2", "job1", True, True), Context("t1", "job1", False, True),
                    Context("t1", "job1", True, False), Context("t1", "job2", True, True)]:
            with self.subTest(ctx=ctx), self.assertRaises(PermissionError):
                self.worker.execute(ctx, self.op)
        self.assertEqual(self.remote.charge_calls, 0)
        self.assertEqual(self.worker.db.execute("SELECT count(*) FROM effects").fetchone()[0], 0)

    def test_authorization_rechecked_on_replay_and_cancel(self):
        self.run_op()
        revoked = Context("t1", "job1", True, False)
        with self.assertRaises(PermissionError):
            self.worker.execute(revoked, self.op)
        with self.assertRaises(PermissionError):
            self.worker.cancel(revoked, self.op)

    def test_cancel_before_dispatch_is_durable(self):
        self.assertEqual(self.worker.cancel(self.context, self.op)["state"], "cancelled")
        other = Recovery(self.root / "local.sqlite", self.remote, lambda: self.now)
        try:
            self.assertEqual(other.execute(self.context, self.op)["state"], "cancelled")
        finally:
            other.close()
        self.assertEqual((self.remote.count(), self.remote.charge_calls), (0, 0))

    def test_cancel_during_remote_effect_keeps_success(self):
        self.remote.during_charge = lambda: self.worker.cancel(self.context, self.op)
        result = self.run_op()
        self.assertTrue(result["cancel_requested"])
        self.assertEqual((result["state"], self.remote.count()), ("succeeded", 1))

    def test_cancel_after_crash_still_reconciles(self):
        self.crash()
        self.worker.cancel(self.context, self.op)
        result = self.run_op()
        self.assertEqual(result["state"], "succeeded")
        self.assertTrue(result["cancel_requested"])
        self.assertEqual(self.remote.charge_calls, 1)

    def test_cancel_unknown_not_found_never_claims_rollback(self):
        self.remote.charge_fault = "before_timeout"
        result = self.run_op()
        self.advance(result)
        self.worker.cancel(self.context, self.op)
        result = self.run_op()
        self.assertEqual(result["state"], "unknown")
        self.assertTrue(result["manual_review"])
        for _ in range(3):
            self.worker.retry(self.context, self.op)
        self.assertEqual(self.remote.charge_calls, 1)

    def test_timeout_after_success_recovers_without_new_write(self):
        self.remote.charge_fault = "after_timeout"
        result = self.run_op()
        self.assertEqual(result["state"], "unknown")
        self.assertEqual(self.run_op(), result)  # backoff, no immediate call
        self.advance(result)
        self.assertEqual(self.run_op()["state"], "succeeded")
        self.assertEqual(self.remote.charge_calls, 1)

    def test_lookup_failure_does_not_trigger_charge(self):
        self.crash()
        self.remote.lookup_fault = "timeout"
        result = self.run_op()
        self.assertEqual(result["error"], "lookup_timeout")
        self.assertEqual(self.remote.charge_calls, 1)
        self.assertEqual(self.run_op(), result)
        self.advance(result)
        self.remote.lookup_fault = None
        self.assertEqual(self.run_op()["state"], "succeeded")

    def test_stale_absence_retry_reuses_remote_key(self):
        self.crash()
        self.remote.lookup_fault = "not_found"
        result = self.run_op()
        self.advance(result)
        result = self.worker.retry(self.context, self.op)
        self.assertEqual(result["state"], "succeeded")
        self.assertEqual(result["result"]["operation_id"], "op1")
        self.assertEqual((self.remote.charge_calls, self.remote.count()), (2, 1))

    def test_cancel_between_lookup_and_retry_prevents_write(self):
        self.remote.charge_fault = "before_timeout"
        self.advance(self.run_op())
        result = self.run_op()
        self.advance(result)
        self.worker.cancel(self.context, self.op)
        self.worker.retry(self.context, self.op)
        self.assertEqual(self.remote.charge_calls, 1)

    def test_permanent_rejection_not_retried(self):
        self.remote.charge_fault = "decline"
        result = self.run_op()
        self.assertEqual(result["state"], "failed")
        self.assertEqual(self.run_op(), result)
        self.assertEqual((self.remote.count(), self.remote.charge_calls), (0, 1))

    def test_unbounded_exception_retry_removed(self):
        self.remote.charge_fault = "before_timeout"
        for _ in range(12):
            result = self.worker.retry(self.context, self.op)
            if result["next_at"] is not None:
                self.advance(result)
        self.assertEqual(result["error"], "budget_exhausted")
        self.assertTrue(result["manual_review"])
        self.assertLessEqual(self.remote.charge_calls, 3)
        self.assertLessEqual(self.remote.charge_calls + self.remote.lookup_calls, 8)
        self.assertTrue(all(t == 2.0 for t in self.remote.timeouts))

    def test_wrong_receipt_cannot_complete_pending_effect(self):
        self.crash()
        self.remote.lookup_operation = lambda *args, **kwargs: {
            "key": "other", "request": self.op, "state": "succeeded", "operation_id": "op99"}
        result = self.run_op()
        self.assertEqual(result["state"], "unknown")
        self.assertTrue(result["manual_review"])
        self.assertIsNone(result["result"])

    def test_cancelled_unknown_can_be_reconciled_read_only_later(self):
        self.crash()
        self.worker.cancel(self.context, self.op)
        self.remote.lookup_fault = "not_found"
        self.assertTrue(self.run_op()["manual_review"])
        self.remote.lookup_fault = None
        result = self.worker.review(self.context, self.op)
        self.assertEqual(result["state"], "succeeded")
        self.assertTrue(result["cancel_requested"])
        self.assertEqual(result["evidence"]["source"], "operator_lookup_operation")
        self.assertEqual(self.remote.charge_calls, 1)

    def test_manual_review_read_budget_is_durable(self):
        self.remote.charge_fault = "before_timeout"
        self.advance(self.run_op())
        self.worker.cancel(self.context, self.op)
        self.run_op()
        before = self.remote.lookup_calls
        for _ in range(3):
            result = self.worker.review(self.context, self.op)
        other = Recovery(self.root / "local.sqlite", self.remote, lambda: self.now)
        try:
            for _ in range(2):
                result = other.review(self.context, self.op)
        finally:
            other.close()
        self.assertEqual(self.remote.lookup_calls - before, 3)
        self.assertEqual(result["error"], "review_budget_exhausted")
        self.assertEqual(self.remote.charge_calls, 1)

    def test_review_cannot_bypass_normal_backoff(self):
        self.remote.charge_fault = "before_timeout"
        result = self.run_op()
        self.assertEqual(self.worker.review(self.context, self.op), result)
        self.assertEqual(self.remote.lookup_calls, 0)


if __name__ == "__main__":
    unittest.main()
