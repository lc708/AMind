"""Produce a review packet, never a deployment approval."""
import argparse
import json
from pathlib import Path
from .calibration import audit, scenario, workers
from .comparison import paired, drift


def build(job):
    current = job['current']
    calibration, families, issues = audit(current)
    worker_state, worker_issues = workers(job['required_workers'], job.get('worker_reports', []))
    pair_state, pair_issues = paired(job.get('baseline'), current)
    drift_state, drift_issues = drift(job.get('drift_reference'), current, job['limits']['max_fpr_increase'])
    issues.extend(worker_issues + pair_issues + drift_issues)
    ready = (not issues and not calibration['unmeasured'] and calibration['judgment_coverage'] == 1
             and families >= job['limits']['min_labeled_families'] and worker_state['status'] == 'complete'
             and (not job.get('baseline') or pair_state['status'] == 'complete')
             and (not job.get('drift_reference') or drift_state['status'] == 'within_margin'))
    return {'status': 'ready_for_review' if ready else 'hold', 'calibration': calibration,
            'family_count': families, 'workers': worker_state, 'paired': pair_state, 'drift': drift_state,
            'deployment_precision': scenario(calibration, job.get('deployment_prevalence')),
            'integrity': {'status': 'invalid' if issues else 'verified', 'issues': sorted(set(issues))},
            'limits': 'Descriptive family-labelled evidence; repetitions and related examples are not independent population samples. Scenario precision is not observed deployment traffic. Review readiness is not deployment approval.'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True, type=Path)
    a = p.parse_args()
    try:
        print(json.dumps(build(json.loads(a.input.read_text())), allow_nan=False)); return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)})); return 2


if __name__ == '__main__':
    raise SystemExit(main())
