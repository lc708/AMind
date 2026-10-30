#!/usr/bin/env python3
"""Refresh from a portable, immutable release; no historical private vault required.

Discovery and capture are explicit network stages. Build/review/package replay the
retained bytes. A failed source never advances its source checkpoint. The package
retains every baseline row and separates publication, observation and eligibility.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import copy
import difflib
import gzip
import json
from pathlib import Path
import re
import shutil
import sys
import urllib.parse
import xml.etree.ElementTree as ET

import refresh_amind_sources as old
import package_amind_refresh as packaging
import build_amind_skill_index as indexer

ROOT = Path(__file__).resolve().parents[1]
rows, put, putrows, sha, jb, normalize = old.rows, old.put, old.putrows, old.sha, old.jb, old.normalize


def extract_article(raw, url):
    """Use source article boundaries, excluding recommendations and site chrome."""
    dom = old.DOM(); dom.feed(raw.decode('utf-8', errors='replace'))
    nodes = list(dom.root.walk())
    article = next((n for n in nodes if n.tag == 'article'), None)
    extracted = old.extract_html(raw, url)
    # The first date in prose can describe an old event or a recommendation.
    # Only explicit publication metadata/bylines establish a publication day.
    evidence=[x for x in extracted['date_evidence'] if x['kind']!='visible_initial_date']
    extracted['published_at']=next((old.parse_date(x['value']) for x in evidence
        if x['kind'] not in {'visible_month_only; exact day unavailable'} and old.parse_date(x['value'])), '')
    extracted['date_evidence']=evidence
    for node in nodes:
        if node.tag=='time' and node.attrs.get('datetime') and node.attrs.get('itemprop')=='datePublished':
            value=node.attrs['datetime'];date=old.parse_date(value)
            if date and not extracted['published_at']:
                extracted['published_at']=date
                extracted['date_evidence'].append({'kind':'native publication time element','value':value})
    # Claude resources place the byline before the article node. Retain metadata
    # from the full page, but render only the actual article for its claim body.
    if article is not None:
        def serialize(n):
            if isinstance(n, str): return old.html.escape(n)
            attrs = ''.join(' '+k+'="'+old.html.escape(v or '', quote=True)+'"' for k,v in n.attrs.items())
            return '<'+n.tag+attrs+'>'+''.join(serialize(c) for c in n.children)+'</'+n.tag+'>'
        body = old.extract_html(('<main>'+serialize(article)+'</main>').encode(), url)
        if len(body['text']) > 150:
            extracted['text'] = body['text']
            extracted['body_links'] = body['body_links']
    text = extracted['text']
    if urllib.parse.urlsplit(url).hostname=='jack-clark.net':
        heading=re.search(r'(?m)^#{1,6}\s+(Import AI \d+:[^\n]+)',text)
        if heading:extracted['title']=heading.group(1).strip()
    if not extracted['authors']:
        byline=re.search(r'(?m)^\s*-\s*Author\s*([^\n]+)',text)
        if byline:extracted['authors']=[byline.group(1).strip()]
    # Recommendation cards are outside the source's argument even when included
    # in a CMS main element. These are exact heading boundaries, not keywords.
    text = re.split(r'(?im)^#{1,4}\s+(?:Related articles|Explore more|Get the developer newsletter|Transform how your organization operates with Claude)\s*$', text)[0].strip()
    extracted['text'] = text
    extracted['extractor'] = 'stdlib-article-markdown-v2'
    return extracted


def validate_baseline(root, baseline):
    manifest = json.loads((baseline/'manifest.json').read_text())
    if manifest.get('release_id') != baseline.name:
        raise ValueError('baseline release identity mismatch')
    for a in manifest['artifacts']:
        candidate=baseline/a['path'];p=candidate.resolve()
        chain=[candidate]+[parent for parent in candidate.parents if parent!=baseline.parent and parent.is_relative_to(baseline)]
        if not p.is_relative_to(baseline.resolve()) or not p.is_file() or any(part.is_symlink() for part in chain):
            raise ValueError('invalid baseline artifact: '+a['path'])
        if p.stat().st_size != a['bytes'] or sha(p.read_bytes()) != a['sha256']:
            raise ValueError('baseline fingerprint mismatch: '+a['path'])
    units = rows(baseline/'data/analysis-units.jsonl.gz')
    if not units: raise ValueError('baseline has no analysis units')
    return units


class Snapshot(old.Refresh):
    def __init__(self, args):
        self.a=args; self.date=args.date; self.base=(ROOT/args.baseline).resolve()
        self.release=(ROOT/args.release).resolve()
        if self.release == self.base or self.release.parent != (ROOT/'release').resolve():
            raise ValueError('new release must be a distinct direct child of release/, never inside a frozen snapshot')
        self.oldunits=validate_baseline(ROOT,self.base)
        if any(p.is_symlink() for p in self.release.rglob('*')):
            raise ValueError('owned release cannot contain symbolic links to markers or output artifacts')
        marker=self.release/'audits/refresh-run.json'
        identity={'schema_name':'amind-refresh-run','release_id':self.release.name,'date':self.date,'base_release_id':self.base.name}
        if self.release.exists() and any(self.release.iterdir()):
            if not marker.is_file() or json.loads(marker.read_text())!=identity:
                raise ValueError('existing release is not owned by this refresh run; published snapshots are immutable')
        else:put(marker,identity)
        self.oldby={normalize(u['canonical']):u for u in sorted(self.oldunits,key=lambda u:u.get('observed_at',''))}
        self.oldtitle=collections.defaultdict(list)
        for u in self.oldunits: self.oldtitle[re.sub(r'\W+','',u['title'].casefold())].append(u)
        self.oldraw={u['raw_sha256']:u for u in self.oldunits if u.get('raw_sha256')}
        self.known=set(self.oldby); self.vault=None
        self.sources=self.release/'sources'; self.cache=self.sources/'requests'
        self.extractor_version='amind-portable-refresh-2'
        self.preserve()

    def require_comparison_vault(self):
        # The complete previous release and its bound raw/text are the comparison
        # input. Missing individual historic captures are explicit, not invented.
        return validate_baseline(ROOT,self.base)

    def preserve(self):
        destination=self.release/'audits/frozen-history.json'
        if destination.exists():
            fingerprints=json.loads(destination.read_text())
            for relative,digest in fingerprints.items():
                if sha((ROOT/relative).read_bytes()) != digest:
                    raise ValueError('frozen release changed: '+relative)
        else:
            fingerprints={str(p.relative_to(ROOT)):sha(p.read_bytes())
                for directory in (ROOT/'release').iterdir() if directory.is_dir() and directory.resolve()!=self.release
                for p in directory.rglob('*') if p.is_file()}
            put(destination,fingerprints)

    def configured(self):
        sources=json.loads((self.base/'audits/configured-sources.json').read_text())
        for s in sources:
            if s['id']=='claude-blog-index': s['url']='https://claude.com/resources/articles'
            if s['id']=='anthropic-economic-research-team-index': s['url']='https://www.anthropic.com/research/team/economics'
        extra=[
            ('claude-resources-home','https://claude.com/resources'),
            ('claude-developer-blog','https://claude.dev/'),
            ('anthropic-science-team','https://www.anthropic.com/research/team/science'),
            ('anthropic-notebook-current','https://notebook.anthropic.com/'),
        ]
        known={s['id'] for s in sources}
        sources += [{'id':i,'url':u,'method':'index','publisher':'Anthropic','lane':'main'} for i,u in extra if i not in known]
        return sources

    def discover(self):
        super().discover()
        # Retain native article dates on index links. A lastmod is never used as
        # a publication date. Explicit analysis seeds remain the minimum scope.
        ledger={}
        previous=self.base/'audits/source-checkpoints.json'
        if previous.exists(): ledger=json.loads(previous.read_text())
        for s in self.configured():
            requests=[r for r in rows(self.release/'audits/source-fetches.jsonl') if r.get('source_id')==s['id']]
            state={'last_attempt_at':max((r.get('completed_at','') for r in requests),default=''),
                'status':'captured' if requests and all(r.get('ok') for r in requests) else 'failed_or_unobserved',
                'previous_success_at':ledger.get(s['id'],{}).get('last_success_at','')}
            state['discovery_success_at']=state['last_attempt_at'] if state['status']=='captured' else ''
            state['last_success_at']=state['previous_success_at']
            state['checkpoint_scope']='ingestion checkpoint advances only after complete source-bound capture, build and verification'
            state['discovery_method']=s.get('method','unknown')
            ledger[s['id']]=state
        put(self.release/'audits/source-checkpoints.json',ledger)

    def select(self):
        seeds=json.loads((ROOT/self.a.seeds).read_text())
        selected={normalize(s['url']):dict(s,selection_reason=s.get('selection_reason','analysis-reviewed source')) for s in seeds}
        decisions=[]
        allowed={'anthropic.com','claude.com','claude.dev','alignment.anthropic.com','transformer-circuits.pub','jack-clark.net'}
        for r in rows(self.release/'audits/discovery.jsonl'):
            u=normalize(r['url']);s=urllib.parse.urlsplit(u);path=s.path
            translation=path.split('/')[1].lower() in {'ja','de','es','fr','ko','zh','zh-cn','zh-tw','pt','it','id','ru'}
            reason=''
            recent=old.parse_date(r.get('lastmod','')) >= self.a.since[:10] if r.get('lastmod') else False
            if not translation and s.hostname in allowed:
                if s.hostname=='claude.dev' and path.startswith('/blog/') and u not in self.known:
                    reason='developer-blog historical omission; native publication date checked after capture'
                elif u not in self.known and recent and path.startswith(('/news/','/research/','/engineering/','/resources/articles/','/2026/')):
                    reason='recent source candidate; sitemap/feed date is discovery metadata only'
            if path.startswith('/research/team/'):
                reason=''
            disposition='excluded_translation_alias' if translation else 'not_selected_no_new_publication_signal'
            if reason:
                if len(selected)<self.a.max_candidates: selected.setdefault(u,{**r,'url':r['url'],'selection_reason':reason})
                else: disposition='not_fetched_candidate_limit'
            if u in selected: disposition='selected_body_capture'
            decisions.append({**r,'disposition':disposition,'reason':reason or 'Explicit scope or no qualifying new/recent article signal'})
        putrows(self.release/'audits/discovery-decisions.jsonl',decisions)
        putrows(self.release/'audits/collection-queue.jsonl',list(selected.values()))
        return list(selected.values())

    def collect(self):
        queue=self.select()
        def one(item):
            raw,request=self.request(item['url']);record={**item,**request,'record_id':old.sid('am-refresh-',normalize(item['url']),16)}
            if request.get('ok'):
                try:
                    if raw.startswith(b'%PDF'):
                        import pymupdf as fitz
                        doc=fitz.open(stream=raw,filetype='pdf')
                        text='\n\n'.join('## Page '+str(i+1)+'\n\n'+'\n\n'.join(re.sub(r'\s+',' ',x[4]).strip() for x in page.get_text('blocks',sort=True) if x[6]==0) for i,page in enumerate(doc))
                        e={'title':doc.metadata.get('title',''),'authors':[],'published_at':'','modified_at':'','date_evidence':[],'body_links':[],'text':text,'pages':len(doc),'extractor':'pymupdf-blocks-v1'}
                    else:e=extract_article(raw,request.get('final_url',item['url']))
                    canonical=normalize(e.get('declared_canonical_url') or request.get('final_url',item['url']))
                    record['canonical_url']=canonical
                    if item.get('publication_date'):
                        if e.get('published_at') and e['published_at'][:10]!=item['publication_date']:
                            raise ValueError('seed and native publication date disagree')
                        e['published_at']=item['publication_date']
                        e['date_evidence'].append({'kind':'AI-reviewed primary source date','value':item['publication_date'],'source':item.get('date_source',item['url'])})
                    if item.get('publication_unknown'):
                        e['date_evidence'].append({'kind':'publication day unconfirmed; retained native status/update dates','value':e.get('published_at','')})
                        e['published_at']=''
                    if item.get('title'):
                        if re.sub(r'\W+','',item['title'].casefold()) not in re.sub(r'\W+','',e['text'].casefold()):
                            raise ValueError('reviewed title not present in native body')
                        e['title']=item['title']
                    if item.get('authors'):
                        e['authors']=item['authors']
                        e['author_evidence']={'kind':'AI-reviewed native byline','value':item['authors'],'source':item['url']}
                    text=e.pop('text');textpath=Path('sources/texts')/(sha(text.encode())+'.md');put(self.release/textpath,text.encode())
                    record['extracted']={**e,'body_sha256':sha(text.encode()),'text_path':str(textpath)}
                except Exception as error:record['extraction_error']=str(error)
            put(self.sources/'records'/(record['record_id']+'.json'),record)
            return record
        with concurrent.futures.ThreadPoolExecutor(self.a.workers) as pool:records=list(pool.map(one,queue))
        attachments={}
        for r in records:
            for link in r.get('extracted',{}).get('body_links',[]):
                url=link['url'];host=(urllib.parse.urlsplit(url).hostname or '')
                if '.pdf' in url.lower() and (host.endswith('anthropic.com') or host=='cdn.sanity.io'):
                    attachments.setdefault(normalize(url),{'url':url,'parent_url':r['url'],'selection_reason':'explicit primary-source PDF attachment','publication_unknown':True})
        already={normalize(r['url']) for r in records}
        todo=[v for k,v in attachments.items() if k not in already]
        with concurrent.futures.ThreadPoolExecutor(min(4,self.a.workers)) as pool:records+=list(pool.map(one,todo))
        failures=[{'url':r['url'],'error':r.get('error') or r.get('extraction_error')} for r in records if not r.get('extracted')]
        summary={'selected_urls':len(queue),'attachment_urls':len(todo),'captured':sum(bool(r.get('ok')) for r in records),'bodies':sum(bool(r.get('extracted')) for r in records),'failed':failures,'completed_at':max(r['completed_at'] for r in records)}
        retained=[json.loads(p.read_text()) for p in (self.sources/'records').glob('*.json')]
        summary.update(retained_capture_records=len(retained),retained_metadata_only_records=sum(
            urllib.parse.urlsplit(r.get('canonical_url') or r['url']).path.startswith('/research/team/') for r in retained),
            record_inventory_scope='selected source URLs and their PDF attachments; prior candidate captures remain in the record inventory, including excluded team navigation')
        put(self.release/'audits/collection-summary.json',summary)
        print(json.dumps(summary),flush=True)

    def old_derivative(self,unit):
        path=ROOT/unit.get('text_path','')
        if path.is_file():
            data=path.read_bytes()
            if sha(data)!=unit['text_file_sha256']: raise ValueError('prior derivative fingerprint mismatch')
            return data.decode()
        return None

    def additional_artifact_ranges(self,unit,text):
        if unit['canonical'].endswith('/a9ceec76a54d28d27affffcdab6faf7c142cd587.pdf'):
            end=text.find('## Page 2\n')
            if end>0:return [(0,end,'Public Benefit Report table of contents; objective summaries are navigation, not achieved facts')]
        return []

    def migration_alias(self,candidates,canonical,text):
        for candidate in candidates:
            request_path=self.cache/(sha(candidate['canonical'].encode())+'.json')
            if not request_path.is_file():continue
            request=json.loads(request_path.read_text())
            if not request.get('ok'):continue
            raw=gzip.decompress((self.release/request['raw_path']).read_bytes())
            if sha(raw)!=request['raw_sha256']:raise ValueError('alias capture fingerprint mismatch')
            extracted=extract_article(raw,request.get('final_url',candidate['canonical']))
            identity=normalize(extracted.get('declared_canonical_url') or request.get('final_url',candidate['canonical']))
            if identity==normalize(canonical) and old.body_equal(extracted['text'],text):
                return {'analysis_unit_id':candidate['analysis_unit_id'],'requested_url':candidate['canonical'],
                    'canonical':identity,'raw_sha256':request['raw_sha256'],'body_sha256':sha(extracted['text'].encode()),
                    'basis':'original carrier now declares/redirects to the same canonical and identical current body; frozen edition is retained without duplicating the work'}
        return None

    def build(self):
        self.preserve();units=[];passages=[];decisions=[];versions=[];texts={};seen={}
        records=[json.loads(p.read_text()) for p in sorted((self.sources/'records').glob('*.json'))]
        records.sort(key=lambda r:(bool(r.get('parent_url')),r['url']))
        editorial={r['record_id']:r for r in rows(self.release/'audits/reviewed-body-decisions.jsonl')}
        for r in records:
            e=r.get('extracted');canonical=r.get('canonical_url') or normalize(r['url'])
            prior=self.oldby.get(normalize(canonical)) or self.oldby.get(normalize(r['url']))
            d={'record_id':r['record_id'],'url':r['url'],'canonical':canonical,'raw_sha256':r.get('raw_sha256'),'observed_at':r.get('completed_at'),'prior_analysis_unit_id':prior['analysis_unit_id'] if prior else None,'selection_reason':r['selection_reason']}
            if urllib.parse.urlsplit(canonical).path.startswith('/research/team/'):
                decisions.append({**d,'disposition':'metadata_only','reason':'team navigation registry; individual source bodies are indexed separately'});continue
            if not e:
                decisions.append({**d,'disposition':'unavailable','reason':r.get('error') or r.get('extraction_error')});continue
            text=(self.release/e['text_path']).read_text();digest=e['body_sha256'];pub=e.get('published_at','')
            reviewed=editorial.get(r['record_id'])
            if reviewed and reviewed['raw_sha256']==r['raw_sha256']:
                if not prior or reviewed['prior_analysis_unit_id']!=prior['analysis_unit_id']:
                    raise ValueError('editorial review no longer binds the prior source')
                decisions.append({**d,**reviewed});continue
            if pub and pub[:10]>self.date:
                decisions.append({**d,'disposition':'future_publication','reason':'native publication follows collection cutoff'});continue
            if len(text)<150:
                decisions.append({**d,'disposition':'metadata_only','reason':'no substantive body'});continue
            if digest in seen:
                decisions.append({**d,'disposition':'duplicate_carrier','equivalent_analysis_unit_id':seen[digest]});continue
            # A redirected URL can name an existing work under its new path.
            if not prior:
                prior=next((u for u in self.oldunits if u['title'].casefold()==e['title'].casefold() and self.old_derivative(u) is not None and old.body_equal(self.old_derivative(u),text)),None)
                alias_candidates=[u for u in self.oldtitle.get(re.sub(r'\W+','',e['title'].casefold()),[])
                    if urllib.parse.urlsplit(normalize(u['canonical'])).hostname==urllib.parse.urlsplit(normalize(canonical)).hostname
                    and urllib.parse.urlsplit(normalize(u['canonical'])).path.rsplit('/',1)[-1]==urllib.parse.urlsplit(normalize(canonical)).path.rsplit('/',1)[-1]]
                if not prior and alias_candidates:
                    proof=self.migration_alias(alias_candidates,canonical,text)
                    decisions.append({**d,'disposition':'baseline_redirect_alias' if proof else 'possible_alias_comparison_unavailable',
                        'candidate_analysis_unit_ids':[u['analysis_unit_id'] for u in alias_candidates],'alias_proof':proof,
                        'reason':'same native title and terminal URL path under a migrated carrier; bound current carrier proof when available; historic assertions are not rewritten'});continue
            previous=self.old_derivative(prior) if prior else None
            if prior and (digest==prior['body_sha256'] or previous is not None and old.body_equal(previous,text)):
                decisions.append({**d,'disposition':'unchanged_body','equivalent_analysis_unit_id':prior['analysis_unit_id']});continue
            if prior and previous is None:
                # No invented same-renderer comparison for nonportable old raw.
                decisions.append({**d,'disposition':'comparison_unavailable','reason':'historic derivative unavailable; retain capture, require review before creating a revision'});continue
            if prior:
                put(self.release/'audits/body-diffs'/(r['record_id']+'.diff'),'\n'.join(difflib.unified_diff(previous.splitlines(),text.splitlines(),fromfile=prior['analysis_unit_id'],tofile=r['record_id'],n=3)).encode())
            work=prior['work_id'] if prior else old.sid('wrk-',normalize(canonical),32)
            edition=old.sid('edn-',work+'\0'+r['raw_sha256'],32)
            uid=old.sid('nuwa1804-unit-',work+'\0'+edition+'\0'+digest,20)
            authors=e.get('authors',[])
            if 'jack-clark.net' in canonical:authors=['Jack Clark']
            u={'schema_name':'nuwa-v1-analysis-unit','schema_version':1,'analysis_unit_id':uid,'work_id':work,'edition_id':edition,'title':e['title'] or canonical.rsplit('/',1)[-1],
                'authors':authors,'canonical':canonical,'published_at':pub,'publication_date_basis':'; '.join(str(x['kind'])+': '+str(x['value']) for x in e.get('date_evidence',[])) or 'unknown; observation is not publication',
                'observed_at':r['completed_at'],'modified_at':e.get('modified_at',''),'language':'en','unit_status':'body_primary','component_origin':'revised_work' if prior else 'new_work',
                'historical_role':{'status':'native author/editorial attribution; no inferred institutional consensus'},'source_seed_record_ids':[r['record_id']],
                'source_manifest_row_sha256':sha(jb(r)),'body_sha256':digest,'text_file_sha256':digest,'text_path':str((self.release/e['text_path']).relative_to(ROOT)),
                'selection_reason':r['selection_reason'],'raw_sha256':r['raw_sha256'],'extraction':{'native_extractor':e['extractor'],'pages':e.get('pages'),'date_evidence':e.get('date_evidence',[])},'batch_id':self.date}
            _,pp=old.atoms.segment_text(text,uid,digest,6000)
            for i,p in enumerate(pp):p.update(schema_name='nuwa-v1-passage',schema_version=1,analysis_unit_id=uid,work_id=work,edition_id=edition,source_seed_record_ids=u['source_seed_record_ids'],source_text_path=u['text_path'],source_text_file_sha256=digest,source_body_sha256=digest,previous_passage_id=pp[i-1]['passage_id'] if i else '',next_passage_id=pp[i+1]['passage_id'] if i+1<len(pp) else '')
            if prior:versions.append({'work_id':work,'prior_analysis_unit_id':prior['analysis_unit_id'],'new_analysis_unit_id':uid,'prior_edition_id':prior['edition_id'],'new_edition_id':edition,'observed_at':r['completed_at'],'relation':'later_observed_revision','eligibility_scope':'claim','basis':'source body changed; claim-level eligibility requires separate curation','historical_claims_retained':True})
            partition='revised_existing_work' if prior else 'period_publication' if pub and pub>self.a.since[:10] else 'cutoff_day_first_indexing' if pub==self.a.since[:10] else 'historical_backfill' if pub else 'undated_first_indexing'
            decisions.append({**d,'disposition':u['component_origin'],'publication_partition':partition,'analysis_unit_id':uid,'title':u['title'],'published_at':pub})
            units.append(u);passages.extend(pp);texts[uid]=text;seen[digest]=uid
        self.extract(units,passages,decisions,versions,texts)
        put(self.release/'audits/preparation-audit.json',{'analysis_units':len(units),'passages':len(passages),'publication_partitions':dict(collections.Counter(d.get('publication_partition') for d in decisions if d.get('analysis_unit_id'))),'source_dispositions':dict(collections.Counter(d['disposition'] for d in decisions))})

    def review(self):
        import curate_amind_october_30 as curation
        unreviewed=self.release/'delta/atomic-claims.jsonl.gz'
        put(self.release/'audits/curation-inputs'/(sha(unreviewed.read_bytes())+'.jsonl.gz'),unreviewed.read_bytes())
        result=curation.curate_release(self.release,self.base,apply=True)
        reviews=rows(self.release/'curation/claim-reviews.jsonl')
        claims=curation.apply_claim_reviews(rows(self.release/'delta/atomic-claims.jsonl.gz'),reviews,rows(self.release/'curation/source-scope-notes.jsonl'))
        audits=[old.auditor.claim_attribution(c,json.loads((ROOT/'config/nuwa-v1-claim-audit-policy.json').read_text())) for c in claims]
        cb={c['claim_id']:c for c in claims};ab={a['claim_id']:a for a in audits}
        members=rows(self.release/'delta/theme-membership.jsonl.gz')
        for m in members:
            a=ab[m['claim_id']];m.update(claim_row_sha256=sha(jb(cb[m['claim_id']])),attribution_class=a['attribution_class'],synthesis_disposition=a['synthesis_disposition'])
        for name,values in [('atomic-claims',claims),('claim-attribution-audit',audits),('theme-membership',members)]:
            putrows(self.release/'delta'/(name+'.jsonl.gz'),values)
            putrows(self.release/'data'/(name+'.jsonl.gz'),sorted(rows(self.base/'data'/(name+'.jsonl.gz'))+values,key=lambda r:r['claim_id']))
        putrows(self.release/'delta/context-reviews.jsonl',reviews)
        statuses=rows(self.release/'curation/current-status.jsonl')
        putrows(self.release/'delta/current-status.jsonl',statuses)
        putrows(self.release/'data/current-status.jsonl',statuses)
        print(json.dumps(result['audit'],default=str),flush=True)

    def commit_checkpoints(self):
        """Advance only after the exact package and selected bodies verify."""
        import verify_amind_snapshot
        verified=verify_amind_snapshot.verify(self.release,self.base,require_current=True)
        ledger=json.loads((self.release/'audits/source-checkpoints.json').read_text())
        queue=rows(self.release/'audits/collection-queue.jsonl')
        discovery={normalize(r['url']):r for r in rows(self.release/'audits/discovery.jsonl')}
        records={normalize(r['url']):r for p in (self.sources/'records').glob('*.json') for r in [json.loads(p.read_text())]}
        decisions={r['record_id']:r for r in rows(self.release/'delta/source-decisions.jsonl')}
        terminal={'new_work','revised_work','unchanged_body','duplicate_carrier','baseline_redirect_alias',
            'future_publication','metadata_only','editorial_or_template_change'}
        def resolved(record):
            return bool(record and record.get('extracted') and
                decisions.get(record.get('record_id'),{}).get('disposition') in terminal)
        unresolved=collections.defaultdict(list);counts=collections.Counter()
        for item in queue:
            key=normalize(item['url']);record=records.get(key);row=discovery.get(key,{})
            origins=row.get('sources',[]) or item.get('sources',[])
            for source_id in origins:
                counts[source_id]+=1
                if not resolved(record):
                    unresolved[source_id].append(item['url'])
                for child in records.values():
                    if child.get('parent_url')==item['url'] and not resolved(child):
                        unresolved[source_id].append(child['url'])
                # Expected links also catch a missing attachment record and a
                # shared PDF whose parent_url names a different source.
                for link in (record or {}).get('extracted',{}).get('body_links',[]):
                    url=link['url'];host=urllib.parse.urlsplit(url).hostname or ''
                    if '.pdf' in url.lower() and (host.endswith('anthropic.com') or host=='cdn.sanity.io'):
                        if not resolved(records.get(normalize(url))):unresolved[source_id].append(url)
        for item in rows(self.release/'audits/discovery-decisions.jsonl'):
            if item['disposition']=='not_fetched_candidate_limit':
                for source_id in item.get('sources',[]):unresolved[source_id].append(item['url'])
        completed=old.now()
        for source_id,state in ledger.items():
            state['selected_bodies']=counts[source_id];state['unresolved_selected_bodies']=sorted(set(unresolved[source_id]))
            if state.get('discovery_success_at') and not unresolved[source_id]:
                state['last_success_at']=completed;state['status']='ingestion_verified'
            else:state['status']='blocked_source_bodies' if unresolved[source_id] else 'static_seed_not_refreshed' if state.get('discovery_method')=='seed' else 'failed_discovery'
        put(self.release/'audits/source-checkpoints.json',ledger)
        put(self.release/'audits/checkpoint-verification.json',{'verified_before_checkpoint_commit':verified,
            'committed_at':completed,'advanced':sum(s['status']=='ingestion_verified' for s in ledger.values()),
            'not_advanced':{k:v['status'] for k,v in ledger.items() if v['status']!='ingestion_verified'}})
        return ledger


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['discover','collect','build','review','commit_checkpoints','all'])
    p.add_argument('--date',default='2026-10-30');p.add_argument('--since',default='2026-10-18')
    p.add_argument('--baseline',default='release/amind-v1-increment-2026-10-18')
    p.add_argument('--release',default='release/amind-v1-increment-2026-10-30')
    p.add_argument('--seeds',default='config/amind-refresh-2026-10-30-sources.json')
    p.add_argument('--workers',type=int,default=10);p.add_argument('--max-candidates',type=int,default=220)
    p.add_argument('--max-bytes',type=int,default=96*1024*1024);p.add_argument('--retry-failed',action='store_true')
    p.add_argument('--deps',action='append',default=[])
    a=p.parse_args()
    for directory in reversed(a.deps):sys.path.insert(0,directory)
    snap=Snapshot(a)
    for stage in ['discover','collect','build','review'] if a.stage=='all' else [a.stage]:getattr(snap,stage)()


if __name__=='__main__':main()
