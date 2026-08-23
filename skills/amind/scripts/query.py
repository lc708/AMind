#!/usr/bin/env python3
"""Query the compact AMind evidence kernel with the Python standard library."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
MANIFEST_SCHEMA = "amind-skill-evidence-manifest"


class AMindSkillError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AMindSkillError(message)


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AMindSkillError(f"cannot read JSON at {path}: {error}") from error
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    require(path.is_file(), f"missing file: {path}")
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as error:
                    raise AMindSkillError(f"invalid JSONL at {path}:{line_number}: {error.msg}") from error
                require(isinstance(value, dict), f"expected object at {path}:{line_number}")
                yield value
    except (OSError, UnicodeError) as error:
        raise AMindSkillError(f"cannot read JSONL at {path}: {error}") from error


def load_manifest(data_root: Path) -> dict[str, Any]:
    manifest = read_json(data_root / "manifest.json")
    require(manifest.get("schema_name") == MANIFEST_SCHEMA, "invalid AMind skill manifest schema")
    require(manifest.get("schema_version") == 1, "unsupported AMind skill manifest version")
    require(manifest.get("skill_id") == "amind", "invalid AMind skill identity")
    require(manifest.get("release_id") == "amind-v1", "invalid AMind release identity")
    counts = manifest.get("counts")
    require(isinstance(counts, dict), "missing AMind skill counts")
    for field in (
        "full_release_atomic_claims",
        "full_release_analysis_units",
        "human_reviewed_evidence_rows",
        "human_reviewed_evidence_rows_per_theme",
        "preserved_tensions",
        "themes",
        "voice_profiles",
    ):
        require(type(counts.get(field)) is int and counts[field] >= 0, f"invalid count: {field}")
    return manifest


def load_rows(data_root: Path, name: str) -> list[dict[str, Any]]:
    return list(iter_jsonl(data_root / name))


def json_output(rows: Iterable[dict[str, Any]]) -> None:
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))


def printable_voice(row: dict[str, Any]) -> str:
    voice = row.get("voice") or {}
    return voice.get("name") or voice.get("organization") or "Unattributed source voice"


def print_evidence(row: dict[str, Any]) -> None:
    print(f"{row['claim_id']}  [{row['theme_id']}]")
    print(f"Proposition: {row['proposition']}")
    print(f"Voice: {printable_voice(row)}")
    print(f"Source: {row['source_title']}")
    if row.get("source_published_at"):
        print(f"Published: {row['source_published_at']}")
    print(f"URL: {row['source_canonical']}")
    print(f"Quote: {row['exact_quote']}")
    print(f"Review: {row['review']['semantic_status']} / {row['review']['support_mode']}")


def tokenize_query(query: str) -> list[str]:
    return [token for token in re.split(r"\s+", query.casefold().strip()) if token]


def searchable_text(row: dict[str, Any], theme: dict[str, Any] | None = None) -> str:
    voice = row.get("voice") or {}
    theme = theme or {}
    values = (
        row.get("claim_id"),
        row.get("theme_id"),
        row.get("proposition"),
        row.get("exact_quote"),
        row.get("source_title"),
        row.get("source_canonical"),
        voice.get("name"),
        voice.get("organization"),
        theme.get("name_zh"),
        theme.get("thesis_zh"),
        " ".join(theme.get("keywords") or []),
    )
    return "\n".join(str(value) for value in values if value).casefold()


def command_summary(data_root: Path, args: argparse.Namespace) -> int:
    del args
    manifest = load_manifest(data_root)
    counts = manifest["counts"]
    print(f"AMind skill {manifest['skill_version']} — evidence kernel from AMind v1")
    print(f"Human-reviewed evidence rows: {counts['human_reviewed_evidence_rows']}")
    print(f"Reviewed evidence per theme: {counts['human_reviewed_evidence_rows_per_theme']}")
    print(f"Themes: {counts['themes']}")
    print(f"Voice profiles: {counts['voice_profiles']}")
    print(f"Preserved tensions: {counts['preserved_tensions']}")
    print(f"Full release: {counts['full_release_analysis_units']} analysis units / {counts['full_release_atomic_claims']} atomic claims")
    return 0


def command_search(data_root: Path, args: argparse.Namespace) -> int:
    query = args.query.strip()
    tokens = tokenize_query(query)
    require(tokens, "search query must not be empty")
    require(1 <= args.limit <= 54, "--limit must be between 1 and 54")
    phrase = query.casefold()
    scored: list[tuple[int, str, dict[str, Any]]] = []
    themes = {row["theme_id"]: row for row in load_rows(data_root, "theme-catalog.jsonl")}
    for row in load_rows(data_root, "evidence-kernel.jsonl"):
        text = searchable_text(row, themes.get(row.get("theme_id")))
        token_hits = sum(1 for token in tokens if token in text)
        if not token_hits:
            continue
        phrase_bonus = 4 if phrase in text else 0
        scored.append((phrase_bonus + token_hits, row["claim_id"], row))
    matches = [row for _, _, row in sorted(scored, key=lambda item: (-item[0], item[1]))[: args.limit]]
    if args.json:
        json_output(matches)
    else:
        for index, row in enumerate(matches):
            if index:
                print()
            print_evidence(row)
    if not matches:
        print("No reviewed evidence matched the bounded kernel.", file=sys.stderr)
        return 1
    return 0


def command_show(data_root: Path, args: argparse.Namespace) -> int:
    for row in load_rows(data_root, "evidence-kernel.jsonl"):
        if row.get("claim_id") != args.claim_id:
            continue
        if args.json:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            print_evidence(row)
        return 0
    print(f"Unknown reviewed claim ID: {args.claim_id}", file=sys.stderr)
    return 1


def command_themes(data_root: Path, args: argparse.Namespace) -> int:
    rows = load_rows(data_root, "theme-catalog.jsonl")
    if args.theme_id:
        rows = [row for row in rows if row.get("theme_id") == args.theme_id]
        if not rows:
            print(f"Unknown theme: {args.theme_id}", file=sys.stderr)
            return 1
    if args.json:
        json_output(rows)
    else:
        for row in rows:
            print(f"{row['theme_id']}: {row['name_zh']}")
            print(f"  {row['thesis_zh']}")
    return 0


def command_voices(data_root: Path, args: argparse.Namespace) -> int:
    rows = load_rows(data_root, "voice-profiles.jsonl")
    if args.voice:
        needle = args.voice.casefold()
        rows = [row for row in rows if needle in row.get("name", "").casefold() or needle == row.get("voice_id", "").casefold()]
        if not rows:
            print(f"Unknown voice: {args.voice}", file=sys.stderr)
            return 1
    if args.json:
        json_output(rows)
    else:
        for row in rows:
            print(f"{row['voice_id']}: {row['name']}")
            print(f"  {row['summary_zh']}")
    return 0


def command_tensions(data_root: Path, args: argparse.Namespace) -> int:
    rows = load_rows(data_root, "synthesis-tensions.jsonl")
    if args.json:
        json_output(rows)
    else:
        for row in rows:
            print(f"{row['tension_id']}: {row['name_zh']}")
            print(f"  {row['summary_zh']}")
    return 0


def parser() -> argparse.ArgumentParser:
    answer = argparse.ArgumentParser(description=__doc__)
    answer.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    commands = answer.add_subparsers(dest="command", required=True)

    summary = commands.add_parser("summary", help="show compact and full-release counts")
    summary.set_defaults(handler=command_summary)

    search = commands.add_parser("search", help="search the reviewed evidence kernel")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.add_argument("--json", action="store_true")
    search.set_defaults(handler=command_search)

    show = commands.add_parser("show", help="show one reviewed evidence row")
    show.add_argument("claim_id")
    show.add_argument("--json", action="store_true")
    show.set_defaults(handler=command_show)

    themes = commands.add_parser("themes", help="list or show framework themes")
    themes.add_argument("theme_id", nargs="?")
    themes.add_argument("--json", action="store_true")
    themes.set_defaults(handler=command_themes)

    voices = commands.add_parser("voices", help="list or show bounded voice profiles")
    voices.add_argument("voice", nargs="?")
    voices.add_argument("--json", action="store_true")
    voices.set_defaults(handler=command_voices)

    tensions = commands.add_parser("tensions", help="list preserved framework tensions")
    tensions.add_argument("--json", action="store_true")
    tensions.set_defaults(handler=command_tensions)
    return answer


def main() -> int:
    args = parser().parse_args()
    data_root = args.data_root.resolve()
    load_manifest(data_root)
    return args.handler(data_root, args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AMindSkillError as error:
        print(f"AMind error: {error}", file=sys.stderr)
        raise SystemExit(2)
