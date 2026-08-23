#!/usr/bin/env python3
"""Browse the self-contained AMind v1 release with the Python standard library."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any, Iterable


SCRIPT = Path(__file__).resolve()
DEFAULT_RELEASE = (
    SCRIPT.parent
    if (SCRIPT.parent / "manifest.json").is_file()
    else SCRIPT.parents[1] / "release/amind-v1"
)
MANIFEST_SCHEMA_NAME = "amind-v1-release-manifest"
MANIFEST_SCHEMA_VERSION = 1
RELEASE_ID = "amind-v1"
RELEASE_NAME = "AMind v1"
SUMMARY_COUNT_FIELDS = (
    "analysis_units",
    "body_units",
    "bounded_unavailable_units",
    "passages",
    "claims",
    "themes",
    "representative_evidence_rows",
)


class AMindError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AMindError(message)


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        details = f"{error.msg} (line {error.lineno}, column {error.colno})"
        raise AMindError(f"invalid JSON at {path}: {details}") from error
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def validate_manifest(manifest: dict[str, Any], path: Path) -> dict[str, Any]:
    require(manifest.get("schema_name") == MANIFEST_SCHEMA_NAME, f"invalid AMind manifest schema: {path}")
    require(
        type(manifest.get("schema_version")) is int
        and manifest["schema_version"] == MANIFEST_SCHEMA_VERSION,
        f"invalid AMind manifest schema version: {path}",
    )
    require(manifest.get("release_id") == RELEASE_ID, f"invalid AMind release ID: {path}")
    require(manifest.get("release_name") == RELEASE_NAME, f"invalid AMind release name: {path}")
    release_date = manifest.get("release_date")
    require(isinstance(release_date, str) and bool(release_date.strip()), f"missing or invalid release_date: {path}")
    counts = manifest.get("counts")
    require(isinstance(counts, dict), f"missing or invalid manifest counts: {path}")
    for field in SUMMARY_COUNT_FIELDS:
        value = counts.get(field)
        require(
            type(value) is int and value >= 0,
            f"missing or invalid manifest count {field}: {path}",
        )
    return manifest


def load_manifest(path: Path) -> dict[str, Any]:
    return validate_manifest(read_json(path), path)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    require(path.is_file(), f"missing file: {path}")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise AMindError(f"invalid JSONL at {path}:{line_number}") from error
            require(isinstance(value, dict), f"expected JSON object at {path}:{line_number}")
            yield value


def load_units(release_root: Path) -> dict[str, dict[str, Any]]:
    rows = iter_jsonl(release_root / "data/analysis-units.jsonl.gz")
    answer = {row["analysis_unit_id"]: row for row in rows}
    require(len(answer) == 1351, "analysis-unit population drift")
    return answer


def enriched_claim(claim: dict[str, Any], units: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evidence = (claim.get("evidence") or [{}])[0]
    unit = units.get(evidence.get("analysis_unit_id"), {})
    return {
        "claim_id": claim.get("claim_id", ""),
        "proposition": claim.get("proposition", ""),
        "claim_type": claim.get("claim_type", ""),
        "epistemic_force": claim.get("epistemic_force", ""),
        "voice": claim.get("voice", {}),
        "exact_quote": evidence.get("exact_quote", ""),
        "analysis_unit_id": evidence.get("analysis_unit_id", ""),
        "work_id": evidence.get("work_id", ""),
        "edition_id": evidence.get("edition_id", ""),
        "source_title": unit.get("title", ""),
        "source_canonical": unit.get("canonical", ""),
        "source_published_at": unit.get("published_at", ""),
        "source_record_ids": unit.get("source_seed_record_ids", []),
    }


def searchable_text(row: dict[str, Any]) -> str:
    voice = row.get("voice") or {}
    return "\n".join(
        str(value)
        for value in (
            row.get("claim_id"),
            row.get("proposition"),
            row.get("exact_quote"),
            row.get("source_title"),
            row.get("source_canonical"),
            voice.get("name"),
            voice.get("organization"),
        )
        if value
    ).casefold()


def print_claim(row: dict[str, Any]) -> None:
    voice = row.get("voice") or {}
    speaker = voice.get("name") or voice.get("organization") or "未明确署名"
    print(f"{row['claim_id']}  [{row['claim_type']} / {row['epistemic_force']}]")
    print(f"主张：{row['proposition']}")
    print(f"声部：{speaker}")
    print(f"来源：{row['source_title']}")
    if row.get("source_canonical"):
        print(f"链接：{row['source_canonical']}")
    print(f"引句：{row['exact_quote']}")


def command_summary(release_root: Path, args: argparse.Namespace) -> int:
    manifest_path = release_root / "manifest.json"
    manifest = getattr(args, "manifest", None)
    if manifest is None:
        manifest = load_manifest(manifest_path)
    else:
        manifest = validate_manifest(manifest, manifest_path)
    counts = manifest["counts"]
    print(f"{manifest['release_name']} ({manifest['release_date']})")
    print(f"分析单位：{counts['analysis_units']}（正文 {counts['body_units']}，有界 unavailable {counts['bounded_unavailable_units']}）")
    print(f"证据段：{counts['passages']}")
    print(f"原子主张：{counts['claims']}")
    print(f"主题：{counts['themes']}")
    print(f"代表证据：{counts['representative_evidence_rows']}")
    return 0


def command_themes(release_root: Path, args: argparse.Namespace) -> int:
    rows = list(iter_jsonl(release_root / "data/theme-catalog.jsonl"))
    if args.json:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        return 0
    for row in rows:
        print(f"{row['theme_id']}  {row['name_zh']}")
        print(f"  {row['thesis_zh']}")
        print(f"  覆盖：{row['matched_analysis_unit_count']} units / {row['matched_claim_count']} claims")
    return 0


def command_search(release_root: Path, args: argparse.Namespace) -> int:
    query = args.query.casefold().strip()
    require(query, "search query must not be empty")
    require(1 <= args.limit <= 100, "--limit must be between 1 and 100")
    units = load_units(release_root)
    matches: list[dict[str, Any]] = []
    for claim in iter_jsonl(release_root / "data/atomic-claims.jsonl.gz"):
        row = enriched_claim(claim, units)
        if query in searchable_text(row):
            matches.append(row)
            if len(matches) == args.limit:
                break
    if args.json:
        for row in matches:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
    else:
        for index, row in enumerate(matches):
            if index:
                print()
            print_claim(row)
    if not matches:
        print("没有匹配结果。", file=sys.stderr)
        return 1
    return 0


def command_show(release_root: Path, args: argparse.Namespace) -> int:
    units = load_units(release_root)
    for claim in iter_jsonl(release_root / "data/atomic-claims.jsonl.gz"):
        if claim.get("claim_id") != args.claim_id:
            continue
        row = enriched_claim(claim, units)
        if args.json:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            print_claim(row)
        return 0
    print(f"未找到主张：{args.claim_id}", file=sys.stderr)
    return 1


def parser() -> argparse.ArgumentParser:
    answer = argparse.ArgumentParser(
        description="AMind v1 零依赖浏览工具；不联网，不修改发布数据。"
    )
    answer.add_argument("--release-root", type=Path, default=DEFAULT_RELEASE)
    subparsers = answer.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summary", help="显示发布人口与规模")
    summary.set_defaults(handler=command_summary)

    themes = subparsers.add_parser("themes", help="列出九个归纳主题")
    themes.add_argument("--json", action="store_true", help="输出 JSONL")
    themes.set_defaults(handler=command_themes)

    search = subparsers.add_parser("search", help="搜索主张、引句、来源或声部")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--json", action="store_true", help="输出 JSONL")
    search.set_defaults(handler=command_search)

    show = subparsers.add_parser("show", help="按稳定 claim ID 回查一条主张")
    show.add_argument("claim_id", help="兼容性 ID，例如 nuwa1-claim-…")
    show.add_argument("--json", action="store_true", help="输出 JSON")
    show.set_defaults(handler=command_show)
    return answer


def main() -> int:
    args = parser().parse_args()
    release_root = args.release_root.resolve()
    manifest_path = release_root / "manifest.json"
    require(manifest_path.is_file(), f"not an AMind v1 release: {release_root}")
    args.manifest = load_manifest(manifest_path)
    return args.handler(release_root, args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AMindError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
