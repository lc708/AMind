#!/usr/bin/env python3
"""Build the deterministic SQLite FTS index shipped with the AMind skill."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import zlib
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "release/amind-v1"
DATA_ROOT = RELEASE_ROOT / "data"
SKILL_INDEX = ROOT / "skills/amind/data/amind-full-index.sqlite3"

ANALYSIS_UNITS = DATA_ROOT / "analysis-units.jsonl.gz"
ATOMIC_CLAIMS = DATA_ROOT / "atomic-claims.jsonl.gz"
ATTRIBUTION_AUDIT = DATA_ROOT / "claim-attribution-audit.jsonl.gz"
EQUIVALENCE_COMPONENTS = DATA_ROOT / "claim-equivalence-components.jsonl"
PASSAGES = DATA_ROOT / "passages.jsonl.gz"
SYNTHESIS_EVIDENCE = DATA_ROOT / "synthesis-evidence.jsonl"
THEME_MEMBERSHIP = DATA_ROOT / "theme-membership.jsonl.gz"

INDEX_SCHEMA_NAME = "amind-full-evidence-index"
INDEX_SCHEMA_VERSION = 1
INDEX_APPLICATION_ID = 0x414D4E44  # AMND

INPUTS = (
    ANALYSIS_UNITS,
    ATOMIC_CLAIMS,
    ATTRIBUTION_AUDIT,
    EQUIVALENCE_COMPONENTS,
    PASSAGES,
    SYNTHESIS_EVIDENCE,
    THEME_MEMBERSHIP,
)


class IndexBuildError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IndexBuildError(message)


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
                raise IndexBuildError(f"invalid JSONL at {path}:{line_number}: {error.msg}") from error
            require(isinstance(value, dict), f"expected object at {path}:{line_number}")
            yield value


def validated_passage_ids(path: Path) -> set[str]:
    passage_ids: set[str] = set()
    for row in iter_jsonl(path):
        passage_id = row.get("passage_id")
        require(isinstance(passage_id, str) and bool(passage_id.strip()), f"missing passage ID in {path}")
        require(passage_id not in passage_ids, f"duplicate passage ID: {passage_id}")
        passage_ids.add(passage_id)
    return passage_ids


def validated_claim_passage_id(claim_id: str, evidence: dict[str, Any], passage_ids: set[str]) -> str:
    passage_id = evidence.get("passage_id")
    require(isinstance(passage_id, str) and bool(passage_id.strip()), f"missing claim passage ID: {claim_id}")
    require(passage_id in passage_ids, f"unknown claim passage: {claim_id}/{passage_id}")
    return passage_id


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def packed_json(value: Any) -> bytes:
    return zlib.compress(canonical_json(value).encode("utf-8"), level=9)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def publication_year(value: Any) -> int | None:
    match = re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", str(value or ""))
    return int(match.group(0)) if match else None


def source_host(value: Any) -> str:
    host = (urlparse(str(value or "")).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        f"""
        PRAGMA application_id={INDEX_APPLICATION_ID};
        PRAGMA user_version={INDEX_SCHEMA_VERSION};
        PRAGMA page_size=4096;
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        PRAGMA temp_store=MEMORY;
        PRAGMA locking_mode=EXCLUSIVE;
        PRAGMA auto_vacuum=NONE;

        CREATE TABLE metadata(
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) WITHOUT ROWID;

        CREATE TABLE sources(
            id INTEGER PRIMARY KEY,
            analysis_unit_id TEXT NOT NULL UNIQUE,
            work_id TEXT NOT NULL,
            edition_id TEXT NOT NULL,
            title TEXT NOT NULL,
            canonical TEXT NOT NULL,
            published_at TEXT NOT NULL,
            publication_year INTEGER,
            source_host TEXT NOT NULL,
            payload_zlib BLOB NOT NULL
        );

        CREATE TABLE voices(
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            organization TEXT NOT NULL,
            voice_type TEXT NOT NULL,
            role_at_time TEXT NOT NULL,
            attribution_basis TEXT NOT NULL,
            UNIQUE(name, organization, voice_type, role_at_time, attribution_basis)
        );

        CREATE TABLE claims(
            id INTEGER PRIMARY KEY,
            claim_id TEXT NOT NULL UNIQUE,
            source_id INTEGER NOT NULL,
            voice_id INTEGER NOT NULL,
            attribution_class TEXT NOT NULL,
            synthesis_disposition TEXT NOT NULL,
            equivalence_component_id TEXT NOT NULL,
            is_equivalence_representative INTEGER NOT NULL,
            is_reviewed_kernel INTEGER NOT NULL,
            payload_zlib BLOB NOT NULL
        );

        CREATE VIRTUAL TABLE claims_fts USING fts5(
            proposition,
            source_title,
            voice_name,
            voice_organization,
            domains,
            content='',
            tokenize='porter unicode61 remove_diacritics 2'
        );
        """
    )


def build_index_file(path: Path) -> dict[str, int]:
    require(not path.exists(), f"refusing to overwrite temporary index: {path}")

    units = sorted(iter_jsonl(ANALYSIS_UNITS), key=lambda row: row["analysis_unit_id"])
    claims = sorted(iter_jsonl(ATOMIC_CLAIMS), key=lambda row: row["claim_id"])
    attribution_by_claim = {row["claim_id"]: row for row in iter_jsonl(ATTRIBUTION_AUDIT)}
    themes_by_claim = {row["claim_id"]: row for row in iter_jsonl(THEME_MEMBERSHIP)}
    kernel_claim_ids = {row["claim_id"] for row in iter_jsonl(SYNTHESIS_EVIDENCE)}

    equivalence_by_claim: dict[str, tuple[str, str]] = {}
    equivalence_components = list(iter_jsonl(EQUIVALENCE_COMPONENTS))
    for component in equivalence_components:
        component_id = component["component_id"]
        representative = component["representative_claim_id"]
        for claim_id in component["member_claim_ids"]:
            require(claim_id not in equivalence_by_claim, f"claim appears in multiple equivalence components: {claim_id}")
            equivalence_by_claim[claim_id] = (component_id, representative)

    passage_ids = validated_passage_ids(PASSAGES)
    passage_count = len(passage_ids)
    require(len(units) == 1351, "expected 1,351 analysis units")
    require(len(claims) == 52225, "expected 52,225 atomic claims")
    require(len(attribution_by_claim) == len(claims), "attribution population mismatch")
    require(len(themes_by_claim) == len(claims), "theme population mismatch")
    require(len(kernel_claim_ids) == 54, "reviewed-kernel population mismatch")
    require(passage_count == 13436, "expected 13,436 passages")

    unit_by_id = {row["analysis_unit_id"]: row for row in units}
    source_id_by_unit = {row["analysis_unit_id"]: index for index, row in enumerate(units, start=1)}
    voice_keys = sorted(
        {
            (
                (claim.get("voice") or {}).get("name") or "",
                (claim.get("voice") or {}).get("organization") or "",
                (claim.get("voice") or {}).get("voice_type") or "",
                (claim.get("voice") or {}).get("role_at_time") or "",
                (claim.get("voice") or {}).get("attribution_basis") or "",
            )
            for claim in claims
        }
    )
    voice_id_by_key = {key: index for index, key in enumerate(voice_keys, start=1)}

    connection = sqlite3.connect(path)
    try:
        create_schema(connection)
        metadata = {
            "analysis_units": len(units),
            "atomic_claims": len(claims),
            "equivalence_components": len(equivalence_components),
            "passages_external": passage_count,
            "release_id": "amind-v1",
            "reviewed_kernel_claims": len(kernel_claim_ids),
            "schema_name": INDEX_SCHEMA_NAME,
            "schema_version": INDEX_SCHEMA_VERSION,
            "source_fingerprints": {
                str(input_path.relative_to(ROOT)): sha256_file(input_path)
                for input_path in sorted(INPUTS)
            },
        }
        for key, value in sorted(metadata.items()):
            connection.execute("INSERT INTO metadata(key, value) VALUES(?, ?)", (key, canonical_json(value)))

        for source_id, unit in enumerate(units, start=1):
            published_at = str(unit.get("published_at") or "")
            payload = {
                "authors": unit.get("authors") or [],
                "body_sha256": unit.get("body_sha256") or "",
                "component_origin": unit.get("component_origin") or "",
                "historical_role": unit.get("historical_role") or {},
                "language": unit.get("language") or "",
                "source_record_ids": unit.get("source_seed_record_ids") or [],
                "text_file_sha256": unit.get("text_file_sha256") or "",
                "unit_status": unit.get("unit_status") or "",
            }
            connection.execute(
                """
                INSERT INTO sources(
                    id, analysis_unit_id, work_id, edition_id, title, canonical,
                    published_at, publication_year, source_host, payload_zlib
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    unit["analysis_unit_id"],
                    unit["work_id"],
                    unit["edition_id"],
                    unit.get("title") or "",
                    unit.get("canonical") or "",
                    published_at,
                    publication_year(published_at),
                    source_host(unit.get("canonical")),
                    packed_json(payload),
                ),
            )

        for voice_id, voice_key in enumerate(voice_keys, start=1):
            connection.execute(
                """
                INSERT INTO voices(
                    id, name, organization, voice_type, role_at_time, attribution_basis
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (voice_id, *voice_key),
            )

        for claim_row_id, claim in enumerate(claims, start=1):
            claim_id = claim["claim_id"]
            evidence_rows = claim.get("evidence") or []
            require(len(evidence_rows) == 1, f"claim must bind exactly one evidence row: {claim_id}")
            evidence = evidence_rows[0]
            passage_id = validated_claim_passage_id(claim_id, evidence, passage_ids)
            unit_id = evidence["analysis_unit_id"]
            require(unit_id in unit_by_id, f"unknown analysis unit: {claim_id}/{unit_id}")
            require(claim_id in attribution_by_claim, f"missing attribution audit: {claim_id}")
            require(claim_id in themes_by_claim, f"missing theme membership: {claim_id}")

            unit = unit_by_id[unit_id]
            attribution = attribution_by_claim[claim_id]
            membership = themes_by_claim[claim_id]
            voice = claim.get("voice") or {}
            voice_key = (
                voice.get("name") or "",
                voice.get("organization") or "",
                voice.get("voice_type") or "",
                voice.get("role_at_time") or "",
                voice.get("attribution_basis") or "",
            )
            component_id, representative_claim_id = equivalence_by_claim.get(claim_id, ("", ""))
            is_representative = not component_id or claim_id == representative_claim_id
            temporal_scope = claim.get("temporal_scope") or {}

            payload = {
                "claim_type": claim.get("claim_type") or "",
                "conditions": claim.get("conditions") or [],
                "domains": claim.get("domains") or [],
                "epistemic_force": claim.get("epistemic_force") or "",
                "equivalence_representative_claim_id": representative_claim_id,
                "exact_quote": evidence.get("exact_quote") or "",
                "exact_quote_sha256": evidence.get("exact_quote_sha256") or "",
                "invalidation_conditions": claim.get("invalidation_conditions") or [],
                "passage_id": passage_id,
                "proposition": claim.get("proposition") or "",
                "temporal_scope": temporal_scope,
                "theme_ids": membership.get("theme_ids") or [],
            }
            connection.execute(
                """
                INSERT INTO claims(
                    id, claim_id, source_id, voice_id,
                    attribution_class, synthesis_disposition,
                    equivalence_component_id, is_equivalence_representative,
                    is_reviewed_kernel, payload_zlib
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_row_id,
                    claim_id,
                    source_id_by_unit[unit_id],
                    voice_id_by_key[voice_key],
                    attribution.get("attribution_class") or "",
                    attribution.get("synthesis_disposition") or "",
                    component_id,
                    int(is_representative),
                    int(claim_id in kernel_claim_ids),
                    packed_json(payload),
                ),
            )
            fts_values = (
                claim_row_id,
                claim.get("proposition") or "",
                unit.get("title") or "",
                voice.get("name") or "",
                voice.get("organization") or "",
                " ".join(claim.get("domains") or []),
            )
            connection.execute(
                """
                INSERT INTO claims_fts(
                    rowid, proposition, source_title,
                    voice_name, voice_organization, domains
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                fts_values,
            )

        connection.execute("INSERT INTO claims_fts(claims_fts) VALUES('optimize')")
        connection.commit()
        connection.execute("VACUUM")
        require(connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "generated index failed integrity check")
    finally:
        connection.close()

    return {
        "analysis_units": len(units),
        "atomic_claims": len(claims),
        "equivalence_components": len(equivalence_components),
        "passages": passage_count,
        "reviewed_kernel_claims": len(kernel_claim_ids),
    }


def build_index_bytes() -> tuple[bytes, dict[str, int]]:
    with tempfile.TemporaryDirectory(prefix="amind-index-") as temporary:
        path = Path(temporary) / "amind-full-index.sqlite3"
        counts = build_index_file(path)
        return path.read_bytes(), counts


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=SKILL_INDEX)
    parser.add_argument("--check", action="store_true", help="compare generated bytes with the existing index")
    args = parser.parse_args()

    payload, counts = build_index_bytes()
    output = args.output.resolve()
    if args.check:
        require(output.is_file(), f"missing generated index: {output}")
        require(output.read_bytes() == payload, f"generated index drift: {output}")
        print(f"AMind full index check PASS: {counts['atomic_claims']:,} claims")
        return 0

    atomic_write(output, payload)
    print(
        f"Built AMind full index: {counts['atomic_claims']:,} claims / "
        f"{counts['analysis_units']:,} sources / {len(payload):,} bytes"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except IndexBuildError as error:
        print(f"error: {error}")
        raise SystemExit(2)
