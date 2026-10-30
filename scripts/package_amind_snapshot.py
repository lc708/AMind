#!/usr/bin/env python3
"""Package a portable append-only release; eligibility is explicit curation.

Use --seal-only after adding reports: it refreshes the release artifact manifest
without rebuilding the data or index. It never alters a frozen previous release.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

import build_amind_skill_index as indexer
from package_amind_refresh import rows, write, write_rows

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/amind/scripts'))
import lifecycle

DEFAULT_RELEASE = 'release/amind-v1-increment-2026-10-30'
DEFAULT_BASE = 'release/amind-v1-increment-2026-10-18'
TABLES = [('analysis-units', 'analysis_unit_id'), ('atomic-claims', 'claim_id'), ('passages', 'passage_id'),
          ('claim-attribution-audit', 'claim_id'), ('theme-membership', 'claim_id')]
SUPPLEMENTS = {
    'alignment-as-hidden-behavior': ('新增 GRAFT 与 UK AISI 事故分析，补充奖励投机干预和错误轨迹持续机制。既往事故的发生、披露与本次分析时间分开；任务驱动不能淡化欺骗和越权。', ['graft', 'alignment-assessment-ukaisi']),
    'capability-scaling-under-uncertainty': ('新科学与软件安全研究扩大了所观察的能力范围，但内部未发布模型、受限实验和个人研发加速预测不互相替代，也不构成 AMind 本地能力提升证明。', ['drug-development', 'discovering-vulnerabilities', 'import-ai-478']),
    'capability-triggered-governance': ('新增公共利益报告和股权基金、标准治理及路线图状态。已完成、退休、修订和未来目标分别标注；投入、承诺和实际公共利益成果保持区别。', ['public-benefit', 'responsible-scaling-policy', 'donating-agent-skills']),
    'disciplined-agent-engineering': ('补充将高耦合子代理折回主循环的条件，以及自动化游标、审查收敛和云会话验收。保留独立验证、并行研究与权限隔离的条件价值，不推导一律单代理。', ['fold-subagents', 'effective-agent-automations', 'solving-code-review', 'claude-code-in-the-cloud']),
    'economic-transition-and-distribution': ('公共利益分配、行业工作流和科学合作扩展了采用与收益讨论。供应商案例、计划条件、投入和已测社会效果分别归属；不将潜在收益当作因果效果。', ['public-benefit', 'financial-advisors', 'nonprofits', 'science-expands']),
    'human-agency-values-and-welfare': ('专家判断实验要求区分有人审阅与独立判断；主动代理材料补充信息发送、记忆、撤销访问和重要动作的边界。单一实验比例不能成为普遍错误率。', ['agents-judgment-calls', 'claude-duet']),
    'measurement-and-adaptive-evaluation': ('补充代理架构逐任务得失、专家偏好、跨交接监测以及验证器范围的评测。审计器与监督者自身也需要校准；平均分或审批率不足以替代这些测量。', ['fold-subagents', 'agents-judgment-calls', 'red-teaming-auto-mode', 'formal-verification']),
    'mechanistic-legibility': ('新增十月 J++ lens 初步研究，保留月份与官方 feed 更新时间的区别。读出中间变量的方法进展不自动证明模型思维或意识已得到解释。', ['2026/october-update']),
    'security-and-defense-in-depth': ('新增真实事故分析、持续对抗代理红队、攻击面缩减、形式化验证和漏洞链案例。授权、共享状态、监测覆盖、可信组件与实验版本须一并核对。', ['red-teaming-auto-mode', 'attack-surface-reduction', 'formal-verification', 'discovering-vulnerabilities', 'alignment-assessment-ukaisi']),
}
VOICE_NOTES = {
    'anthropic-institution': '新增治理、代理判断、科学、安全和产品材料；实验、伙伴自述、机构承诺及实际成果分别归属。具体部署和访问条件不自动推广到所有产品。',
    'dario-amodei': '本轮已检查的个人站点没有形成新的独立人物结论；保留九月文章的月份精度和个人归属，不用机构新材料代替个人新立场。',
    'jack-clark': '新增 Import AI 477 和 478。演讲发生日与文字公开日分开；个人奇点及研究加速判断、第三方结果和 Tech Tales 小说分别保留范围。',
    'amanda-askell': '本轮未形成新的独立人物观点结论，原有画像继续作为历史校准；覆盖计数不代表观点权重。',
    'chris-olah': '新增 Transformer Circuits 团队方法不能自动归于个人观点；原有画像保留，初步方法结果保留限制。',
}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''): digest.update(block)
    return digest.hexdigest()


def paths(release, base):
    release = (ROOT / release).resolve(); base = (ROOT / base).resolve()
    if release == base or not release.is_relative_to((ROOT / 'release').resolve()) or not base.is_relative_to((ROOT / 'release').resolve()):
        raise ValueError('distinct release/base directories must be under release/')
    return release, base


def preserved_statuses(base, curated):
    old = rows(base / 'data/current-status.jsonl')
    merged = {r['status_id']: r for r in old}
    for row in curated:
        key = row['status_id']
        if key in merged and merged[key] != row: raise ValueError('existing lifecycle decision rewritten: ' + key)
        merged[key] = row
    result = list(merged.values()); lifecycle.validate_records(result)
    return result


def historical_versions(base):
    # Delta relations are retained in each frozen release. Combining all previous
    # increments preserves metadata and their original eligibility semantics.
    result = {}; releases = []
    current = base
    while current not in releases:
        releases.append(current)
        manifest = json.loads((current / 'manifest.json').read_text())
        prior = manifest.get('base_release_id')
        if not prior or prior == current.name or prior == 'amind-v1': break
        current = ROOT / 'release' / prior
    for directory in reversed(releases):
        file = directory / 'delta/version-relations.jsonl'
        if file.exists():
            for version in rows(file): result[version['new_analysis_unit_id']] = version
    return list(result.values())


def update_synthesis(data, base, release_id, date, units, claims, audits):
    unit_by_id = {u['analysis_unit_id']: u for u in units}; claim_by_id = {c['claim_id']: c for c in claims}
    memberships = rows(data / 'theme-membership.jsonl.gz')
    themes = rows(base / 'data/theme-catalog.jsonl')
    new_ids = {c['claim_id'] for c in rows(data.parent / 'delta/atomic-claims.jsonl.gz')}
    direct_ids = {a['claim_id'] for a in audits if a['synthesis_disposition'] == 'eligible_for_source_level_synthesis'}
    for theme in themes:
        matched = [m for m in memberships if theme['theme_id'] in m['theme_ids']]
        direct = [m for m in matched if m['claim_id'] in direct_ids]
        ids = {m['analysis_unit_id'] for m in matched}; bands = Counter()
        for uid in ids:
            match = re.search(r'\b(?:19|20)\d{2}\b', unit_by_id[uid].get('published_at', ''))
            year = int(match.group()) if match else None
            bands['undated' if year is None else 'through_2018' if year <= 2018 else '2019_2022' if year <= 2022 else '2023_2024' if year <= 2024 else '2025_2026'] += 1
        text, needles = SUPPLEMENTS[theme['theme_id']]
        candidates = [m for m in direct if m['claim_id'] in new_ids and any(n in unit_by_id[m['analysis_unit_id']]['canonical'] for n in needles)]
        chosen = []; works = set()
        for member in candidates:
            work = unit_by_id[member['analysis_unit_id']]['work_id']
            if work in works: continue
            works.add(work); chosen.append(member['claim_id'])
            if len(chosen) == 4: break
        theme.update(count_scope=release_id, matched_claim_count=len(matched), matched_analysis_unit_count=len(ids),
            direct_synthesis_claim_count=len(direct), analysis_units_by_time_band=dict(sorted(bands.items())),
            direct_claims_by_voice_type=dict(sorted(Counter(claim_by_id[m['claim_id']]['voice']['voice_type'] for m in direct).items())),
            current_supplement_zh=text, supplement_as_of=date, supplement_review='AI synthesis; not human Gold',
            supplement_claim_ids=chosen, coverage_count_interpretation='all retained historical and current claims; current eligibility is applied during retrieval')
    write_rows(data / 'theme-catalog.jsonl', themes)
    voices = rows(base / 'data/voice-profiles.jsonl')
    for voice in voices:
        direct = [c for c in claims if c['claim_id'] in direct_ids and c['voice']['name'] == voice['name']]
        voice.update(direct_claim_count=len(direct), analysis_unit_count=len({c['evidence'][0]['analysis_unit_id'] for c in direct}),
            count_scope=release_id, current_supplement_zh=VOICE_NOTES[voice['voice_id']], supplement_as_of=date,
            supplement_review='AI synthesis; not human Gold', supplement_claim_ids=[c['claim_id'] for c in direct if c['claim_id'] in new_ids][:4])
    write_rows(data / 'voice-profiles.jsonl', voices)


def require_owned_release(release, base, date):
    if release.parent != (ROOT/'release').resolve() or release.name != 'amind-v1-increment-'+date:
        raise ValueError('only the direct, dated release owned by this refresh can be written')
    if any(p.is_symlink() for p in release.rglob('*')):
        raise ValueError('owned release cannot contain symlinked markers, directories or output artifacts')
    marker=release/'audits/refresh-run.json'
    expected={'schema_name':'amind-refresh-run','release_id':release.name,'date':date,'base_release_id':base.name}
    if not marker.is_file() or marker.is_symlink() or json.loads(marker.read_text())!=expected:
        raise ValueError('published historical release is immutable; matching refresh-run ownership is required')


def seal(release, base, counts=None):
    skill_manifest = ROOT / 'skills/amind/data/manifest.json'
    skill = json.loads(skill_manifest.read_text())
    require_owned_release(release,base,skill['source_observation_cutoff'])
    if skill['release_id'] != release.name: raise ValueError('cannot seal a release different from current packaged skill')
    manifest_path = release / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    manifest.update(schema_name='amind-increment-release', schema_version=1, release_id=release.name,
        base_release_id=base.name, source_observation_cutoff=skill['source_observation_cutoff'], timezone='Asia/Singapore',
        counts=counts or manifest['counts'], review_boundary=skill['incremental_boundary'], skill_manifest_sha256=sha(skill_manifest),
        index_revision_policy='explicit claim/unit eligibility_scope; no automatic retirement for claim-curated revisions')
    artifacts = []
    for item in sorted(release.rglob('*')):
        if item == manifest_path: continue
        if item.is_symlink(): raise ValueError('release cannot contain symbolic links: ' + str(item))
        if item.is_file(): artifacts.append({'path': item.relative_to(release).as_posix(), 'bytes': item.stat().st_size, 'sha256': sha(item)})
    manifest['artifacts'] = artifacts; write(manifest_path, manifest)
    return manifest['counts']


def package(release=DEFAULT_RELEASE, base=DEFAULT_BASE, date='2026-10-30', skill_version='1.4.0', seal_only=False):
    release, base = paths(release, base)
    require_owned_release(release,base,date)
    if seal_only: return seal(release, base)
    # Verify frozen history before writing any package data.
    frozen = json.loads((release / 'audits/frozen-history.json').read_text())
    if not frozen: raise ValueError('missing frozen historical fingerprints')
    for relative, digest in frozen.items():
        file = (ROOT / relative).resolve()
        if not file.is_relative_to((ROOT / 'release').resolve()) or file.is_relative_to(release):
            raise ValueError('invalid frozen historical path')
        if sha(file) != digest: raise ValueError('frozen artifact changed: ' + relative)
    data = release / 'data'; skill = ROOT / 'skills/amind/data'
    populations = {}
    for name, key in TABLES:
        all_rows = rows(data / (name + '.jsonl.gz')); old = rows(base / 'data' / (name + '.jsonl.gz'))
        delta = rows(release / 'delta' / (name + '.jsonl.gz')); lookup = {r[key]: r for r in all_rows}
        if len(lookup) != len(all_rows) or len(all_rows) != len(old) + len(delta): raise ValueError('invalid population: ' + name)
        if any(lookup.get(r[key]) != r for r in old + delta): raise ValueError('old/delta row drift: ' + name)
        populations[name] = all_rows
    units = populations['analysis-units']; claims = populations['atomic-claims']; passages = populations['passages']
    audits = populations['claim-attribution-audit']; update_synthesis(data, base, release.name, date, units, claims, audits)
    curated = rows(release / 'curation/current-status.jsonl')
    statuses = preserved_statuses(base, curated)
    write_rows(data / 'current-status.jsonl', statuses)
    counts = {'analysis_units': len(units), 'atomic_claims': len(claims), 'passages': len(passages), 'reviewed_kernel_claims': 54,
        'equivalence_components': len(rows(data / 'claim-equivalence-components.jsonl')),
        'new_units': len(rows(release / 'delta/analysis-units.jsonl.gz')),
        'new_claims': len(rows(release / 'delta/atomic-claims.jsonl.gz')),
        'new_passages': len(rows(release / 'delta/passages.jsonl.gz'))}
    versions = historical_versions(base) + rows(release / 'delta/version-relations.jsonl')
    for attr, name in [('ANALYSIS_UNITS', 'analysis-units.jsonl.gz'), ('ATOMIC_CLAIMS', 'atomic-claims.jsonl.gz'),
        ('ATTRIBUTION_AUDIT', 'claim-attribution-audit.jsonl.gz'), ('EQUIVALENCE_COMPONENTS', 'claim-equivalence-components.jsonl'),
        ('PASSAGES', 'passages.jsonl.gz'), ('SYNTHESIS_EVIDENCE', 'synthesis-evidence.jsonl'), ('THEME_MEMBERSHIP', 'theme-membership.jsonl.gz')]:
        setattr(indexer, attr, data / name)
    indexer.INPUTS = (indexer.ANALYSIS_UNITS, indexer.ATOMIC_CLAIMS, indexer.ATTRIBUTION_AUDIT, indexer.EQUIVALENCE_COMPONENTS,
        indexer.PASSAGES, indexer.SYNTHESIS_EVIDENCE, indexer.THEME_MEMBERSHIP)
    with tempfile.TemporaryDirectory(prefix='amind-snapshot-index-', dir=skill) as temporary:
        index_path = Path(temporary) / 'index.sqlite3'
        indexer.build_index_file(index_path, release_id=release.name, expected=counts, version_relations=versions)
        index_path.replace(skill / 'amind-full-index.sqlite3')
    for name in ['passages.jsonl.gz', 'theme-catalog.jsonl', 'voice-profiles.jsonl', 'current-status.jsonl']:
        shutil.copyfile(data / name, skill / name)
    manifest = json.loads((skill / 'manifest.json').read_text())
    manifest.update(release_id=release.name, skill_version=skill_version, base_release_id='amind-v1', previous_release_id=base.name,
        source_observation_cutoff=date, incremental_batch_id=date, current_status_bundled=True,
        current_status_scope='claim-bound dated corrections, edition availability and effective windows; historical evidence retained')
    collection = json.loads((release / 'audits/collection-summary.json').read_text())
    discovery = json.loads((release / 'audits/discovery-summary.json').read_text())
    manifest['source_observation_completed_at'] = collection['completed_at']
    manifest['source_coverage'] = {'configured_entry_points': discovery['configured_sources'], 'failed_entry_points': discovery['failed_sources'],
        'body_captures': collection['captured'], 'failed_selected_bodies': len(collection['failed']),
        'retained_capture_records': collection.get('retained_capture_records',collection['captured']),
        'retained_metadata_only_records': collection.get('retained_metadata_only_records',0),
        'scope': 'configured public entry points, reviewed new/backfill seeds and selected attachments; not complete internet or spoken-interview coverage'}
    manifest['counts'].update(full_index_analysis_units=len(units), full_index_atomic_claims=len(claims), full_index_passages=len(passages),
        full_release_analysis_units=len(units), full_release_atomic_claims=len(claims), full_index_equivalence_components=counts['equivalence_components'],
        full_index_direct_claims=sum(a['synthesis_disposition'] == 'eligible_for_source_level_synthesis' for a in audits), current_status_decisions=len(statuses))
    old_artifacts = {a['path']: a for a in manifest['artifacts']}; artifacts = []
    for name in ['amind-full-index.sqlite3', 'evidence-kernel.jsonl', 'passages.jsonl.gz', 'synthesis-tensions.jsonl', 'theme-catalog.jsonl', 'voice-profiles.jsonl', 'current-status.jsonl']:
        file = skill / name
        count = len(claims) if name.endswith('.sqlite3') else len(passages) if name == 'passages.jsonl.gz' else len(rows(file))
        artifacts.append({'path': name, 'format': 'sqlite3-fts5' if name.endswith('.sqlite3') else 'jsonl-gzip' if name.endswith('.gz') else 'jsonl',
            'bytes': file.stat().st_size, 'sha256': sha(file), 'rows': count,
            'schema_name': old_artifacts.get(name, {}).get('schema_name', 'amind-current-status-decision')})
    manifest['artifacts'] = artifacts
    manifest['sources'] = [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)} for p in sorted(data.iterdir()) if p.is_file()]
    manifest['incremental_boundary'] = {'raw_baseline_unchanged': True, 'new_human_reviewed_gold_rows': 0,
        'new_claims_review': 'machine checked; selected passages additionally reviewed in context by AI', 'complete_web_coverage_claimed': False,
        'recurring_update_configured': False, 'report': str((release / 'reports/update.zh-CN.md').relative_to(ROOT))}
    write(skill / 'manifest.json', manifest)
    return seal(release, base, counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', default=DEFAULT_RELEASE); parser.add_argument('--base', default=DEFAULT_BASE)
    parser.add_argument('--date', default='2026-10-30'); parser.add_argument('--skill-version', default='1.4.0')
    parser.add_argument('--seal-only', action='store_true'); args = parser.parse_args()
    print(json.dumps(package(args.release, args.base, args.date, args.skill_version, args.seal_only), indent=2))


if __name__ == '__main__': main()
