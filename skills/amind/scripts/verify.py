#!/usr/bin/env python3
"""Verify the self-contained AMind skill evidence package."""

from __future__ import annotations

import hashlib
import gzip
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = SKILL_ROOT / "data"

MANIFEST_COUNT_FIELDS = (
    "full_index_analysis_units",
    "full_index_atomic_claims",
    "full_index_equivalence_components",
    "full_index_passages",
    "full_release_atomic_claims",
    "full_release_analysis_units",
    "human_reviewed_evidence_rows",
    "human_reviewed_evidence_rows_per_theme",
    "preserved_tensions",
    "themes",
    "voice_profiles",
)
EXPECTED_ARTIFACTS = {
    "amind-full-index.sqlite3": "sqlite3-fts5",
    "evidence-kernel.jsonl": "jsonl",
    "passages.jsonl.gz": "jsonl-gzip",
    "synthesis-tensions.jsonl": "jsonl",
    "theme-catalog.jsonl": "jsonl",
    "voice-profiles.jsonl": "jsonl",
}
WELFARE_TENSION_ID = "anthropomorphism-versus-welfare-precaution"
WELFARE_ANTI_ANTHROPOMORPHISM_CLAIM_ID = "nuwa1-claim-9c32c30410fed30e9680935e"
WELFARE_AGENDA_CLAIM_ID = "nuwa1-claim-f169332e5fa3d349672a254d"
WELFARE_PRECAUTION_CLAIM_ID = "nuwa1-claim-0bfc58759990a8c4886e1aa7"


class VerifyError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerifyError(message)


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerifyError(f"invalid JSON at {path}: {error}") from error
    require(isinstance(value, dict), f"expected object at {path}")
    return value


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    require(path.is_file(), f"missing file: {path}")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise VerifyError(f"invalid JSONL at {path}:{line_number}: {error.msg}") from error
            require(isinstance(value, dict), f"expected object at {path}:{line_number}")
            yield value


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_artifact_path(relative: str) -> Path:
    candidate = (DATA_ROOT / relative).resolve()
    try:
        candidate.relative_to(DATA_ROOT.resolve())
    except ValueError as error:
        raise VerifyError(f"artifact path escapes data root: {relative}") from error
    return candidate


def main() -> int:
    license_text = (SKILL_ROOT / "LICENSE.txt").read_text(encoding="utf-8")
    notice_text = (SKILL_ROOT / "NOTICE.txt").read_text(encoding="utf-8")
    require("Apache License" in license_text and "Version 2.0" in license_text, "missing or invalid Apache-2.0 license")
    require("third-party works" in notice_text, "missing third-party evidence notice")
    require("does not imply affiliation" in notice_text, "missing trademark and affiliation notice")
    manifest = read_json(DATA_ROOT / "manifest.json")
    require(manifest.get("schema_name") == "amind-skill-evidence-manifest", "invalid manifest schema")
    require(manifest.get("schema_version") == 1, "unsupported manifest schema version")
    require(manifest.get("skill_id") == "amind", "invalid skill identity")
    require(manifest.get("release_id") == "amind-v1", "invalid release identity")
    counts = manifest.get("counts")
    require(isinstance(counts, dict), "missing counts")
    for field in MANIFEST_COUNT_FIELDS:
        require(type(counts.get(field)) is int and counts[field] >= 0, f"invalid manifest count: {field}")

    artifacts = manifest.get("artifacts")
    require(isinstance(artifacts, list) and len(artifacts) == len(EXPECTED_ARTIFACTS), "unexpected evidence artifact count")
    seen_paths: set[str] = set()
    rows_by_path: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        require(isinstance(artifact, dict), "invalid artifact entry")
        relative = artifact.get("path")
        require(isinstance(relative, str) and relative not in seen_paths, "duplicate or invalid artifact path")
        seen_paths.add(relative)
        path = safe_artifact_path(relative)
        payload = path.read_bytes()
        require(len(payload) == artifact.get("bytes"), f"byte count mismatch: {relative}")
        require(sha256(payload) == artifact.get("sha256"), f"SHA-256 mismatch: {relative}")
        artifact_format = artifact.get("format")
        require(artifact_format == EXPECTED_ARTIFACTS.get(relative), f"invalid artifact format: {relative}")
        if artifact_format == "jsonl":
            rows = list(iter_jsonl(path))
            require(len(rows) == artifact.get("rows"), f"row count mismatch: {relative}")
            rows_by_path[relative] = rows
        elif artifact_format == "jsonl-gzip":
            require(sum(1 for _ in iter_jsonl(path)) == artifact.get("rows"), f"row count mismatch: {relative}")
    require(seen_paths == set(EXPECTED_ARTIFACTS), "missing or unexpected evidence artifacts")

    index_path = safe_artifact_path("amind-full-index.sqlite3")
    try:
        connection = sqlite3.connect(index_path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        metadata = {key: json.loads(value) for key, value in connection.execute("SELECT key, value FROM metadata")}
        require(connection.execute("PRAGMA quick_check").fetchone()[0] == "ok", "full index quick check failed")
        require(metadata.get("schema_name") == "amind-full-evidence-index", "invalid full index schema")
        require(metadata.get("schema_version") == 1, "unsupported full index schema")
        require(metadata.get("release_id") == "amind-v1", "full index release mismatch")
        require(connection.execute("SELECT count(*) FROM claims").fetchone()[0] == counts["full_index_atomic_claims"] == 52225, "full index claim count mismatch")
        require(connection.execute("SELECT count(*) FROM claims_fts").fetchone()[0] == 52225, "full index FTS count mismatch")
        require(connection.execute("SELECT count(*) FROM sources").fetchone()[0] == counts["full_index_analysis_units"] == 1351, "full index source count mismatch")
        require(connection.execute("SELECT count(*) FROM claims WHERE is_reviewed_kernel = 1").fetchone()[0] == 54, "full index gold count mismatch")
        require(connection.execute("SELECT count(*) FROM claims WHERE synthesis_disposition = 'eligible_for_source_level_synthesis'").fetchone()[0] == 45941, "full index direct-position count mismatch")
    except (json.JSONDecodeError, sqlite3.Error) as error:
        raise VerifyError(f"invalid full SQLite index: {error}") from error
    finally:
        if "connection" in locals():
            connection.close()

    require(counts["full_index_passages"] == 13436, "bundled passage count mismatch")

    evidence = rows_by_path["evidence-kernel.jsonl"]
    themes = rows_by_path["theme-catalog.jsonl"]
    voices = rows_by_path["voice-profiles.jsonl"]
    tensions = rows_by_path["synthesis-tensions.jsonl"]
    require(len(evidence) == counts.get("human_reviewed_evidence_rows") == 54, "evidence count mismatch")
    require(len(themes) == counts.get("themes") == 9, "theme count mismatch")
    require(len(voices) == counts.get("voice_profiles") == 5, "voice count mismatch")
    require(len(tensions) == counts.get("preserved_tensions") == 5, "tension count mismatch")

    claim_ids = {row.get("claim_id") for row in evidence}
    require(None not in claim_ids and len(claim_ids) == len(evidence), "duplicate or missing claim ID")
    evidence_by_claim = {row["claim_id"]: row for row in evidence}
    theme_ids = {row.get("theme_id") for row in themes}
    require(None not in theme_ids and len(theme_ids) == len(themes), "duplicate or missing theme ID")
    for row in evidence:
        require(row.get("theme_id") in theme_ids, f"unknown evidence theme: {row.get('claim_id')}")
        review = row.get("review")
        require(isinstance(review, dict), f"missing review: {row.get('claim_id')}")
        require(review.get("semantic_status") == "passage_context_supported", f"unapproved evidence: {row.get('claim_id')}")
        require(bool(row.get("source_canonical")), f"missing canonical source: {row.get('claim_id')}")
        require(bool(row.get("exact_quote")), f"missing exact quote: {row.get('claim_id')}")
    expected_per_theme = counts.get("human_reviewed_evidence_rows_per_theme")
    require(expected_per_theme == 6, "invalid per-theme evidence count")
    for theme_id in theme_ids:
        require(sum(1 for row in evidence if row.get("theme_id") == theme_id) == expected_per_theme, f"evidence coverage mismatch: {theme_id}")

    tension_ids = {row.get("tension_id") for row in tensions}
    require(None not in tension_ids and len(tension_ids) == len(tensions), "duplicate or missing tension ID")
    for tension in tensions:
        tension_claim_ids = tension.get("evidence_claim_ids")
        require(
            isinstance(tension_claim_ids, list)
            and tension_claim_ids
            and all(isinstance(claim_id, str) for claim_id in tension_claim_ids)
            and len(set(tension_claim_ids)) == len(tension_claim_ids),
            f"invalid tension evidence: {tension.get('tension_id')}",
        )
        require(
            set(tension_claim_ids).issubset(claim_ids),
            f"unknown tension evidence: {tension.get('tension_id')}",
        )

    welfare_tensions = [row for row in tensions if row.get("tension_id") == WELFARE_TENSION_ID]
    require(len(welfare_tensions) == 1, "missing welfare tension")
    welfare_tension = welfare_tensions[0]
    expected_welfare_claims = [
        WELFARE_ANTI_ANTHROPOMORPHISM_CLAIM_ID,
        WELFARE_PRECAUTION_CLAIM_ID,
    ]
    require(welfare_tension.get("evidence_claim_ids") == expected_welfare_claims, "invalid welfare tension evidence")
    for claim_id in expected_welfare_claims:
        row = evidence_by_claim[claim_id]
        require(row.get("attribution_class") == "direct_source_position", f"indirect welfare tension evidence: {claim_id}")
        require((row.get("review") or {}).get("agenda_is_not_answer") is False, f"agenda-only welfare tension evidence: {claim_id}")

    require(
        manifest.get("evidence_adjustments")
        == [
            {
                "artifact": "synthesis-tensions.jsonl",
                "reason": "replace an agenda-only research question with reviewed direct evidence of welfare precaution",
                "replaced_claim_id": WELFARE_AGENDA_CLAIM_ID,
                "replacement_claim_id": WELFARE_PRECAUTION_CLAIM_ID,
                "tension_id": WELFARE_TENSION_ID,
            }
        ],
        "invalid evidence adjustment provenance",
    )

    boundary = manifest.get("evidence_boundary")
    require(isinstance(boundary, dict), "missing evidence boundary")
    require(boundary.get("full_release_bundled") is False, "indexed skill must not claim every raw release artifact")
    require(boundary.get("full_claim_index_bundled") is True, "skill must bundle the full claim index")
    require(boundary.get("full_passage_context_bundled") is True, "skill must bundle passage context")
    require(boundary.get("private_anthropic_information_claimed") is False, "skill must not claim private evidence")
    print("AMind skill verification PASS: 52,225 indexed claims, 13,436 passages, 54 reviewed gold rows")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, VerifyError) as error:
        print(f"AMind verification error: {error}", file=sys.stderr)
        raise SystemExit(2)
