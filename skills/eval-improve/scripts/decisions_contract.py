#!/usr/bin/env python3
"""Offline preflight for Decisions GA message/JSON/image/question contracts.

This implements a documented message subset, not a replacement SDK schema or
server availability check. Tool-history items must use the installed SDK's full
schema. It never contacts a service or fetches image URLs.
"""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
from kernel_common import canonical, read_json

SOURCE = 'https://developers.openai.com/api/reference/resources/decisions/methods/create'


def json_evidence(data):
    if not isinstance(data, dict) and not (isinstance(data, list) and all(isinstance(x, dict) for x in data)):
        raise ValueError('input_json data must be an object or array of objects')
    if len(canonical(data).encode('utf-8')) > 256 * 1024:
        raise ValueError('input_json exceeds 256 KiB of compact UTF-8 JSON')
    count = 0
    def walk(value, depth):
        nonlocal count
        count += 1
        if count > 10000: raise ValueError('input_json exceeds 10000 values')
        if isinstance(value, (dict, list)):
            depth += 1
            if depth > 32: raise ValueError('input_json exceeds 32 container levels')
            if isinstance(value, dict) and any(not isinstance(k, str) for k in value):
                raise ValueError('JSON object keys must be strings')
            for child in value.values() if isinstance(value, dict) else value: walk(child, depth)
    walk(data, 0)


def parts(content, *, role, question=False):
    if isinstance(content, str): return {'images': 0, 'json': 0, 'breakpoints': 0}
    if not isinstance(content, list) or len(content) > 16384 or (question and not content):
        raise ValueError('content parts must be a bounded array; question instructions cannot be empty')
    result = {'images': 0, 'json': 0, 'breakpoints': 0}
    for part in content:
        if not isinstance(part, dict): raise ValueError('content part must be an object')
        kind = part.get('type', 'input_text')
        if kind == 'input_text':
            allowed = {'type', 'text'}
            if not question: allowed.add('prompt_cache_breakpoint')
            if not isinstance(part.get('text'), str): raise ValueError('input_text needs text')
        elif kind == 'input_image' and role == 'user':
            allowed = {'type', 'image_url', 'detail'}
            if not question: allowed.add('prompt_cache_breakpoint')
            url = part.get('image_url')
            if not isinstance(url, str) or not (url.startswith('data:') or
                    (urlsplit(url).scheme in {'http', 'https'} and urlsplit(url).netloc)):
                raise ValueError('image_url must be inline data or HTTP(S); file IDs are unsupported')
            if part.get('detail') not in {None, 'low', 'high', 'auto', 'original'}:
                raise ValueError('unsupported image detail')
            result['images'] += 1
        elif kind == 'input_json' and role == 'user' and not question:
            allowed = {'type', 'data'}
            if 'data' not in part: raise ValueError('input_json needs data')
            json_evidence(part['data']); result['json'] += 1
        else: raise ValueError('unsupported content for this role/local preflight subset')
        if set(part) - allowed: raise ValueError('unadapted content fields')
        point = part.get('prompt_cache_breakpoint')
        if point is not None:
            if not isinstance(point, dict) or set(point) - {'mode'} or point.get('mode', 'explicit') != 'explicit':
                raise ValueError('Decisions breakpoint supports explicit mode only; TTL is request-level')
            result['breakpoints'] += 1
    return result


def validate_request(request):
    allowed = {'model', 'input', 'questions', 'prompt_cache_key', 'prompt_cache_options', 'safety_identifier'}
    if not isinstance(request, dict) or set(request) - allowed:
        raise ValueError('unadapted request fields; validate other surfaces with the installed SDK')
    if not isinstance(request.get('model'), str) or not request['model']:
        raise ValueError('retain an explicit model; the preflight never selects one')
    # Availability/model eligibility is deliberately not inferred from a local
    # test. The official guide currently lists gpt-6-luna; preserve the request.
    summary = {'shared_images': 0, 'question_images': 0, 'json_parts': 0, 'explicit_breakpoints': 0}
    evidence = request.get('input')
    if isinstance(evidence, str): pass
    elif isinstance(evidence, list):
        if len(evidence) > 16384: raise ValueError('too many input items')
        for message in evidence:
            if not isinstance(message, dict) or set(message) - {'type', 'role', 'content'}:
                raise ValueError('tool history/other input items require the full installed SDK schema')
            role = message.get('role', 'user')
            if message.get('type', 'message') != 'message' or role not in {'user', 'developer', 'system'}:
                raise ValueError('this local preflight covers user/developer/system messages only')
            if 'content' not in message: raise ValueError('message needs content')
            found = parts(message['content'], role=role)
            summary['shared_images'] += found['images']; summary['json_parts'] += found['json']
            summary['explicit_breakpoints'] += found['breakpoints']
    else: raise ValueError('input must be a string or supported message array')
    questions = request.get('questions')
    if not isinstance(questions, list) or not 1 <= len(questions) <= 400:
        raise ValueError('Decisions requires 1 to 400 questions')
    names = set()
    for question in questions:
        if not isinstance(question, dict): raise ValueError('question must be an object')
        kind = question.get('type', 'predicate')
        keys = {'type', 'name', 'instructions'}
        if kind == 'choice': keys.add('choices')
        elif kind == 'score': keys.add('levels')
        elif kind != 'predicate': raise ValueError('unsupported question type')
        if set(question) - keys or 'instructions' not in question: raise ValueError('invalid question fields')
        if 'name' in question:
            name = question['name']
            if not isinstance(name, str) or name in names: raise ValueError('question names must be unique strings')
            names.add(name)
        found = parts(question['instructions'], role='user', question=True)
        summary['question_images'] += found['images']
        if kind == 'choice':
            choices = question.get('choices')
            if not isinstance(choices, list) or not 2 <= len(choices) <= 255:
                raise ValueError('choice requires 2 to 255 options')
            values = set()
            for choice in choices:
                if not isinstance(choice, dict) or set(choice) - {'value', 'description'}:
                    raise ValueError('invalid choice fields')
                value = choice.get('value')
                if type(value) not in {str, bool}: raise ValueError('choice values must be strings or booleans')
                typed = (type(value).__name__, value)
                if typed in values: raise ValueError('duplicate typed choice value')
                values.add(typed)
                if 'description' in choice and not isinstance(choice['description'], str):
                    raise ValueError('choice description must be a string')
        if kind == 'score':
            levels = question.get('levels')
            if not isinstance(levels, list) or not 2 <= len(levels) <= 10:
                raise ValueError('score requires 2 to 10 ordered levels')
            for level in levels:
                if not isinstance(level, dict) or set(level) - {'label', 'description'}:
                    raise ValueError('invalid score level')
                if not isinstance(level.get('label'), str) or ('description' in level and not isinstance(level['description'], str)):
                    raise ValueError('score level needs label and optional string description')
    options = request.get('prompt_cache_options')
    if options is None: options = {}
    if not isinstance(options, dict) or set(options) - {'mode', 'ttl'}:
        raise ValueError('unadapted Decisions prompt_cache_options')
    if options.get('ttl', '30m') != '30m': raise ValueError('Decisions currently supports only 30m TTL')
    mode = options.get('mode', 'implicit')
    if mode is None: mode = 'implicit'
    if mode not in {'implicit', 'explicit'}: raise ValueError('invalid cache mode')
    summary['selected_explicit_write_slots'] = min(summary['explicit_breakpoints'], 3 if mode == 'implicit' else 4)
    for key, maximum in [('prompt_cache_key', 64), ('safety_identifier', 128)]:
        if key in request and request[key] is not None and (not isinstance(request[key], str) or len(request[key]) > maximum):
            raise ValueError('invalid ' + key)
    return {'verdict': 'PASS', 'scope': 'local message/JSON/image/question preflight; not complete server validation',
            'model': request['model'], 'model_availability_checked': False, 'questions': len(questions),
            **summary, 'source': SOURCE, 'checked_at': '2026-10-30'}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('request', type=Path)
    args = parser.parse_args()
    try: print(json.dumps(validate_request(read_json(args.request)), indent=2)); return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print(json.dumps({'verdict': 'FAIL', 'error': str(error)})); return 2


if __name__ == '__main__': sys.exit(main())
