#!/usr/bin/env python3
"""Score captured CLI evidence against the frozen source-bound rubric."""
import hashlib,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
def parsed(run):
 return [json.loads(line) for line in run['stdout'].splitlines() if line.startswith('{')]
def passage_text(rows):return '\n'.join(row.get('passage',{}).get('text','') for row in rows)
def status(rows):return rows[0].get('current_status',{}) if rows else {}
def judge(case,runs,gold_same):
 cid=case['id'];shows=[r for r in runs if r['argv'][2]=='show'];search=next((r for r in runs if r['argv'][2]=='search'),None)
 first=parsed(shows[0]) if shows else [];text=passage_text(first)
 supported=bool(first) and all(row.get('exact_quote') and row['exact_quote'] in row.get('passage',{}).get('text','') for row in first)
 successful=bool(shows) and shows[0]['returncode']==0 and supported
 if cid=='K01':return successful and first[0].get('voice',{}).get('name')=='Matthew Schwartz' and not first[0]['voice'].get('organization')
 if cid=='K02':return successful and all(v in text.lower() for v in ['reward-hacked','pairwise','benign targets','false positive'])
 if cid=='K03':return successful and 'limited publication rights' in text
 if cid=='K04':return successful and "do not represent Anthropic's plans" in text
 if cid=='K05':return successful and all(v in text for v in ['impossible','permitted actions','network boundaries'])
 if cid=='K06':return successful and all(v in text for v in ['fourteen times','seven times','re-run','95% CI']) and all(any('simulation' in c for c in row['conditions']) for row in first)
 if cid=='K07':return successful and first[0]['evidence_tier']=='full_release_machine_checked' and first[0]['synthesis_disposition']=='preserve_as_reported_position_not_source_belief'
 if cid=='K08':return bool(shows and shows[0]['returncode']==1 and search and all('/system-prompts/' not in row.get('source_canonical','') for row in parsed(search)))
 if cid=='T01':return successful and status(first).get('eligible') is False and 'corrected' in status(first).get('reasons',[])
 if cid=='T02':
  rows=parsed(shows[-1]);return successful and shows[-1]['returncode']==0 and status(rows).get('as_of')=='2026-09-08' and status(rows).get('eligible') is True
 if cid=='T03':return successful and first[0]['source_published_at']=='2026-10-08' and 'November 12' in text and status(first).get('eligible') is True
 if cid=='T04':
  a,b=parsed(shows[-2]),parsed(shows[-1]);return successful and status(a).get('eligible') is False and 'not_yet_effective' in status(a).get('reasons',[]) and status(b).get('eligible') is True and status(b).get('verification_required') is True
 if cid=='T05':
  a,b=parsed(shows[-2]),parsed(shows[-1]);return successful and a and b and all(row.get('current_status',{}).get('eligible') is False for row in a) and all(row.get('current_status',{}).get('eligible') is True for row in b)
 if cid=='T06':return successful and status(parsed(shows[-1])).get('verification_required') is True
 if cid=='T07':return successful and status(first).get('publication_day_known') is False and not first[0]['source_published_at']
 if cid=='T08':return successful and status(first).get('eligible') is False and 'historical_only' in status(first).get('reasons',[])
 if cid=='C01':return successful and gold_same
 if cid=='C02':return gold_same and runs[0]['returncode']==0
 if cid in ['C03','C04']:return runs[0]['returncode']==1 and not parsed(runs[0])
 return False

def main():
 raw=[json.loads(l) for l in (OUT/'raw-cli.jsonl').read_text().splitlines()];cases=[json.loads(l) for l in (OUT/'cases.jsonl').read_text().splitlines()]
 old=ROOT/'.codex-tmp/contrast-2026-10-18/old/skills/amind/data/evidence-kernel.jsonl';new=ROOT/'.codex-tmp/contrast-2026-10-18/new/skills/amind/data/evidence-kernel.jsonl';gold_same=old.read_bytes()==new.read_bytes()
 exhibits={x['claim_id']:x for x in map(json.loads,(OUT/'native-exhibits.jsonl').read_text().splitlines())};scores=[];metrics={}
 for side in ['old','new']:
  R=[r for r in raw if r['side']==side];shown={};positive_hits=[]
  for r in R:
   if r['argv'][2]=='show' and r['returncode']==0:
    for row in parsed(r):shown[row['claim_id']]=row
  for c in cases:
   runs=[r for r in R if r['case_id']==c['id']];sr=next((r for r in runs if r['argv'][2]=='search'),None)
   # These three frozen rubrics explicitly expect exclusion, not retrieval.
   positive=bool(c['source_fragment']) and c['id'] not in ['K08','T04','T08']
   hit=bool(positive and sr and any(c['source_fragment'] in x.get('source_canonical','') for x in parsed(sr)))
   if positive:positive_hits.append(hit)
   scores.append({'side':side,'case_id':c['id'],'group':c['group'],'qualified':int(bool(judge(c,runs,gold_same))),'positive_source_retrieval_case':positive,'source_hit_at_20':hit if positive else None})
  mismatches=[cid for cid,x in shown.items() if cid in exhibits and (x['source_canonical']!=exhibits[cid]['source_canonical'] or x['passage_id']!=exhibits[cid]['evidence']['passage_id'])]
  metrics[side]={'qualified_by_group':{g:sum(x['qualified'] for x in scores if x['side']==side and x['group']==g) for g in ['accuracy','timeliness','control']},'unique_shown_claims':len(shown),'exact_quote_present_in_bound_passage':sum(bool(x.get('exact_quote')) and x['exact_quote'] in x.get('passage',{}).get('text','') for x in shown.values()),'citation_binding_mismatches':len(mismatches),'positive_source_recall_at_20':{'hits':sum(positive_hits),'tasks':len(positive_hits)},'cli_exitcodes':{str(code):sum(r['returncode']==code for r in R) for code in [0,1,2]}}
 metrics['gold_control']={'byte_identical':gold_same,'old_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'new_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'rows':len(old.read_text().splitlines())}
 (OUT/'case-scores.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False,sort_keys=True)+'\n' for x in scores));(OUT/'paired-scores.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2)+'\n');print(json.dumps(metrics,ensure_ascii=False))
if __name__=='__main__':main()
