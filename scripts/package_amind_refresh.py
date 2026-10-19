#!/usr/bin/env python3
"""Package the append-only October release and rebuild the self-contained skill."""
from __future__ import annotations
import gzip
import hashlib
import json
import shutil
import re
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import build_amind_skill_index as indexer
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/amind/scripts'))
import lifecycle

ROOT=Path(__file__).resolve().parents[1]
RELEASE_ID='amind-v1-increment-2026-10-18'
RELEASE=ROOT/'release'/RELEASE_ID
DATA=RELEASE/'data'
SKILL=ROOT/'skills/amind/data'
BASE=ROOT/'release/amind-v1-increment-2026-09-08'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):
    with (gzip.open if path.suffix=='.gz' else open)(path,'rt',encoding='utf-8') as h:
        return [json.loads(l) for l in h if l.strip()]
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def write_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n' for v in values),encoding='utf-8')


def revision_day(version):
    explicit=version.get('explicit_modified_at') or ''
    if explicit:return explicit[:10]
    observed=version.get('observed_at') or ''
    if not observed:return ''
    return datetime.fromisoformat(observed.replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Singapore')).date().isoformat()


def publication_windows(units):
    """Derive partial-date boundaries from retained source-native metadata."""
    decisions=[]
    for unit in units:
        if lifecycle.day(unit.get('published_at')):
            continue
        evidence=(unit.get('extraction') or {}).get('date_evidence') or []
        for item in evidence:
            # A date somewhere on a PDF cover can be a revision, CV entry or
            # report period. Only the explicitly classified visible publication
            # month is strong enough to date availability of this edition.
            if item.get('kind') != 'visible_month_only; exact day unavailable':
                continue
            first,last,precision=lifecycle.publication_bounds(item.get('value'))
            if precision != 'month':
                continue
            decisions.append({'status_id':'publication-month-'+unit['analysis_unit_id'],
                'target_analysis_unit_ids':[unit['analysis_unit_id']], 'kind':'publication_window',
                'valid_from':first.isoformat(), 'publication_month':first.strftime('%Y-%m'),
                'source_canonical':unit['canonical'],
                'reason':'The source labels its publication month as '+item['value']+
                    '; the exact day is unavailable. The first day is only an earliest possible bound, not a publication date.',
                'observed_at':unit.get('observed_at',''), 'reviewer_type':'retained source-native partial date'})
            break
    return decisions


def revision_windows(units,versions,statuses):
    """Date edition transitions without mistaking publication metadata for retirement."""
    # Explicit retirement dates (such as a policy's scheduled replacement) take
    # precedence. A publication month or start-only window does not retire it.
    retired_units={u for r in statuses
        if r.get('kind') in {'corrected','superseded','historical_only','effective_window'}
        and lifecycle.day(r.get('valid_until'))
        for u in r.get('target_analysis_unit_ids',[])}
    unit_by_id={u['analysis_unit_id']:u for u in units}
    decisions=[]
    for version in versions:
        old=version.get('prior_analysis_unit_id')
        new=unit_by_id[version['new_analysis_unit_id']]
        when=revision_day(version)
        if len(when)<10:continue
        if old and old not in retired_units:
            decisions.append({'status_id':'revision-'+old,'target_analysis_unit_ids':[old],
                'kind':'superseded','valid_until':when,
                'replacement_analysis_unit_ids':[version['new_analysis_unit_id']],
                'source_canonical':new['canonical'],'reason':version.get('basis') or 'Later observed revision of the same work.',
                'observed_at':version.get('observed_at',''),'reviewer_type':'recorded version relation'})
        decisions.append({'status_id':'edition-start-'+new['analysis_unit_id'],
            'target_analysis_unit_ids':[new['analysis_unit_id']],'kind':'effective_window','valid_from':when,
            'source_canonical':new['canonical'],'reason':'This edition is known from the explicit revision date, or conservatively from its observation day; the original work publication date does not date this revision.',
            'observed_at':version.get('observed_at',''),'reviewer_type':'recorded version relation'})
    return decisions


def index_inputs():
    for attr,name in [('ANALYSIS_UNITS','analysis-units.jsonl.gz'),('ATOMIC_CLAIMS','atomic-claims.jsonl.gz'),
        ('ATTRIBUTION_AUDIT','claim-attribution-audit.jsonl.gz'),('EQUIVALENCE_COMPONENTS','claim-equivalence-components.jsonl'),
        ('PASSAGES','passages.jsonl.gz'),('SYNTHESIS_EVIDENCE','synthesis-evidence.jsonl'),('THEME_MEMBERSHIP','theme-membership.jsonl.gz')]:
        setattr(indexer,attr,DATA/name)
    indexer.INPUTS=(indexer.ANALYSIS_UNITS,indexer.ATOMIC_CLAIMS,indexer.ATTRIBUTION_AUDIT,indexer.EQUIVALENCE_COMPONENTS,
                   indexer.PASSAGES,indexer.SYNTHESIS_EVIDENCE,indexer.THEME_MEMBERSHIP)


SUPPLEMENTS={
 'alignment-as-hidden-behavior':('新增事故复盘更正了七月的初步机制解释；接受失败和未经请求行动的评测仍须保留具体任务、轨迹与重采样条件，不能推断模型具有稳定恶意目标。',['alignment-assessment','unintended']),
 'capability-scaling-under-uncertainty':('新增模型卡和个人文章扩展了能力、加速与安全措施之间的讨论。Dario 与 Jack 的时间线判断保留作者归属；不同模型卡的任务与重跑样本不能直接拼成趋势。',['claude-opus-5-5','claude-sonnet-5-5','claude-haiku-5-5','darioamodei.com','importai']),
 'capability-triggered-governance':('治理材料增加了 Cyber Verification Program 与新的政策公告。公告日、生效日和旧目标归档日分开处理；已归档目标不能证明任务完成，新 Usage Policy 到十一月十二日才生效。',['cyber-verification','usage-policy','responsible-scaling-policy']),
 'disciplined-agent-engineering':('新材料强调任务分解、上下文、委派与检查；模型演示、系统提示和客户引文保留为来源材料，并排除出机构立场抽取。工程实现与供应商能力说明的验证层级分别记录。',['claude-code','agent','claude-opus-5-5']),
 'economic-transition-and-distribution':('新增经济与科学应用材料补充了采用、任务分布与潜在影响；观察期、情景假设和样本范围保留，产品使用比例与情景推演不被改写为已经发生的就业或生产率结果。',['economic','science']),
 'human-agency-values-and-welfare':('本轮继续保留人类能动性和模型心理归因的边界：事故轨迹中的自述、实验中的失败接受行为与个人预测各自保留条件，不互相替代为心理状态或普遍能力的证明。',['alignment-assessment','unintended','failure']),
 'measurement-and-adaptive-evaluation':('新增 RL 评测审计与完整模型卡，补充了奖励投机、审计器可靠性和评测局限。跨卡重跑、样本规模、置信区间及独立任务分别解释，低分或高审计通过率不能独立证明总体安全。',['auditor','reinforcement','claude-opus-5-5','claude-sonnet-5-5','claude-haiku-5-5']),
 'mechanistic-legibility':('补录的历史研究和系统卡扩大了机制与行为证据的可检索范围；本轮没有把这些历史补录标为九月以后才出现的新发现，也不把行为成绩自动解释为已理解内部机制。',['interpret','alignment','system-card']),
 'security-and-defense-in-depth':('新增事故复盘、模型卡及可信访问材料进一步区分了实际事件、受控沙箱和访问政策。事故纠错逐条退出现行解释；网络风险数值须连同任务、运行次数与访问条件读取。',['alignment-assessment','cyber-verification','claude-opus-5-5','claude-sonnet-5-5','claude-haiku-5-5']),
}


def update_synthesis_metadata(units,claims,audits):
    """Recount the full corpus; preserve v1 theses and human calibration rows."""
    unit_by_id={u['analysis_unit_id']:u for u in units}
    claim_by_id={c['claim_id']:c for c in claims}
    memberships=rows(DATA/'theme-membership.jsonl.gz')
    themes=rows(BASE/'data/theme-catalog.jsonl')
    new_ids={c['claim_id'] for c in rows(RELEASE/'delta/atomic-claims.jsonl.gz')}
    direct_ids={a['claim_id'] for a in audits if a['synthesis_disposition']=='eligible_for_source_level_synthesis'}
    for t in themes:
        matched=[m for m in memberships if t['theme_id'] in m['theme_ids']]
        direct=[m for m in matched if m['claim_id'] in direct_ids]
        ids={m['analysis_unit_id'] for m in matched}
        bands=Counter()
        for uid in ids:
            match=re.search(r'\b(?:19|20)\d{2}\b',unit_by_id[uid].get('published_at',''))
            year=int(match.group()) if match else None
            bands['undated' if year is None else 'through_2018' if year<=2018 else '2019_2022' if year<=2022 else '2023_2024' if year<=2024 else '2025_2026']+=1
        t.update(count_scope=RELEASE_ID,matched_claim_count=len(matched),matched_analysis_unit_count=len(ids),
                 direct_synthesis_claim_count=len(direct),analysis_units_by_time_band=dict(sorted(bands.items())),
                 direct_claims_by_voice_type=dict(sorted(Counter(claim_by_id[m['claim_id']]['voice']['voice_type'] for m in direct).items())))
        text,needles=SUPPLEMENTS[t['theme_id']]
        candidates=[m for m in direct if m['claim_id'] in new_ids and any(n in unit_by_id[m['analysis_unit_id']]['canonical'] for n in needles)]
        chosen=[];works=set()
        for m in candidates:
            u=unit_by_id[m['analysis_unit_id']]
            if u['work_id'] in works:continue
            works.add(u['work_id']);chosen.append(m['claim_id'])
            if len(chosen)==4:break
        t.update(current_supplement_zh=text,supplement_as_of='2026-10-18',supplement_review='AI synthesis; not human Gold',supplement_claim_ids=chosen,
                 coverage_count_interpretation='all retained historical and current claims; current eligibility is applied during retrieval')
    write_rows(DATA/'theme-catalog.jsonl',themes)
    voices=rows(BASE/'data/voice-profiles.jsonl')
    voice_notes={
      'anthropic-institution':'新增模型卡、事故纠错、治理与经济材料。机构材料、具名客座文章、客户引文和模型示例保持分离；三项新模型的卡片条件不合并为统一安全排名。',
      'dario-amodei':'新增九月关于能力进展与安全节奏的个人文章；原网页仅标月份，不制造具体发布日期，也不将个人判断升级为机构共识。',
      'jack-clark':'新增 Import AI 473–476；个人时间线和评论保留作者归属，不能按篇幅密度加权成机构立场。',
      'amanda-askell':'本轮未建立新的独立人物观点结论；原有画像作为历史校准保留，条目计数以全量索引重算。',
      'chris-olah':'本轮新增补录不自动扩写个人立场；原有画像保留，研究文档的编辑口径不自动归给个人。',
    }
    for v in voices:
        direct=[c for c in claims if c['claim_id'] in direct_ids and c['voice']['name']==v['name']]
        v.update(direct_claim_count=len(direct),analysis_unit_count=len({c['evidence'][0]['analysis_unit_id'] for c in direct}),
          count_scope=RELEASE_ID,current_supplement_zh=voice_notes[v['voice_id']],supplement_as_of='2026-10-18',
          supplement_review='AI synthesis; not human Gold',supplement_claim_ids=[c['claim_id'] for c in direct if c['claim_id'] in new_ids][:4])
    write_rows(DATA/'voice-profiles.jsonl',voices)


def package():
    units=rows(DATA/'analysis-units.jsonl.gz');claims=rows(DATA/'atomic-claims.jsonl.gz')
    passages=rows(DATA/'passages.jsonl.gz');audits=rows(DATA/'claim-attribution-audit.jsonl.gz')
    update_synthesis_metadata(units,claims,audits)
    counts={'analysis_units':len(units),'atomic_claims':len(claims),'passages':len(passages),'reviewed_kernel_claims':54,
            'equivalence_components':len(rows(DATA/'claim-equivalence-components.jsonl')),
            'new_units':len(rows(RELEASE/'delta/analysis-units.jsonl.gz')),
            'new_claims':len(rows(RELEASE/'delta/atomic-claims.jsonl.gz')),
            'new_passages':len(rows(RELEASE/'delta/passages.jsonl.gz'))}
    versions=rows(BASE/'delta/version-relations.jsonl')
    new_versions=RELEASE/'delta/version-relations.jsonl'
    if new_versions.exists():versions+=rows(new_versions)
    index_inputs()
    temporary=SKILL/'amind-refresh-building.sqlite3'
    if temporary.exists():temporary.unlink()
    indexer.build_index_file(temporary,release_id=RELEASE_ID,expected=counts,version_relations=versions)
    temporary.replace(SKILL/'amind-full-index.sqlite3')
    for name in ['passages.jsonl.gz','theme-catalog.jsonl','voice-profiles.jsonl']:
        shutil.copyfile(DATA/name,SKILL/name)
    statuses=rows(RELEASE/'delta/current-status.jsonl')
    statuses+=publication_windows(units)
    # Earlier same-work revisions are dated as well; a historical as-of query
    # must not suppress a document merely because it was revised later.
    statuses+=revision_windows(units,versions,statuses)
    write_rows(DATA/'current-status.jsonl',statuses);write_rows(SKILL/'current-status.jsonl',statuses)
    manifest=json.loads((SKILL/'manifest.json').read_text())
    manifest.update(release_id=RELEASE_ID,skill_version='1.3.1',base_release_id='amind-v1',
        previous_release_id=BASE.name,source_observation_cutoff='2026-10-18',incremental_batch_id='2026-10-18',
        current_status_bundled=True,current_status_scope='dated known corrections and effective windows; historical evidence retained')
    collection=json.loads((RELEASE/'audits/collection-summary.json').read_text())
    discovery=json.loads((RELEASE/'audits/discovery-summary.json').read_text())
    manifest['source_observation_completed_at']=collection['completed_at']
    manifest['source_coverage']={'configured_entry_points':discovery['configured_sources'],
        'failed_entry_points':discovery['failed_sources'],'body_captures':collection['captured'],
        'failed_selected_bodies':len(collection['failed']),
        'scope':'configured public entry points and selected source bodies; no assertion of complete internet or spoken-interview coverage'}
    c=manifest['counts']
    c.update(full_index_analysis_units=len(units),full_index_atomic_claims=len(claims),full_index_passages=len(passages),
        full_release_analysis_units=len(units),full_release_atomic_claims=len(claims),
        full_index_equivalence_components=counts['equivalence_components'],
        full_index_direct_claims=sum(a['synthesis_disposition']=='eligible_for_source_level_synthesis' for a in audits),
        current_status_decisions=len(statuses))
    artifacts=[]
    old_artifacts={a['path']:a for a in manifest['artifacts']}
    for name in ['amind-full-index.sqlite3','evidence-kernel.jsonl','passages.jsonl.gz','synthesis-tensions.jsonl',
                 'theme-catalog.jsonl','voice-profiles.jsonl','current-status.jsonl']:
        p=SKILL/name
        count=len(claims) if name.endswith('.sqlite3') else len(passages) if name=='passages.jsonl.gz' else len(rows(p))
        artifacts.append({'path':name,'format':'sqlite3-fts5' if name.endswith('.sqlite3') else 'jsonl-gzip' if name.endswith('.gz') else 'jsonl',
            'bytes':p.stat().st_size,'sha256':sha(p),'rows':count,
            'schema_name':old_artifacts.get(name,{}).get('schema_name','amind-current-status-decision')})
    manifest['artifacts']=artifacts
    manifest['sources']=[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in sorted(DATA.iterdir()) if p.is_file()]
    manifest['incremental_boundary']={'raw_baseline_unchanged':True,'new_human_reviewed_gold_rows':0,
        'new_claims_review':'machine checked; selected claims additionally reviewed in context by AI',
        'complete_web_coverage_claimed':False,'recurring_update_configured':False,
        'report':f'release/{RELEASE_ID}/reports/update.zh-CN.md'}
    write(SKILL/'manifest.json',manifest)
    frozen=ROOT/'.codex-tmp/pre-refresh-baseline.json'
    if frozen.exists():write(RELEASE/'audits/frozen-history.json',json.loads(frozen.read_text()))
    release_manifest=json.loads((RELEASE/'manifest.json').read_text()) if (RELEASE/'manifest.json').exists() else {}
    release_manifest.update(schema_name='amind-increment-release',schema_version=1,release_id=RELEASE_ID,
        base_release_id=BASE.name,source_observation_cutoff='2026-10-18',timezone='Asia/Singapore',
        counts=counts,review_boundary=manifest['incremental_boundary'],skill_manifest_sha256=sha(SKILL/'manifest.json'))
    release_manifest['artifacts']=[{'path':p.relative_to(RELEASE).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
        for p in sorted(RELEASE.rglob('*')) if p.is_file() and p!=RELEASE/'manifest.json']
    write(RELEASE/'manifest.json',release_manifest)
    print(json.dumps(counts,ensure_ascii=False,indent=2))
    return counts


if __name__=='__main__':package()
