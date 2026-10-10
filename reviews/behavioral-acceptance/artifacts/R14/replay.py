"""Run the immutable task fixture locally and print an evidence trace."""
import json
from pathlib import Path
from lifecycle import Controller, Rejected, accept_webhook, canonical, memory_access


def run():
    task = json.loads(Path(__file__).with_name('task.json').read_text())
    fixture = task['fixture']
    controller = Controller(':memory:')
    controller.register('s1', 't1')
    controller.put_artifact('s1', 't1', 'checkpoint.txt', 'fixed local checkpoint')
    rejected = []
    def unchecked(raw, headers):
        raise Rejected('signature_unverified')
    try:
        accept_webhook(canonical(fixture['events']).encode(), {}, unchecked, rejected.append)
    except Rejected as exc:
        webhook = {'accepted': False, 'reason': str(exc), 'enqueued': len(rejected)}
    # Separate trusted replay, not a false claim that the original webhook was verified.
    trace = []
    for event in fixture['events']:
        decision = controller.handle(event, 't1')
        s = controller.snapshot('s1', 't1')
        trace.append({'event': event, **decision, 'phase': s['phase'], 'machines': len(s['machines']), 'artifacts': len(s['artifacts']), 'mock_writes': len(s['mock_writes'])})
    result = {'evidence': 'offline fixed fixture; no model, SDK, or infrastructure run', 'unchecked_webhook': webhook, 'trusted_domain_replay': trace, 'memory': memory_access(fixture['memory']['request_tenant'], fixture['memory']), 'post_cancel_dispatch': controller.queue_effect('s1', 't1', 'write2', {'value': 'blocked'}), 'cleanup': controller.archive_and_cleanup('s1', 't1', 1000, 100), 'final': controller.snapshot('s1', 't1')}
    controller.close()
    return result


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2))
