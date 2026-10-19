#!/usr/bin/env python3
"""Run application-skill offline tests and write an evidence manifest; no model calls."""
import argparse
import datetime
import hashlib
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from check_amind_capability_map import check

class EvidenceResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs): super().__init__(*args,**kwargs); self.passed=[]
    def addSuccess(self,test): super().addSuccess(test); self.passed.append(test.id())


def verify(output):
    loader=unittest.TestLoader();suite=unittest.TestSuite()
    for module in ('test_amind_app_skills','test_amind_capability_kernel','test_amind_behavior_regressions','test_amind_eval_reporting'):
        suite.addTests(loader.loadTestsFromName(module))
    result=unittest.TextTestRunner(verbosity=1,resultclass=EvidenceResult).run(suite)
    inventory={}
    for name in ('amind-engineering','eval-improve'):
        base=ROOT/'skills'/name
        inventory[name]={p.relative_to(base).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(base.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    evidence={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tests_run':result.testsRun,
              'passed':result.passed,'failures':[{'test':str(t),'details':detail} for t,detail in result.failures+result.errors],
              'successful':result.wasSuccessful(),'source_map':check(),'package_hashes':inventory,
              'scope':'Synthetic local processes, deterministic fixtures and package/install checks. No live target/judge API or independent skill-agent run.'}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'tests':result.testsRun,'successful':result.wasSuccessful(),'evidence':str(output)},ensure_ascii=False))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.exit(verify(a.output))
