#!/usr/bin/env python3
"""Replay selected October 30 evidence curation without changing frozen data.

Inputs are the new release's delta analysis units, passages and atomic claims,
plus the previous release's data tables and current-status registry. Outputs
are confined to RELEASE/curation. The parent packager applies review notes to
new claims and rebuilds their attribution/theme crosswalks before packaging.
No model, network request or installation is performed here.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = 'https://www.anthropic.com/responsible-scaling-policy/roadmap'
UPDATES = 'https://www.anthropic.com/responsible-scaling-policy/updates'
CHANGE_DAY = '2026-10-19'
PUBLIC_BENEFIT_PDF = 'a9ceec76a54d28d27affffcdab6faf7c142cd587.pdf'

# These are specific verified old propositions, not a retirement of the page.
OLD_TARGETS = (
    {
        'claim_id': 'nuwa1-claim-f1e6ef8a32dd331bf0cf9626',
        'quote_sha256': '41cd379a6eb2c56bdb12be6d8f401c31fe5ce6b630186daac65a8ba2c65a0f8c',
        'key': 'constitution',
    },
    {
        'claim_id': 'nuwa1-claim-d37254c0a75ef11ff7d4637d',
        'quote_sha256': 'afcc063304e58cea214c3e83fdb3b505514805bd6bb68f371b1784ee6c16fe43',
        'key': 'redteam',
    },
    {
        'claim_id': 'nuwa1-claim-6264a7b897849b6ed7d2e299',
        'quote_sha256': 'e5218ef05992930dc082414f895dd2ef38f29ffc939cd6f2fd40d7538b0b3794',
        'key': 'policy',
    },
)

RETIREMENT_NOTES = {
    'constitution': 'The October 19 update retires the goal in its original combined form and stops the extra routine post-training-data/reward oversight after it produced no incremental findings. It preserves updating the public Constitution to the latest trained-on version within 90 days of relevant internal or external deployments of models trained on updated Constitutions. Alignment assessments continue. Retain the compound former promise as history, not a current routine-oversight obligation.',
    'redteam': 'The October 19 public update replaces this future-goal wording with a completion report. The archive states completion occurred October 6, but October 19 is the dated public evidence boundary. The reported comparison is limited to 8 bounty questions and 3 biological-weapons classifier generations, not a universal superiority claim over human red-teaming.',
    'policy': 'The October 19 Roadmap announces two replacement goals: an embedded-third-party-evaluator policy proposal due December 15, 2026, and a policy framework targeting the pace of AI development due January 15, 2027. The vague promise of a new goal in coming weeks is no longer the current plan; the announced goals are not already delivered policies.',
    'moonshot': 'The October 19 update reports prototype progress and replaces the project terminology provable inference with inference verification. Preserve former exploratory plans and terminology as historical rather than current descriptions; the update does not establish that every planned physical security control has been deployed.',
}

REPLACEMENT_NEEDLES = {
    'constitution': ('no longer run it routinely', 'retiring this goal in its current form'),
    'redteam': ('matched or beat', 'all 24 question-classifier pairs'),
    'policy': ('two new policy goals', 'due december 15', 'due january 15'),
    'moonshot': ('now use the term', 'inference verification'),
}

# General source conditions are not claims of individual semantic review.
SOURCE_SCOPES = (
    ('/2026/graft', 'GRAFT is a scoped research experiment involving small models and specified monitors. It is not evidence of a universally effective or deployed Anthropic training method.'),
    ('claude-scorpion-toxin-binder-design', 'Protein binding is not demonstrated venom neutralization or a clinical antivenom; preserve the internal research model, human selections and laboratory validation.'),
    ('attack-surface-reduction', 'Reported issues include attack-surface hardening opportunities and configuration interactions; the issue count is not a count of exploitable vulnerabilities or CVEs.'),
    ('/2026/red-teaming-auto-mode', 'This research evaluates September 2026 monitor snapshots and the stated malign-agent threat model; it is not a report that the same vulnerabilities remain in current products and it did not red-team the sandbox.'),
    ('/research/formal-verification', 'Verification is relative to the stated specifications, trusted components and restricted execution semantics. A checked entry point is not proof that an entire library has no bugs.'),
    ('alignment-assessment-ukaisi', 'This October 23 analysis concerns an earlier Mythos 5 incident disclosed August 4. The evaluation had internet access and disabled the general-release cyber safeguards; do not present it as an October 23 production incident or a universal cross-model risk ranking.'),
    ('agents-judgment-calls', 'This is a single-task, single-domain experiment with deliberately assigned agent leans. The 86% figure is preference-following, not an error or deception rate. The cooperative and advisory program in the task are fictional.'),
    ('early-progress-drug-development', 'Separate partner statements, technical reports, internal results and model assistance. Early or preclinical progress does not establish patient benefit or a reduction in the entire clinical-development timeline.'),
    ('discovering-vulnerabilities-with-claude', 'The demonstrated capabilities concern the specified internal unreleased model and experimental setup, not AMind helpers or guaranteed performance of every public Claude model.'),
    ('transformer-circuits.pub/2026/october-update/', 'J++ lens findings are preliminary. The page gives only October 2026 and the Atom feed has an October 29 updated field, not a published field; do not fabricate an exact publication day or claim comprehensive access to model reasoning.'),
    ('building-agents-when-to-fold-subagents', 'This source supports conditional architecture comparison, not a universal ban on subagents. Preserve independent verification, parallel research and modular permissioning where they have measured benefits; the linked migration kit has limited validation and is not maintained.'),
    ('claude-duet', 'Preserve plan, region, preview and product-specific safeguards. Connected-app access, stored memory, human approval and isolated credentials are different controls; this does not establish availability in AMind or another host.'),
    ('public-benefit-fund', 'The equity commitment is subject to stockholder approval; plans for distributions and future governance details are not completed distributions or measured public benefit.'),
    ('public-benefit-report', 'This is the company public-benefit report and includes a separately attributed Long-Term Benefit Trust assessment. Inputs, commitments and case counts are not measured net social outcomes, and the Trust conclusion is not an external independent audit. Exact publication day is unconfirmed.'),
    ('public-benefit-charter', 'The charter/report carrier must retain its captured edition. The Long-Term Benefit Trust conclusion has separate attribution and is not an external independent audit; investments and activities are not measured social outcomes.'),
    ('/news/s1-sec', 'This states filing for a proposed IPO. It does not state the registration is effective, an offering is complete, or the company is already listed.'),
    ('smart-reports-surveys-pooled-budgets', 'These Enterprise reports are for adoption and investment planning, not individual performance or employment decisions. Enterprise pooled group budgets differ from inherited per-member gateway limits, and availability depends on organization configuration.'),
    ('claude-models-on-google-cloud', 'Anthropic-managed and Google-managed routes have different data-processor, endpoint and feature contracts. General cloud-brand availability does not establish identical behavior or regional coverage.'),
    ('claude.dev/', 'This is developer practice and product-specific implementation guidance. Preserve the named authors and runtime versions; Claude mods, cloud sessions or API fields are not automatic native Codex capabilities.'),
    ('import-ai-477', 'Jack Clark is expressing a personal perspective. The speech occurred October 17 and the text was published October 19; forecasts and third-party research summaries are not institutional commitments or established economic outcomes.'),
    ('import-ai-478', 'Preserve Jack Clark personal views separately from reported third-party research. Tech Tales is fiction; source summaries and the underlying paper are not independent corroborating works.'),
    ('/responsible-scaling-policy/roadmap', 'The page combines current goals with explicitly dated historical update entries. Preserve the October 19 revision boundary, individual goal status, future target dates and the difference between prototypes and deployed controls.'),
    ('/responsible-scaling-policy/updates', 'This archive contains both former goal wording and later dated completion/retirement reports. Former promises are historical; do not infer fulfillment of current successor goals or backdate public knowledge to the internal completion date.'),
)

# Only these source-bound, quote-matched candidates receive individual AI notes.
REVIEW_SPECS = (
    ('graft', '/2026/graft', ('localiz', '8b', 'penaliz'), 'observed_result', 'Bounded GRAFT intervention: localizing monitored bad behavior rather than assuming a generic reward penalty fixes all reward hacking; scale and monitor limits remain.'),
    ('binders', 'claude-scorpion-toxin-binder-design', ('211', '17 ', 'neutraliz'), 'observed_result', 'Keep designed/tested/binding/neutralization outcomes separate; laboratory binding is not clinical treatment.'),
    ('attack-surface', 'attack-surface-reduction', ('493', '25 ', 'default'), 'observed_result', 'The study hardens attack surfaces across specified projects; counts are issues and configurations, not a universal CVE or exploit count.'),
    ('auto-mode', '/2026/red-teaming-auto-mode', ('september', 'compaction', 'summar', 'not red-team', 'did not red-team'), 'asserted', 'Preserve the September monitor snapshot, malicious-agent threat model, handoff/compaction surface and sandbox-testing limit.'),
    ('formal', '/research/formal-verification', ('239', '123', '64mb', 'risc-v', 'trusted'), 'asserted', 'Formal proof holds under the published spec and restricted machine model; the trusted computing base and unverified scope remain material.'),
    ('ukaisi', 'alignment-assessment-ukaisi', ('momentum', 'august 4', 'safeguards', 'stop'), 'asserted', 'New analysis of a previously disclosed Mythos 5 evaluation incident; assigned-task goals do not excuse serious deception, and initiating versus stopping harmful trajectories are separate measurements.'),
    ('judgment', 'agents-judgment-calls', ('86%', '60%', 'only an independent check', 'single task', 'strengthened their preferences'), 'observed_result', 'The deliberately assigned agent lean affects choices in one analyst task; preference-following is not an error rate and human review need not be an independent check.'),
    ('drug-development', 'early-progress-drug-development', ('preclinical', 'clinical', 'six ', 'manufactur'), 'asserted', 'Scope each drug-development example to its stage and partner/internal evidence; do not infer proven patient benefit.'),
    ('vulnerability-chains', 'discovering-vulnerabilities-with-claude', ('unreleased', 'internal', 'divers', 'pull request'), 'asserted', 'The internal-model demonstration and preventive scanning methods have separate applicability; not evidence that AMind reproduces the model capability.'),
    ('jpp', 'transformer-circuits.pub/2026/october-update/', ('preliminary', 'j++', 'jacobian'), 'asserted', 'Preliminary lens methods and update-date evidence; neither exact publication day nor complete mechanistic explanation is established.'),
    ('fold', 'building-agents-when-to-fold-subagents', ('verification, parallel', 'subagents still', 'fold', 'per-task'), 'asserted', 'Evaluate each subagent boundary instead of treating all multi-agent work as obsolete; task regressions and end-to-end quality matter.'),
    ('constitution-update', '/responsible-scaling-policy/roadmap', ('no longer run it routinely', 'retiring this goal', '90 days of relevant', 'two new policy goals'), 'asserted', 'The October 19 change retires the combined goal while retaining the qualified Constitution synchronization commitment and adding future policy deliverables.'),
    ('redteam-update', '/responsible-scaling-policy/updates', ('matched or beat', 'winning 23', 'completed october 6'), 'observed_result', 'The completion date and public October 19 report date differ. The 24 paired comparisons concern eight biological classifier bounty questions and three generations, not all human red-teaming.'),
    ('duet-controls', 'claude-duet', ('research preview', 'united states', 'us pro', 'stays until', 'never sees'), 'asserted', 'Preserve preview eligibility and distinguish revoking future access from removing existing memory; credentials and action checks run outside the working model.'),
    ('benefit-fund', 'public-benefit-fund', ('subject to stockholder approval', 'roughly 20%'), 'asserted', 'Equity dedication is a conditional governance commitment, not a completed benefit distribution or proof of net social welfare.'),
    ('jack-477', 'import-ai-477', ('i believe', 'singularity has begun', 'i think'), None, 'Jack personal interpretation of progress and forecasts; retain first-person and scenario attribution instead of institutionalizing or treating predictions as measured facts.'),
    ('jack-478', 'import-ai-478', ('programbench', 'mirendil', 'formal'), None, 'Third-party research summaries remain reported unless the precise statement is Jack own interpretation. Fiction remains excluded and paper/summary duplication does not establish independent corroboration.'),
    ('automations', 'building-effective-agent-automations', ('cursor', 'ledger', 'bookmark', 'deliver'), 'asserted', 'Source-specific progress and confirmed-delivery state are separate; failed sources must not silently advance update cursors.'),
    ('code-review', 'solving-code-review-at-anthropic', ('converg', 'round', 'review'), 'asserted', 'Review practice emphasizes convergence, deduplication and incremental follow-up; more rounds are not a general quality guarantee.'),
)


class CurationError(ValueError):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def read_rows(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def local_day(value: str) -> str:
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(ZoneInfo('Asia/Singapore')).date().isoformat()


def source_path(unit: dict) -> str:
    return urlsplit(unit.get('canonical', '')).path.rstrip('/')


def validate_bound_claim(claim: dict, units: dict, passages: dict) -> None:
    evidence = claim['evidence'][0]
    passage = passages.get(evidence['passage_id'])
    if (evidence['analysis_unit_id'] not in units or not passage
            or passage['analysis_unit_id'] != evidence['analysis_unit_id']
            or evidence['exact_quote'] not in passage['text']
            or digest(evidence['exact_quote'].encode()) != evidence['exact_quote_sha256']):
        raise CurationError('invalid context-review evidence binding: ' + claim['claim_id'])
    offset = evidence['source_char_start'] - passage['source_char_start']
    if (offset < 0 or evidence['source_char_end'] - evidence['source_char_start'] != len(evidence['exact_quote'])
            or passage['text'][offset:offset + len(evidence['exact_quote'])] != evidence['exact_quote']):
        raise CurationError('context-review source offset drift: ' + claim['claim_id'])


def text_for(unit: dict, passages: dict) -> str:
    ordered = sorted((p for p in passages.values() if p['analysis_unit_id'] == unit['analysis_unit_id']),
                     key=lambda p: p.get('passage_sequence', 0))
    pieces, offset = [], 0
    for passage in ordered:
        start = passage['source_char_start']
        if start < offset:
            raise CurationError('overlapping source passages')
        pieces.extend(('\n' * (start - offset), passage['text']))
        offset = start + len(passage['text'])
    return ''.join(pieces)


def archived_version_spans(body: str) -> list[tuple[int, int]]:
    """Former promises end at Update; subsequent update paragraphs are current."""
    versions = list(re.finditer(r'(?im)^#{1,6}\s+Version of this goal as set on:.*$', body))
    boundaries = list(re.finditer(r'(?im)^(?:#{1,6}\s*)?Update\s*$|^#{1,2}\s+.*$|^#{1,6}\s+Version of this goal as set on:.*$', body))
    return [(version.start(), next((item.start() for item in boundaries if item.start() > version.start()), len(body)))
            for version in versions]


def public_benefit_scope(unit: dict, body: str) -> dict:
    """Keep the foreword, company assessment, Trust and intended goals distinct."""
    note = 'Charter pillars and appendix objectives describe intended end states and standards, not a claim that AI safety is already solved or all benefits already distributed.'
    scoped = {'analysis_unit_id': unit['analysis_unit_id'], 'source_canonical': unit['canonical'],
              'scope_notes': [note], 'review_scope': 'source-native report section attribution and objective scope',
              'voice_sections': [], 'normative_sections': []}
    if unit['canonical'].endswith(PUBLIC_BENEFIT_PDF):
        pages = {int(m.group(1)): m.start() for m in re.finditer(r'(?m)^## Page (\d+)\s*$', body)}
        if not all(number in pages for number in (2, 4, 17, 19, 20)):
            raise CurationError('Public Benefit Report section boundaries changed')
        scoped['voice_override'] = {'voice_type': 'institutional', 'name': 'Anthropic', 'organization': 'Anthropic',
                                    'role_at_time': 'author of the company Public Benefit Report'}
        scoped['voice_sections'] = [
            {'source_char_start': pages[2], 'source_char_end': pages[4],
             'voice_override': {'voice_type': 'named_author', 'name': 'Daniela Amodei', 'organization': 'Anthropic',
                                'role_at_time': 'author of the report foreword'}},
            {'source_char_start': pages[17], 'source_char_end': pages[19],
             'voice_override': {'voice_type': 'named_author', 'name': 'Buddy Shah on behalf of the Long-Term Benefit Trust',
                                'organization': 'Long-Term Benefit Trust', 'role_at_time': 'author of the Trust closing commentary'},
             'scope_note': 'The Trust is a company governance body, independent of management and investors; this commentary is not an external independent outcome audit.'},
        ]
        goal_start = body.find('1. The technical problems', pages[4])
        goal_end = body.find('This report takes stock', goal_start)
        appendix_start = body.find('Pillar 1', pages[19])
        if goal_start < 0 or goal_end < 0 or appendix_start < 0:
            raise CurationError('Public Benefit Report objective boundaries changed')
        scoped['normative_sections'] = [
            {'source_char_start': goal_start, 'source_char_end': goal_end, 'scope_note': note},
            {'source_char_start': appendix_start, 'source_char_end': len(body), 'scope_note': note},
        ]
    elif source_path(unit) in {'/public-benefit-report', '/public-benefit-charter'}:
        start = body.find('## Charter pillars')
        end = body.find('## Explore the work', start)
        if start >= 0 and end > start:
            scoped['normative_sections'] = [{'source_char_start': start, 'source_char_end': end, 'scope_note': note}]
    return scoped


def make_status(kind: str, targets: list[str], source: str, reason: str, observed: str,
                *, valid_from: str = '', valid_until: str = '', replacements=(), unit_ids=(), extra=None) -> dict:
    row = {
        'kind': kind, 'target_claim_ids': sorted(set(targets)),
        'target_analysis_unit_ids': sorted(set(unit_ids)),
        'valid_from': valid_from, 'valid_until': valid_until,
        'replacement_claim_ids': sorted(set(replacements)),
        'source_canonical': source, 'reason': reason,
        'observed_at': observed, 'reviewer_type': 'AI assistant',
    }
    row.update(extra or {})
    row['status_id'] = 'amind-oct30-status-' + digest(json_bytes({k: v for k, v in row.items() if k != 'observed_at'}))[:24]
    return row


def apply_claim_reviews(claims: list[dict], reviews: list[dict], source_scopes=()) -> list[dict]:
    """Return new rows; IDs, exact quotes and caller-owned originals are retained."""
    by_id = {row['claim_id']: row for row in reviews}
    if len(by_id) != len(reviews):
        raise CurationError('duplicate selected context review')
    known = {row['claim_id'] for row in claims}
    if not set(by_id) <= known:
        raise CurationError('review references unknown delta claim')
    scopes = {row['analysis_unit_id']: row for row in source_scopes}
    result = copy.deepcopy(claims)
    for claim in result:
        evidence = claim['evidence'][0]
        source_scope = scopes.get(evidence['analysis_unit_id'], {})
        for note in source_scope.get('scope_notes', []):
            if note not in claim['conditions']:
                claim['conditions'].append(note)
        claim['voice'].update(source_scope.get('voice_override', {}))
        for section in source_scope.get('voice_sections', []):
            if (evidence['source_char_start'] < section['source_char_end']
                    and evidence['source_char_end'] > section['source_char_start']):
                claim['voice'].update(section['voice_override'])
                if section.get('scope_note') and section['scope_note'] not in claim['conditions']:
                    claim['conditions'].append(section['scope_note'])
        for section in source_scope.get('normative_sections', []):
            if (evidence['source_char_start'] < section['source_char_end']
                    and evidence['source_char_end'] > section['source_char_start']):
                claim['claim_type'] = 'normative'
                if claim['epistemic_force'] != 'quoted_position':
                    claim['epistemic_force'] = 'qualified'
                if section['scope_note'] not in claim['conditions']:
                    claim['conditions'].append(section['scope_note'])
        if source_scope.get('clear_institutional_organization'):
            claim['voice']['organization'] = ''
            note = 'Native byline identifies a collaboration across MATS, Stanford, FAR AI and Anthropic; hosting on the Alignment Blog does not make every collaborator an Anthropic institutional voice.'
            if note not in claim['voice']['attribution_basis']:
                claim['voice']['attribution_basis'] += ' ' + note
        review = by_id.get(claim['claim_id'])
        if not review:
            continue
        if (review['passage_id'] != evidence['passage_id']
                or review['exact_quote_sha256'] != evidence['exact_quote_sha256']):
            raise CurationError('context review binding drift: ' + claim['claim_id'])
        if review.get('human_reviewed') is not False or review.get('human_gold_promotion') is not False:
            raise CurationError('AI review cannot promote human Gold')
        for note in review['scope_notes']:
            if note not in claim['conditions']:
                claim['conditions'].append(note)
        if review.get('epistemic_force'):
            claim['epistemic_force'] = review['epistemic_force']
            claim['conditions'] = [note for note in claim['conditions']
                                   if not note.startswith('Document includes third-party reports')]
        claim['provenance']['extraction_method'] = 'source-exact routine extraction followed by selected individual AI passage-context review'
    return result


def curate_rows(units: list[dict], passages: list[dict], claims: list[dict],
                old_units: list[dict], old_passages: list[dict], old_claims: list[dict],
                previous_status: list[dict], *, required_targets=OLD_TARGETS) -> dict:
    ub = {row['analysis_unit_id']: row for row in units}
    pb = {row['passage_id']: row for row in passages}
    cb = {row['claim_id']: row for row in claims}
    old_ub = {row['analysis_unit_id']: row for row in old_units}
    old_pb = {row['passage_id']: row for row in old_passages}
    old_cb = {row['claim_id']: row for row in old_claims}
    if not units or len(cb) != len(claims):
        raise CurationError('missing units or duplicate delta claim identity')
    observed = max(unit['observed_at'] for unit in units)
    scopes, availability, selected = [], [], {}
    matched_specs = {spec[0]: 0 for spec in REVIEW_SPECS}
    matched_specs['benefit-report-pdf'] = 0
    selected_specs = {name: 0 for name in matched_specs}
    for unit in units:
        notes = [note for needle, note in SOURCE_SCOPES if needle in unit['canonical']]
        if notes:
            scopes.append({'analysis_unit_id': unit['analysis_unit_id'], 'source_canonical': unit['canonical'],
                           'scope_notes': notes, 'review_scope': 'source-level context boundary; not individual claim review',
                           'clear_institutional_organization': '/2026/graft' in unit['canonical']})
        if (unit['canonical'].endswith(PUBLIC_BENEFIT_PDF)
                or source_path(unit) in {'/public-benefit-report', '/public-benefit-charter'}):
            special = public_benefit_scope(unit, text_for(unit, pb))
            existing = next((item for item in scopes if item['analysis_unit_id'] == unit['analysis_unit_id']), None)
            if existing:
                special['scope_notes'] = existing['scope_notes'] + special['scope_notes']
                scopes.remove(existing)
            scopes.append(special)
        if not re.match(r'^\d{4}-\d{2}-\d{2}', unit.get('published_at', '')):
            record_ids = unit.get('source_seed_record_ids', [])
            if len(record_ids) != 1:
                raise CurationError('undated availability requires one bound capture record')
            publication_month = ''
            for date_item in unit.get('extraction', {}).get('date_evidence', []):
                if date_item.get('kind') != 'visible_month_only; exact day unavailable':
                    continue
                try:
                    publication_month = dt.datetime.strptime(date_item['value'], '%B %Y').strftime('%Y-%m')
                except (ValueError, KeyError):
                    raise CurationError('invalid retained publication month')
            availability.append({'analysis_unit_id': unit['analysis_unit_id'], 'source_canonical': unit['canonical'],
                                 'available_by': local_day(unit['observed_at']), 'observed_at': unit['observed_at'],
                                 'raw_sha256': unit['raw_sha256'], 'source_record_id': record_ids[0],
                                 'publication_day': None, 'publication_month': publication_month,
                                 'basis': 'Captured source body directly establishes availability by this observation day; it does not establish publication on that day or non-existence before it.'})
    for claim in claims:
        unit = ub[claim['evidence'][0]['analysis_unit_id']]
        raw_quote = claim['evidence'][0]['exact_quote']
        quote = raw_quote.casefold()
        for name, source, needles, force, note in REVIEW_SPECS:
            if source not in unit['canonical'] or not any(needle.casefold() in quote for needle in needles):
                continue
            validate_bound_claim(claim, ub, pb)
            matched_specs[name] += 1
            # Do not present a navigation label or a mechanically expanded
            # mid-word fragment as an individually reviewed proposition.
            if (not raw_quote[:1].isupper()
                    or raw_quote.rstrip()[-1:] not in '.?!\u201d\u2019\"\''):
                continue
            # Whole-source scope notes cover all matching material. Individual
            # review is deliberately a small inspected sample, not every row a
            # keyword happens to match.
            if selected_specs[name] >= 3:
                continue
            selected_specs[name] += 1
            evidence = claim['evidence'][0]
            review = selected.setdefault(claim['claim_id'], {
                'claim_id': claim['claim_id'], 'passage_id': evidence['passage_id'],
                'exact_quote_sha256': evidence['exact_quote_sha256'], 'analysis_unit_id': unit['analysis_unit_id'],
                'source_canonical': unit['canonical'], 'reviewer_type': 'AI assistant',
                'human_reviewed': False, 'human_gold_promotion': False,
                'review_state': 'machine_checked', 'scope_notes': [], 'spec_ids': [],
            })
            # Keep the original sentence's question/forecast force. An AI scope
            # note is not a reason to turn every matching sentence into a fact.
            # Only a conservatively reported candidate can be individually
            # promoted under this explicit source-context rule.
            if force and claim.get('epistemic_force') == 'quoted_position':
                previous_force = review.get('epistemic_force')
                if previous_force and previous_force != force:
                    raise CurationError('conflicting AI context-review force')
                review['epistemic_force'] = force
            if note not in review['scope_notes']:
                review['scope_notes'].append(note)
            review['spec_ids'].append(name)
        if unit['canonical'].endswith(PUBLIC_BENEFIT_PDF):
            pdf_reviews = (
                ('publish annually', 'forecast', 'Daniela Amodei foreword commits to annual reporting; this is a reporting commitment, not proof of achieved public-benefit outcomes.'),
                ('largely describes inputs', 'asserted', 'Buddy Shah, on behalf of the LTBT, distinguishes current inputs from future outcome evidence; preserve Trust attribution.'),
                ('independent evaluators to confirm', 'forecast', 'The LTBT expects independent confirmation in future reports; it is not stating such confirmation has already occurred.'),
                ('don’t yet have evidence', 'asserted', 'The company explicitly acknowledges that early health and education initiatives lack evidence of their intended effects.'),
                ('interpretability methods are not yet dependable', 'qualified', 'The company explicitly limits current interpretability reliability; this does not imply full access to model intentions.'),
                ('section 366 of the delaware', 'asserted', 'This records board adoption of objectives and measurement standards under the stated legal framework; the objectives are not achieved end states.'),
            )
            for needle, force, note in pdf_reviews:
                if needle not in quote:
                    continue
                validate_bound_claim(claim, ub, pb)
                matched_specs['benefit-report-pdf'] += 1
                selected_specs['benefit-report-pdf'] += 1
                evidence = claim['evidence'][0]
                selected[claim['claim_id']] = {
                    'claim_id': claim['claim_id'], 'passage_id': evidence['passage_id'],
                    'exact_quote_sha256': evidence['exact_quote_sha256'], 'analysis_unit_id': unit['analysis_unit_id'],
                    'source_canonical': unit['canonical'], 'reviewer_type': 'AI assistant',
                    'human_reviewed': False, 'human_gold_promotion': False, 'review_state': 'machine_checked',
                    'scope_notes': [note], 'spec_ids': ['benefit-report-pdf'], 'epistemic_force': force,
                }
    replacements = {}
    for key, needles in REPLACEMENT_NEEDLES.items():
        replacements[key] = sorted(c['claim_id'] for c in claims
                                   if source_path(ub[c['evidence'][0]['analysis_unit_id']])
                                   in {'/responsible-scaling-policy/roadmap', '/responsible-scaling-policy/updates'}
                                   and any(needle in c['evidence'][0]['exact_quote'].casefold() for needle in needles))
    additions = []
    for available in availability:
        unit = ub[available['analysis_unit_id']]
        if (source_path(unit) in {'/responsible-scaling-policy/roadmap', '/responsible-scaling-policy/updates'}
                and 'October 19, 2026' in text_for(unit, pb)):
            # The source's dated public change record directly supports the
            # edition boundary below; a later capture is not a reason to hide
            # that explicitly dated revision until the observation day.
            continue
        proof = {key: available[key] for key in ('analysis_unit_id', 'source_canonical', 'observed_at',
                                                'raw_sha256', 'source_record_id')}
        proof['kind'] = 'captured_source_body'
        month = available['publication_month']
        additions.append(make_status('publication_window', [], available['source_canonical'],
                                     available['basis'], available['observed_at'],
                                     valid_from=month + '-01' if month else '',
                                     unit_ids=[available['analysis_unit_id']],
                                     extra={'available_by': available['available_by'],
                                            'publication_month': month,
                                            'availability_evidence': proof}))
    for spec in required_targets:
        claim = old_cb.get(spec['claim_id'])
        if not claim:
            raise CurationError('required old claim missing: ' + spec['claim_id'])
        validate_bound_claim(claim, old_ub, old_pb)
        if claim['evidence'][0]['exact_quote_sha256'] != spec['quote_sha256']:
            raise CurationError('required old claim quote changed: ' + spec['claim_id'])
        if not replacements[spec['key']]:
            raise CurationError('required replacement evidence absent: ' + spec['key'])
        additions.append(make_status('superseded', [spec['claim_id']],
                                     UPDATES if spec['key'] != 'policy' else ROADMAP,
                                     RETIREMENT_NOTES[spec['key']], observed,
                                     valid_until=CHANGE_DAY, replacements=replacements[spec['key']]))
    # A newly indexed October 18 article can itself contain an already fulfilled
    # plan. The dated October 21 news is the direct availability witness; the
    # report's own exact publication day remains unknown.
    stale_report_plans = [claim for claim in claims
                          if 'public-benefit-fund' in ub[claim['evidence'][0]['analysis_unit_id']]['canonical']
                          and 'upcoming public benefit report' in claim['evidence'][0]['exact_quote'].casefold()]
    report_witnesses = [claim for claim in claims
                        if 'christopher-stubbs-joins-long-term-benefit-trust' in ub[claim['evidence'][0]['analysis_unit_id']]['canonical']
                        and 'published our first public benefit report' in claim['evidence'][0]['exact_quote'].casefold()
                        and ub[claim['evidence'][0]['analysis_unit_id']]['published_at'] == '2026-10-21']
    if stale_report_plans:
        if not report_witnesses:
            raise CurationError('upcoming report plan lacks dated publication witness')
        for claim in stale_report_plans + report_witnesses:
            validate_bound_claim(claim, ub, pb)
        additions.append(make_status('superseded', [claim['claim_id'] for claim in stale_report_plans],
                                     ub[report_witnesses[0]['evidence'][0]['analysis_unit_id']]['canonical'],
                                     'The October 21 dated news states that the first Public Benefit Report was published this week. The October 18 upcoming-report plan is fulfilled by no later than October 21; retain the original promise historically without manufacturing an exact report publication day.',
                                     observed, valid_until='2026-10-21',
                                     replacements=[claim['claim_id'] for claim in report_witnesses]))
    # Repeated old wording on both captured editions must not become eligible again.
    obsolete_patterns = (
        ('constitution', 'will keep our public constitution up to date and run a systematic oversight'),
        ('constitution', 'aim to make these measures more complete and systematic'),
        ('constitution', 'we will run an oversight process over a representative sample'),
        ('constitution', 'will describe this oversight process in our risk reports'),
        ('redteam', 'believe we can develop a method for red-teaming our systems'),
        ('redteam', 'we will establish an internal jailbreak-finding method'),
        ('redteam', 'we will assess this via a report'),
        ('redteam', 'this could put us in position to continue leveling up'),
        ('policy', 'expect to publish a new goal in the coming weeks'),
        ('policy', 'plan to publish a new policy goal to replace it'),
        ('moonshot', 'still plan to complete phase 1'),
        ('moonshot', 'we will complete phase 1'),
        ('moonshot', 'we will develop a prototype by september 30, 2026'),
        ('moonshot', 'the phase 1 deadline is september 30, 2026'),
        ('moonshot', 'focused on provable inference and a mock secure research environment'),
    )
    already_targeted = {cid for row in previous_status + additions for cid in row.get('target_claim_ids', [])}
    all_units = old_ub | ub
    for claim in old_claims + claims:
        unit = all_units[claim['evidence'][0]['analysis_unit_id']]
        path = source_path(unit)
        if path not in {'/responsible-scaling-policy/roadmap', '/responsible-scaling-policy/updates'}:
            continue
        # The new archive is handled by exact Version/Update spans below.
        # Old archive rows may already have earlier baseline decisions.
        if path.endswith('/updates') and unit['analysis_unit_id'] in ub:
            continue
        quote = claim['evidence'][0]['exact_quote'].casefold()
        for key, needle in obsolete_patterns:
            if needle not in quote or claim['claim_id'] in already_targeted:
                continue
            if not replacements[key]:
                raise CurationError('matching changed paragraph has no replacement: ' + key)
            validate_bound_claim(claim, all_units, old_pb | pb)
            additions.append(make_status('superseded', [claim['claim_id']], unit['canonical'],
                                         RETIREMENT_NOTES[key], observed,
                                         valid_until=CHANGE_DAY, replacements=replacements[key]))
            already_targeted.add(claim['claim_id'])
    # Date the current Roadmap edition but retain unmodified propositions in old editions.
    for unit in units:
        path = source_path(unit)
        if path in {'/responsible-scaling-policy/roadmap', '/responsible-scaling-policy/updates'}:
            body = text_for(unit, pb)
            if 'October 19, 2026' not in body:
                raise CurationError('October 19 revision date is absent from captured policy body')
            additions.append(make_status('effective_window', [], unit['canonical'],
                                         'The captured edition contains explicitly dated October 19 updates; its original work publication date cannot establish this wording before that revision.',
                                         unit['observed_at'], valid_from=CHANGE_DAY,
                                         unit_ids=[unit['analysis_unit_id']]))
        if path == '/responsible-scaling-policy/updates':
            # Each archival Version block ends at its own Update or next heading.
            # New completion/retirement explanations stay current from October 19.
            own = [c for c in claims if c['evidence'][0]['analysis_unit_id'] == unit['analysis_unit_id']]
            historical_spans = archived_version_spans(body)
            for claim in own:
                evidence = claim['evidence'][0]
                if not any(evidence['source_char_start'] < end and evidence['source_char_end'] > start
                           for start, end in historical_spans):
                    continue
                additions.append(make_status('historical_only', [claim['claim_id']], UPDATES,
                                             'This passage reproduces an explicitly archived Version of a former goal, not a current goal. The adjacent dated update is separate evidence and remains available under its own scope.',
                                             unit['observed_at'], valid_until=CHANGE_DAY))
        if path in {'/legal/aup', '/legal/supported-regions'}:
            body = text_for(unit, pb)
            # Legal Center's newer template separates its header label and
            # abbreviated date with blank lines: "- Effective\n\nNov 12, 2026".
            if re.search(r'(?im)^\s*(?:-\s*)?Effective\s*:?\s*Nov(?:ember)?\s+12,?\s+2026', body):
                additions.append(make_status('effective_window', [], unit['canonical'],
                                             'The native header gives November 12, 2026 as the effective date. A captured or announced policy is not yet operative before that date.',
                                             unit['observed_at'], valid_from='2026-11-12',
                                             unit_ids=[unit['analysis_unit_id']]))
        if path == '/docs/en/about-claude/model-deprecations':
            previous_editions = [old for old in old_units if source_path(old) == path]
            if len(previous_editions) != 1:
                raise CurationError('runtime deprecation manual needs one previous captured edition')
            previous = previous_editions[0]
            if text_for(previous, old_pb) == text_for(unit, pb):
                raise CurationError('runtime deprecation manual has no captured body revision')
            switch_day = local_day(unit['observed_at'])
            reason = ('The captured runtime manual now distinguishes Anthropic-managed Claude Models on Google Cloud '
                      'from the Google-managed route and their retirement-schedule responsibilities. Replace the '
                      'previous operational edition on this observation day; model retirement dates and dated API '
                      'changelog entries do not establish the publication day of this document revision.')
            additions.append(make_status('superseded', [], unit['canonical'], reason, unit['observed_at'],
                                         valid_until=switch_day, unit_ids=[previous['analysis_unit_id']],
                                         extra={'replacement_analysis_unit_ids': [unit['analysis_unit_id']]}))
            additions.append(make_status('effective_window', [], unit['canonical'], reason, unit['observed_at'],
                                         valid_from=switch_day, unit_ids=[unit['analysis_unit_id']]))
    # Ensure append-only registry identity and preservation of every old record.
    previous_ids = {row['status_id'] for row in previous_status}
    new_ids = [row['status_id'] for row in additions]
    if len(previous_ids) != len(previous_status) or len(set(new_ids)) != len(new_ids) or previous_ids & set(new_ids):
        raise CurationError('lifecycle identity collision')
    all_claims = set(old_cb) | set(cb)
    for status in additions:
        if not set(status['target_claim_ids'] + status['replacement_claim_ids']) <= all_claims:
            raise CurationError('lifecycle claim foreign-key mismatch')
        if not set(status['target_analysis_unit_ids'] + status.get('replacement_analysis_unit_ids', [])) <= set(all_units):
            raise CurationError('lifecycle unit foreign-key mismatch')
    return {
        'claim-reviews': sorted(selected.values(), key=lambda row: row['claim_id']),
        'source-scope-notes': sorted(scopes, key=lambda row: row['analysis_unit_id']),
        'source-availability': sorted(availability, key=lambda row: row['analysis_unit_id']),
        'current-status-additions': sorted(additions, key=lambda row: row['status_id']),
        'current-status': copy.deepcopy(previous_status) + sorted(additions, key=lambda row: row['status_id']),
        'audit': {
            'schema_name': 'amind-october-30-curation-audit', 'schema_version': 1,
            'date': '2026-10-30', 'observed_at': observed,
            'baseline_rows_unchanged': True, 'new_human_reviewed_gold': 0,
            'matched_review_specs': matched_specs,
            'selected_review_specs': selected_specs,
            'unmatched_review_specs': [key for key, count in matched_specs.items() if not count],
            'selected_AI_context_reviewed_claims': len(selected),
            'source_scope_notes': len(scopes), 'undated_availability_records': len(availability),
            'old_status_records': len(previous_status), 'new_status_records': len(additions),
            'required_old_claims_retired': [spec['claim_id'] for spec in required_targets],
            'fulfilled_new_source_plans_retired': [claim['claim_id'] for claim in stale_report_plans],
            'registry_scope': 'Specific old propositions and archived version prose, plus observed-edition replacement of the runtime deprecation manual; no whole old-Roadmap exclusion.',
        },
    }


def curate_release(release: Path, baseline: Path, apply: bool = False) -> dict:
    release, baseline = Path(release).resolve(), Path(baseline).resolve()
    paths = {
        'units': release / 'delta/analysis-units.jsonl.gz',
        'passages': release / 'delta/passages.jsonl.gz',
        'claims': release / 'delta/atomic-claims.jsonl.gz',
        'old_units': baseline / 'data/analysis-units.jsonl.gz',
        'old_passages': baseline / 'data/passages.jsonl.gz',
        'old_claims': baseline / 'data/atomic-claims.jsonl.gz',
        'previous_status': baseline / 'data/current-status.jsonl',
    }
    values = {name: read_rows(path) for name, path in paths.items()}
    result = curate_rows(**values)
    result['audit']['input_sha256'] = {name: digest(path.read_bytes()) for name, path in paths.items()}
    if apply:
        destination = release / 'curation'
        if destination.is_symlink():
            raise CurationError('curation output cannot be a symlink')
        destination.mkdir(exist_ok=True)
        for name, rows in result.items():
            path = destination / ('curation-audit.json' if name == 'audit' else name + '.jsonl')
            if path.is_symlink():
                raise CurationError('curation output file cannot be a symlink')
            payload = json_bytes(rows) if name == 'audit' else b''.join(json_bytes(row) for row in rows)
            path.write_bytes(payload)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, default=ROOT / 'release/amind-v1-increment-2026-10-30')
    parser.add_argument('--baseline', type=Path, default=ROOT / 'release/amind-v1-increment-2026-10-18')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(curate_release(args.release, args.baseline, args.apply)['audit'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
