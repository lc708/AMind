#!/usr/bin/env python3
"""Price normalized usage with an explicit dated rate card; never invent missing spend."""
import argparse
import json
import sys
from pathlib import Path
from kernel_common import finite, read_json, read_jsonl, sha


def nonnegative(value, name, integer=False):
    if not finite(value) or value < 0 or (integer and type(value) is not int): raise ValueError('invalid ' + name)
    return value


def price(event, card):
    if event.get('cost_usd') is not None:
        return {'status':'reported','cost_usd':nonnegative(event['cost_usd'],'reported cost'),
                'basis':event.get('cost_source','adapter report; not independently reconciled')}
    rate = card.get('models',{}).get(event.get('model'))
    usage = event.get('usage')
    if rate is None or not isinstance(usage,dict): return {'status':'unknown','cost_usd':None,'reason':'missing rate or usage'}
    if 'input_tokens' not in usage or 'output_tokens' not in usage:
        return {'status':'unknown','cost_usd':None,'reason':'missing token totals'}
    incoming=nonnegative(usage['input_tokens'],'input tokens',True)
    outgoing=nonnegative(usage['output_tokens'],'output tokens',True)
    cached=usage.get('cached_input_tokens',usage.get('input_tokens_details',{}).get('cached_tokens'))
    if cached is None: return {'status':'unknown','cost_usd':None,'reason':'cache counter missing; normalize explicitly'}
    cached=nonnegative(cached,'cached input tokens',True)
    reasoning=usage.get('reasoning_tokens',usage.get('output_tokens_details',{}).get('reasoning_tokens',0))
    nonnegative(reasoning,'reasoning tokens',True)
    if cached>incoming or reasoning>outgoing: raise ValueError('cached/reasoning counters must be subsets of input/output totals')
    for field in ('input_per_million','cached_input_per_million','output_per_million'):
        nonnegative(rate[field],field)
    parts={'uncached_input':(incoming-cached)*rate['input_per_million']/1e6,
           'cached_input':cached*rate['cached_input_per_million']/1e6,
           'output_including_reasoning':outgoing*rate['output_per_million']/1e6}
    extras=event.get('external_charges_usd',[])
    if not isinstance(extras,list): raise ValueError('external_charges_usd must be a list')
    parts['external_known']=sum(nonnegative(x,'external charge') for x in extras)
    complete=event.get('all_billable_usage_included') is True
    return {'status':'estimated_complete' if complete else 'estimated_partial','cost_usd':sum(parts.values()),
            'components':parts,'rate_card_version':card['version'],'rate_card_sha256':sha(card),
            'warning':None if complete else 'Tools, storage, sandbox, retries or other charges may be absent; not total task cost'}


def profile(events, card):
    if any(not isinstance(card.get(key),str) or not card[key] for key in ('version','effective_date','source')):
        raise ValueError('rate card requires version, effective_date and source')
    rows=[{'id':e.get('id'), 'stage':e.get('stage'), 'model':e.get('model'), **price(e,card)} for e in events]
    unknown=sum(r['status']=='unknown' for r in rows); partial=sum(r['status']=='estimated_partial' for r in rows)
    known=sum(r['cost_usd'] for r in rows if r['cost_usd'] is not None)
    return {'rows':rows,'known_or_estimated_subtotal_usd':known,'unknown_events':unknown,'partial_events':partial,
            'total_cost_usd':known if not unknown and not partial else None,
            'basis':'per event; input includes cache, output includes reasoning; do not double-count subsets'}


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--events',type=Path,required=True); p.add_argument('--rates',type=Path,required=True)
    a=p.parse_args()
    try: print(json.dumps(profile(read_jsonl(a.events),read_json(a.rates)),ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,KeyError,TypeError) as e: print(json.dumps({'error':str(e)})); return 2
if __name__=='__main__': sys.exit(main())
