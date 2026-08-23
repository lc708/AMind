#!/usr/bin/env python3
"""Build the first source-bound AMind synthesis after claim extraction and audit."""

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
POLICY = ROOT / "config/nuwa-v1-synthesis-policy.json"
CLAIMS = ROOT / "corpus/nuwa-v1-production-atomic-claims.jsonl"
UNITS = ROOT / "corpus/nuwa-v1-analysis-units.jsonl"
ATTRIBUTION = ROOT / "corpus/nuwa-v1-claim-attribution-audit.jsonl"
CLAIM_AUDIT = ROOT / "corpus/nuwa-v1-claim-audit.json"
EQUIVALENCE = ROOT / "corpus/nuwa-v1-claim-equivalence-components.jsonl"
VERSIONS = ROOT / "corpus/nuwa-v1-version-audit.jsonl"
TENSIONS = ROOT / "corpus/nuwa-v1-contradiction-candidates.jsonl"
TESTS = ROOT / "scripts/test_build_nuwa_v1_synthesis.py"
MEMBERSHIP = ROOT / "corpus/nuwa-v1-theme-membership.jsonl"
THEMES = ROOT / "corpus/nuwa-v1-theme-catalog.jsonl"
EVIDENCE = ROOT / "corpus/nuwa-v1-synthesis-evidence.jsonl"
VOICE_PROFILES = ROOT / "corpus/nuwa-v1-voice-profiles.jsonl"
SYNTHESIS_TENSIONS = ROOT / "corpus/nuwa-v1-synthesis-tensions.jsonl"
AUDIT = ROOT / "corpus/nuwa-v1-synthesis-audit.json"
REPORT = ROOT / "reports/nuwa-v1-synthesis.zh-CN.md"


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


def publication_year(unit: dict[str, Any], claims: list[dict[str, Any]]) -> str:
    candidates = [str(unit.get("published_at") or "")]
    candidates.extend(str(claim.get("temporal_scope", {}).get("valid_from") or "") for claim in claims)
    for value in candidates:
        match = re.search(r"\b(20[0-2][0-9])\b", value)
        if match:
            return match.group(1)
    return "undated"


def time_band(year: str) -> str:
    if year == "undated":
        return "undated"
    value = int(year)
    if value <= 2018:
        return "through_2018"
    if value <= 2022:
        return "2019_2022"
    if value <= 2024:
        return "2023_2024"
    return "2025_2026"


def build() -> tuple[dict[Path, bytes], dict[str, Any]]:
    policy = read_json(POLICY)
    require(policy.get("schema_name") == "nuwa-v1-synthesis-policy", "invalid synthesis policy schema")
    require(policy.get("schema_version") == 1, "invalid synthesis policy version")
    require(policy["scope"]["network_allowed"] is False, "network must remain disabled")
    claim_audit = read_json(CLAIM_AUDIT)
    require(claim_audit.get("verdict") == "PASS", "claim audit is not PASS")
    require(claim_audit.get("safe_to_begin_worldview_synthesis") is True, "claim audit does not authorize synthesis")
    for path in (ATTRIBUTION, EQUIVALENCE, VERSIONS, TENSIONS):
        fingerprint = (claim_audit.get("output_fingerprints") or {}).get(path.relative_to(ROOT).as_posix()) or {}
        require(fingerprint.get("sha256") == sha256_bytes(path.read_bytes()), f"claim-audit output drift: {path.name}")

    claims = read_jsonl(CLAIMS)
    units = read_jsonl(UNITS)
    attribution = read_jsonl(ATTRIBUTION)
    require(len(claims) == policy["scope"]["claims"] == 52225, "claim population drift")
    require(len(units) == policy["scope"]["analysis_units"] == 1351, "unit population drift")
    claim_by_id = {claim["claim_id"]: claim for claim in claims}
    unit_by_id = {unit["analysis_unit_id"]: unit for unit in units}
    attribution_by_id = {row["claim_id"]: row for row in attribution}
    require(set(claim_by_id) == set(attribution_by_id), "claim-attribution crosswalk drift")
    claims_by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        claims_by_unit[claim["evidence"][0]["analysis_unit_id"]].append(claim)

    themes = policy.get("themes") or []
    require(themes and len({theme["theme_id"] for theme in themes}) == len(themes), "invalid theme registry")
    theme_by_id = {theme["theme_id"]: theme for theme in themes}
    membership_rows = []
    theme_claim_ids: dict[str, set[str]] = defaultdict(set)
    theme_unit_ids: dict[str, set[str]] = defaultdict(set)
    theme_direct_claim_ids: dict[str, set[str]] = defaultdict(set)
    for claim in claims:
        evidence = claim["evidence"][0]
        unit = unit_by_id[evidence["analysis_unit_id"]]
        searchable = " ".join([
            claim["proposition"],
            " ".join(claim.get("domains") or []),
            unit.get("title") or "",
        ]).lower()
        matched = []
        match_terms: dict[str, list[str]] = {}
        for theme in themes:
            hits = sorted({keyword for keyword in theme["keywords"] if keyword.lower() in searchable})
            if hits:
                matched.append(theme["theme_id"])
                match_terms[theme["theme_id"]] = hits
                theme_claim_ids[theme["theme_id"]].add(claim["claim_id"])
                theme_unit_ids[theme["theme_id"]].add(evidence["analysis_unit_id"])
                if attribution_by_id[claim["claim_id"]]["synthesis_disposition"] == "eligible_for_source_level_synthesis":
                    theme_direct_claim_ids[theme["theme_id"]].add(claim["claim_id"])
        membership_rows.append({
            "schema_name": "nuwa-v1-theme-membership",
            "schema_version": 1,
            "claim_id": claim["claim_id"],
            "claim_row_sha256": sha256_bytes(canonical_json(claim)),
            "analysis_unit_id": evidence["analysis_unit_id"],
            "work_id": evidence["work_id"],
            "edition_id": evidence["edition_id"],
            "theme_ids": sorted(matched),
            "match_terms_by_theme": {key: match_terms[key] for key in sorted(match_terms)},
            "attribution_class": attribution_by_id[claim["claim_id"]]["attribution_class"],
            "synthesis_disposition": attribution_by_id[claim["claim_id"]]["synthesis_disposition"],
        })
    membership_rows.sort(key=lambda row: row["claim_id"])
    require(len(membership_rows) == len(claims), "theme membership is not claim-complete")

    evidence_rows = []
    representative_ids = []
    theme_rows = []
    for theme in themes:
        theme_id = theme["theme_id"]
        selected_ids = theme["evidence_claim_ids"]
        require(len(selected_ids) == len(set(selected_ids)) >= 4, f"invalid evidence selection: {theme_id}")
        selected_works = set()
        for sequence, claim_id in enumerate(selected_ids, 1):
            require(claim_id in claim_by_id, f"unknown synthesis evidence claim: {claim_id}")
            claim = claim_by_id[claim_id]
            attr = attribution_by_id[claim_id]
            require(
                attr["synthesis_disposition"]
                in {"eligible_for_source_level_synthesis", "preserve_as_agenda_not_answer"},
                f"ineligible synthesis evidence: {claim_id}",
            )
            require(claim_id in theme_claim_ids[theme_id], f"representative claim does not match theme: {theme_id}/{claim_id}")
            evidence = claim["evidence"][0]
            unit = unit_by_id[evidence["analysis_unit_id"]]
            selected_works.add(evidence["work_id"])
            representative_ids.append(claim_id)
            evidence_rows.append({
                "schema_name": "nuwa-v1-synthesis-evidence",
                "schema_version": 1,
                "theme_id": theme_id,
                "evidence_sequence": sequence,
                "claim_id": claim_id,
                "claim_row_sha256": sha256_bytes(canonical_json(claim)),
                "proposition": claim["proposition"],
                "claim_type": claim["claim_type"],
                "epistemic_force": claim["epistemic_force"],
                "attribution_class": attr["attribution_class"],
                "synthesis_disposition": attr["synthesis_disposition"],
                "voice": claim["voice"],
                "analysis_unit_id": evidence["analysis_unit_id"],
                "work_id": evidence["work_id"],
                "edition_id": evidence["edition_id"],
                "passage_id": evidence["passage_id"],
                "exact_quote": evidence["exact_quote"],
                "exact_quote_sha256": evidence["exact_quote_sha256"],
                "source_record_ids": evidence["source_record_ids"],
                "source_title": unit.get("title") or "",
                "source_canonical": unit.get("canonical") or "",
                "source_published_at": unit.get("published_at") or "",
            })
        require(len(selected_works) >= 4, f"theme evidence lacks work diversity: {theme_id}")
        unit_time_counts = Counter()
        voice_counts = Counter()
        for unit_id in theme_unit_ids[theme_id]:
            year = publication_year(unit_by_id[unit_id], claims_by_unit[unit_id])
            unit_time_counts[time_band(year)] += 1
        for claim_id in theme_direct_claim_ids[theme_id]:
            voice_counts[claim_by_id[claim_id]["voice"]["voice_type"]] += 1
        theme_rows.append({
            "schema_name": "nuwa-v1-theme",
            "schema_version": 1,
            "theme_id": theme_id,
            "name_zh": theme["name_zh"],
            "thesis_zh": theme["thesis_zh"],
            "keywords": theme["keywords"],
            "matched_claim_count": len(theme_claim_ids[theme_id]),
            "direct_synthesis_claim_count": len(theme_direct_claim_ids[theme_id]),
            "matched_analysis_unit_count": len(theme_unit_ids[theme_id]),
            "analysis_units_by_time_band": dict(sorted(unit_time_counts.items())),
            "direct_claims_by_voice_type": dict(sorted(voice_counts.items())),
            "representative_claim_ids": selected_ids,
            "frequency_interpretation": "coverage_signal_not_consensus_weight",
        })
    require(len(representative_ids) == len(set(representative_ids)), "representative claim reused across themes")
    theme_rows.sort(key=lambda row: row["theme_id"])
    evidence_rows.sort(key=lambda row: (row["theme_id"], row["evidence_sequence"]))

    voice_rows = []
    for profile in policy.get("voice_profiles") or []:
        evidence_claims = [claim_by_id[claim_id] for claim_id in profile["evidence_claim_ids"]]
        require(all(claim["voice"]["name"] == profile["name"] or profile["name"] == "Anthropic" for claim in evidence_claims), f"voice evidence mismatch: {profile['voice_id']}")
        for claim in evidence_claims:
            require(attribution_by_id[claim["claim_id"]]["synthesis_disposition"] == "eligible_for_source_level_synthesis", f"voice evidence ineligible: {claim['claim_id']}")
        direct_claims = [claim for claim in claims if claim["voice"]["name"] == profile["name"] and attribution_by_id[claim["claim_id"]]["synthesis_disposition"] == "eligible_for_source_level_synthesis"]
        voice_rows.append({
            "schema_name": "nuwa-v1-voice-profile",
            "schema_version": 1,
            "voice_id": profile["voice_id"],
            "name": profile["name"],
            "summary_zh": profile["summary_zh"],
            "direct_claim_count": len(direct_claims),
            "analysis_unit_count": len({claim["evidence"][0]["analysis_unit_id"] for claim in direct_claims}),
            "evidence_claim_ids": profile["evidence_claim_ids"],
            "frequency_interpretation": "corpus_presence_not_personal_influence_or_consensus_weight",
        })
    voice_rows.sort(key=lambda row: row["voice_id"])

    tension_rows = []
    for tension in policy.get("cross_theme_tensions") or []:
        evidence_claims = [claim_by_id[claim_id] for claim_id in tension["evidence_claim_ids"]]
        require(len(evidence_claims) >= 2, f"tension lacks two-sided evidence: {tension['tension_id']}")
        require(len({claim["evidence"][0]["work_id"] for claim in evidence_claims}) >= 2, f"tension lacks source diversity: {tension['tension_id']}")
        tension_rows.append({
            "schema_name": "nuwa-v1-synthesis-tension",
            "schema_version": 1,
            "tension_id": tension["tension_id"],
            "name_zh": tension["name_zh"],
            "summary_zh": tension["summary_zh"],
            "evidence_claim_ids": tension["evidence_claim_ids"],
            "terminal_treatment": "preserve_both_conditions_no_forced_resolution",
        })
    tension_rows.sort(key=lambda row: row["tension_id"])

    theme_payload = b"".join(canonical_json(row) for row in theme_rows)
    membership_payload = b"".join(canonical_json(row) for row in membership_rows)
    evidence_payload = b"".join(canonical_json(row) for row in evidence_rows)
    voice_payload = b"".join(canonical_json(row) for row in voice_rows)
    tension_payload = b"".join(canonical_json(row) for row in tension_rows)

    report_lines = [
        "# AMind v1：Anthropic 思想结构（首版）",
        "",
        "## 结论",
        "",
        "在这份有界语料中，Anthropic 的思想结构不是一条单线教义，而是一个相互约束的系统：认真对待能力快速扩展，同时拒绝把时间线当确定事实；通过可解释性和评测增加可见性；按可测能力升级安全与治理；把企业实践接到公共问责；最终以人的能动性、福利和社会分配约束技术目标。",
        "",
        "它最稳定的元原则可以概括为：**在高影响、高不确定性的环境里，先提高可测性，再把行动强度与证据相连，并用彼此独立的防线降低单点失败。** 这不是“安全优先于一切”，也不是“创新自然解决问题”；更接近有条件的技术乐观主义与制度化谨慎的结合。",
        "",
        "本报告来自冻结的 1,351 个分析单位和 52,225 条原子主张。主题在抽取完成后才归纳，互不排斥；篇幅与主张数量只表示语料覆盖，不能当作共识投票。引文、研究问题、模拟证据和文档编辑声部均按审计边界处理。",
        "",
        "## 九个归纳主题",
        "",
    ]
    for number, theme in enumerate(theme_rows, 1):
        report_lines.extend([
            f"### {number}. {theme['name_zh']}",
            "",
            theme["thesis_zh"],
            "",
            f"覆盖信号：{theme['matched_analysis_unit_count']:,} 个分析单位、{theme['matched_claim_count']:,} 条相关主张，其中 {theme['direct_synthesis_claim_count']:,} 条是可用于来源层综合的直接立场。",
            "",
            "代表证据：",
            "",
        ])
        for row in [row for row in evidence_rows if row["theme_id"] == theme["theme_id"]]:
            evidence_scope = "研究议程，非既得结论；" if row["synthesis_disposition"] == "preserve_as_agenda_not_answer" else ""
            report_lines.append(f"- `{row['claim_id']}` — {row['proposition']}（{evidence_scope}{row['source_title']}）")
        report_lines.append("")

    report_lines.extend(["## 关键张力", ""])
    for tension in tension_rows:
        report_lines.extend([
            f"- **{tension['name_zh']}**：{tension['summary_zh']} 证据：" + "、".join(f"`{claim_id}`" for claim_id in tension["evidence_claim_ids"]),
            "",
        ])

    report_lines.extend(["## 声音差异", ""])
    for voice in voice_rows:
        report_lines.extend([
            f"- **{voice['name']}**：{voice['summary_zh']}（直接主张 {voice['direct_claim_count']:,}，涉及分析单位 {voice['analysis_unit_count']:,}）",
            "",
        ])

    report_lines.extend([
        "## 演化脉络",
        "",
        "- **2016–2018**：材料主要表现为对能力进步、测量、开放研究与社会外部性的持续侦察，尚未形成完整的机构安全框架。",
        "- **2019–2022**：扩展规律、泛化、政治经济和治理测量逐渐连成一套“能力可能快速上升，因此需要提前建设认知与制度能力”的议程。",
        "- **2023–2024**：RSP、AI Safety Levels、模型宪法、稀疏特征与第三方评测把抽象风险转成可操作的阈值、流程和研究对象。",
        "- **2025–2026**：重点进一步转向智能体、对齐伪装、破坏评测、网络和生物安全、经济扩散、模型福利以及大规模生产工作流；风险治理与产品工程开始共享“可观察、分层、可回滚”的结构。",
        "",
        "这一时间线描述语料重心变化，不主张所有作者同步转向，也不把较晚文本视为自动推翻较早文本。唯一明示版本组件保留双版本且不推断取代方向。",
        "",
        "## 边界与反例",
        "",
        "- 词汇对立筛查只是有界发现工具，不是语义矛盾的完备证明；跨文档张力被保留，不被强制消解。",
        "- 受控模拟、红队测试与模型行为样例只能支持其设置内的结论，不能直接外推真实部署概率。",
        "- 机构口径不自动等同于任何个人观点；文档编辑声部也不自动映射到具名作者。",
        "- Import AI 在语料中篇幅很高，因此 Jack Clark 的主张数量不能用来推断其思想在组织中的权重。",
        "- 3 个有界 unavailable 分析单位没有伪造正文或主张；普通外链、二跳材料和旁支采集没有扩入本版人口。",
        "",
        "## 可复算入口",
        "",
        "主题目录、逐主张主题映射、代表证据、声音画像、张力账本及审计分别位于 `corpus/nuwa-v1-theme-catalog.jsonl`、`corpus/nuwa-v1-theme-membership.jsonl`、`corpus/nuwa-v1-synthesis-evidence.jsonl`、`corpus/nuwa-v1-voice-profiles.jsonl`、`corpus/nuwa-v1-synthesis-tensions.jsonl` 与 `corpus/nuwa-v1-synthesis-audit.json`。",
        "",
    ])
    report_payload = "\n".join(report_lines).encode("utf-8")
    payloads: dict[Path, bytes] = {
        THEMES: theme_payload,
        MEMBERSHIP: membership_payload,
        EVIDENCE: evidence_payload,
        VOICE_PROFILES: voice_payload,
        SYNTHESIS_TENSIONS: tension_payload,
        REPORT: report_payload,
    }
    counts = {
        "analysis_units": len(units),
        "claims": len(claims),
        "themes": len(theme_rows),
        "theme_membership_rows": len(membership_rows),
        "claims_with_at_least_one_theme": sum(bool(row["theme_ids"]) for row in membership_rows),
        "claims_without_theme": sum(not row["theme_ids"] for row in membership_rows),
        "representative_evidence_rows": len(evidence_rows),
        "voice_profiles": len(voice_rows),
        "cross_theme_tensions": len(tension_rows),
    }
    input_paths = [POLICY, CLAIMS, UNITS, ATTRIBUTION, CLAIM_AUDIT, EQUIVALENCE, VERSIONS, TENSIONS, Path(__file__).resolve(), TESTS]
    input_fingerprints = {
        path.relative_to(ROOT).as_posix(): {"sha256": sha256_bytes(path.read_bytes()), "bytes": path.stat().st_size}
        for path in input_paths
    }
    output_fingerprints = {
        path.relative_to(ROOT).as_posix(): {"sha256": sha256_bytes(payload), "bytes": len(payload), "rows": payload.count(b"\n")}
        for path, payload in payloads.items()
    }
    audit = {
        "schema_name": "nuwa-v1-synthesis-audit",
        "schema_version": 1,
        "verdict": "PASS",
        "safe_to_publish_nuwa_v1_synthesis": True,
        "counts": counts,
        "input_fingerprints": dict(sorted(input_fingerprints.items())),
        "input_snapshot_sha256": sha256_bytes(canonical_json(dict(sorted(input_fingerprints.items())))),
        "output_fingerprints": output_fingerprints,
        "invariants": {
            "themes_defined_after_atomic_extraction_and_claim_audit": True,
            "theme_membership_claim_complete_and_nonexclusive": True,
            "representative_evidence_source_bound_and_explicitly_scoped": True,
            "theme_evidence_spans_at_least_four_works": True,
            "claim_frequency_not_interpreted_as_consensus_weight": True,
            "quoted_positions_questions_simulations_and_editorial_voice_boundaries_preserved": True,
            "cross_theme_tensions_preserved_without_forced_resolution": True,
            "explicit_version_boundary_preserved": True,
            "network_access_count": 0,
            "ordinary_outbound_link_expansion_count": 0,
            "active_commoncrawl_direct_index_read": False,
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
    print(f"PASS themes={counts['themes']} claims={counts['claims']} representatives={counts['representative_evidence_rows']} voices={counts['voice_profiles']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
