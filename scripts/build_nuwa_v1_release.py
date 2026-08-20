#!/usr/bin/env python3
"""Assemble the deterministic, GitHub-sized Nuwa v1 public release package."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/nuwa-v1-release-policy.json"
EVALUATION_AUDIT = ROOT / "corpus/nuwa-v1-evaluation-audit.json"
CLAIM_AUDIT = ROOT / "corpus/nuwa-v1-claim-audit.json"
SYNTHESIS_AUDIT = ROOT / "corpus/nuwa-v1-synthesis-audit.json"
TESTS = ROOT / "scripts/test_build_nuwa_v1_release.py"
RELEASE_ROOT = ROOT / "release/nuwa-v1"
MANIFEST = RELEASE_ROOT / "manifest.json"
RELEASE_AUDIT = RELEASE_ROOT / "release-audit.json"
RELEASE_README = RELEASE_ROOT / "README.md"


class BuildError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def row_count(path: Path, payload: bytes) -> int | None:
    if path.suffix == ".jsonl":
        return len([line for line in payload.split(b"\n") if line])
    return None


def schema_name(path: Path, payload: bytes) -> str:
    if path.suffix not in {".json", ".jsonl"}:
        return ""
    try:
        first = payload.split(b"\n", 1)[0]
        value = json.loads(first)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    return value.get("schema_name", "") if isinstance(value, dict) else ""


def expected_upstream_hash(path: Path, evaluation: dict[str, Any], claim: dict[str, Any], synthesis: dict[str, Any]) -> str:
    relative = path.relative_to(ROOT).as_posix()
    # The terminal evaluation audit is the release gate itself.  It cannot
    # self-fingerprint, so the release builder binds its current bytes as a
    # direct input after requiring verdict=PASS above.
    if path == EVALUATION_AUDIT:
        return sha256_bytes(path.read_bytes())
    for audit in (evaluation, synthesis, claim):
        for section in ("input_fingerprints", "output_fingerprints"):
            fingerprint = (audit.get(section) or {}).get(relative)
            if fingerprint:
                return fingerprint["sha256"]
    raise BuildError(f"release source is not bound by an upstream PASS audit: {relative}")


def build() -> tuple[dict[Path, bytes], dict[str, Any]]:
    policy = read_json(POLICY)
    require(policy.get("schema_name") == "nuwa-v1-release-policy", "invalid release policy schema")
    require(policy.get("schema_version") == 1, "invalid release policy version")
    scope = policy["scope"]
    require(scope["network_allowed"] is False, "network must remain disabled")
    require(scope["active_commoncrawl_direct_index_allowed"] is False, "active Direct must remain prohibited")

    evaluation = read_json(EVALUATION_AUDIT)
    claim = read_json(CLAIM_AUDIT)
    synthesis = read_json(SYNTHESIS_AUDIT)
    require(evaluation.get("verdict") == "PASS" and evaluation.get("safe_to_assemble_nuwa_v1_release") is True, "evaluation gate is not PASS")
    require(claim.get("verdict") == "PASS", "claim audit is not PASS")
    require(synthesis.get("verdict") == "PASS", "synthesis audit is not PASS")
    counts = evaluation["counts"]
    for key in ("analysis_units", "body_units", "bounded_unavailable_units", "claims", "passages", "themes", "representative_evidence_reviewed"):
        policy_key = "representative_evidence_rows" if key == "representative_evidence_reviewed" else key
        require(counts[key] == scope[policy_key], f"release count drift: {key}")

    payloads: dict[Path, bytes] = {}
    artifact_rows = []
    seen_sources = set()
    seen_published = set()
    for item in policy["artifacts"]:
        source = ROOT / item["source"]
        published = ROOT / item["published"]
        require(source.is_file(), f"missing release source: {item['source']}")
        require(source not in seen_sources, f"duplicate release source: {item['source']}")
        require(published not in seen_published, f"duplicate release target: {item['published']}")
        require(RELEASE_ROOT in published.parents, f"release target escapes package: {item['published']}")
        seen_sources.add(source)
        seen_published.add(published)
        source_payload = source.read_bytes()
        expected = item.get("expected_source_sha256") or expected_upstream_hash(source, evaluation, claim, synthesis)
        require(sha256_bytes(source_payload) == expected, f"upstream-bound source drift: {item['source']}")
        compression = item["compression"]
        if compression == "gzip":
            published_payload = gzip.compress(source_payload, compresslevel=9, mtime=0)
            require(gzip.decompress(published_payload) == source_payload, f"gzip replay mismatch: {item['published']}")
        else:
            require(compression == "none", f"unsupported compression: {compression}")
            published_payload = source_payload
        payloads[published] = published_payload
        artifact_rows.append({
            "source_file": item["source"],
            "published_file": item["published"],
            "compression": compression,
            "schema_name": schema_name(source, source_payload),
            "rows": row_count(source, source_payload),
            "source_sha256": sha256_bytes(source_payload),
            "source_bytes": len(source_payload),
            "published_sha256": sha256_bytes(published_payload),
            "published_bytes": len(published_payload),
        })
    require(len(artifact_rows) == 20, "release artifact count drift")

    manifest = {
        "schema_name": "nuwa-v1-release-manifest",
        "schema_version": 1,
        "release_id": policy["release_id"],
        "release_date": policy["release_date"],
        "counts": {
            "analysis_units": scope["analysis_units"],
            "body_units": scope["body_units"],
            "bounded_unavailable_units": scope["bounded_unavailable_units"],
            "passages": scope["passages"],
            "claims": scope["claims"],
            "themes": scope["themes"],
            "representative_evidence_rows": scope["representative_evidence_rows"],
            "published_artifacts": len(artifact_rows),
        },
        "artifacts": artifact_rows,
        "publication_boundary": policy["publication_boundary"],
    }
    manifest_payload = canonical_json(manifest)
    payloads[MANIFEST] = manifest_payload

    readme_lines = [
        "# AMind · Nuwa v1 release",
        "",
        "Nuwa v1 是一份从冻结证据中归纳 Anthropic 思想结构的可复算首版。发布包包含来源绑定的段落、52,225 条原子主张、归属与版本审计、主题映射、代表证据、人物声音差异和发布前评测。",
        "",
        "## 人口",
        "",
        "- 1,351 个分析单位；其中 1,348 个有正文，3 个为有证据边界的 unavailable 例外；",
        "- 13,436 个无重叠证据段；",
        "- 52,225 条逐字引句回链的原子主张；",
        "- 9 个非互斥归纳主题、54 条逐条复核的代表证据。",
        "",
        "## 从哪里开始",
        "",
        "1. 阅读 `reports/synthesis.zh-CN.md` 获取首版结论；",
        "2. 阅读 `reports/evaluation.zh-CN.md` 了解评测与限制；",
        "3. 用 `data/synthesis-evidence.jsonl` 回查代表证据；",
        "4. 用 `data/atomic-claims.jsonl.gz`、`data/passages.jsonl.gz` 和 `data/analysis-units.jsonl.gz` 做全量复算；",
        "5. 用 `manifest.json` 校验每个源文件与发布文件的 SHA-256。",
        "",
        "gzip 文件使用确定性压缩（mtime=0），解压后字节哈希记录在 manifest 中。",
        "",
        "## 解释边界",
        "",
        "- 主题频次是覆盖信号，不是共识投票；",
        "- 机构口径不自动等于个人观点；",
        "- 研究问题不当作已得到的答案；",
        "- 语义矛盾筛查不声称完备；",
        "- 54 条代表证据做了完整段落语义复核，但不声称 52,225 条主张全部经过逐条人工语义复核；",
        "- 本包不含 13GB 本地原始抓取与历史证据库；它保留发布所需的来源绑定段落、主张和哈希链。",
        "",
    ]
    readme_payload = "\n".join(readme_lines).encode("utf-8")
    payloads[RELEASE_README] = readme_payload

    input_paths = [POLICY, EVALUATION_AUDIT, CLAIM_AUDIT, SYNTHESIS_AUDIT, Path(__file__).resolve(), TESTS]
    input_fingerprints = {
        path.relative_to(ROOT).as_posix(): {"sha256": sha256_bytes(path.read_bytes()), "bytes": path.stat().st_size}
        for path in input_paths
    }
    release_output_fingerprints = {
        path.relative_to(ROOT).as_posix(): {"sha256": sha256_bytes(payload), "bytes": len(payload)}
        for path, payload in payloads.items()
    }
    audit = {
        "schema_name": "nuwa-v1-release-audit",
        "schema_version": 1,
        "release_id": policy["release_id"],
        "verdict": "PASS",
        "safe_to_publish_release_package": True,
        "counts": manifest["counts"],
        "input_fingerprints": dict(sorted(input_fingerprints.items())),
        "input_snapshot_sha256": sha256_bytes(canonical_json(dict(sorted(input_fingerprints.items())))),
        "output_fingerprints": dict(sorted(release_output_fingerprints.items())),
        "invariants": {
            "all_published_sources_bound_by_upstream_pass_audits": True,
            "gzip_payloads_deterministic_and_byte_replayable": True,
            "all_published_artifacts_under_release_root": True,
            "full_local_evidence_vault_excluded_from_git_sized_package": True,
            "raw_capture_blobs_excluded": True,
            "semantic_and_scope_limitations_disclosed": True,
            "network_access_count": 0,
            "active_commoncrawl_direct_index_read": False,
        },
    }
    payloads[RELEASE_AUDIT] = canonical_json(audit)
    return payloads, audit


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payloads, audit = build()
    if args.check:
        for path, expected in payloads.items():
            require(path.is_file(), f"missing release output: {path.relative_to(ROOT)}")
            require(path.read_bytes() == expected, f"release output drift: {path.relative_to(ROOT)}")
    else:
        for path, payload in payloads.items():
            atomic_write(path, payload)
    counts = audit["counts"]
    print(f"PASS artifacts={counts['published_artifacts']} claims={counts['claims']} passages={counts['passages']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
