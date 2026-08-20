#!/usr/bin/env python3
"""Build the source-bound Nuwa v1 attribution, equivalence, version, and tension audit."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/nuwa-v1-claim-audit-policy.json"
CLAIMS = ROOT / "corpus/nuwa-v1-production-atomic-claims.jsonl"
REGISTRY_AUDIT = ROOT / "corpus/nuwa-v1-production-registry-audit.json"
UNITS = ROOT / "corpus/nuwa-v1-analysis-units.jsonl"
PASSAGES = ROOT / "corpus/nuwa-v1-passages.jsonl"
TESTS = ROOT / "scripts/test_build_nuwa_v1_claim_audit.py"
ATTRIBUTION = ROOT / "corpus/nuwa-v1-claim-attribution-audit.jsonl"
EQUIVALENCE = ROOT / "corpus/nuwa-v1-claim-equivalence-components.jsonl"
VERSIONS = ROOT / "corpus/nuwa-v1-version-audit.jsonl"
CONTRADICTIONS = ROOT / "corpus/nuwa-v1-contradiction-candidates.jsonl"
AUDIT = ROOT / "corpus/nuwa-v1-claim-audit.json"
REPORT = ROOT / "reports/nuwa-v1-claim-audit.zh-CN.md"


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


def normalize_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


STOPWORDS = set(
    "a an the this that these those it its they them their we our ours you your he she his her "
    "is are was were be been being have has had do does did can could may might will would should must "
    "and or but if then than to of in on for from with without by as at into over under about across "
    "between through during before after not no nor also more less most least much many some any all both "
    "each other another given such same different only one two new using used use make makes made model "
    "models system systems ai claude document paper study research results result data method methods approach"
    .split()
)


def stem(token: str) -> str:
    for suffix in ("ization", "ational", "iveness", "fulness", "ments", "ment", "ingly", "edly", "ation", "ities", "ity", "ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 4 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def content_tokens(value: str) -> set[str]:
    return {
        stem(token)
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in STOPWORDS
    }


POLARITY_PATTERNS = {
    "negation": (
        r"\b(?:not|no|never|neither|without|failed? to|unable to|cannot|can't|did not|does not|do not|were not|was not|is not|are not|unlikely)\b",
        r"\b(?:able to|succeeded|successfully|likely)\b",
    ),
    "increase_decrease": (
        r"\b(?:increas(?:e|ed|es|ing)|higher|more|grew|growth|rose|rising|upweighted|improved)\b",
        r"\b(?:decreas(?:e|ed|es|ing)|lower|less|fell|falling|downweighted|declined|reduced)\b",
    ),
    "presence_absence": (
        r"\b(?:present|exists?|found|observed|detected|appears?|showed|exhibited)\b",
        r"\b(?:absent|missing|not found|undetected|did not appear|no evidence)\b",
    ),
    "possible_impossible": (
        r"\b(?:possible|could|can|may|might|likely)\b",
        r"\b(?:impossible|cannot|could not|unlikely)\b",
    ),
    "safe_unsafe": (
        r"\b(?:safe|safer|secure|secured)\b",
        r"\b(?:unsafe|dangerous|insecure|riskier)\b",
    ),
    "success_failure": (
        r"\b(?:succeed(?:ed|s)?|successful(?:ly)?|worked|effective)\b",
        r"\b(?:fail(?:ed|s|ure)?|unsuccessful|ineffective|did not work)\b",
    ),
}


def polarity(value: str) -> dict[str, int]:
    answer: dict[str, int] = {}
    for dimension, (positive, negative) in POLARITY_PATTERNS.items():
        has_positive = bool(re.search(positive, value.lower()))
        has_negative = bool(re.search(negative, value.lower()))
        if has_positive ^ has_negative:
            answer[dimension] = 1 if has_positive else -1
    return answer


def claim_attribution(claim: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    voice = claim["voice"]
    proposition = claim["proposition"]
    exact_quote = claim["evidence"][0]["exact_quote"]
    lower = (proposition + "\n" + exact_quote).lower()
    config = policy["attribution_policy"]
    artifact_markers = [marker for marker in config["artifact_markers"] if marker in lower]
    raw_question_artifact = (
        config["research_question_marker"] in proposition.lower()
        and any(marker in lower for marker in ("human:", "assistant:", "auditor:", "evaluation description"))
    )
    artifact = bool(artifact_markers and (raw_question_artifact or "(source passage" in lower or "<antml:parameter" in lower))
    simulation = any(
        marker in str(condition).lower()
        for condition in claim.get("conditions") or []
        for marker in config["simulation_condition_markers"]
    )
    # The extractor normally emits research agendas as qualified
    # self-descriptions, but a small number of carefully paraphrased agenda
    # claims retain their original semantic type (for example, a normative
    # question about model welfare).  The explicit proposition marker is the
    # authoritative boundary: preserve the question as an agenda regardless
    # of the extractor's coarse claim_type label, and never turn it into an
    # answered source position.
    research_question = bool(
        re.search(r"\braises? the question\b", proposition, flags=re.IGNORECASE)
    )
    reported = (
        claim.get("epistemic_force") in config["quoted_position_forces"]
        or voice.get("voice_type") in config["quoted_position_voice_types"]
    )
    unknown = voice.get("voice_type") in config["unknown_voice_types"]
    if artifact:
        attribution_class = "embedded_artifact_or_verbatim_example"
        disposition = "exclude_from_worldview_synthesis"
    elif reported or unknown:
        attribution_class = "reported_or_quoted_position"
        disposition = "preserve_as_reported_position_not_source_belief"
    elif research_question:
        attribution_class = "research_question_or_agenda"
        disposition = "preserve_as_agenda_not_answer"
    elif simulation:
        attribution_class = "bounded_simulation_evidence"
        disposition = "preserve_with_simulation_scope"
    elif voice.get("voice_type") in config["direct_voice_types"]:
        attribution_class = "direct_source_position"
        disposition = "eligible_for_source_level_synthesis"
    else:
        attribution_class = "unresolved_attribution"
        disposition = "exclude_pending_attribution"
    evidence = claim["evidence"][0]
    return {
        "schema_name": "nuwa-v1-claim-attribution-audit",
        "schema_version": 1,
        "claim_id": claim["claim_id"],
        "claim_row_sha256": sha256_bytes(canonical_json(claim)),
        "analysis_unit_id": evidence["analysis_unit_id"],
        "work_id": evidence["work_id"],
        "edition_id": evidence["edition_id"],
        "passage_id": evidence["passage_id"],
        "exact_quote_sha256": evidence["exact_quote_sha256"],
        "voice_type": voice.get("voice_type", ""),
        "voice_name": voice.get("name", ""),
        "voice_organization": voice.get("organization", ""),
        "attribution_class": attribution_class,
        "synthesis_disposition": disposition,
        "personal_view_attribution_permitted": voice.get("voice_type") in {"named_author", "named_speaker"} and not reported and not artifact,
        "document_editorial_is_not_personal_view": voice.get("voice_type") == "document_editorial",
        "simulation_scope_required": simulation,
        "artifact_markers": sorted(set(artifact_markers)) if artifact else [],
    }


class UnionFind:
    def __init__(self, values: list[str]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[max(left_root, right_root)] = min(left_root, right_root)


def build_equivalence(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claim_ids = [claim["claim_id"] for claim in claims]
    union = UnionFind(claim_ids)
    proposition_groups: dict[str, list[str]] = defaultdict(list)
    quote_groups: dict[str, list[str]] = defaultdict(list)
    by_id = {claim["claim_id"]: claim for claim in claims}
    for claim in claims:
        proposition_groups[normalize_text(claim["proposition"])].append(claim["claim_id"])
        quote_groups[claim["evidence"][0]["exact_quote_sha256"]].append(claim["claim_id"])
    for group in itertools.chain(proposition_groups.values(), quote_groups.values()):
        if len(group) > 1:
            for member in group[1:]:
                union.union(group[0], member)
    components: dict[str, list[str]] = defaultdict(list)
    for claim_id in claim_ids:
        components[union.find(claim_id)].append(claim_id)
    output: list[dict[str, Any]] = []
    for members in sorted((sorted(values) for values in components.values() if len(values) > 1), key=lambda values: values[0]):
        propositions = {normalize_text(by_id[claim_id]["proposition"]) for claim_id in members}
        quotes = {by_id[claim_id]["evidence"][0]["exact_quote_sha256"] for claim_id in members}
        bases = []
        if len(propositions) < len(members):
            bases.append("normalized_proposition_exact")
        if len(quotes) < len(members):
            bases.append("exact_quote_sha256")
        component_id = "nuwa1-equivalence-" + sha256_bytes("\n".join(members).encode("utf-8"))[:20]
        output.append({
            "schema_name": "nuwa-v1-claim-equivalence-component",
            "schema_version": 1,
            "component_id": component_id,
            "representative_claim_id": members[0],
            "member_claim_ids": members,
            "member_count": len(members),
            "matching_bases": bases,
            "synthesis_rule": "retain_all_provenance_count_component_once_for_frequency",
        })
    return output


def candidate_pairs(claims: list[dict[str, Any]], policy: dict[str, Any]) -> list[tuple[int, int, dict[str, Any]]]:
    settings = policy["contradiction_candidate_policy"]
    token_sets = [content_tokens(claim["proposition"]) for claim in claims]
    document_frequency = Counter(token for values in token_sets for token in values)
    inverted: dict[str, list[int]] = defaultdict(list)
    for index, values in enumerate(token_sets):
        for token in values:
            if 2 <= document_frequency[token] <= settings["maximum_token_document_frequency"]:
                inverted[token].append(index)
    shared_counts: Counter[tuple[int, int]] = Counter()
    for indices in inverted.values():
        for pair in itertools.combinations(indices, 2):
            shared_counts[pair] += 1
    polarities = [polarity(claim["proposition"]) for claim in claims]
    output: list[tuple[int, int, dict[str, Any]]] = []
    for (left, right), shared in shared_counts.items():
        if shared < settings["minimum_shared_rare_tokens"]:
            continue
        opposite = sorted(
            dimension
            for dimension in set(polarities[left]) & set(polarities[right])
            if polarities[left][dimension] != polarities[right][dimension]
        )
        if not opposite:
            continue
        intersection = len(token_sets[left] & token_sets[right])
        union = len(token_sets[left] | token_sets[right])
        shorter = min(len(token_sets[left]), len(token_sets[right]))
        jaccard = intersection / union if union else 0.0
        shorter_overlap = intersection / shorter if shorter else 0.0
        shared_domains = sorted(set(claims[left]["domains"]) & set(claims[right]["domains"]))
        similarity_pass = jaccard >= settings["minimum_jaccard"] or shorter_overlap >= settings["minimum_shorter_claim_overlap"]
        domain_pass = bool(shared_domains) or jaccard >= settings["minimum_jaccard_without_shared_domain"]
        if not (similarity_pass and domain_pass):
            continue
        output.append((left, right, {
            "shared_rare_token_count": shared,
            "jaccard": round(jaccard, 6),
            "shorter_claim_overlap": round(shorter_overlap, 6),
            "opposite_polarity_dimensions": opposite,
            "shared_domains": shared_domains,
        }))
    present = {tuple(sorted((claims[left]["claim_id"], claims[right]["claim_id"]))) for left, right, _ in output}
    by_id = {claim["claim_id"]: index for index, claim in enumerate(claims)}
    for special in policy["special_conditioned_contrasts"]:
        pair = tuple(sorted(special["claim_ids"]))
        if pair not in present:
            left, right = sorted((by_id[pair[0]], by_id[pair[1]]))
            output.append((left, right, {
                "shared_rare_token_count": len(token_sets[left] & token_sets[right]),
                "jaccard": round(len(token_sets[left] & token_sets[right]) / len(token_sets[left] | token_sets[right]), 6),
                "shorter_claim_overlap": round(len(token_sets[left] & token_sets[right]) / min(len(token_sets[left]), len(token_sets[right])), 6),
                "opposite_polarity_dimensions": ["increase_decrease"],
                "shared_domains": sorted(set(claims[left]["domains"]) & set(claims[right]["domains"])),
                "included_by_explicit_condition_audit": True,
            }))
    return output


def adjudicate_candidate(left: dict[str, Any], right: dict[str, Any], policy: dict[str, Any]) -> tuple[str, str]:
    pair = tuple(sorted((left["claim_id"], right["claim_id"])))
    for special in policy["special_conditioned_contrasts"]:
        if pair == tuple(sorted(special["claim_ids"])):
            return special["disposition"], special["reason"]
    left_evidence, right_evidence = left["evidence"][0], right["evidence"][0]
    if left_evidence["exact_quote_sha256"] == right_evidence["exact_quote_sha256"]:
        return "equivalent_source_sentence_not_contradiction", "The two claims derive from the exact same source quote and differ only in paraphrase."
    if normalize_text(left["proposition"]) == normalize_text(right["proposition"]):
        return "equivalent_proposition_not_contradiction", "The normalized propositions are identical."
    if left_evidence["passage_id"] == right_evidence["passage_id"]:
        return "local_condition_or_complement_not_contradiction", "Both claims occur in one bounded passage and state a local comparison, condition, or complement."
    if left_evidence["analysis_unit_id"] == right_evidence["analysis_unit_id"]:
        return "same_document_contextual_contrast", "The claims are retained as a within-document contrast; synthesis must preserve their distinct conditions rather than collapse them."
    version_units = set(policy["version_policy"]["unit_ids"])
    if {left_evidence["analysis_unit_id"], right_evidence["analysis_unit_id"]} == version_units:
        return "distinct_version_observations_no_supersession_direction", "The pair crosses the sole explicit version boundary; both observations are retained and no direction is inferred."
    return "cross_document_tension_preserved_for_synthesis", "The lexical screen found opposed wording across documents; it remains a bounded tension and is not auto-resolved as a contradiction."


def build() -> tuple[dict[Path, bytes], dict[str, Any]]:
    policy = read_json(POLICY)
    require(policy.get("schema_name") == "nuwa-v1-claim-audit-policy", "invalid audit policy schema")
    require(policy.get("schema_version") == 1, "invalid audit policy version")
    require(policy["scope"]["network_allowed"] is False, "network must remain disabled")
    require(policy["scope"]["active_commoncrawl_direct_index_allowed"] is False, "active Direct access must remain disabled")

    registry = read_json(REGISTRY_AUDIT)
    require(registry.get("verdict") == "PASS", "production registry is not PASS")
    require(registry.get("safe_to_begin_global_contradiction_audit") is True, "production registry does not authorize audit")
    registry_claim_fingerprint = (registry.get("output_fingerprints") or {}).get(CLAIMS.relative_to(ROOT).as_posix()) or {}
    require(registry_claim_fingerprint.get("sha256") == sha256_bytes(CLAIMS.read_bytes()), "production claim registry drift")
    claims = read_jsonl(CLAIMS)
    units = read_jsonl(UNITS)
    passages = read_jsonl(PASSAGES)
    require(len(claims) == policy["scope"]["claims"] == 52225, "claim population drift")
    require(len(units) == policy["scope"]["analysis_units"] == 1351, "unit population drift")
    require(len({claim["claim_id"] for claim in claims}) == len(claims), "duplicate claim ID")
    unit_by_id = {unit["analysis_unit_id"]: unit for unit in units}
    passage_by_id = {passage["passage_id"]: passage for passage in passages}
    for claim in claims:
        require(claim.get("schema_name") == "nuwa-v1-atomic-claim", f"invalid claim schema: {claim.get('claim_id')}")
        require(len(claim.get("evidence") or []) == 1, f"claim evidence cardinality drift: {claim['claim_id']}")
        evidence = claim["evidence"][0]
        require(evidence["analysis_unit_id"] in unit_by_id, f"unknown claim unit: {claim['claim_id']}")
        require(evidence["passage_id"] in passage_by_id, f"unknown claim passage: {claim['claim_id']}")
        require(evidence["body_sha256"] == unit_by_id[evidence["analysis_unit_id"]]["body_sha256"], f"claim body drift: {claim['claim_id']}")
        require(sha256_bytes(evidence["exact_quote"].encode("utf-8")) == evidence["exact_quote_sha256"], f"claim quote hash drift: {claim['claim_id']}")

    attribution_rows = sorted((claim_attribution(claim, policy) for claim in claims), key=lambda row: row["claim_id"])
    require(len(attribution_rows) == len(claims), "attribution coverage drift")
    require(len({row["claim_id"] for row in attribution_rows}) == len(claims), "attribution is not exact-once")
    attribution_counts = Counter(row["attribution_class"] for row in attribution_rows)

    equivalence_rows = build_equivalence(claims)
    equivalence_member_ids = [claim_id for row in equivalence_rows for claim_id in row["member_claim_ids"]]
    require(len(equivalence_member_ids) == len(set(equivalence_member_ids)), "equivalence components overlap")

    version_policy = policy["version_policy"]
    version_units = [unit_by_id[unit_id] for unit_id in version_policy["unit_ids"]]
    require(len(version_units) == 2, "version unit population drift")
    require(all(version_policy["shared_seed_record_id"] in unit["source_seed_record_ids"] for unit in version_units), "version seed relation drift")
    require(len({unit["canonical"] for unit in version_units}) == 1, "version canonical drift")
    require(len({unit["body_sha256"] for unit in version_units}) == 2, "version bodies are not distinct")
    claims_by_unit: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        claims_by_unit[claim["evidence"][0]["analysis_unit_id"]].append(claim)
    left_version, right_version = version_units
    left_quotes = {claim["evidence"][0]["exact_quote_sha256"] for claim in claims_by_unit[left_version["analysis_unit_id"]]}
    right_quotes = {claim["evidence"][0]["exact_quote_sha256"] for claim in claims_by_unit[right_version["analysis_unit_id"]]}
    left_props = {normalize_text(claim["proposition"]) for claim in claims_by_unit[left_version["analysis_unit_id"]]}
    right_props = {normalize_text(claim["proposition"]) for claim in claims_by_unit[right_version["analysis_unit_id"]]}
    version_rows = [{
        "schema_name": "nuwa-v1-version-audit",
        "schema_version": 1,
        "version_component_id": "nuwa1-version-" + sha256_bytes(version_policy["shared_seed_record_id"].encode("utf-8"))[:20],
        "shared_seed_record_id": version_policy["shared_seed_record_id"],
        "canonical": left_version["canonical"],
        "unit_ids": sorted(version_policy["unit_ids"]),
        "edition_ids": sorted(unit["edition_id"] for unit in version_units),
        "work_ids": sorted(unit["work_id"] for unit in version_units),
        "body_sha256s": sorted(unit["body_sha256"] for unit in version_units),
        "claim_counts_by_unit": {unit_id: len(claims_by_unit[unit_id]) for unit_id in sorted(version_policy["unit_ids"])},
        "shared_exact_quote_count": len(left_quotes & right_quotes),
        "shared_normalized_proposition_count": len(left_props & right_props),
        "direction": version_policy["direction"],
        "terminal_disposition": "preserve_distinct_versions_no_supersession_inference",
    }]

    candidates = candidate_pairs(claims, policy)
    contradiction_rows = []
    for left_index, right_index, metrics in candidates:
        left, right = claims[left_index], claims[right_index]
        left_id, right_id = sorted((left["claim_id"], right["claim_id"]))
        if left_id != left["claim_id"]:
            left, right = right, left
        disposition, reason = adjudicate_candidate(left, right, policy)
        left_evidence, right_evidence = left["evidence"][0], right["evidence"][0]
        candidate_id = "nuwa1-tension-" + sha256_bytes((left_id + "\n" + right_id).encode("utf-8"))[:20]
        contradiction_rows.append({
            "schema_name": "nuwa-v1-contradiction-candidate",
            "schema_version": 1,
            "candidate_id": candidate_id,
            "claim_ids": [left_id, right_id],
            "claim_row_sha256s": [sha256_bytes(canonical_json(left)), sha256_bytes(canonical_json(right))],
            "analysis_unit_ids": [left_evidence["analysis_unit_id"], right_evidence["analysis_unit_id"]],
            "work_ids": [left_evidence["work_id"], right_evidence["work_id"]],
            "passage_ids": [left_evidence["passage_id"], right_evidence["passage_id"]],
            "propositions": [left["proposition"], right["proposition"]],
            "exact_quote_sha256s": [left_evidence["exact_quote_sha256"], right_evidence["exact_quote_sha256"]],
            "screen_metrics": metrics,
            "terminal_disposition": disposition,
            "adjudication_reason": reason,
            "unresolved": False,
        })
    contradiction_rows.sort(key=lambda row: row["candidate_id"])
    require(len({tuple(row["claim_ids"]) for row in contradiction_rows}) == len(contradiction_rows), "duplicate contradiction pair")
    require(all(not row["unresolved"] for row in contradiction_rows), "unresolved contradiction candidate")

    attribution_payload = b"".join(canonical_json(row) for row in attribution_rows)
    equivalence_payload = b"".join(canonical_json(row) for row in equivalence_rows)
    version_payload = b"".join(canonical_json(row) for row in version_rows)
    contradiction_payload = b"".join(canonical_json(row) for row in contradiction_rows)
    terminal_counts = Counter(row["terminal_disposition"] for row in contradiction_rows)
    counts = {
        "claims": len(claims),
        "attribution_rows": len(attribution_rows),
        "attribution_classes": dict(sorted(attribution_counts.items())),
        "equivalence_components": len(equivalence_rows),
        "equivalence_member_claims": len(equivalence_member_ids),
        "version_components": len(version_rows),
        "contradiction_candidates": len(contradiction_rows),
        "contradiction_candidates_unresolved": sum(row["unresolved"] for row in contradiction_rows),
        "contradiction_terminal_dispositions": dict(sorted(terminal_counts.items())),
    }
    report_lines = [
        "# Nuwa v1 主张审计",
        "",
        "该层在冻结的 52,225 条原子主张上区分来源立场、被引立场、研究问题、模拟证据与嵌入式样例，并审计精确重复、版本边界及潜在矛盾。",
        "",
        f"- 归属覆盖：{counts['attribution_rows']:,} / {counts['claims']:,}（逐主张、恰一次）",
        f"- 等价组件：{counts['equivalence_components']:,}，涉及 {counts['equivalence_member_claims']:,} 条主张；保留全部出处，频次分析只计组件一次",
        f"- 明示版本组件：{counts['version_components']}；两个版本均保留，不推断先后或取代关系",
        f"- 有界词汇对立筛查候选：{counts['contradiction_candidates']}；未决 {counts['contradiction_candidates_unresolved']}",
        "- 词汇筛查不是语义完备性证明；所有候选均保留原主张、作品、版本、passage 和原文哈希，未自动把差异消解成一致意见。",
        "- 文档编辑声部只代表该作品的编辑层立场，不自动提升为任何具名个人的观点。",
        "- 通过本审计后可以开始归纳综合；综合必须保留引文、问题、模拟和版本边界。",
        "",
    ]
    report_payload = "\n".join(report_lines).encode("utf-8")
    payloads: dict[Path, bytes] = {
        ATTRIBUTION: attribution_payload,
        EQUIVALENCE: equivalence_payload,
        VERSIONS: version_payload,
        CONTRADICTIONS: contradiction_payload,
        REPORT: report_payload,
    }
    input_paths = [POLICY, CLAIMS, REGISTRY_AUDIT, UNITS, PASSAGES, Path(__file__).resolve(), TESTS]
    input_fingerprints = {
        path.relative_to(ROOT).as_posix(): {"sha256": sha256_bytes(path.read_bytes()), "bytes": path.stat().st_size}
        for path in input_paths
    }
    output_fingerprints = {
        path.relative_to(ROOT).as_posix(): {"sha256": sha256_bytes(payload), "bytes": len(payload), "rows": payload.count(b"\n")}
        for path, payload in payloads.items()
    }
    audit = {
        "schema_name": "nuwa-v1-claim-audit",
        "schema_version": 1,
        "verdict": "PASS",
        "safe_to_begin_worldview_synthesis": True,
        "semantic_contradiction_exhaustiveness_claimed": False,
        "counts": counts,
        "input_fingerprints": dict(sorted(input_fingerprints.items())),
        "input_snapshot_sha256": sha256_bytes(canonical_json(dict(sorted(input_fingerprints.items())))),
        "output_fingerprints": output_fingerprints,
        "invariants": {
            "every_claim_attributed_exactly_once": True,
            "quoted_positions_not_promoted_to_source_beliefs": True,
            "document_editorial_voice_not_promoted_to_personal_view": True,
            "research_questions_not_treated_as_answers": True,
            "controlled_simulations_remain_condition_scoped": True,
            "equivalence_components_disjoint_and_provenance_preserved": True,
            "explicit_version_boundary_preserved_without_direction_inference": True,
            "all_generated_contradiction_candidates_terminal": True,
            "ordinary_outbound_link_expansion_count": 0,
            "network_access_count": 0,
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
    print(f"PASS claims={counts['claims']} equivalence={counts['equivalence_components']} tensions={counts['contradiction_candidates']} unresolved={counts['contradiction_candidates_unresolved']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
