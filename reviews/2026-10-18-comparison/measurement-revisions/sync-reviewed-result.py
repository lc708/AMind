import datetime,hashlib,json,shutil,subprocess
from pathlib import Path
r=Path.cwd();p=r/'reviews/2026-10-18-comparison';t=r/'.codex-tmp/contrast-2026-10-18';o=Path('/Users/damonalbarn/Work/AMind');before=json.loads((t/'sync-plan.json').read_text())
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
# Preserve the evidence assembly code with the finished report.
shutil.copyfile(t/'finalize_evidence.py',p/'measurement-revisions/finalize-evidence.py')
shutil.copyfile(t/'sync_reviewed_result.py',p/'measurement-revisions/sync-reviewed-result.py')
files=[x for x in subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],text=True).split('\0') if x and (r/x).is_file()]
changed={}
for n in files:
 a,b=sha(o/n),sha(r/n)
 if a==b:continue
 if n in before['files']:assert a==before['files'][n]['original_sha256'],('concurrent original edit',n)
 else:assert a is None,('unreviewed existing difference',n)
 changed[n]={'original_sha256':a,'candidate_sha256':b}
for n,h in before['preserved_user_files'].items():assert sha(o/n)==h,('user file changed',n)
backup=t/'original-before-sync'
for n,fp in changed.items():
 if fp['original_sha256'] is not None:
  b=backup/n;b.parent.mkdir(parents=True,exist_ok=True)
  if b.exists():assert sha(b)==fp['original_sha256']
  else:shutil.copyfile(o/n,b)
 q=o/n;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(r/n,q)
 assert sha(q)==fp['candidate_sha256'],('copy mismatch',n)
for n,h in before['preserved_user_files'].items():assert sha(o/n)==h
# Check every authorized tracked/new candidate, including unchanged packages.
assert all(sha(o/n)==sha(r/n) for n in files)
receipt={'verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original':str(o),'worktree':str(r),'branch':'codex/amind-october-refresh','copied_files':len(changed),'replaced_existing_files':sum(v['original_sha256'] is not None for v in changed.values()),'all_candidate_files_match':True,'candidate_file_count':len(files),'preserved_user_files':before['preserved_user_files'],'user_files_unchanged':True,'concurrent_edit_guard':'Existing original differences matched pre-sync hashes; new artifacts did not replace existing original files.','original_before_sync_backup':str(backup),'files':changed,'git_commit_created':False,'pushed':False}
q=p/'validation/workspace-sync.json';q.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');dest=o/q.relative_to(r);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(q,dest)
print({k:v for k,v in receipt.items() if k not in ['files','preserved_user_files']})
