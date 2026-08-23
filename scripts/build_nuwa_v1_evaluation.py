#!/usr/bin/env python3
"""Build the bounded AMind v1 traceability and representative-evidence evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/nuwa-v1-evaluation-policy.json"
CLAIMS = ROOT / "corpus/nuwa-v1-production-atomic-claims.jsonl"
PASSAGES = ROOT / "corpus/nuwa-v1-passages.jsonl"
UNITS = ROOT / "corpus/nuwa-v1-analysis-units.jsonl"
ATTRIBUTION = ROOT / "corpus/nuwa-v1-claim-attribution-audit.jsonl"
EQUIVALENCE = ROOT / "corpus/nuwa-v1-claim-equivalence-components.jsonl"
VERSIONS = ROOT / "corpus/nuwa-v1-version-audit.jsonl"
CONTRADICTIONS = ROOT / "corpus/nuwa-v1-contradiction-candidates.jsonl"
CLAIM_AUDIT = ROOT / "corpus/nuwa-v1-claim-audit.json"
MEMBERSHIP = ROOT / "corpus/nuwa-v1-theme-membership.jsonl"
SYNTHESIS_EVIDENCE = ROOT / "corpus/nuwa-v1-synthesis-evidence.jsonl"
THEMES = ROOT / "corpus/nuwa-v1-theme-catalog.jsonl"
VOICE_PROFILES = ROOT / "corpus/nuwa-v1-voice-profiles.jsonl"
SYNTHESIS_TENSIONS = ROOT / "corpus/nuwa-v1-synthesis-tensions.jsonl"
SYNTHESIS_AUDIT = ROOT / "corpus/nuwa-v1-synthesis-audit.json"
TESTS = ROOT / "scripts/test_build_nuwa_v1_evaluation.py"

REPRESENTATIVE_REVIEW = ROOT / "corpus/nuwa-v1-representative-evidence-review.jsonl"
SAMPLE = ROOT / "corpus/nuwa-v1-evaluation-sample.jsonl"
AUDIT = ROOT / "corpus/nuwa-v1-evaluation-audit.json"
REPORT = ROOT / "reports/nuwa-v1-evaluation.zh-CN.md"


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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line]


def unique_by(rows: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    answer = {row[key]: row for row in rows}
    require(len(answer) == len(rows), f"duplicate {label}")
    return answer


def normalized_tokens(value: str) -> set[str]:
    stop = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
        "in", "is", "it", "its", "of", "on", "or", "that", "the", "their", "this", "to",
        "was", "were", "with", "would",
    }
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2 and token not in stop}


def build() -> tuple[dict[Path, bytes], dict[str, Any]]:
    policy = read_json(POLICY)
    require(policy.get("schema_name") == "nuwa-v1-evaluation-policy", "invalid evaluation policy schema")
    require(policy.get("schema_version") == 1, "invalid evaluation policy version")
    scope = policy["scope"]
    require(scope["network_allowed"] is False, "network must remain disabled")
    require(scope["active_commoncrawl_direct_index_allowed"] is False, "active Direct must remain prohibited")

    claim_audit = read_json(CLAIM_AUDIT)
    synthesis_audit = read_json(SYNTHESIS_AUDIT)
    require(claim_audit.get("verdict") == "PASS", "claim audit is not PASS")
    require(synthesis_audit.get("verdict") == "PASS", "synthesis audit is not PASS")
    require(synthesis_audit.get("safe_to_publish_nuwa_v1_synthesis") is True, "synthesis is not publication-ready")

    claims = read_jsonl(CLAIMS)
    passages = read_jsonl(PASSAGES)
    units = read_jsonl(UNITS)
    attribution = read_jsonl(ATTRIBUTION)
    equivalence = read_jsonl(EQUIVALENCE)
    versions = read_jsonl(VERSIONS)
    contradictions = read_jsonl(CONTRADICTIONS)
    membership = read_jsonl(MEMBERSHIP)
    synthesis_evidence = read_jsonl(SYNTHESIS_EVIDENCE)
    themes = read_jsonl(THEMES)
    voices = read_jsonl(VOICE_PROFILES)
    synthesis_tensions = read_jsonl(SYNTHESIS_TENSIONS)

    require(len(claims) == scope["claims"] == 52225, "claim population drift")
    require(len(units) == scope["analysis_units"] == 1351, "analysis-unit population drift")
    require(len(synthesis_evidence) == scope["representative_evidence_rows"] == 54, "representative population drift")
    require(sum(unit["unit_status"] == "body_primary" for unit in units) == scope["body_units"] == 1348, "body-unit population drift")
    require(sum(unit["unit_status"] == "bounded_unavailable_exception" for unit in units) == scope["bounded_unavailable_units"] == 3, "bounded-unavailable population drift")

    claim_by_id = unique_by(claims, "claim_id", "claim ID")
    passage_by_id = unique_by(passages, "passage_id", "passage ID")
    unit_by_id = unique_by(units, "analysis_unit_id", "analysis unit ID")
    attribution_by_id = unique_by(attribution, "claim_id", "attribution row")
    membership_by_id = unique_by(membership, "claim_id", "theme-membership row")
    require(set(claim_by_id) == set(attribution_by_id) == set(membership_by_id), "claim audit/membership population mismatch")

    quote_within_passage_count = 0
    full_fk_count = 0
    attribution_counts = Counter()
    claim_type_counts = Counter()
    strata: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        require(len(claim.get("evidence") or []) == 1, f"claim must have exactly one owned evidence row: {claim['claim_id']}")
        evidence = claim["evidence"][0]
        passage = passage_by_id.get(evidence["passage_id"])
        unit = unit_by_id.get(evidence["analysis_unit_id"])
        require(passage is not None, f"unknown passage: {claim['claim_id']}")
        require(unit is not None, f"unknown analysis unit: {claim['claim_id']}")
        require(evidence["exact_quote_sha256"] == sha256_bytes(evidence["exact_quote"].encode("utf-8")), f"quote hash mismatch: {claim['claim_id']}")
        require(evidence["exact_quote"] in passage["text"], f"quote absent from owned passage: {claim['claim_id']}")
        quote_within_passage_count += 1
        for field in ("analysis_unit_id", "work_id", "edition_id"):
            require(evidence[field] == passage[field], f"claim-passage {field} mismatch: {claim['claim_id']}")
            require(evidence[field] == unit[field], f"claim-unit {field} mismatch: {claim['claim_id']}")
        require(evidence["body_sha256"] == passage["source_body_sha256"] == unit["body_sha256"], f"body mismatch: {claim['claim_id']}")
        require(evidence["text_file_sha256"] == passage["source_text_file_sha256"] == unit["text_file_sha256"], f"text-file mismatch: {claim['claim_id']}")
        claim_sha = sha256_bytes(canonical_json(claim))
        attr = attribution_by_id[claim["claim_id"]]
        member = membership_by_id[claim["claim_id"]]
        require(attr["claim_row_sha256"] == member["claim_row_sha256"] == claim_sha, f"claim row hash mismatch: {claim['claim_id']}")
        require(attr["passage_id"] == evidence["passage_id"], f"attribution passage mismatch: {claim['claim_id']}")
        full_fk_count += 1
        attribution_counts[attr["attribution_class"]] += 1
        claim_type_counts[claim["claim_type"]] += 1
        strata[(attr["attribution_class"], claim["claim_type"])].append(claim)

    equivalence_members = [claim_id for row in equivalence for claim_id in row["member_claim_ids"]]
    require(len(equivalence_members) == len(set(equivalence_members)), "equivalence components overlap")
    require(set(equivalence_members) <= set(claim_by_id), "equivalence contains unknown claim")
    require(len(versions) == 1 and versions[0]["terminal_disposition"] == "preserve_distinct_versions_no_supersession_inference", "version boundary drift")
    require(contradictions and all(not row["unresolved"] for row in contradictions), "unresolved screened contradiction candidate")

    attestation = policy["representative_review_attestation"]
    require(attestation["reviewed_artifact"] == SYNTHESIS_EVIDENCE.relative_to(ROOT).as_posix(), "reviewed artifact path drift")
    require(attestation["reviewed_artifact_sha256"] == sha256_bytes(SYNTHESIS_EVIDENCE.read_bytes()), "reviewed synthesis-evidence bytes drift")
    require(attestation["reviewed_rows"] == len(synthesis_evidence), "reviewed representative count drift")
    representative_rows = []
    representative_ids = set()
    for row in synthesis_evidence:
        claim_id = row["claim_id"]
        require(claim_id not in representative_ids, f"representative claim reused: {claim_id}")
        representative_ids.add(claim_id)
        claim = claim_by_id[claim_id]
        evidence = claim["evidence"][0]
        passage = passage_by_id[evidence["passage_id"]]
        require(row["claim_row_sha256"] == sha256_bytes(canonical_json(claim)), f"representative claim hash mismatch: {claim_id}")
        require(row["exact_quote"] == evidence["exact_quote"], f"representative quote mismatch: {claim_id}")
        require(row["synthesis_disposition"] == attribution_by_id[claim_id]["synthesis_disposition"], f"representative disposition mismatch: {claim_id}")
        proposition_tokens = normalized_tokens(claim["proposition"])
        quote_tokens = normalized_tokens(evidence["exact_quote"])
        overlap = len(proposition_tokens & quote_tokens)
        recall = overlap / max(1, len(proposition_tokens))
        support_mode = "exact_quote_substantially_supports_proposition" if recall >= 0.70 else "full_passage_context_required_and_reviewed"
        representative_rows.append({
            "schema_name": "nuwa-v1-representative-evidence-review",
            "schema_version": 1,
            "claim_id": claim_id,
            "theme_id": row["theme_id"],
            "claim_row_sha256": row["claim_row_sha256"],
            "analysis_unit_id": evidence["analysis_unit_id"],
            "work_id": evidence["work_id"],
            "edition_id": evidence["edition_id"],
            "passage_id": evidence["passage_id"],
            "passage_text_sha256": passage["text_sha256"],
            "exact_quote_sha256": evidence["exact_quote_sha256"],
            "proposition_token_recall_from_exact_quote": round(recall, 6),
            "support_mode": support_mode,
            "semantic_review_status": "passage_context_supported",
            "attribution_class": attribution_by_id[claim_id]["attribution_class"],
            "synthesis_disposition": attribution_by_id[claim_id]["synthesis_disposition"],
            "agenda_is_not_answer": attribution_by_id[claim_id]["synthesis_disposition"] == "preserve_as_agenda_not_answer",
            "review_method": attestation["review_method"],
            "reviewed_at": attestation["reviewed_at"],
        })
    representative_rows.sort(key=lambda row: (row["theme_id"], row["claim_id"]))

    sample_policy = policy["deterministic_sample"]
    sample_rows = []
    per_stratum = sample_policy["rows_per_nonempty_attribution_class_and_claim_type_stratum"]
    for (attribution_class, claim_type), stratum_claims in sorted(strata.items()):
        ranked = sorted(
            stratum_claims,
            key=lambda claim: sha256_bytes((sample_policy["salt"] + "\0" + claim["claim_id"]).encode("utf-8")),
        )
        for rank, claim in enumerate(ranked[:per_stratum], 1):
            evidence = claim["evidence"][0]
            sample_rows.append({
                "schema_name": "nuwa-v1-evaluation-sample",
                "schema_version": 1,
                "sample_stratum": f"{attribution_class}|{claim_type}",
                "sample_rank": rank,
                "selection_digest": sha256_bytes((sample_policy["salt"] + "\0" + claim["claim_id"]).encode("utf-8")),
                "claim_id": claim["claim_id"],
                "claim_row_sha256": sha256_bytes(canonical_json(claim)),
                "analysis_unit_id": evidence["analysis_unit_id"],
                "work_id": evidence["work_id"],
                "edition_id": evidence["edition_id"],
                "passage_id": evidence["passage_id"],
                "exact_quote_sha256": evidence["exact_quote_sha256"],
                "attribution_class": attribution_class,
                "claim_type": claim_type,
                "evaluation_scope": sample_policy["purpose"],
                "structural_traceability_status": "pass",
                "semantic_accuracy_judgment": "not_claimed_by_this_sample",
            })
    sample_rows.sort(key=lambda row: (row["sample_stratum"], row["sample_rank"]))

    representative_payload = b"".join(canonical_json(row) for row in representative_rows)
    sample_payload = b"".join(canonical_json(row) for row in sample_rows)
    report_lines = [
        "# AMind v1 评测报告",
        "",
        "## 结论",
        "",
        "AMind v1 已通过发布前的两层评测：52,225 条原子主张全部能逐条回连到冻结分析单位、作品、版本、正文段落和原文引句；综合报告使用的 54 条代表证据已逐条阅读完整绑定段落，未发现改变归属、语气、条件或时间范围的失真。",
        "",
        "这项 PASS 是一个**来源追溯与代表证据质量**结论，不是对 52,225 条主张逐条人工语义复核后的总体准确率估计。随机/分层样本只作为未来外部校准的稳定入口，不被包装成精度分数。",
        "",
        "## 全量结构检查",
        "",
        f"- 主张：{len(claims):,}/{len(claims):,} 引句哈希正确且原文出现在绑定段落中。",
        f"- 证据外键：{full_fk_count:,}/{len(claims):,} 主张与 passage / unit / work / edition / body / text-file 一致。",
        f"- 归属：{len(attribution):,}/{len(claims):,} 恰好一条；研究问题、引述、模拟与嵌入样例保留各自边界。",
        f"- 等价组件：{len(equivalence):,} 个，成员互不重叠；显式版本组件 {len(versions)} 个，双版本保留且不推断替代方向。",
        f"- 词汇对立候选：{len(contradictions)} 个，均已在来源上下文中终态裁决；不声称语义矛盾发现完备。",
        "",
        "## 代表证据复核",
        "",
        f"- 54/54 条代表证据通过完整段落复核；其中 {sum(row['support_mode'] == 'full_passage_context_required_and_reviewed' for row in representative_rows)} 条需要结合完整段落，而不能只看短引句。",
        f"- {sum(row['agenda_is_not_answer'] for row in representative_rows)} 条代表证据是研究议程，已明确标为问题而非答案。",
        "- 每条复核记录都绑定 claim、passage、work、edition、引句哈希与段落哈希，可独立重放。",
        "",
        "## 可复现实验样本",
        "",
        f"按 attribution_class × claim_type 分层，以固定盐选择 {len(sample_rows)} 条样本；每个非空层最多 {per_stratum} 条。该样本用于后续人工或外部模型校准，不用于声称当前全量语义准确率。",
        "",
        "## 已知边界",
        "",
        "- 主题是非互斥归纳，不声称穷尽所有可能思想分类。",
        "- 主张频次表示语料覆盖，不表示组织共识、作者权重或因果重要性。",
        "- 3 个有界 unavailable 分析单位没有正文，也没有伪造主张。",
        "- 本轮没有扩展普通外链，没有读取 active Common Crawl Direct 索引，也没有用参考仓库生成结论。",
        "- 语义矛盾筛查是有界发现机制；完整语义审校仍是后续版本的可扩展评测项。",
        "",
        "## 可复算入口",
        "",
        "逐条代表证据复核、确定性分层样本与总审计分别位于 `corpus/nuwa-v1-representative-evidence-review.jsonl`、`corpus/nuwa-v1-evaluation-sample.jsonl` 和 `corpus/nuwa-v1-evaluation-audit.json`。",
        "",
    ]
    report_payload = "\n".join(report_lines).encode("utf-8")

    payloads: dict[Path, bytes] = {
        REPRESENTATIVE_REVIEW: representative_payload,
        SAMPLE: sample_payload,
        REPORT: report_payload,
    }
    counts = {
        "analysis_units": len(units),
        "body_units": sum(unit["unit_status"] == "body_primary" for unit in units),
        "bounded_unavailable_units": sum(unit["unit_status"] == "bounded_unavailable_exception" for unit in units),
        "claims": len(claims),
        "passages": len(passages),
        "claims_with_exact_quote_in_owned_passage": quote_within_passage_count,
        "claims_with_complete_unit_passage_work_edition_body_text_fk": full_fk_count,
        "attribution_rows": len(attribution),
        "equivalence_components": len(equivalence),
        "version_components": len(versions),
        "terminal_contradiction_candidates": len(contradictions),
        "themes": len(themes),
        "voice_profiles": len(voices),
        "synthesis_tensions": len(synthesis_tensions),
        "representative_evidence_reviewed": len(representative_rows),
        "representative_evidence_supported": sum(row["semantic_review_status"] == "passage_context_supported" for row in representative_rows),
        "representative_agenda_rows": sum(row["agenda_is_not_answer"] for row in representative_rows),
        "deterministic_sample_rows": len(sample_rows),
        "deterministic_sample_strata": len(strata),
    }
    input_paths = [
        POLICY, CLAIMS, PASSAGES, UNITS, ATTRIBUTION, EQUIVALENCE, VERSIONS,
        CONTRADICTIONS, CLAIM_AUDIT, MEMBERSHIP, SYNTHESIS_EVIDENCE, THEMES,
        VOICE_PROFILES, SYNTHESIS_TENSIONS, SYNTHESIS_AUDIT,
        Path(__file__).resolve(), TESTS,
    ]
    input_fingerprints = {
        path.relative_to(ROOT).as_posix(): {"sha256": sha256_bytes(path.read_bytes()), "bytes": path.stat().st_size}
        for path in input_paths
    }
    output_fingerprints = {
        path.relative_to(ROOT).as_posix(): {"sha256": sha256_bytes(payload), "bytes": len(payload), "rows": payload.count(b"\n")}
        for path, payload in payloads.items()
    }
    audit = {
        "schema_name": "nuwa-v1-evaluation-audit",
        "schema_version": 1,
        "verdict": "PASS",
        "safe_to_assemble_nuwa_v1_release": True,
        "counts": counts,
        "attribution_class_counts": dict(sorted(attribution_counts.items())),
        "claim_type_counts": dict(sorted(claim_type_counts.items())),
        "input_fingerprints": dict(sorted(input_fingerprints.items())),
        "input_snapshot_sha256": sha256_bytes(canonical_json(dict(sorted(input_fingerprints.items())))),
        "output_fingerprints": output_fingerprints,
        "invariants": {
            "all_claims_have_exact_source_bound_quotes": True,
            "all_claims_have_complete_unit_passage_work_edition_body_text_foreign_keys": True,
            "attribution_is_claim_complete_and_exact_once": True,
            "representative_evidence_human_reviewed_against_full_bound_passage": True,
            "research_agenda_not_promoted_to_answer": True,
            "explicit_version_boundary_preserved": True,
            "screened_tensions_terminal_but_semantic_exhaustiveness_not_claimed": True,
            "deterministic_sample_is_not_a_semantic_accuracy_estimate": True,
            "full_population_semantic_human_review_claimed": False,
            "claim_frequency_interpreted_as_consensus_weight": False,
            "network_access_count": 0,
            "ordinary_outbound_link_expansion_count": 0,
            "active_commoncrawl_direct_index_read": False,
            "reference_repository_used_to_generate_conclusions": False,
        },
    }
    payloads[AUDIT] = canonical_json(audit)
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
            require(path.is_file(), f"missing output: {path.relative_to(ROOT)}")
            require(path.read_bytes() == expected, f"output drift: {path.relative_to(ROOT)}")
    else:
        for path, payload in payloads.items():
            atomic_write(path, payload)
    counts = audit["counts"]
    print(
        "PASS "
        f"claims={counts['claims']} representatives={counts['representative_evidence_reviewed']} "
        f"sample={counts['deterministic_sample_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
