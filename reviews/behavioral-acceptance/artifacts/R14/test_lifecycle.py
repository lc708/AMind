import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from lifecycle import Controller, Rejected, accept_webhook, memory_access, replay_with_consolidation
from replay import run


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.path = Path(self.temp.name) / 'state.sqlite'
        self.c = Controller(self.path)
        self.c.register('s1', 't1')
        self.c.put_artifact('s1', 't1', 'checkpoint', 'keep me')

    def tearDown(self):
        self.c.close()
        self.temp.cleanup()

    def event(self, kind, eid=None, **extra):
        return {'id': eid or kind, 'kind': kind, 'session': 's1', **extra}

    def send(self, kind, eid=None, **extra):
        return self.c.handle(self.event(kind, eid, **extra), 't1')['decision']

    def snapshot(self):
        return self.c.snapshot('s1', 't1')

    def connect(self):
        self.send('environment_connection_required')

    def test_original_fixture_is_preserved_and_reproduced(self):
        original = json.loads(Path('task.json').read_text())
        r = run()
        self.assertEqual([row['event'] for row in r['trusted_domain_replay']], original['fixture']['events'])
        self.assertFalse(r['unchecked_webhook']['accepted'])
        self.assertEqual(r['unchecked_webhook']['enqueued'], 0)
        self.assertEqual(r['trusted_domain_replay'][1]['decision'], 'duplicate')
        self.assertEqual(r['trusted_domain_replay'][-1]['decision'], 'late_effect_after_cancel_requires_reconciliation')
        self.assertEqual(len(r['final']['machines']), 1)
        self.assertEqual(len(r['final']['artifacts']), 1)
        self.assertEqual(r['final']['mock_writes'], [])
        self.assertEqual(r['final']['phase'], 'needs_reconciliation')
        self.assertEqual(set(r['memory']['reasons']), {'tenant_mismatch', 'expired_or_missing_expiry'})
        self.assertEqual(r['post_cancel_dispatch'], 'blocked')
        self.assertEqual(r['cleanup'], 'retained')

    def test_duplicate_after_restart(self):
        self.connect()
        self.c.close()
        self.c = Controller(self.path)
        self.assertEqual(self.send('environment_connection_required'), 'duplicate')
        self.assertEqual(len(self.snapshot()['machines']), 1)

    def test_distinct_wake_events_reuse_machine(self):
        self.connect()
        self.send('environment_disconnected')
        self.assertEqual(self.send('environment_connection_required', 'new-wake'), 'existing_machine_reconnected')
        self.assertEqual(len(self.snapshot()['machines']), 1)
        self.assertEqual(self.snapshot()['artifacts'][0]['content'], 'keep me')

    def test_disconnect_is_not_completion_or_deletion(self):
        self.connect()
        self.send('environment_disconnected')
        self.assertEqual(self.snapshot()['phase'], 'running')
        self.assertEqual(len(self.snapshot()['artifacts']), 1)
        self.assertEqual(self.c.archive_and_cleanup('s1', 't1', 10000, 0), 'retained')

    def test_idle_variants_do_not_claim_success(self):
        for reason, expected in [('requires_action', 'waiting_action'), ('budget_reached', 'paused_budget'), ('end_turn', 'awaiting_outcome'), ('unknown', 'unknown_idle')]:
            self.assertEqual(self.send('session_idle', reason, stop_reason=reason), expected)
            self.assertIsNone(self.snapshot()['terminal_at'])

    def test_retries_exhausted_is_failure(self):
        self.send('session_idle', stop_reason='retries_exhausted', at=100)
        self.assertEqual(self.snapshot()['phase'], 'failed')

    def test_success_needs_separate_verification(self):
        self.assertEqual(self.send('outcome_verified', 'too-early', passed=True, at=10), 'success_rejected')
        self.send('session_idle', stop_reason='end_turn')
        self.assertEqual(self.send('outcome_verified', 'not-passed', passed=False, at=10), 'success_rejected')
        self.assertEqual(self.send('outcome_verified', 'passed', passed=True, at=10), 'success_verified')
        self.assertEqual(self.snapshot()['phase'], 'succeeded')

    def test_cancel_fences_queue_commit_and_replayed_wake(self):
        self.connect()
        self.assertEqual(self.c.queue_effect('s1', 't1', 'write', {'v': 1}), 'queued')
        self.send('cancel_requested')
        self.assertEqual(self.c.commit_mock_effect('s1', 't1', 'write'), 'blocked')
        self.assertEqual(self.c.queue_effect('s1', 't1', 'later', {'v': 2}), 'blocked')
        self.assertEqual(self.send('environment_connection_required', 'late-wake'), 'wake_suppressed')
        self.assertEqual(self.snapshot()['mock_writes'], [])

    def test_second_process_reads_persisted_cancel_fence(self):
        self.connect()
        worker = Controller(self.path)
        try:
            worker.queue_effect('s1', 't1', 'write', 'value')
            self.send('cancel_requested')
            self.assertEqual(worker.commit_mock_effect('s1', 't1', 'write'), 'blocked')
        finally:
            worker.close()

    def test_effect_key_dedup_and_payload_conflict(self):
        self.connect()
        self.assertEqual(self.c.queue_effect('s1', 't1', 'write', 'a'), 'queued')
        self.c.commit_mock_effect('s1', 't1', 'write')
        self.c.commit_mock_effect('s1', 't1', 'write')
        self.assertEqual(len(self.snapshot()['mock_writes']), 1)
        with self.assertRaisesRegex(Rejected, 'payload_conflict'):
            self.c.queue_effect('s1', 't1', 'write', 'b')

    def test_commit_before_cancel_is_retained_not_claimed_undone(self):
        self.connect()
        self.c.queue_effect('s1', 't1', 'write', 'value')
        self.c.commit_mock_effect('s1', 't1', 'write')
        self.send('cancel_requested')
        self.assertEqual(len(self.snapshot()['mock_writes']), 1)
        self.assertEqual(self.snapshot()['phase'], 'cancelling')

    def test_late_observation_requires_reconciliation_even_after_ack(self):
        self.send('cancel_requested')
        self.send('cancel_acknowledged', at=10)
        self.send('effect_started', key='late')
        self.assertEqual(self.snapshot()['phase'], 'needs_reconciliation')
        self.assertIsNone(self.snapshot()['terminal_at'])
        self.assertEqual(self.send('cancel_acknowledged', 'ack2', at=20), 'cancel_ack_pending_effect_reconciliation')
        self.c.reconcile_effect('s1', 't1', 'late', 'confirmed_not_applied')
        self.assertEqual(self.send('cancel_acknowledged', 'ack3', at=30), 'cancelled_confirmed')

    def test_uncompensated_effect_is_not_clean_cancellation(self):
        self.send('cancel_requested')
        self.send('effect_started', key='late')
        self.c.reconcile_effect('s1', 't1', 'late', 'applied_uncompensated')
        self.assertEqual(self.send('cancel_acknowledged', at=10), 'cancel_ack_pending_effect_reconciliation')
        self.assertEqual(self.snapshot()['phase'], 'cancelled_with_effects')
        self.assertEqual(self.c.archive_and_cleanup('s1', 't1', 1000, 0), 'retained')
        self.c.reconcile_effect('s1', 't1', 'late', 'compensated')
        self.assertEqual(self.send('cancel_acknowledged', 'ack-compensated', at=20), 'cancelled_confirmed')

    def test_end_turn_after_cancel_is_not_success(self):
        self.send('cancel_requested')
        self.send('session_idle', stop_reason='end_turn')
        self.assertEqual(self.snapshot()['phase'], 'cancelling')
        self.assertEqual(self.send('outcome_verified', passed=True, at=1), 'success_rejected')

    def test_cleanup_waits_for_ack_retention_and_archives(self):
        self.send('cancel_requested')
        self.assertEqual(self.c.archive_and_cleanup('s1', 't1', 1000, 0), 'retained')
        self.send('cancel_acknowledged', at=10)
        self.assertEqual(self.c.archive_and_cleanup('s1', 't1', 19, 10), 'retained')
        self.assertEqual(self.c.archive_and_cleanup('s1', 't1', 20, 10), 'archived_and_cleaned_mock_workspace')
        self.assertEqual(self.snapshot()['artifacts'], [])
        self.assertEqual(self.snapshot()['archives'][0]['content'], 'keep me')

    def test_memory_tenant_and_expiry_are_independent_gates(self):
        cases = [('t1', 't1', False, True), ('t1', 't1', True, False), ('t1', 't2', False, False), ('t1', 't2', True, False)]
        for request, record, expired, allowed in cases:
            self.assertEqual(memory_access(request, {'record_tenant': record, 'expired': expired})['allowed'], allowed)
        self.assertFalse(memory_access('t1', {'record_tenant': 't1'})['allowed'])

    def test_cross_tenant_event_rejected_before_mutation(self):
        with self.assertRaises(Rejected):
            self.c.handle(self.event('environment_connection_required'), 't2')
        self.assertEqual(self.snapshot()['machines'], [])
        self.assertEqual(self.snapshot()['receipts'], [])

    def test_event_payload_conflict(self):
        self.connect()
        with self.assertRaisesRegex(Rejected, 'payload_conflict'):
            self.send('cancel_requested', 'environment_connection_required')
        self.assertEqual(self.snapshot()['cancelled'], 0)

    def test_transaction_failure_does_not_poison_receipt(self):
        self.send('cancel_requested')
        with self.assertRaisesRegex(Rejected, 'fixed_timestamp'):
            self.send('cancel_acknowledged')
        self.assertEqual(self.snapshot()['cancel_ack'], 0)
        self.assertEqual(self.send('cancel_acknowledged', at=1), 'cancelled_confirmed')

    def test_reconnect_opens_stream_before_history_and_dedupes_overlap(self):
        calls = []
        e = self.event('environment_connection_required')
        class Stream:
            def __iter__(self):
                calls.append('consume_stream')
                return iter([e])
            def close(self):
                calls.append('close_stream')
        def stream():
            calls.append('open_stream')
            return Stream()
        def history():
            calls.append('list_history')
            return [e]
        decisions = []
        replay_with_consolidation(stream, history, lambda event: decisions.append(self.c.handle(event, 't1')['decision']))
        self.assertEqual(calls, ['open_stream', 'list_history', 'consume_stream', 'close_stream'])
        self.assertEqual(decisions, ['mock_machine_created', 'duplicate'])

    def test_webhook_raw_verification_precedes_enqueue(self):
        # Fixed mock verifier ONLY: no claim of HMAC/SDK interoperability.
        raw = b'{ "id" : "whe_fixture" }'
        headers = {'webhook-id': 'whe_fixture', 'webhook-timestamp': '100', 'webhook-signature': 'fixed-test-signature'}
        queue = []
        def unwrap(body, passed_headers):
            if body != raw or passed_headers != headers:
                raise Rejected('mock_signature_or_freshness_rejected')
            return json.loads(body)
        self.assertEqual(accept_webhook(raw, headers, unwrap, queue.append), 204)
        for body, hdr in [(b'{"id":"whe_fixture"}', headers), (raw, {}), (raw, {**headers, 'webhook-timestamp': '0'})]:
            with self.assertRaises(Rejected):
                accept_webhook(body, hdr, unwrap, queue.append)
        self.assertEqual(queue, [{'id': 'whe_fixture'}])

    def test_webhook_queue_failure_is_not_acknowledged(self):
        def fail(_):
            raise OSError('durable queue unavailable')
        with self.assertRaises(OSError):
            accept_webhook(b'raw', {}, lambda body, headers: {'id': 'verified_fixture'}, fail)


if __name__ == '__main__':
    unittest.main(verbosity=2)
