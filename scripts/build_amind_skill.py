#!/usr/bin/env python3
"""Build the compact, source-bound evidence kernel shipped with the AMind skill."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "release/amind-v1"
SKILL_ROOT = ROOT / "skills/amind"
DATA_ROOT = SKILL_ROOT / "data"

RELEASE_MANIFEST = RELEASE_ROOT / "manifest.json"
SYNTHESIS_EVIDENCE = RELEASE_ROOT / "data/synthesis-evidence.jsonl"
REVIEW_EVIDENCE = RELEASE_ROOT / "data/representative-evidence-review.jsonl"
THEMES = RELEASE_ROOT / "data/theme-catalog.jsonl"
VOICES = RELEASE_ROOT / "data/voice-profiles.jsonl"
TENSIONS = RELEASE_ROOT / "data/synthesis-tensions.jsonl"

WELFARE_TENSION_ID = "anthropomorphism-versus-welfare-precaution"
WELFARE_ANTI_ANTHROPOMORPHISM_CLAIM_ID = "nuwa1-claim-9c32c30410fed30e9680935e"
WELFARE_AGENDA_CLAIM_ID = "nuwa1-claim-f169332e5fa3d349672a254d"
WELFARE_PRECAUTION_CLAIM_ID = "nuwa1-claim-0bfc58759990a8c4886e1aa7"


class BuildError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    require(path.is_file(), f"missing input: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing input: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise BuildError(f"invalid JSON at {path}: {error}") from error
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    require(path.is_file(), f"missing input: {path}")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise BuildError(f"invalid JSONL at {path}:{line_number}: {error}") from error
            require(isinstance(value, dict), f"expected object at {path}:{line_number}")
            yield value


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def canonical_jsonl(rows: Iterable[dict[str, Any]]) -> bytes:
    return b"".join(canonical_json(row) for row in rows)


def artifact_entry(path: str, payload: bytes, rows: int | None, schema_name: str) -> dict[str, Any]:
    return {
        "bytes": len(payload),
        "path": path,
        "rows": rows,
        "schema_name": schema_name,
        "sha256": sha256_bytes(payload),
    }


def build_payloads() -> dict[Path, bytes]:
    release_manifest = read_json(RELEASE_MANIFEST)
    require(release_manifest.get("release_id") == "amind-v1", "unexpected release ID")
    require(release_manifest.get("release_name") == "AMind v1", "unexpected release name")

    synthesis_rows = list(iter_jsonl(SYNTHESIS_EVIDENCE))
    review_rows = list(iter_jsonl(REVIEW_EVIDENCE))
    theme_rows = list(iter_jsonl(THEMES))
    voice_rows = list(iter_jsonl(VOICES))
    tension_rows = list(iter_jsonl(TENSIONS))

    require(len(synthesis_rows) == 54, "expected 54 synthesis evidence rows")
    require(len(review_rows) == 54, "expected 54 reviewed evidence rows")
    require(len(theme_rows) == 9, "expected 9 themes")
    require(len(voice_rows) == 5, "expected 5 voice profiles")
    require(len(tension_rows) == 5, "expected 5 preserved tensions")

    synthesis_by_claim = {row.get("claim_id"): row for row in synthesis_rows}
    review_by_claim = {row.get("claim_id"): row for row in review_rows}
    require(None not in synthesis_by_claim and len(synthesis_by_claim) == 54, "duplicate or missing synthesis claim ID")
    require(None not in review_by_claim and len(review_by_claim) == 54, "duplicate or missing review claim ID")
    require(set(synthesis_by_claim) == set(review_by_claim), "synthesis/review claim population mismatch")

    theme_ids = {row.get("theme_id") for row in theme_rows}
    require(None not in theme_ids and len(theme_ids) == 9, "invalid theme population")

    kernel_rows: list[dict[str, Any]] = []
    for claim_id in sorted(synthesis_by_claim):
        evidence = synthesis_by_claim[claim_id]
        review = review_by_claim[claim_id]
        for field in ("analysis_unit_id", "edition_id", "passage_id", "theme_id", "work_id"):
            require(evidence.get(field) == review.get(field), f"review join mismatch for {claim_id}: {field}")
        require(evidence.get("claim_row_sha256") == review.get("claim_row_sha256"), f"claim hash mismatch: {claim_id}")
        require(evidence.get("exact_quote_sha256") == review.get("exact_quote_sha256"), f"quote hash mismatch: {claim_id}")
        require(evidence.get("theme_id") in theme_ids, f"unknown theme for {claim_id}")
        require(review.get("semantic_review_status") == "passage_context_supported", f"unapproved evidence: {claim_id}")

        kernel_rows.append(
            {
                "analysis_unit_id": evidence["analysis_unit_id"],
                "attribution_class": evidence["attribution_class"],
                "claim_id": claim_id,
                "claim_row_sha256": evidence["claim_row_sha256"],
                "claim_type": evidence["claim_type"],
                "edition_id": evidence["edition_id"],
                "epistemic_force": evidence["epistemic_force"],
                "exact_quote": evidence["exact_quote"],
                "exact_quote_sha256": evidence["exact_quote_sha256"],
                "passage_id": evidence["passage_id"],
                "proposition": evidence["proposition"],
                "review": {
                    "agenda_is_not_answer": review["agenda_is_not_answer"],
                    "method": review["review_method"],
                    "reviewed_at": review["reviewed_at"],
                    "semantic_status": review["semantic_review_status"],
                    "support_mode": review["support_mode"],
                },
                "schema_name": "amind-skill-evidence-kernel-row",
                "schema_version": 1,
                "source_canonical": evidence["source_canonical"],
                "source_published_at": evidence["source_published_at"],
                "source_record_ids": evidence["source_record_ids"],
                "source_title": evidence["source_title"],
                "theme_id": evidence["theme_id"],
                "voice": evidence["voice"],
                "work_id": evidence["work_id"],
            }
        )

    kernel_rows.sort(key=lambda row: (row["theme_id"], row["claim_id"]))
    kernel_by_claim = {row["claim_id"]: row for row in kernel_rows}
    evidence_by_theme = {
        theme_id: sum(1 for row in kernel_rows if row["theme_id"] == theme_id)
        for theme_id in sorted(theme_ids)
    }
    require(set(evidence_by_theme.values()) == {6}, "expected six reviewed evidence rows per theme")

    compact_tension_rows: list[dict[str, Any]] = []
    welfare_adjustments = 0
    for source_row in tension_rows:
        row = dict(source_row)
        if row.get("tension_id") == WELFARE_TENSION_ID:
            require(
                row.get("evidence_claim_ids")
                == [WELFARE_ANTI_ANTHROPOMORPHISM_CLAIM_ID, WELFARE_AGENDA_CLAIM_ID],
                "unexpected source evidence for welfare tension",
            )
            replacement = kernel_by_claim.get(WELFARE_PRECAUTION_CLAIM_ID)
            require(replacement is not None, "missing direct welfare-precaution evidence")
            require(
                replacement.get("attribution_class") == "direct_source_position",
                "welfare-precaution replacement is not a direct source position",
            )
            require(
                (replacement.get("review") or {}).get("agenda_is_not_answer") is False,
                "welfare-precaution replacement is agenda-only evidence",
            )
            row["evidence_claim_ids"] = [
                WELFARE_ANTI_ANTHROPOMORPHISM_CLAIM_ID,
                WELFARE_PRECAUTION_CLAIM_ID,
            ]
            welfare_adjustments += 1
        compact_tension_rows.append(row)
    require(welfare_adjustments == 1, "expected one welfare tension evidence adjustment")

    data_payloads: dict[str, bytes] = {
        "evidence-kernel.jsonl": canonical_jsonl(kernel_rows),
        "theme-catalog.jsonl": THEMES.read_bytes(),
        "voice-profiles.jsonl": VOICES.read_bytes(),
        "synthesis-tensions.jsonl": canonical_jsonl(compact_tension_rows),
    }
    row_counts = {
        "evidence-kernel.jsonl": len(kernel_rows),
        "theme-catalog.jsonl": len(theme_rows),
        "voice-profiles.jsonl": len(voice_rows),
        "synthesis-tensions.jsonl": len(tension_rows),
    }
    schemas = {
        "evidence-kernel.jsonl": "amind-skill-evidence-kernel-row",
        "theme-catalog.jsonl": "nuwa-v1-theme",
        "voice-profiles.jsonl": "nuwa-v1-voice-profile",
        "synthesis-tensions.jsonl": "nuwa-v1-synthesis-tension",
    }
    artifacts = [
        artifact_entry(name, data_payloads[name], row_counts[name], schemas[name])
        for name in sorted(data_payloads)
    ]
    manifest = {
        "artifacts": artifacts,
        "counts": {
            "full_release_atomic_claims": release_manifest["counts"]["claims"],
            "full_release_analysis_units": release_manifest["counts"]["analysis_units"],
            "human_reviewed_evidence_rows": len(kernel_rows),
            "human_reviewed_evidence_rows_per_theme": 6,
            "preserved_tensions": len(tension_rows),
            "themes": len(theme_rows),
            "voice_profiles": len(voice_rows),
        },
        "evidence_boundary": {
            "advice_without_exact_precedent_allowed": True,
            "exploratory_extrapolation_must_be_labeled": True,
            "full_release_bundled": False,
            "human_review_claim_limited_to_kernel": True,
            "private_anthropic_information_claimed": False,
        },
        "evidence_adjustments": [
            {
                "artifact": "synthesis-tensions.jsonl",
                "reason": "replace an agenda-only research question with reviewed direct evidence of welfare precaution",
                "replaced_claim_id": WELFARE_AGENDA_CLAIM_ID,
                "replacement_claim_id": WELFARE_PRECAUTION_CLAIM_ID,
                "tension_id": WELFARE_TENSION_ID,
            }
        ],
        "release_id": "amind-v1",
        "schema_name": "amind-skill-evidence-manifest",
        "schema_version": 1,
        "skill_id": "amind",
        "skill_version": "1.0.0",
        "sources": [
            {"path": "release/amind-v1/manifest.json", "sha256": sha256_file(RELEASE_MANIFEST)},
            {"path": "release/amind-v1/data/synthesis-evidence.jsonl", "sha256": sha256_file(SYNTHESIS_EVIDENCE)},
            {"path": "release/amind-v1/data/representative-evidence-review.jsonl", "sha256": sha256_file(REVIEW_EVIDENCE)},
            {"path": "release/amind-v1/data/theme-catalog.jsonl", "sha256": sha256_file(THEMES)},
            {"path": "release/amind-v1/data/voice-profiles.jsonl", "sha256": sha256_file(VOICES)},
            {"path": "release/amind-v1/data/synthesis-tensions.jsonl", "sha256": sha256_file(TENSIONS)},
        ],
    }

    outputs = {DATA_ROOT / name: payload for name, payload in data_payloads.items()}
    outputs[DATA_ROOT / "manifest.json"] = canonical_json(manifest)
    return outputs


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify generated bytes without writing")
    args = parser.parse_args()

    outputs = build_payloads()
    if args.check:
        mismatches = [str(path.relative_to(ROOT)) for path, payload in outputs.items() if not path.is_file() or path.read_bytes() != payload]
        require(not mismatches, "generated output drift: " + ", ".join(mismatches))
        print(f"AMind skill data check PASS ({len(outputs)} files)")
        return 0

    for path, payload in outputs.items():
        atomic_write(path, payload)
    print(f"Built AMind skill evidence kernel: {len(outputs)} files")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as error:
        print(f"error: {error}")
        raise SystemExit(2)
