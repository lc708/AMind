#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys
BASE=Path(__file__).resolve().parent

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def actual(root):return {p.relative_to(root).as_posix():digest(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
f=json.loads((BASE/'freeze.json').read_text());tasks=json.loads((BASE/'tasks.json').read_text());checks={'metadata':digest(BASE/'tasks.json')==f['task_metadata_sha256'],'rubric':digest(BASE/'private/rubric.json')==f['private_rubric_sha256'],'controls':digest(BASE/'private/grader-validation.json')==f['control_validation_sha256']}
for t in tasks['tasks']:checks[t['id']]=actual(Path(t['repo_path']))==f['public_repos'][t['id']]['files']
for name,h in f['private_grader_files_sha256'].items():checks[name]=digest(BASE/'private'/name)==h
for name,files in f['private_reference_files_sha256'].items():checks['reference/'+name]=actual(BASE/'private/reference'/name)==files
print(json.dumps({'all_passed':all(checks.values()),'checks':checks}));sys.exit(0 if all(checks.values()) else 1)
