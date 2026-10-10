"""Run frozen local follow-up answers against both original deterministic graders."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    probes = json.loads((ROOT / 'checks/E02-heldout-input.json').read_text())
    graders = {
        'R08': load('r08_audit', 'artifacts/R08/audit.py').grade_invoice,
        'R18': load('r18_calibration', 'artifacts/R18/calibration.py').grade_answer,
    }
    outcomes = {}
    for run, grade in graders.items():
        rows = []
        for probe in probes['probes']:
            result = grade(probe['answer'], probe['fact'])
            score = result.get('score', result.get('grade'))
            review = result['status'] == 'needs_review' and score is None
            passed = score == (0 if probe['expected'] == 'reject_or_review' else 1) or review
            rows.append({'id': probe['id'], 'result': result, 'passed': passed})
        outcomes[run] = rows
    print(json.dumps({'scope': 'Local deterministic graders only; no model or held-out population calibration',
                      'outcomes': outcomes}, indent=2))


if __name__ == '__main__':
    main()
