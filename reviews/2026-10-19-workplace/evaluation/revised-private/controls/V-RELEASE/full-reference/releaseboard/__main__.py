"""Build one release dashboard JSON from saved local evidence."""
import argparse
import json
from pathlib import Path
from .report import build


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bundle', required=True, type=Path)
    p.add_argument('--rates', required=True, type=Path)
    p.add_argument('--variant', required=True)
    a = p.parse_args()
    try:
        manifest = json.loads((a.bundle / 'manifest.json').read_text())
        report = build(manifest, jsonl(a.bundle / 'results.jsonl'), jsonl(a.bundle / 'attempts.jsonl'),
                       json.loads(a.rates.read_text()), a.variant)
        print(json.dumps(report, allow_nan=False)); return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)})); return 2


if __name__ == '__main__':
    raise SystemExit(main())
