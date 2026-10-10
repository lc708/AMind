#!/usr/bin/env python3
"""Locate prompt/config/tool surfaces in explicit source paths. Heuristics, never automatic edits."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RULES={
 'prompt_assembly':r'(?i)(system_prompt|developer_prompt|instructions\s*[:=]|role\s*["\x27]?\s*:\s*["\x27](system|developer))',
 'model_config':r'(?i)(model\s*[:=]|reasoning_effort|reasoning\s*[:=]|max_output_tokens|temperature|top_p)',
 'tool_contract':r'(?i)(tool_choice|function_call|tools\s*[:=]|input_schema|parameters\s*[:=])',
 'state_ownership':r'(previous_response_id|conversation_id|context_management|encrypted_content|compact_threshold)',
 'pressure_candidate':r'(?i)\b(MUST|NEVER|ALWAYS|CRITICAL|IMPORTANT)\b',
 'fragile_format_candidate':r'(?i)(start (your |the )?(answer|response) with|begin with|exactly [0-9]+ (words|sentences)|think step.by.step)',
 'routing_surface':r'(?i)^(description:|name:)|allowed.tools|\btrigger\b'
}
EXCLUDED={'.git','node_modules','.venv','venv','__pycache__','.eval-improve','.codex-tmp'}
SUFFIXES={'.py','.ts','.tsx','.js','.mjs','.jsx','.md','.json','.yaml','.yml','.toml','.go','.rb','.java','.cs','.php','.txt'}


def inventory(root, paths, git_provenance=False):
    root=root.resolve(); findings=[]; skipped=[]; files=set()
    for given in paths:
        path=root/given
        if path.is_symlink(): skipped.append({'path':str(given),'reason':'symlink'}); continue
        if path.is_dir():
            candidates=path.rglob('*')
        else: candidates=[path]
        for candidate in candidates:
            if candidate.is_symlink() or not candidate.is_file(): continue
            resolved=candidate.resolve()
            if root not in resolved.parents: raise ValueError('source path escapes root')
            rel=resolved.relative_to(root)
            if any(x in EXCLUDED for x in rel.parts) or candidate.suffix not in SUFFIXES: continue
            if candidate.name.startswith('.env') or re.search(r'(?i)(secret|credential|private.key)',candidate.name):
                skipped.append({'path':str(rel),'reason':'credential-like filename'}); continue
            if candidate.stat().st_size>2*1024*1024: skipped.append({'path':str(rel),'reason':'size'}); continue
            files.add(resolved)
    for path in sorted(files):
        rel=path.relative_to(root).as_posix()
        try: lines=path.read_text().splitlines()
        except UnicodeError: skipped.append({'path':rel,'reason':'nontext'}); continue
        hits=[]
        for n,line in enumerate(lines,1):
            rules=[key for key,pattern in RULES.items() if re.search(pattern,line)]
            if rules: hits.append({'line':n,'signals':rules})
        if not hits: continue
        provenance=None
        if git_provenance:
            proc=subprocess.run(['git','log','-1','--format=%h %cs','--',rel],cwd=root,text=True,capture_output=True,timeout=10)
            provenance=proc.stdout.strip() if proc.returncode==0 else None
        findings.append({'path':rel,'hits':hits,'last_commit':provenance})
    return {'files_scanned':len(files),'surfaces':findings,'skipped':skipped,
            'limits':'Locations only; no source content is copied. Signals are hypotheses. Inspect effective rendered prompts and provenance before classifying or editing. Unmatched/dynamically loaded prompts remain possible.'}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--root',type=Path,required=True)
    p.add_argument('--paths',nargs='+',required=True); p.add_argument('--git-provenance',action='store_true'); a=p.parse_args()
    try: print(json.dumps(inventory(a.root,a.paths,a.git_provenance),ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,subprocess.SubprocessError) as e: print(json.dumps({'error':str(e)})); return 2
if __name__=='__main__': sys.exit(main())
