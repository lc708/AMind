#!/usr/bin/env python3
"""Verify the self-contained AMind v1 release package using only the stdlib."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELEASE = ROOT / "release/amind-v1"


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_inside(root: Path, relative: str) -> Path:
    expected_prefix = "release/amind-v1/"
    require(relative.startswith(expected_prefix), f"unexpected published path: {relative}")
    candidate = (root / relative[len(expected_prefix):]).resolve()
    release_root = root.resolve()
    require(candidate == release_root or release_root in candidate.parents, f"published path escapes release: {relative}")
    return candidate


def verify(release_root: Path) -> dict[str, int]:
    manifest_path = release_root / "manifest.json"
    audit_path = release_root / "release-audit.json"
    require(manifest_path.is_file(), "missing manifest.json")
    require(audit_path.is_file(), "missing release-audit.json")
    manifest = read_json(manifest_path)
    audit = read_json(audit_path)
    require(manifest.get("schema_name") == "amind-v1-release-manifest", "invalid manifest schema")
    require(audit.get("schema_name") == "amind-v1-release-audit", "invalid release audit schema")
    require(manifest.get("release_id") == audit.get("release_id") == "amind-v1", "invalid release ID")
    require(manifest.get("release_name") == audit.get("release_name") == "AMind v1", "invalid release name")
    require(audit.get("verdict") == "PASS", "release audit is not PASS")
    require(audit.get("safe_to_publish_release_package") is True, "release is not publication-authorized")

    artifacts = manifest.get("artifacts") or []
    require(len(artifacts) == manifest["counts"]["published_artifacts"] == 21, "artifact count drift")
    seen = set()
    for row in artifacts:
        path = resolve_inside(release_root, row["published_file"])
        require(path not in seen, f"duplicate published path: {path}")
        seen.add(path)
        require(path.is_file(), f"missing artifact: {row['published_file']}")
        published = path.read_bytes()
        require(len(published) == row["published_bytes"], f"published byte count mismatch: {row['published_file']}")
        require(sha256_bytes(published) == row["published_sha256"], f"published hash mismatch: {row['published_file']}")
        if row["compression"] == "gzip":
            try:
                source = gzip.decompress(published)
            except gzip.BadGzipFile as error:
                raise VerificationError(f"invalid gzip artifact: {row['published_file']}") from error
        else:
            require(row["compression"] == "none", f"unknown compression: {row['published_file']}")
            source = published
        require(len(source) == row["source_bytes"], f"source byte count mismatch: {row['published_file']}")
        require(sha256_bytes(source) == row["source_sha256"], f"source hash mismatch: {row['published_file']}")
        if row["rows"] is not None:
            require(len([line for line in source.split(b"\n") if line]) == row["rows"], f"row count mismatch: {row['published_file']}")

    expected_outputs = audit.get("output_fingerprints") or {}
    for relative, fingerprint in expected_outputs.items():
        path = resolve_inside(release_root, relative)
        require(path.is_file(), f"missing audited output: {relative}")
        payload = path.read_bytes()
        require(len(payload) == fingerprint["bytes"], f"audited byte count mismatch: {relative}")
        require(sha256_bytes(payload) == fingerprint["sha256"], f"audited hash mismatch: {relative}")
    return {
        "artifacts": len(artifacts),
        "claims": manifest["counts"]["claims"],
        "passages": manifest["counts"]["passages"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, default=DEFAULT_RELEASE)
    args = parser.parse_args()
    counts = verify(args.release_root)
    print(f"PASS artifacts={counts['artifacts']} claims={counts['claims']} passages={counts['passages']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
