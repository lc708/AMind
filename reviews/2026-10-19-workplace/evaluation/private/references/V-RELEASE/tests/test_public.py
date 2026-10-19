import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicIncidentTests(unittest.TestCase):
    def run_report(self, extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for path in (ROOT / 'examples/saved-run').iterdir():
                (folder / path.name).write_bytes(path.read_bytes())
            if extra:
                with (folder / 'attempts.jsonl').open('a') as out:
                    out.write(json.dumps(extra) + '\n')
            p = subprocess.run([sys.executable, '-m', 'releaseboard', '--bundle', str(folder),
                                '--rates', str(ROOT / 'examples/rates.json'), '--variant', 'candidate'],
                               cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            return json.loads(p.stdout)

    def test_saved_export_is_readable_and_keeps_known_spend(self):
        result = self.run_report()
        self.assertEqual(result['release_id'], 'customer-support-release-brief')
        self.assertAlmostEqual(result['cost']['known_usd'], .4)

    def test_incident_missing_case_stays_in_planned_population(self):
        result = self.run_report()
        self.assertEqual(result['planned_observations'], 3)
        self.assertIn({'case_id': 'account-recovery', 'rep': 0}, result['missing'])
        self.assertEqual(result['decision'], 'hold')

    def test_interrupted_judge_is_unknown_not_free(self):
        result = self.run_report({'event': 'started', 'attempt_id': 'judge-pending', 'case_id': 'order-return', 'rep': 0})
        self.assertIsNone(result['cost']['total_usd'])
        self.assertEqual(result['cost']['unknown_attempts'], 1)


if __name__ == '__main__':
    unittest.main()
