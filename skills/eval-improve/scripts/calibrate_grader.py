#!/usr/bin/env python3
"""Audit binary human/judge agreement, repeat stability and pairwise order bias offline."""
import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from kernel_common import read_jsonl


def calibrate(rows):
    if not rows: raise ValueError('calibration requires adjudicated examples')
    counts={'tp':0,'tn':0,'fp':0,'fn':0}; disagreements=[]; grouped={}; swaps=[]
    seen=set()
    for row in rows:
        key=(row.get('id'),row.get('rep',0))
        if not isinstance(key[0],str) or not key[0] or type(key[1]) is not int or key[1]<0 or key in seen:
            raise ValueError('unique string id and nonnegative rep required')
        seen.add(key)
        human,grade=row.get('human'),row.get('grade')
        if type(human) not in (int,bool) or type(grade) not in (int,bool) or human not in (0,1) or grade not in (0,1):
            raise ValueError('human and grade must be adjudicated binary labels')
        counts['tp' if grade and human else 'fp' if grade else 'fn' if human else 'tn']+=1
        if human!=grade: disagreements.append({'id':key[0],'rep':key[1],'human':human,'grade':grade})
        grouped.setdefault(key[0],[]).append(grade)
        if 'swapped_grade' in row:
            swapped=row['swapped_grade']
            if type(swapped) not in (int,bool) or swapped not in (0,1): raise ValueError('swapped_grade must be binary')
            swaps.append(grade != 1-swapped)
    n=len(rows); correct=counts['tp']+counts['tn']; p=correct/n
    # Agreement is descriptive: repeated labels and curated examples are not independent population samples.
    return {'examples':len(grouped),'judgments':n,'confusion':counts,'agreement':p,
            'precision':counts['tp']/(counts['tp']+counts['fp']) if counts['tp']+counts['fp'] else None,
            'recall':counts['tp']/(counts['tp']+counts['fn']) if counts['tp']+counts['fn'] else None,
            'disagreements':disagreements,
            'unstable_cases':[key for key,values in grouped.items() if len(set(values))>1],
            'order_inconsistency_rate':statistics.mean(swaps) if swaps else None,
            'ready_for_review':not disagreements and not any(swaps) and all(len(set(v))==1 for v in grouped.values()),
            'limits':'Agreement on this calibration sample is not construct validity or generalization. Resolve disagreements, adversarial rubric attacks and rubric blind spots with humans before freezing.'}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('labels',type=Path); a=p.parse_args()
    try: print(json.dumps(calibrate(read_jsonl(a.labels)),ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({'error':str(e)})); return 2
if __name__=='__main__': sys.exit(main())
