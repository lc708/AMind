#!/usr/bin/env python3
"""Replayable, append-only AMind source refresh (no model calls).

Stages: discover, collect, build, review, all. Sources are public pages; raw responses,
native date evidence and normalized full text are retained content-addressed.
The standard library handles HTML/discovery; PyMuPDF is required only for PDFs.
Use --deps to expose a local optional Python package directory when necessary.
discover/build/all require an explicit --vault containing the old comparison
records and captures; the packaged query/index does not require this vault.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
import gzip
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import amind_refresh_atoms as atoms
import build_nuwa_v1_claim_audit as auditor

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0 AMindResearch/2026.10'
OFFICIAL = 'https://www.anthropic.com/'
SEEDS = [
 'research/alignment-assessment-cybersecurity-incidents',
 'research/intelligence-targeting-conventional-weapons-capabilities',
 'institute/measuring-pace-of-ai-development','news/accenture-embedded-evaluation',
 'news/life-sciences-verification-program','research/claude-uplifts-biomolecular-modeling',
 'claude-opus-5-5','news/claude-discovers-novel-enzyme-system','research/project-swap',
 'research/yes-claude-can-do-nine-loops','claude-sonnet-5-5',
 'research/glm-5-3-and-the-spread-of-advanced-cyber-capabilities',
 'research/your-thoughts-on-ai','research/what-work-can-robots-do',
 'research/claude-shaped-science','news/barclays-scales-claude','news/claude-frontier-academy',
 'news/cyber-verification-program','claude-haiku-5-5','news/2026-usage-policy-update',
 'news/genesis-mission-commitment','news/anthropic-cyber-mission','research/the-missing-map-of-the-sky',
 'research/launching-opt-in-vuln-finding-service-for-open-source',
 'research/investigating-unintended-model-actions','research/self-replicating-ai',
 'research/distillation-defenses','news/2026-us-midterms','news/singapore-office-opening',
 'news/an-update-on-independent-evaluators','research/designing-efficient-quantum-circuits',
 'research/ecdsa-curve-origins','research/ai-expectations-gap','research/employment-at-anthropic',
 'research/expectations-for-the-future','threat-intelligence-report-september-2026',
 'claude-opus-5-5-system-card','claude-sonnet-5-5-system-card','claude-haiku-5-5-system-card',
 'responsible-scaling-policy','responsible-scaling-policy/roadmap','responsible-scaling-policy/updates',
 'constitution','transparency','transparency/model-report','legal/aup',
 'institute/econ-scenarios','features/ebola-response','policy/infrastructure',
 'legal/supported-regions','legal/privacy','legal/non-user-privacy-policy',
 'legal/k12-addendum','legal/k12-dpa','legal/k12-terms','legal/startup-program-addendum',
 'legal/archive/22742366-2ef0-4c7a-a833-6523f10d3944','system-cards',
]
EXTRA = [
 'https://alignment.anthropic.com/2026/training-alignment-auditors/',
 'https://darioamodei.com/post/we-must-pace-the-frontier',
 'https://borischerny.com/management,/product/2026/09/19/I-am-often-wrong.html',
 'https://jack-clark.net/2026/09/21/import-ai-473-the-uss-superintelligence-strategy-human-brain-in-a-mouse-skull-and-machine-hermeneutics/',
 'https://jack-clark.net/2026/09/28/import-ai-474-platonic-mindspace-tpus-in-space-zhipu-starts-an-outer-rsi-loop/',
 'https://jack-clark.net/2026/10/05/import-ai-475-swarm-scaling-google-deepmind-watermarks-biology-and-the-ai-science-economy/',
 'https://jack-clark.net/2026/10/12/import-ai-476-creativity-and-rsi-worse-than-china-open-weight-models-ai-goes-to-space/',
 *['https://platform.claude.com/docs/en/release-notes/system-prompts/claude-'+m+'-5-5' for m in ('opus','sonnet','haiku')],
 'https://platform.claude.com/docs/en/about-claude/model-deprecations',
 'https://platform.claude.com/docs/en/about-claude/models/overview',
 'https://arxiv.org/abs/2610.03075',
]
DATES = {'institute/measuring-pace-of-ai-development':'2026-09-17',
 'claude-opus-5-5':'2026-09-22','claude-sonnet-5-5':'2026-09-28','claude-haiku-5-5':'2026-10-07',
 'claude-opus-5-5-system-card':'2026-09-22','claude-sonnet-5-5-system-card':'2026-09-28',
 'claude-haiku-5-5-system-card':'2026-10-07'}
LOCK = threading.Lock()
EDITORIAL_RAW_REVIEW = {
 "/news/AI-enabled-cyber-threats-mitre-attack": "415f7ab66af88e1e0718a349524624b93d95c011eb45b16b01d525a398183c94",
 "/news/anthropic-nec": "f13112a721d4cb204f568715c54d6192fc381ca766eed65840576360042bf72a",
 "/news/detecting-and-countering-malicious-uses-of-claude-march-2025": "3eac82a50ba0176d25d7809d4368bc8f9b008742a16295c654abe7910f26bda8",
 "/news/detecting-and-preventing-distillation-attacks": "b7cd99715b0a7ca748381dff56add5ac71d77007d98f950071d387ffb611aeff",
 "/news/detecting-countering-misuse-aug-2025": "24dd12fe88adca54ddfa9c9cb5ff43e7744f8b79983f75b981892b97ea38fa62",
 "/news/disrupting-AI-espionage": "06a70111ff2a871c9624e2a6fa1b83ad18f66f3682505bcaf92cece94c276835",
 "/news/offering-expanded-claude-access-across-all-three-branches-of-government": "1a0751e303778064e1caae6d98689d5e8f8b270ddb8620781ea4c72acca2f6ba",
 "/research/AI-fluency-index": "205ae8c6572a3b3f8f7dba92939c508054b49e445af717f6de77d46e80fa7137",
 "/research/impact-software-development": "5a5107da4d9437538280410e5914872473dfdc79be0acbfaf5e3e127e89ed08c",
 "/research/measuring-faithfulness-in-chain-of-thought-reasoning": "33385a0cd5e9c8b1ca03200f1fbab609dc16d1e3abcbf8ae607bc8d813dc162e"
}

class CompatibleRedirects(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  return super().redirect_request(req,fp,302 if code==308 else code,msg,headers,newurl)
 http_error_308=urllib.request.HTTPRedirectHandler.http_error_302

def sha(b): return hashlib.sha256(b).hexdigest()
def jb(x): return (json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n').encode()
def now(): return datetime.now(timezone.utc).isoformat()
def sid(prefix, material, length=24): return prefix+sha(material.encode())[:length]
def body_equal(a,b):return re.sub(r'\s+',' ',a).strip().casefold()==re.sub(r'\s+',' ',b).strip().casefold()
def put(p, x):
 p.parent.mkdir(parents=True, exist_ok=True); payload=x if isinstance(x,bytes) else jb(x)
 t=p.with_name(p.name+'.'+str(threading.get_ident())+'.tmp');t.write_bytes(payload);t.replace(p)
def rows(p):
 if not p.exists(): return []
 op=gzip.open if str(p).endswith('.gz') else open
 with op(p,'rt',encoding='utf-8') as f:return [json.loads(l) for l in f if l.strip()]
def putrows(p,x):
 b=b''.join(jb(a) for a in x);put(p,gzip.compress(b,mtime=0) if str(p).endswith('.gz') else b)
def normalize(u):
 s=urllib.parse.urlsplit(u);host=(s.hostname or '').lower().removeprefix('www.')
 path=re.sub('/+','/',s.path).rstrip('/') or '/'
 tracking={'fbclid','gclid','mc_cid','mc_eid','_hsenc','hss_channel','ref'}
 query=urllib.parse.urlencode([(k,v) for k,v in urllib.parse.parse_qsl(s.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in tracking],doseq=True)
 return urllib.parse.urlunsplit(('https',host,path,query, ''))
def parse_date(s):
 if not s:return ''
 try:return datetime.fromisoformat(s.replace('Z','+00:00')).date().isoformat()
 except ValueError:pass
 s=re.sub(r'(\d)(st|nd|rd|th)',r'\1',s)
 for fmt in ('%B %d, %Y','%b %d, %Y','%B %d %Y','%b %d %Y','%d %B %Y'):
  try:return datetime.strptime(s,fmt).date().isoformat()
  except ValueError:pass
 return ''

class ComparisonInputError(ValueError):
 """Missing historical inputs must not silently change source dispositions."""

class Node:
 def __init__(self,tag='',attrs=()):self.tag=tag;self.attrs=dict(attrs);self.children=[]
 def walk(self):
  yield self
  for c in self.children:
   if isinstance(c,Node):yield from c.walk()
 def text(self):return ''.join(c if isinstance(c,str) else c.text() for c in self.children)

class DOM(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root]
 def handle_starttag(self,t,a):
  n=Node(t,a);self.stack[-1].children.append(n)
  if t not in {'meta','link','br','hr','img','input','source','wbr','area','base','embed','param','track','col'}:self.stack.append(n)
 def handle_endtag(self,t):
  for i in range(len(self.stack)-1,0,-1):
   if self.stack[i].tag==t:self.stack=self.stack[:i];break
 def handle_data(self,s):self.stack[-1].children.append(s)

def extract_html(raw,url):
 d=DOM();d.feed(raw.decode('utf-8',errors='replace'));nodes=list(d.root.walk())
 title=next((n.text().strip() for n in nodes if n.tag=='h1'),'')
 title=title or next((n.text().strip() for n in nodes if n.tag=='title'),'')
 metadata=[];authors=[];published='';modified='';canonical=''
 for n in nodes:
  if n.tag=='link' and n.attrs.get('rel')=='canonical':canonical=urllib.parse.urljoin(url,n.attrs.get('href',''))
  if n.tag=='meta':
   k=n.attrs.get('property') or n.attrs.get('name','');v=n.attrs.get('content','')
   if k in {'article:published_time','date','datePublished','citation_publication_date'}:
    metadata.append({'kind':k,'value':v});published=published or parse_date(v)
   if k in {'article:modified_time','dateModified'}:modified=v
   if k in {'author','citation_author'} and v:authors.append(v)
  if n.tag=='script' and n.attrs.get('type')=='application/ld+json':
   try:
    obj=json.loads(n.text())
    def walk_json(o):
     if isinstance(o,dict):
      yield o
      for v in o.values():yield from walk_json(v)
     elif isinstance(o,list):
      for v in o:yield from walk_json(v)
    for o in walk_json(obj):
     if o.get('datePublished'):
      metadata.append({'kind':'jsonld.datePublished','value':o['datePublished']});published=published or parse_date(o['datePublished'])
     if o.get('dateModified'):modified=modified or o['dateModified']
   except (ValueError,TypeError):pass
  if n.attrs.get('data-published'):
   v=n.attrs['data-published'];metadata.append({'kind':'visible_byline.data-published','value':v});published=published or parse_date(v)
 body=next((n for n in nodes if n.tag=='main'),None) or next((n for n in nodes if n.tag=='d-article'),None) or next((n for n in nodes if n.tag=='article'),None) or next((n for n in nodes if n.tag=='body'),d.root)
 links=[]
 for n in body.walk():
  if n.tag=='a' and n.attrs.get('href'):
   links.append({'url':urllib.parse.urljoin(url,n.attrs['href']),'anchor_text':re.sub(r'\s+',' ',n.text()).strip()})
 def render(n):
  if isinstance(n,str):return re.sub(r'\s+',' ',n)
  cl=n.attrs.get('class','').lower()
  if n.tag in {'script','style','nav','footer','noscript','svg','button','input'} or n.attrs.get('aria-hidden')=='true':return ''
  if any(k in cl for k in ['related-content','related-post','newsletter','cookie-banner','site-footer','global-nav']):return ''
  text=''.join(render(c) for c in n.children)
  if n.tag=='pre' or 'rs-xcode' in cl:return '\n\n```source-artifact\n'+n.text().strip()+'\n```\n\n'
  if n.tag=='blockquote':return '\n\n'+'\n'.join('> '+l for l in text.strip().splitlines())+'\n\n'
  if n.tag=='table':
   table=[]
   for row in n.walk():
    if row.tag=='tr':table.append(' | '.join(re.sub(r'\s+',' ',c.text()).strip() for c in row.children if isinstance(c,Node) and c.tag in {'td','th'}))
   return '\n\n```source-table\n'+'\n'.join(table)+'\n```\n\n'
  if re.fullmatch('h[1-6]',n.tag):return '\n\n'+'#'*int(n.tag[1])+' '+text.strip()+'\n\n'
  if n.tag=='li':return '\n- '+text.strip()+'\n'
  if n.tag in {'p','div','section','article','main','ul','ol','d-article'}:return '\n\n'+text.strip()+'\n\n'
  if n.tag=='br':return '\n'
  if n.tag=='img':return ''
  return text
 text=re.sub(r'\n[ \t]+','\n',render(body));text=re.sub(r'\n{3,}','\n\n',text).strip()
 text=re.split(r'(?im)^#{1,3}\s+Related (?:content|posts)\s*$',text)[0].strip()
 headings=re.findall(r'(?m)^# ([^\n]+)',text)
 if headings:title=headings[-1] if headings[0] in {'Boris Cherny\'s Blog','Dario Amodei'} else headings[0]
 if not published:
  # Native visible publication line near the article beginning; never a sitemap lastmod.
  m=re.search(r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?) \d{1,2},? 20\d{2}\b',text[:1800])
  if m:published=parse_date(m.group());metadata.append({'kind':'visible_initial_date','value':m.group()})
 if not published:
  m=re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) 20\d{2}\b',text[:400])
  if m:metadata.append({'kind':'visible_month_only; exact day unavailable','value':m.group()})
 return {'title':title,'authors':list(dict.fromkeys(authors)),'published_at':published,'modified_at':modified,'date_evidence':metadata,'declared_canonical_url':canonical,'body_links':links,'text':text,'extractor':'stdlib-dom-markdown-v1'}

class Refresh:
 def __init__(self,args):
  self.a=args;self.release=(ROOT/args.release).resolve();self.sources=self.release/'sources';self.cache=self.sources/'requests'
  self.base=(ROOT/args.baseline).resolve();self.vault=Path(args.vault).resolve() if args.vault else None;self.date=args.date
  self.oldunits=rows(self.base/'data/analysis-units.jsonl.gz');self.oldby={normalize(u['canonical']):u for u in self.oldunits}
  if args.stage in {'discover','build','all'}:self.require_comparison_vault()
  self.oldraw={u.get('raw_sha256'):u for u in self.oldunits if u.get('raw_sha256')}
  self.oldtitle=collections.defaultdict(list)
  for unit in self.oldunits:self.oldtitle[re.sub(r'\W+','',unit['title'].casefold())].append(unit)
  for unit in self.oldunits if self.vault else []:
   for rid in unit.get('source_seed_record_ids',[]):
    for path in [self.vault/'increments/2026-09-08/records'/(rid+'.json'),self.vault/'records'/(rid+'.json')]:
     if path.exists():
      prior_record=json.loads(path.read_text());digest=prior_record.get('resolved',{}).get('raw_sha256') or prior_record.get('raw_sha256')
      if digest:self.oldraw.setdefault(digest,unit)
  self.known=set(self.oldby)
  for p in [self.vault/'manifest.csv',self.vault/'increments/2026-09-08/discovery.jsonl'] if self.vault else []:
   if p.exists():
    rr=list(csv.DictReader(p.open())) if p.suffix=='.csv' else rows(p)
    self.known.update(normalize(r.get('url','')) for r in rr if r.get('url'))
  self.preserve()
 def require_comparison_vault(self):
  """Read-only preflight, before any release write or network request."""
  if self.vault is None:
   raise ComparisonInputError('discover/build/all require explicit --vault PATH to the historical corpus; no default corpus or empty comparison is allowed')
  if not self.oldunits:
   raise ComparisonInputError('Baseline analysis units are missing or empty: '+str(self.base/'data/analysis-units.jsonl.gz'))
  required=[self.vault/'manifest.csv',self.vault/'increments/2026-09-08/discovery.jsonl']
  missing=[str(p) for p in required if not p.is_file()]
  if missing:raise ComparisonInputError('Historical --vault is incomplete; missing comparison input: '+', '.join(missing))
  # Every seed contributes aliases/raw hashes. A partial records directory can
  # otherwise silently turn unchanged carriers into new or revised works.
  for rid in sorted({rid for u in self.oldunits for rid in u.get('source_seed_record_ids',[])}):
   paths=[self.vault/'increments/2026-09-08/records'/(rid+'.json'),self.vault/'records'/(rid+'.json')]
   records=[p for p in paths if p.is_file()]
   if not records:raise ComparisonInputError('Historical --vault is missing baseline seed record '+rid)
   for p in records:
    try:record=json.loads(p.read_text());blob=record.get('resolved',{}).get('blob_path')
    except (OSError,ValueError) as e:raise ComparisonInputError('Cannot read historical record '+str(p)+': '+str(e)) from e
    if blob:
     raw=self.vault.parent/blob
     if not raw.is_file():raise ComparisonInputError('Historical --vault is missing declared raw capture '+str(raw))
  # Validate discovery inputs now, rather than accepting an empty/malformed
  # historical URL set and treating everything as newly discovered.
  try:
   with required[0].open() as f:
    manifest=list(csv.DictReader(f))
   discovery=rows(required[1])
   if not manifest or not discovery or not any(r.get('url') for r in manifest) or not any(r.get('url') for r in discovery):
    raise ValueError('historical manifest/discovery contains no URLs')
  except (OSError,ValueError) as e:raise ComparisonInputError('Cannot use historical discovery inputs in --vault: '+str(e)) from e
 def old_text_path(self,unit):
  if self.vault is None:return None
  name=unit.get('text_path','')
  if not name:return None
  return next((p for p in [self.vault.parent/name,self.vault/name.removeprefix('corpus/')] if p.is_file()),None)
 def preserve(self):
  paths=[p for name in ('amind-v1','amind-v1-increment-2026-09-08') for p in (ROOT/'release'/name).rglob('*') if p.is_file()]
  fp={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}
  p=self.release/'audits/baseline.json'
  if p.exists():
   old=json.loads(p.read_text());assert old['fingerprints']==fp,'frozen release changed'
  else:put(p,{'fingerprints':fp,'base_release_id':self.base.name,'baseline_cutoff':self.a.since,'started_at':now()})
 def request(self,url):
  key=sha(url.encode());path=self.cache/(key+'.json')
  if path.exists():
   r=json.loads(path.read_text())
   if r.get('ok'):
    b=gzip.decompress((self.release/r['raw_path']).read_bytes());assert sha(b)==r['raw_sha256'];return b,r
   if not self.a.retry_failed:return b'',r
   put(self.sources/'request-history'/(key+'-'+sha(jb(r))[:12]+'.json'),r)
  r={'requested_url':url,'started_at':now(),'ok':False}
  try:
   req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/pdf,application/xml;q=0.9,*/*;q=0.8'})
   with urllib.request.build_opener(CompatibleRedirects()).open(req,timeout=25) as f:
    b=f.read(self.a.max_bytes+1)
    if len(b)>self.a.max_bytes:raise ValueError('response exceeds max_bytes')
    r.update(ok=True,final_url=f.url,http_status=f.status,content_type=f.headers.get('Content-Type',''),bytes=len(b),response_headers={k:v for k,v in f.headers.items() if k.lower() in {'etag','last-modified','content-type','date','content-length'}})
   digest=sha(b);rawpath=Path('sources/raw')/(digest+'.bin.gz');put(self.release/rawpath,gzip.compress(b,mtime=0))
   r.update(raw_sha256=digest,raw_path=str(rawpath))
  except Exception as e:
   b=b'';r.update(error=str(e),http_status=getattr(e,'code',None))
  r['completed_at']=now();put(path,r)
  return b,r
 def configured(self):
  paths=[ROOT/'config'/name for name in ('sources.json','person-expansion-sources.json','spoken-sources.json')]
  if not all(p.is_file() for p in paths):
   snapshot=self.release/'audits/configured-sources.json'
   if snapshot.is_file():
    sources=json.loads(snapshot.read_text())
    if isinstance(sources,list) and sources and all(isinstance(s,dict) and s.get('id') and s.get('method') and (s.get('url') or s.get('urls')) for s in sources):return sources
   raise ComparisonInputError('Discovery configuration is missing; provide config/*.json or a nonempty validated release audits/configured-sources.json snapshot')
  result=[]
  p=ROOT/'config/sources.json'
  if p.exists():result.extend({**s,'lane':'main'} for s in json.loads(p.read_text())['sources'] if not s['method'].startswith('wayback'))
  p=ROOT/'config/person-expansion-sources.json'
  if p.exists():
   for person in json.loads(p.read_text())['people']:
    result.extend({**s,'publisher':person['canonical_name'],'lane':'person'} for s in person['sources'] if s['method'] in {'index','sitemap','feed'})
  p=ROOT/'config/spoken-sources.json'
  if p.exists():
   for s in json.loads(p.read_text())['official_surfaces']:
    result.extend({'id':s['surface_id']+'-'+str(i),'url':u,'method':'feed' if '/feeds/' in u else 'index','publisher':'Anthropic','lane':'spoken'} for i,u in enumerate(s['entrypoints']))
  if not result:raise ComparisonInputError('Discovery configuration contains zero eligible entrypoints')
  return result
 def discover(self):
  self.require_comparison_vault()
  sources=self.configured();put(self.release/'audits/configured-sources.json',sources);occ=[];fetches=[]
  def one(s):
   found=[];observed=[]
   def visit(u,method,depth=0):
    if depth>3:return
    b,r=self.request(u);observed.append({**r,'source_id':s['id']})
    if not r['ok']:return
    if method in {'sitemap','feed'}:
     try:
      root=ET.fromstring(b)
      if root.tag.endswith('sitemapindex'):
       for n in root:
        loc=next((c.text for c in n if c.tag.endswith('loc')),None)
        if loc:visit(loc,'sitemap',depth+1)
       return
      for n in root.iter():
       local=n.tag.rsplit('}',1)[-1]
       if local in {'url','item','entry'}:
        loc='';dt=''
        for c in n:
         k=c.tag.rsplit('}',1)[-1]
         if k in {'loc','link'}:loc=c.text or c.attrib.get('href') or loc
         if k in {'lastmod','pubDate','published','updated'}:dt=c.text or dt
        if loc:found.append({'url':urllib.parse.urljoin(u,loc),'lastmod':dt})
     except ET.ParseError:pass
    else:
     e=extract_html(b,r.get('final_url',u));found.extend({'url':x['url'],'lastmod':''} for x in e['body_links'])
   if s['method']=='seed':found.extend({'url':u,'lastmod':''} for u in s.get('urls',[]))
   elif s.get('url'):visit(s['url'],s['method'])
   return [{**r,'source_id':s['id'],'publisher':s.get('publisher',''),'lane':s['lane']} for r in found],observed
  with concurrent.futures.ThreadPoolExecutor(self.a.workers) as pool:
   for s,(found,observed) in zip(sources,pool.map(one,sources)):
    occ.extend(found);fetches.extend(observed);print('discover',s['id'],len(found),sum(not r['ok'] for r in observed),flush=True)
  unique={}
  for r in occ:
   u=normalize(r['url'])
   if not urllib.parse.urlsplit(u).hostname:continue
   if u not in unique:unique[u]={**r,'url':u,'discovery_change':'known_url' if u in self.known else 'new_url','sources':[],'observed_urls':[]}
   unique[u]['sources'].append(r['source_id'])
   if r['url'] not in unique[u]['observed_urls']:unique[u]['observed_urls'].append(r['url'])
  putrows(self.release/'audits/discovery-occurrences.jsonl',occ);putrows(self.release/'audits/source-fetches.jsonl',fetches)
  putrows(self.release/'audits/discovery.jsonl',sorted(unique.values(),key=lambda r:r['url']))
  summary={'configured_sources':len(sources),'observed_unique_urls':len(unique),'new_urls':sum(r['discovery_change']=='new_url' for r in unique.values()),'failed_sources':sorted({r['source_id'] for r in fetches if not r['ok']}),'scope':'configured current sources; historical web archives not re-enumerated','completed_at':now()}
  put(self.release/'audits/discovery-summary.json',summary);print(json.dumps(summary),flush=True)
 def select(self):
  selected={normalize(OFFICIAL+s):{'url':OFFICIAL+s,'selection_reason':'reviewed priority source'} for s in SEEDS}
  selected.update({normalize(u):{'url':u,'selection_reason':'reviewed personal or system-prompt source'} for u in EXTRA})
  if self.a.urls:
   for line in Path(self.a.urls).read_text().splitlines():
    if line.strip() and not line.startswith('#'):selected[normalize(line)]={'url':line.strip(),'selection_reason':'explicit additional URL'}
  discovery_decisions=[]
  for r in rows(self.release/'audits/discovery.jsonl'):
   s=urllib.parse.urlsplit(r['url']);host=s.hostname or '';path=s.path;reason=''
   translation=path.split('/')[1].lower() in {'ja','de','es','fr','ko','zh','zh-cn','zh-tw','pt','it','id','ru'}
   if r['discovery_change']=='new_url' and not translation:
    if host in {'anthropic.com','claude.com','alignment.anthropic.com','transformer-circuits.pub'} and (path.startswith(('/news/','/research/','/engineering/','/blog/','/2026/')) or 'system-card' in path):reason='new first-party article candidate'
    elif host in {'darioamodei.com','borischerny.com','jack-clark.net','jan.leike.name','aligned.substack.com','benjmann.net','evhub.github.io','dganguli.github.io','ethanperez.net','askell.io','askell.blog'} and path not in {'/','/home','/rss','/feed','/feed.xml','/sitemap.xml','/essays','/photography','/ceramics','/blog','/publications','/privacy-policy','/research/home'} and not path.startswith('/page/'):reason='new person-controlled written candidate; date and attribution need review'
   if not translation and host in {'anthropic.com','claude.com','alignment.anthropic.com','transformer-circuits.pub'} and r['discovery_change']=='known_url' and path.startswith(('/news/','/research/','/engineering/','/blog/','/2026/')) and parse_date(r.get('lastmod',''))>=self.a.since[:10]:reason='existing source revision check: sitemap/feed lastmod is candidate evidence only'
   disposition='excluded_translation_alias' if translation else 'retained_navigation_or_out_of_scope' if not reason else 'selected_body_capture'
   if reason:
    if len(selected)<self.a.max_candidates:selected.setdefault(r['url'],{**r,'selection_reason':reason})
    elif r['url'] not in selected:disposition='not_fetched_candidate_limit'
   if r['url'] in selected:disposition='selected_body_capture'
   discovery_decisions.append({**r,'disposition':disposition,'reason':reason or ('English original scope; alias preserved in discovery' if translation else 'No new/recent qualifying written work signaled by this configured discovery row')})
  putrows(self.release/'audits/discovery-decisions.jsonl',discovery_decisions)
  putrows(self.release/'audits/collection-queue.jsonl',list(selected.values()));return list(selected.values())
 def collect(self):
  queue=self.select()
  def one(item):
   u=item['url'];b,r=self.request(u);record={**item,**r,'record_id':sid('am-oct-',normalize(u),12)}
   if r['ok']:
    try:
     if b.startswith(b'%PDF') or 'application/pdf' in r.get('content_type',''):
      try:import pymupdf as fitz
      except ImportError:import fitz
      doc=fitz.open(stream=b,filetype='pdf');text='\n\n'.join('## Page '+str(i+1)+'\n\n'+'\n\n'.join(re.sub(r'\s+',' ',x[4]).strip() for x in p.get_text('blocks',sort=True) if x[6]==0) for i,p in enumerate(doc))
      e={'title':doc.metadata.get('title',''),'authors':[],'published_at':'','modified_at':'','date_evidence':[],'body_links':[],'text':text,'pages':len(doc),'extractor':'pymupdf-blocks-v1'}
     else:e=extract_html(b,r.get('final_url',u))
     path=urllib.parse.urlsplit(u).path.lstrip('/')
     if not e.get('published_at') and path in DATES:
      e['published_at']=DATES[path];e['date_evidence'].append({'kind':'reviewed_official_release_or_research_index','value':DATES[path],'source':'https://www.anthropic.com/system-cards' if 'system-card' in path else 'https://www.anthropic.com/research'})
     if '/system-prompts/' in u:e['published_at']=e.get('published_at') or {'opus':'2026-09-22','sonnet':'2026-09-28','haiku':'2026-10-07'}.get(path.split('claude-')[-1].split('-')[0],'')
     text=e.pop('text');textpath=Path('sources/texts')/(sha(text.encode())+'.md');put(self.release/textpath,text.encode());record['extracted']={**e,'body_sha256':sha(text.encode()),'text_path':str(textpath)}
    except Exception as err:record['extraction_error']=str(err)
   put(self.sources/'records'/(record['record_id']+'.json'),record)
   return record
  with concurrent.futures.ThreadPoolExecutor(self.a.workers) as pool:
   records=list(pool.map(one,queue))
  # Explicit first-party PDF attachments are separate carriers, never silently lost.
  attachments={}
  for r in records:
   e=r.get('extracted',{})
   for l in e.get('body_links',[]):
    u=l['url'];a=l['anchor_text'].lower();host=urllib.parse.urlsplit(u).hostname or ''
    if ('anthropic.com' in host or host=='cdn.sanity.io') and '.pdf' in u.lower() and (any(k in a for k in ['paper','appendix','risk report','technical report','system card']) or 'system-card' in r['url']):
     attachments.setdefault(normalize(u),{'url':u,'selection_reason':'explicit first-party paper/card attachment','parent_url':r['url']})
  already={normalize(r['url']) for r in records}
  todo=[r for k,r in attachments.items() if k not in already]
  with concurrent.futures.ThreadPoolExecutor(min(4,self.a.workers)) as pool:records.extend(pool.map(one,todo))
  summary={'selected_urls':len(queue),'attachment_urls':len(todo),'captured':sum(bool(r.get('ok')) for r in records),'bodies':sum(bool(r.get('extracted')) for r in records),'failed':[{'url':r['url'],'error':r.get('error') or r.get('extraction_error')} for r in records if not r.get('extracted')],'completed_at':now()}
  put(self.release/'audits/collection-summary.json',summary);print(json.dumps(summary),flush=True)

 def build(self):
  self.require_comparison_vault()
  self.preserve();units=[];passages=[];decisions=[];versions=[];seen={};texts={}
  selected_urls={normalize(r['url']) for r in rows(self.release/'audits/collection-queue.jsonl')}
  records=[(p,json.loads(p.read_text())) for p in (self.sources/'records').glob('*.json')]
  records.sort(key=lambda pr:(bool(pr[1].get('parent_url')),normalize(pr[1]['url']) not in self.oldby,not pr[1].get('extracted',{}).get('published_at'),pr[1]['url']))
  for p,r in records:
   e=r.get('extracted',{});u=normalize(r['url']);prior=self.oldby.get(u)
   if e and not e.get('pages') and r.get('raw_path'):
    raw=gzip.decompress((self.release/r['raw_path']).read_bytes());updated=extract_html(raw,r.get('final_url',r['url']))
    if not updated['published_at'] and e.get('published_at'):
     updated['published_at']=e['published_at'];updated['date_evidence'].extend(x for x in e.get('date_evidence',[]) if x not in updated['date_evidence'])
    text=updated.pop('text');tp=Path('sources/texts')/(sha(text.encode())+'.md');put(self.release/tp,text.encode());e={**updated,'body_sha256':sha(text.encode()),'text_path':str(tp)};r['extracted']=e;put(p,r)
   native_path=urllib.parse.urlsplit(u).path
   if e and (native_path.startswith('/legal/') or native_path in {'/responsible-scaling-policy','/responsible-scaling-policy/roadmap','/responsible-scaling-policy/updates','/constitution','/transparency','/transparency/model-report','/docs/en/about-claude/model-deprecations','/docs/en/about-claude/models/overview'}):
    e['published_at']=''
    for item in e.get('date_evidence',[]):
     if item['kind']=='visible_initial_date':item['kind']='native status/effective/last-update date; not a publication date'
    r['extracted']=e;put(p,r)
   d={'record_id':r['record_id'],'url':r['url'],'raw_sha256':r.get('raw_sha256'),'observed_at':r.get('completed_at'),'prior_analysis_unit_id':prior['analysis_unit_id'] if prior else None,'selection_reason':r['selection_reason']}
   if 'arxiv.org/abs/2610.03075' in u:
    d.update(disposition='excluded_homonym',reason='Native arXiv author affiliation identifies Tom Brown at Wellcome Sanger Institute on genome-assembly standards, not the Anthropic core person; raw abstract retained as identity evidence');decisions.append(d);continue
   if u not in selected_urls and not r.get('parent_url'):
    d.update(disposition='excluded_discovery_navigation',reason='Captured during earlier exploratory queue; current reviewed selection excludes navigation/privacy/index material');decisions.append(d);continue
   if urllib.parse.urlsplit(u).path=='/system-cards':
    d.update(disposition='metadata_only',reason='Model-card navigation registry; individual system-card bodies captured separately');decisions.append(d);continue
   if not e:d.update(disposition='unavailable',reason=r.get('error') or r.get('extraction_error'));decisions.append(d);continue
   text=(self.release/e['text_path']).read_text();digest=e['body_sha256'];pub=e.get('published_at','');path=urllib.parse.urlsplit(u).path
   if e.get('pages') and not pub:
    cover=re.sub('[\u200b\u00ad\ufeff]','',text.split('## Page 2')[0]);m=re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2},? 20\d{2}\b',cover)
    if m:
     pub=parse_date(m.group());e['published_at']=pub;item={'kind':'PDF cover printed date','value':m.group()}
     if item not in e['date_evidence']:e['date_evidence'].append(item)
    else:
     m=re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) 20\d{2}\b',cover)
     if m:
      item={'kind':'PDF cover month-only; exact day unavailable','value':m.group()}
      if item not in e['date_evidence']:e['date_evidence'].append(item)
    e['date_evidence']=list({jb(item):item for item in e['date_evidence']}.values())
    r['extracted']=e;put(p,r)
   if r.get('raw_sha256') in self.oldraw:
    d.update(disposition='unchanged_raw_or_baseline_duplicate',equivalent_analysis_unit_id=self.oldraw[r['raw_sha256']]['analysis_unit_id'],reason='Raw response bytes identical to an immutable baseline source');decisions.append(d);continue
   if len(text)<150:d.update(disposition='metadata_only',reason='No substantive article body');decisions.append(d);continue
   if digest in seen:d.update(disposition='duplicate_carrier',equivalent_analysis_unit_id=seen[digest],reason='identical extracted body hash in this batch');decisions.append(d);continue
   if not prior:
    aliases=self.oldtitle.get(re.sub(r'\W+','',e['title'].casefold()),[])
    alias=next((old for old in aliases if (self.old_derivative(old) is not None and body_equal(self.old_derivative(old),text))),None)
    if alias:
     d.update(disposition='baseline_alias_carrier',equivalent_analysis_unit_id=alias['analysis_unit_id'],reason='Same native title plus identical body under the same renderer; URL migration retained as alias, not a new work');decisions.append(d);continue
   # Retain undated institutional manuals; avoid backfilling stale personal archives as new work.
   if pub and pub[:10]<self.a.since[:10] and not prior and r['selection_reason'].startswith('new person'):
    d.update(disposition='historical_discovery_not_increment',published_at=pub,reason='Pre-cutoff person source discovered now; retained raw, not counted as period publication');decisions.append(d);continue
   if prior:
    previous=self.old_derivative(prior)
    if previous is not None:
     if body_equal(previous,text):
      d.update(disposition='unchanged_body',reason='Current and frozen raw HTML re-extracted with the same DOM renderer: body equal');decisions.append(d);continue
     diffpath=self.release/'audits/body-diffs'/(r['record_id']+'.diff')
     import difflib
     put(diffpath,'\n'.join(difflib.unified_diff(previous.splitlines(),text.splitlines(),fromfile=prior['analysis_unit_id'],tofile=r['record_id'],n=2)).encode())
    oldpath=self.old_text_path(prior)
    if oldpath:
     oldtext=oldpath.read_text()
     if body_equal(oldtext,text):
      d.update(disposition='unchanged_body',reason='normalized body equals prior derivative');decisions.append(d);continue
   if prior and EDITORIAL_RAW_REVIEW.get(path)==r.get('raw_sha256'):
    d.update(disposition='editorial_or_template_change',reason='Individually reviewed frozen/current diff: category/byline/navigation/typography/paragraph formatting or migrated AI-Fluency carrier; no substantive source assertion changed. Decision is bound to this exact current raw hash.');decisions.append(d);continue
   origin='source_artifact' if '/system-prompts/' in u else 'revised_work' if prior else 'new_work'
   work=prior['work_id'] if prior else sid('wrk-',u,32);edition=sid('edn-',work+'\0'+r['raw_sha256'],32);uid=sid('nuwa1804-unit-',work+'\0'+edition+'\0'+digest,20)
   title=e['title'] or path.rsplit('/',1)[-1].replace('-',' ').strip().title()
   authors=e.get('authors',[])
   if 'claude-shaped-science' in u:authors=['Matthew Schwartz']
   if 'yes-claude-can-do-nine-loops' in u:authors=['Matt von Hippel']
   if 'darioamodei.com' in u:authors=['Dario Amodei']
   if 'borischerny.com' in u:authors=['Boris Cherny']
   if 'jack-clark.net' in u:authors=['Jack Clark']
   unit={'schema_name':'nuwa-v1-analysis-unit','schema_version':1,'analysis_unit_id':uid,'work_id':work,'edition_id':edition,'title':title,'authors':authors,'canonical':r['url'],'published_at':pub,'publication_date_basis':'; '.join(x['kind']+': '+str(x['value']) for x in e.get('date_evidence',[])) or 'not stated; observation date is not publication date','observed_at':r['completed_at'],'modified_at':e.get('modified_at',''),'language':'en','unit_status':'body_primary','component_origin':origin,'historical_role':{'status':'source-native authorship; no inferred employment or institutional endorsement'},'source_seed_record_ids':[r['record_id']],'source_manifest_row_sha256':sha(jb(r)),'body_sha256':digest,'text_file_sha256':digest,'text_path':str((self.release/e['text_path']).relative_to(ROOT)),'selection_reason':r['selection_reason'],'raw_sha256':r['raw_sha256'],'extraction':{'native_extractor':e['extractor'],'pages':e.get('pages'),'date_evidence':e.get('date_evidence',[])},'batch_id':self.date}
   _,pp=atoms.segment_text(text,uid,digest,6000)
   for i,a in enumerate(pp):a.update(schema_name='nuwa-v1-passage',schema_version=1,analysis_unit_id=uid,work_id=work,edition_id=edition,source_seed_record_ids=unit['source_seed_record_ids'],source_text_path=unit['text_path'],source_text_file_sha256=digest,source_body_sha256=digest,previous_passage_id=pp[i-1]['passage_id'] if i else '',next_passage_id=pp[i+1]['passage_id'] if i+1<len(pp) else '')
   if prior:versions.append({'work_id':work,'prior_analysis_unit_id':prior['analysis_unit_id'],'new_analysis_unit_id':uid,'prior_edition_id':prior['edition_id'],'new_edition_id':edition,'observed_at':r['completed_at'],'prior_raw_sha256':prior.get('raw_sha256'),'relation':'later_observed_revision','basis':'later independently captured body; native extractor differs, semantic supersession only in current-status','historical_claims_retained':True})
   partition='source_artifact' if origin=='source_artifact' else 'revised_existing_work' if prior else 'period_publication' if pub and pub>=self.a.since[:10] else 'historical_backfill' if pub else 'undated_first_indexing'
   d.update(disposition=origin,publication_partition=partition,title=title,published_at=pub,analysis_unit_id=uid,work_id=work,edition_id=edition);decisions.append(d);units.append(unit);passages.extend(pp);seen[digest]=uid;texts[uid]=text
  putrows(self.release/'delta/source-decisions.jsonl',decisions)
  put(self.release/'audits/preparation-audit.json',{'analysis_units':len(units),'passages':len(passages),'source_dispositions':dict(collections.Counter(d['disposition'] for d in decisions)),'publication_partitions':dict(collections.Counter(d.get('publication_partition') for d in decisions if d.get('analysis_unit_id'))),'prepared_at':now()})
  print('prepared',len(units),'units',len(passages),'passages',flush=True)
  self.extract(units,passages,decisions,versions,texts)

 def old_derivative(self,unit):
  """Re-extract old raw HTML using this exact renderer to avoid extractor drift."""
  if self.vault is None:raise ComparisonInputError('Old source comparison requires explicit --vault PATH')
  for rid in unit.get('source_seed_record_ids',[]):
   for path in [self.vault/'increments/2026-09-08/records'/(rid+'.json'),self.vault/'records'/(rid+'.json')]:
    if not path.exists():continue
    record=json.loads(path.read_text());resolved=record.get('resolved',{});blob=resolved.get('blob_path')
    if not blob:continue
    p=self.vault.parent/blob
    if not p.is_file():raise ComparisonInputError('Historical raw capture is missing: '+str(p))
    b=p.read_bytes()
    try:b=gzip.decompress(b)
    except (OSError,EOFError):pass
    expected=resolved.get('raw_sha256')
    if expected and sha(b)!=expected:raise ComparisonInputError('Historical raw capture hash mismatch: '+str(p))
    if b.startswith(b'%PDF'):return None
    return extract_html(b,unit['canonical'])['text']
  if self.old_text_path(unit):return None
  raise ComparisonInputError('Cannot compare baseline unit '+unit['analysis_unit_id']+': historical raw capture and derivative are unavailable in --vault')

 def extract(self,units,passages,decisions,versions,texts):
  byunit={u['analysis_unit_id']:u for u in units};bytext=collections.defaultdict(list)
  for p in passages:bytext[p['analysis_unit_id']].append(p['text'])
  seeds=[];coverage=[];exclusions=[];used=collections.defaultdict(set);props=set();policy=atoms.POLICY
  for u in units:
   text=texts[u['analysis_unit_id']];ranges=[];opened=None
   for m in re.finditer(r'(?m)^\s*(?:```|~~~).*$',text):
    if opened is None:opened=m.start()
    else:ranges.append((opened,m.end(),'fenced source artifact/table/code'));opened=None
   if opened is not None:ranges.append((opened,len(text),'continued source artifact'))
   if u['component_origin']=='source_artifact':ranges.append((0,len(text),'system prompt is a source artifact, not author belief'))
   if urllib.parse.urlsplit(u['canonical']).path=='/claude-opus-5-5':
    start=text.find('Claude Opus 5\n\nPlease explain the issue to me.')
    end=text.find('\n## Safety',start)
    if start<0 or end<0:raise ValueError('Opus comparison artifact boundary changed; requires passage-context re-review')
    ranges.append((start,end,'Full model-comparison demonstrations: generated bug explanation, fictional Slack/finance conversation, and FEN prompts/responses; not institutional beliefs. Communication introduction retained.'))
   if 'jack-clark.net' in u['canonical']:
    m=re.search(r'(?im)^(?:#{1,6}\s*)?Tech Tales',text)
    if m:ranges.append((m.start(),len(text),'fictional Tech Tales; not author belief'))
   for a,b,reason in ranges:exclusions.append({'analysis_unit_id':u['analysis_unit_id'],'source_char_start':a,'source_char_end':b,'reason':reason})
  exby=collections.defaultdict(list)
  for x in exclusions:exby[x['analysis_unit_id']].append(x)
  for p in passages:
   u=byunit[p['analysis_unit_id']];text=p['text'];v=atoms.voice_defaults(u);count=0
   guest=any(s in u['canonical'] for s in ['claude-shaped-science','yes-claude-can-do-nine-loops'])
   if guest:v['organization']='';v['attribution_basis']+=' Guest author hosted by Anthropic; not an institutional policy statement.'
   if 'claude.com' in u['canonical'] or 'platform.claude.com' in u['canonical']:v['organization']='Anthropic'
   reported=bool(u['extraction'].get('pages')) or 'jack-clark.net' in u['canonical']
   skip=atoms.passage_skip_reason(p,policy)
   ranges=exby[u['analysis_unit_id']]
   def overlap(a,b):return any(a<x['source_char_end'] and b>x['source_char_start'] for x in ranges)
   if not skip:
    for ss,se in atoms.eligible_spans(text,policy):
     for start,end in atoms.sentence_spans(text,ss,se):
      for a,b in atoms.split_long_span(text,start,end,320,280):
       if overlap(p['source_char_start']+a,p['source_char_start']+b):continue
       q=text[a:b]
       if not atoms.candidate_is_substantive(q,policy):continue
       q=atoms.unique_quote(bytext[u['analysis_unit_id']],text,a,b,320)
       if not q or len(q)>320 or q in used[u['analysis_unit_id']] or not atoms.candidate_is_substantive(q,policy):continue
       loc=text.find(q)
       if overlap(p['source_char_start']+loc,p['source_char_start']+loc+len(q)):continue
       used[u['analysis_unit_id']].add(q);fragment=a>start or b<end
       prop=atoms.normalize_proposition(text[a:b],v['voice_name'],v['voice_type'],clause_fragment=fragment)
       if prop in props:prop=prop.rstrip('.')+f" (source unit {u['analysis_unit_id'][-6:]}, passage {p['passage_sequence']}, occurrence {count+1})."
       props.add(prop);kind,force=atoms.classify(text[a:b]);conditions=[]
       if fragment:conditions.append('Clause from a longer source sentence; inspect adjacent passage context.')
       cond=atoms.simulation_condition(text)
       if cond:conditions.append(cond)
       if 'fictional' in text[a:b].lower():conditions.append('The source explicitly describes a fictional evaluation/example, not an actual transaction, company, user conversation or empirical financial outcome.')
       if reported:conditions.append('Document includes third-party reports or model/prompt artifacts. Mechanical extraction remains reported pending individual passage-context review; not a blanket author endorsement.')
       if guest:conditions.append('Named guest author; source host does not imply Anthropic institutional endorsement.')
       seed={'seed_id':sid('oct-seed-',p['passage_id']+q),'unit_id':u['analysis_unit_id'],'proposition':prop,'quote':q,'claim_type':kind,'epistemic_force':'quoted_position' if reported else force,'domains':atoms.domains_for(text[a:b],u['title']),'conditions':conditions,'invalidation_conditions':[],**v};seeds.append(seed);count+=1
   coverage.append({'passage_id':p['passage_id'],'analysis_unit_id':u['analysis_unit_id'],'claims':count,'processing':'deterministic source-exact extraction; not human review','claimless_reason':None if count else skip or 'No unique eligible author-prose span after source-artifact filters'})
  claims,bindings=atoms.extract_claim_records(seeds,units,passages,json.loads((ROOT/'config/amind-v1-atomic-claim.schema.json').read_text()),self.date,'source-exact deterministic routine extraction with source-artifact exclusions','amind-refresh-2026-10-18-1')
  auditpolicy=json.loads((ROOT/'config/nuwa-v1-claim-audit-policy.json').read_text());audits=[auditor.claim_attribution(c,auditpolicy) for c in claims]
  themes=json.loads((ROOT/'config/nuwa-v1-synthesis-policy.json').read_text())['themes'];members=[]
  for c,a in zip(claims,audits):
   u=byunit[c['evidence'][0]['analysis_unit_id']];search=' '.join([c['proposition'],' '.join(c['domains']),u['title']]).lower();hits={t['theme_id']:sorted({k for k in t['keywords'] if k.lower() in search}) for t in themes};hits={k:v for k,v in hits.items() if v}
   members.append({'schema_name':'nuwa-v1-theme-membership','schema_version':1,'claim_id':c['claim_id'],'claim_row_sha256':sha(jb(c)),'analysis_unit_id':u['analysis_unit_id'],'work_id':u['work_id'],'edition_id':u['edition_id'],'attribution_class':a['attribution_class'],'synthesis_disposition':a['synthesis_disposition'],'theme_ids':list(hits),'match_terms_by_theme':hits})
  delta={'analysis-units':units,'passages':passages,'atomic-claims':claims,'claim-attribution-audit':audits,'theme-membership':members}
  counts={}
  for name,values in delta.items():
   key='analysis_unit_id' if name=='analysis-units' else 'passage_id' if name=='passages' else 'claim_id';baseline=rows(self.base/'data'/(name+'.jsonl.gz'));assert not ({r[key] for r in values}&{r[key] for r in baseline}),name+' ID collision'
   putrows(self.release/'delta'/(name+'.jsonl.gz'),values);combined=sorted(baseline+values,key=lambda r:r[key]);putrows(self.release/'data'/(name+'.jsonl.gz'),combined);counts[name]={'base':len(baseline),'new':len(values),'total':len(combined)}
  for p in (self.base/'data').iterdir():
   if p.is_file() and p.name not in {n+'.jsonl.gz' for n in delta}:put(self.release/'data'/p.name,p.read_bytes())
  for name,values in [('source-decisions',decisions),('version-relations',versions),('artifact-exclusions',exclusions),('passage-processing',coverage),('claim-bindings',bindings)]:putrows(self.release/'delta'/(name+'.jsonl'),values)
  put(self.release/'audits/extraction-audit.json',{'counts':counts,'attribution':dict(collections.Counter(a['attribution_class'] for a in audits)),'new_human_reviewed_gold':0,'review_boundary':'all claims mechanically exact-quote/offset/hash/schema checked; no human semantic review; selected AI context reviews recorded separately','source_dispositions':dict(collections.Counter(d['disposition'] for d in decisions))})
  self.verify_local(units,passages,claims);self.preserve();print(json.dumps(counts),flush=True)
 def verify_local(self,units,passages,claims):
  ub={u['analysis_unit_id']:u for u in units};pb={p['passage_id']:p for p in passages};texts={u['analysis_unit_id']:(ROOT/u['text_path']).read_text() for u in units}
  exclusions=collections.defaultdict(list)
  for row in rows(self.release/'delta/artifact-exclusions.jsonl'):exclusions[row['analysis_unit_id']].append(row)
  for u in units:assert sha(texts[u['analysis_unit_id']].encode())==u['text_file_sha256']
  for p in passages:assert texts[p['analysis_unit_id']][p['source_char_start']:p['source_char_end']]==p['text'];assert sha(p['text'].encode())==p['text_sha256']
  for c in claims:
   e=c['evidence'][0];assert texts[e['analysis_unit_id']][e['source_char_start']:e['source_char_end']]==e['exact_quote'];assert sha(e['exact_quote'].encode())==e['exact_quote_sha256'];assert e['exact_quote'] in pb[e['passage_id']]['text']
   assert not any(e['source_char_start']<r['source_char_end'] and e['source_char_end']>r['source_char_start'] for r in exclusions[e['analysis_unit_id']]),'source artifact promoted to claim: '+c['claim_id']
  put(self.release/'audits/source-binding-verification.json',{'ok':True,'units_checked':len(units),'passages_checked':len(passages),'claims_checked':len(claims),'checked_at':now(),'checks':['full derivative text hashes','passage source offsets and hashes','unique quotation binding','exact claim source offsets and quote hashes','frozen releases unchanged']})

 def review(self):
  """Apply the explicitly read passage/visual-review scope notes, without changing IDs."""
  units=rows(self.release/'delta/analysis-units.jsonl.gz');ub={u['analysis_unit_id']:u for u in units}
  claims=rows(self.release/'delta/atomic-claims.jsonl.gz');reviews=[]
  specs=[
   ('training-alignment-auditors','Both are reward-hacked:','observed_result','Two pointwise reward designs in the specified planted-hidden-behavior auditor training environment, not a claim that every automated audit reward is hacked.'),
   ('training-alignment-auditors','Pairwise rewards are more robust','observed_result','Pairwise rewards and benign-target calibration in this experiment; held-out composite and cross-scaffold AuditBench transfer do not establish full replacement of human safety research.'),
   ('training-alignment-auditors','Audit quality reaches 72.7','observed_result','Reference pairwise reward with 50% calibration training, three epochs; composite quality, calibration and realism are separate reported metrics.'),
   ('alignment-assessment-cybersecurity-incidents','should have avoided making such strong claims','asserted','Explicit retrospective correction of the July 30 interpretation. CoT statements alone did not establish the models believed the setting was simulated.'),
   ('alignment-assessment-cybersecurity-incidents','two forms of misalignment:','asserted','The assessment identifies biased reasoning and recklessness in the four described incidents; no evidence of coordination, goals beyond the assigned task or evasion of oversight was found.'),
   ('alignment-assessment-cybersecurity-incidents','correct window was less than an hour','asserted','September 10 correction: PyPI removal was less than one hour, not approximately 90 minutes; preserve the correction relation.'),
   ('alignment-assessment-cybersecurity-incidents','only gained access to one','asserted','September 10 correction distinguishes attempted access to several systems from successful access to one.'),
   ('investigating-unintended-model-actions','include all our internal evaluations','asserted','October 9 operational decision: expand the live-internet pause to internal evaluations until security and monitoring reliably catch these behaviors; it is not a prohibition on all customer internet use.'),
   ('measuring-pace-of-ai-development','Claude “leads” 26%','observed_result','Published September 17; measurements refer to August 2026 and an AI-led level with human supervision, not fully autonomous AI R&D.'),
   ('cyber-verification-program','integrating these programs into one expanded offering','asserted','October 6 integration of Project Glasswing and CVP. Distinguish Defense, Red Team and Specialized access tiers and their verification/monitoring requirements.'),
   ('an-update-on-independent-evaluators','Anthropic can’t veto publication','asserted','October 16 clarified METR terms: independent publication with predefined redaction categories, decided by Anthropic; this does not describe unlimited access or the rights of all partner evaluators.'),
   ('an-update-on-independent-evaluators','Updated on October 16','asserted','Native footnote explicitly dates the METR project-terms clarification; publication date remains October 15.'),
   ('2026-usage-policy-update','takes effect on November 12','forecast','October 8 announcement, future effective November 12, 2026. On October 18 the announced new policy is not yet the operative effective version.'),
   ('2026-usage-policy-update','removed our blanket prohibition','asserted','Announced change to the version effective November 12; deception, privacy misuse and surveillance restrictions remain. Do not apply this as an already-effective October 18 permission.'),
   ('import-ai-476','I now think it’s more likely','forecast','Jack Clark personal forecast update on October 12 from 2028 toward 2027 for full RSI becoming possible; neither an Anthropic institutional forecast nor a demonstrated capability.'),
   ('claude-opus-5-5-system-card','escape or tamper with a sandbox in 1.5%','observed_result','Opus 5.5 system-card evaluation, 28 scenarios times 7 runs per model, n=196, Figure 6.4.8 on page 119. This is not a universal model-risk rate; later cards rerun the evaluation and report different reference rates. Page 3 also reports mixed safety regressions despite aggregate improvements.'),
   ('claude-sonnet-5-5-system-card','9 of 196 runs (4.6%)','observed_result','Sonnet 5.5 card page 77, 28 scenarios times 7 runs, n=196; its rerun compares Opus 5.5 at about 10.2%. The footnote states these results differ from the Opus card. Do not mix cross-card rates as the same immutable evaluation.'),
   ('claude-haiku-5-5-system-card','34 of 392 runs (8.7%)','observed_result','Haiku 5.5 card page 75, 28 scenarios times 14 runs, n=392, 95% CI; rerun reference rates Opus 7.4% and Sonnet 6.9%. Not directly interchangeable with Opus or Sonnet release-card numbers.'),
   ('claude-haiku-5-5-system-card','used a leaked answer without telling the user 17%','observed_result','Haiku 5.5 card page 56: leaked-answer nondisclosure 17% versus Haiku 4.5 at 2%, a regression on this targeted evaluation despite improvements elsewhere.'),
   ('claude-haiku-5-5-system-card','outside of its sandbox in 4.0%','observed_result','Haiku card pages 56 and targeted section 6.3.1: use of out-of-sandbox credentials/files in 4.0% of scenarios. This is a separate metric from the 8.7% sandbox-crossing evaluation.'),
  ]
  for c in claims:
   u=ub[c['evidence'][0]['analysis_unit_id']];q=c['evidence'][0]['exact_quote']
   if '/news/2026-usage-policy-update' in u['canonical']:
    boundary='This is the October 8, 2026 announcement of a version effective November 12, 2026. Some paragraphs clarify existing enforcement rather than introduce new restrictions; interpret each statement with its native wording and do not assume all announced changes were already effective on October 18.'
    if boundary not in c['conditions']:c['conditions'].append(boundary)
   if urllib.parse.urlsplit(u['canonical']).path=='/responsible-scaling-policy/updates':
    note='This source explicitly archives former Frontier Safety Roadmap goals that were completed or meaningfully modified. Read each section as its historical goal/version and stated status; neither an elapsed deadline nor this archive proves completion of any current successor goal.'
    if note not in c['conditions']:c['conditions'].append(note)
   matches=[s for s in specs if s[0] in u['canonical'] and s[1].casefold() in q.casefold()]
   for source,needle,force,note in matches:
    c['epistemic_force']=force;c['conditions']=[x for x in c['conditions'] if not x.startswith('Document includes third-party reports')]
    if note not in c['conditions']:c['conditions'].append(note)
    c['provenance']['extraction_method']='source-exact routine extraction followed by selected individual AI passage-context review'
    e=c['evidence'][0];reviews.append({'claim_id':c['claim_id'],'passage_id':e['passage_id'],'exact_quote_sha256':e['exact_quote_sha256'],'reviewer_type':'AI assistant','human_reviewed':False,'review_state':'machine_checked','scope_note':note,'human_gold_promotion':False})
  auditpolicy=json.loads((ROOT/'config/nuwa-v1-claim-audit-policy.json').read_text());audits=[auditor.claim_attribution(c,auditpolicy) for c in claims];ab={a['claim_id']:a for a in audits};cb={c['claim_id']:c for c in claims};members=rows(self.release/'delta/theme-membership.jsonl.gz')
  for m in members:
   a=ab[m['claim_id']];m.update(claim_row_sha256=sha(jb(cb[m['claim_id']])),attribution_class=a['attribution_class'],synthesis_disposition=a['synthesis_disposition'])
  for name,data in [('atomic-claims',claims),('claim-attribution-audit',audits),('theme-membership',members)]:
   putrows(self.release/'delta'/(name+'.jsonl.gz'),data);base=rows(self.base/'data'/(name+'.jsonl.gz'));putrows(self.release/'data'/(name+'.jsonl.gz'),sorted(base+data,key=lambda r:r['claim_id']))
  putrows(self.release/'delta/context-reviews.jsonl',reviews)
  stats=json.loads((self.release/'audits/extraction-audit.json').read_text());stats['individually_AI_context_reviewed_claims']=len({r['claim_id'] for r in reviews});stats['attribution']=dict(collections.Counter(a['attribution_class'] for a in audits));put(self.release/'audits/extraction-audit.json',stats)
  self.current_status(units,claims);self.verify_local(units,rows(self.release/'delta/passages.jsonl.gz'),claims);self.preserve();print('AI context reviewed',len(reviews),'claims',flush=True)

 def current_status(self,units,claims):
  ub={u['analysis_unit_id']:u for u in units};statuses=[];observed=max(u['observed_at'] for u in units)
  def replacement(source,needle):return [c['claim_id'] for c in claims if source in ub[c['evidence'][0]['analysis_unit_id']]['canonical'] and needle.casefold() in c['evidence'][0]['exact_quote'].casefold()]
  def add(kind,targets,until,source,reason,repl=None,from_date='',unitids=None):
   if not targets and not unitids:return
   row={'status_id':sid('amind-status-',kind+'\0'+str(targets)+'\0'+str(unitids)+'\0'+until+'\0'+from_date),'target_claim_ids':targets,'target_analysis_unit_ids':unitids or [],'kind':kind,'valid_from':from_date,'valid_until':until,'replacement_claim_ids':repl or [],'source_canonical':source,'reason':reason,'observed_at':observed,'reviewer_type':'AI assistant'};statuses.append(row)
  add('corrected',['nuwa1-claim-12f017683b9189dab10ff751','nuwa1-claim-40316aceaf939ff7ba539884','nuwa1-claim-67bbb8e0fa91c37a9a5ea1f8'],'2026-09-09',OFFICIAL+'research/alignment-assessment-cybersecurity-incidents','The September 9 assessment explicitly retracts the overly strong July 30 operational-failure/simulated-belief interpretation and identifies biased reasoning plus recklessness, including Mythos acting despite acknowledged real-world-harm possibilities. Statements describing literal CoT quotations, the research model stopping in its original trajectory, and absence of independent goals/coordination are preserved as bounded observations.',replacement('alignment-assessment-cybersecurity-incidents','two forms of misalignment:'))
  add('superseded',['nuwa1-claim-7ac0bf082df80f73697342b7'],'2026-10-06',OFFICIAL+'news/cyber-verification-program','October 6 integrates Glasswing into the expanded CVP; retain the earlier expansion plan as historical rather than the current program arrangement.',replacement('cyber-verification-program','integrating these programs'))
  add('superseded',['nuwa1-claim-57c93e805d99fffa1ee74680','nuwa1-claim-e0cd4c02f4fed830ddfd9003','nuwa1-claim-f4411639c05b037d32f574cd'],'2026-10-12','https://jack-clark.net/2026/10/12/import-ai-476-creativity-and-rsi-worse-than-china-open-weight-models-ai-goes-to-space/','Clark explicitly shifts his personal full-RSI timing expectation from 2028 toward 2027. Old numeric probabilities are historical; the new statement does not supply a replacement percentage.',replacement('import-ai-476','I now think it’s more likely'))
  add('effective_window',['nuwa1-claim-4d9acc196e05849555a41d09'],'2026-11-12',OFFICIAL+'news/2026-usage-policy-update','The old targeted-campaign policy summary is qualified by the announced November 12 effective-date transition, not by the October 8 announcement date.',replacement('2026-usage-policy-update','removed our blanket prohibition'))
  for u in units:
   path=urllib.parse.urlsplit(u['canonical']).path
   if path=='/research/alignment-assessment-cybersecurity-incidents':
    text=(ROOT/u['text_path']).read_text();start=text.find('Updated Sept 10:');end=text.find('\n## Authors',start)
    if start>=0:
     if end<0:end=len(text)
     ids=[c['claim_id'] for c in claims if c['evidence'][0]['analysis_unit_id']==u['analysis_unit_id'] and c['evidence'][0]['source_char_start']<end and c['evidence'][0]['source_char_end']>start]
     add('effective_window',ids,'',u['canonical'],'Native September 10 correction paragraph; corrected PyPI removal interval and single-system access must not be backdated into the September 9 as-of view.',from_date='2026-09-10')
   if path=='/news/an-update-on-independent-evaluators':
    text=(ROOT/u['text_path']).read_text();start=text.find('METR will publish its analysis of our risk levels');end=text.find('\n\n',start)
    if start>=0:
     if end<0:end=len(text)
     ids=[c['claim_id'] for c in claims if c['evidence'][0]['analysis_unit_id']==u['analysis_unit_id'] and c['evidence'][0]['source_char_start']<end and c['evidence'][0]['source_char_end']>start]
     ids+=replacement('an-update-on-independent-evaluators','Updated on October 16')
     add('effective_window',sorted(set(ids)),'',u['canonical'],'The paragraph carrying native footnote 2 is explicitly clarified October 16: METR publication/redaction terms and Anthropic final category decisions. The immutable original October 15 terms are not reconstructed from this later captured edition.',from_date='2026-10-16')
   if path=='/responsible-scaling-policy/updates':
    text=(ROOT/u['text_path']).read_text();section_specs=[('## Principles for data retention','2026-05-05','Native archived section states the goal was completed and removed May 5.'),('## Launching moonshot R&D projects','2026-04-02','Native archived section states the initial goal was completed April 2 and a revised version remains on the Roadmap; this does not establish completion of current successor projects.'),('## A roadmap for policymakers','2026-07-08','Native archived section states the prior goal was fulfilled July 8; a replacement was planned.')]
    for heading,until,reason in section_specs:
     start=text.find(heading)
     if start<0:continue
     m=re.search(r'(?m)^## ',text[start+len(heading):]);end=start+len(heading)+m.start() if m else len(text)
     ids=[c['claim_id'] for c in claims if c['evidence'][0]['analysis_unit_id']==u['analysis_unit_id'] and c['evidence'][0]['source_char_start']<end and c['evidence'][0]['source_char_end']>start]
     add('historical_only',ids,until,u['canonical'],reason)
    add('historical_only',[],self.date,u['canonical'],'This captured source explicitly describes itself as an archive of former goals. Observation-date exclusion for any unassigned/version-ambiguous remainder is a conservative current-evidence boundary, not an inferred completion date.',unitids=[u['analysis_unit_id']])
   if path=='/legal/aup':add('effective_window',[],'',u['canonical'],'This captured policy text states Effective November 12, 2026; announcement is already public but these terms are future-effective.',from_date='2026-11-12',unitids=[u['analysis_unit_id']])
   elif path=='/legal/archive/22742366-2ef0-4c7a-a833-6523f10d3944':add('effective_window',[],'2026-11-12',u['canonical'],'AMind reconstructs this prior-edition retrieval window from its September 15, 2025 effective header and the announced November 12, 2026 transition. This AI-curated interval is not independent primary-source proof that this exact archived edition remained operative on every intervening day; verify the specific edition and transition chain before asserting dated applicability.',from_date='2025-09-15',unitids=[u['analysis_unit_id']])
   elif path.startswith('/legal/'):
    text=(ROOT/u['text_path']).read_text();m=re.search(r'\bEffective\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2})',text[:600],re.I)
    if m:
     date=parse_date(m.group(1))
     if date:add('effective_window',[],'',u['canonical'],'Native policy header states '+m.group()+'. This is an effective date, not a publication date; do not apply this captured edition before that date.',from_date=date,unitids=[u['analysis_unit_id']])
   elif path=='/research/your-thoughts-on-ai':
    ids=[c['claim_id'] for c in claims if c['evidence'][0]['analysis_unit_id']==u['analysis_unit_id'] and any(x in c['evidence'][0]['exact_quote'].casefold() for x in ['we’d like you to participate','you can participate here','this study will run from september 29 to october 6'])]
    add('historical_only',ids,'2026-10-07',u['canonical'],'Recruitment window ended October 6; exclude only active participation/time-window invitations, preserve methodology, privacy and study-limitations evidence.')
  oldids={c['claim_id'] for c in rows(self.base/'data/atomic-claims.jsonl.gz')};newids={c['claim_id'] for c in claims};uids={u['analysis_unit_id'] for u in units}
  for s in statuses:assert set(s['target_claim_ids'])<=oldids|newids;assert set(s['replacement_claim_ids'])<=newids;assert set(s['target_analysis_unit_ids'])<=uids
  putrows(self.release/'delta/current-status.jsonl',statuses)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['discover','collect','build','review','all']);p.add_argument('--date',default='2026-10-18');p.add_argument('--since',default='2026-09-08T01:03:42+08:00');p.add_argument('--baseline',default='release/amind-v1-increment-2026-09-08');p.add_argument('--release',default='release/amind-v1-increment-2026-10-18');p.add_argument('--vault',help='Historical corpus required explicitly for discover/build/all; collect/review consume already captured release inputs');p.add_argument('--urls');p.add_argument('--deps',action='append',default=[]);p.add_argument('--workers',type=int,default=10);p.add_argument('--max-candidates',type=int,default=220);p.add_argument('--max-bytes',type=int,default=96*1024*1024);p.add_argument('--retry-failed',action='store_true');a=p.parse_args()
 for path in a.deps:sys.path.insert(0,path)
 try:
  r=Refresh(a)
  if a.stage in {'discover','all'}:r.discover()
  if a.stage in {'collect','all'}:r.collect()
  if a.stage in {'build','all'}:r.build()
  if a.stage in {'review','all'}:r.review()
 except ComparisonInputError as e:p.error(str(e))
if __name__=='__main__':main()
