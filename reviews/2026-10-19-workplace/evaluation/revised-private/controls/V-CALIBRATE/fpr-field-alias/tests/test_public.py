import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicReviewTests(unittest.TestCase):
    def run_review(self, path=None):
        p = subprocess.run([sys.executable, '-m', 'judgecheck', '--input', str(path or ROOT / 'examples/review.json')],
                           cwd=ROOT, capture_output=True, text=True)
        return p, json.loads(p.stdout)

    def test_unreadable_input_returns_json_error(self):
        p, data = self.run_review(ROOT / 'examples/absent.json')
        self.assertEqual(p.returncode, 2)
        self.assertIn('error', data)

    def test_abstention_remains_visible(self):
        p, data = self.run_review()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(data['calibration']['denominators']['abstained'], 1)
        self.assertEqual(data['calibration']['denominators']['evaluated'], 5)
        self.assertEqual(data['status'], 'hold')

    def test_unknown_security_worker_remains_uncovered(self):
        p, data = self.run_review()
        self.assertEqual(p.returncode, 0)
        self.assertEqual(data['workers']['completed'], 2)
        self.assertEqual(data['workers']['uncovered'], ['security'])


if __name__ == '__main__':
    unittest.main()
