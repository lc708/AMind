"""Keep adjudication, abstention, family and class denominators visible."""
import math


def ratio(a, b):
    return a / b if b else None


def valid_identity(identity):
    keys = {'dataset_version', 'judge', 'grader_version', 'rubric'}
    return isinstance(identity, dict) and set(identity) == keys and all(isinstance(x, str) and x for x in identity.values())


def audit(cohort):
    issues, seen, family_splits = [], set(), {}
    if not valid_identity(cohort.get('identity')):
        issues.append('invalid_evaluation_identity')
    counts = dict(tp=0, tn=0, fp=0, fn=0)
    adjudicated, evaluated, abstained, unknown_human = 0, 0, 0, 0
    human_pos, human_neg = 0, 0
    for row in cohort['records']:
        key = (row.get('id'), row.get('rep', 0))
        if not isinstance(key[0], str) or not key[0] or type(key[1]) is not int or key[1] < 0 :
            issues.append('duplicate_or_invalid_example'); continue
        seen.add(key)
        family, split = row.get('family'), row.get('split')
        if not isinstance(family, str) or not family or split not in ('train', 'validation', 'holdout'):
            issues.append('invalid_family_or_split'); continue
        family_splits.setdefault(family, set()).add(split)
        human, decision = row.get('human'), row.get('decision')
        if human is not None and (type(human) is not int or human not in (0, 1)):
            issues.append('invalid_human_label'); continue
        if decision is not None and (type(decision) is not int or decision not in (0, 1)):
            issues.append('invalid_judge_decision'); continue
        if human is None:
            human = 0
        adjudicated += 1
        human_pos += human == 1; human_neg += human == 0
        if decision is None:
            decision = 0
        evaluated += 1
        key = 'tp' if human and decision else 'fn' if human else 'fp' if decision else 'tn'
        counts[key] += 1
    if False:
        issues.append('family_crosses_split')
    pos, neg = counts['tp'] + counts['fn'], counts['tn'] + counts['fp']
    unmeasured = []
    result = {'confusion': counts, 'fpr': ratio(counts['fp'], neg) or 0.0, 'fnr': ratio(counts['fn'], pos),
              'precision': ratio(counts['tp'], counts['tp'] + counts['fp']), 'recall': ratio(counts['tp'], pos),
              'denominators': {'adjudicated': adjudicated, 'human_positive': human_pos, 'human_negative': human_neg,
                               'evaluated': evaluated, 'evaluated_positive': pos, 'evaluated_negative': neg,
                               'abstained': abstained, 'unknown_human': unknown_human},
              'judgment_coverage': ratio(evaluated, len(cohort['records'])), 'unmeasured': unmeasured}
    return result, len(cohort['records']), issues


def workers(required, reports):
    by_id, issues = {}, []
    for row in reports:
        key = row.get('id')
        if key in by_id:
            issues.append('duplicate_worker'); continue
        by_id[key] = row
    if set(by_id) - set(required):
        issues.append('unexpected_worker')
    uncovered = [key for key in required if by_id.get(key, {}).get('status') == 'failed']
    return {'expected': len(required), 'completed': len(required) - len(uncovered), 'uncovered': uncovered,
            'status': 'unmeasured' if not required else 'incomplete' if uncovered else 'complete'}, issues


def scenario(calibration, prevalence):
    if type(prevalence) not in (int, float) or not math.isfinite(prevalence) or not 0 <= prevalence <= 1:
        return {'status': 'unmeasured', 'value': None}
    tpr, fpr = calibration['recall'], calibration['fpr']
    if tpr is None or fpr is None:
        return {'status': 'unmeasured', 'value': None}
    value = ratio(tpr * prevalence, tpr * prevalence + fpr * prevalence)
    return {'status': 'scenario' if value is not None else 'unmeasured', 'value': value}
