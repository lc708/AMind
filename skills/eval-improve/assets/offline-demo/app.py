#!/usr/bin/env python3
"""Synthetic adapter example. Replace this body with the real application entry point."""
import json
import sys
request = json.load(sys.stdin)
text = request['input']['text']
output = text.upper() if request['context']['config'].get('uppercase') else text
print(json.dumps({'output': output, 'model': 'synthetic-fixture', 'cost_usd': 0,
                  'usage': {'input_tokens': 0, 'output_tokens': 0}, 'synthetic': True}))
