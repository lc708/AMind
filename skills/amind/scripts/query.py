#!/usr/bin/env python3
"""Query AMind's full local evidence index and reviewed gold kernel."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
import sys
import zlib
from collections import Counter
from math import ceil
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
MANIFEST_SCHEMA = "amind-skill-evidence-manifest"
INDEX_SCHEMA = "amind-full-evidence-index"
INDEX_NAME = "amind-full-index.sqlite3"
PASSAGES_NAME = "passages.jsonl.gz"
DIRECT_DISPOSITION = "eligible_for_source_level_synthesis"
REPORTED_DISPOSITION = "preserve_as_reported_position_not_source_belief"
AGENDA_DISPOSITION = "preserve_as_agenda_not_answer"

CURRENT_SIGNALS = {
    "current", "currently", "latest", "newest", "recent", "recently", "today", "now",
    "当前", "现在", "最新", "近期", "最近",
}
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "is",
    "it", "of", "on", "or", "that", "the", "this", "to", "what", "with",
}

# Chinese theme routing is intentionally explicit. Matching arbitrary query
# fragments against a full Chinese thesis made generic words such as “风险”
# activate several unrelated themes.
THEME_ALIASES_ZH = {
    "alignment-as-hidden-behavior": (
        "对齐", "错位", "欺骗", "伪装", "奖励投机", "隐藏目标", "潜伏", "诚实",
    ),
    "capability-scaling-under-uncertainty": (
        "能力扩展", "规模化", "扩展规律", "算力", "泛化", "涌现", "能力进展", "变革性人工智能",
    ),
    "capability-triggered-governance": (
        "治理", "监管", "政策", "问责", "标准", "责任", "法律", "政府",
    ),
    "disciplined-agent-engineering": (
        "智能体", "代理工作流", "工具使用", "计算机使用", "子智能体", "多智能体", "编程工作流", "上下文窗口",
    ),
    "economic-transition-and-distribution": (
        "经济", "劳动", "就业", "岗位", "自动化", "生产率", "不平等", "劳动力", "再培训", "转岗", "扩散",
    ),
    "human-agency-values-and-welfare": (
        "人的能动性", "人类价值", "福利", "意义", "情感", "意识", "人格", "拟人", "繁荣",
    ),
    "measurement-and-adaptive-evaluation": (
        "评估", "评测", "测量", "审计", "监控", "基准", "红队", "测试", "保证",
    ),
    "mechanistic-legibility": (
        "可解释性", "机制可理解性", "特征", "回路", "表征", "叠加", "单义", "字典学习", "归因图",
    ),
    "security-and-defense-in-depth": (
        "网络安全", "生物安全", "纵深防御", "模型权重", "滥用", "权限", "威胁行为者", "破坏活动",
    ),
}

QUERY_CONCEPTS_ZH = {
    "风险": ("risk", "hazard"),
    "治理": ("governance", "regulation", "policy"),
    "监管": ("regulation", "regulator"),
    "政策": ("policy",),
    "安全": ("security", "safety"),
    "评估": ("evaluation", "assessment"),
    "评测": ("evaluation", "benchmark"),
    "能力": ("capability",),
    "扩展": ("scaling", "scale"),
    "算力": ("compute",),
    "经济": ("economic", "economy"),
    "就业": ("employment", "jobs"),
    "再培训": ("retraining", "reskilling"),
    "福利": ("welfare",),
    "意识": ("consciousness",),
    "智能体": ("agent", "agents"),
    "可解释性": ("interpretability",),
    "对齐": ("alignment",),
    "欺骗": ("deception", "deceptive"),
}


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
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8", newline="") as handle:
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
    ):
        require(type(counts.get(field)) is int and counts[field] >= 0, f"invalid count: {field}")
    return manifest


def load_rows(data_root: Path, name: str) -> list[dict[str, Any]]:
    return list(iter_jsonl(data_root / name))


def json_output(rows: Iterable[dict[str, Any]]) -> None:
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))


def unpack_json(payload: bytes) -> dict[str, Any]:
    try:
        value = json.loads(zlib.decompress(payload).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, zlib.error) as error:
        raise AMindSkillError(f"invalid packed index payload: {error}") from error
    require(isinstance(value, dict), "packed index payload is not an object")
    return value


def open_index(data_root: Path) -> sqlite3.Connection:
    path = (data_root / INDEX_NAME).resolve()
    require(path.is_file(), f"missing full evidence index: {path}")
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        connection.row_factory = sqlite3.Row
        metadata = {
            row["key"]: json.loads(row["value"])
            for row in connection.execute("SELECT key, value FROM metadata")
        }
    except (sqlite3.Error, json.JSONDecodeError) as error:
        raise AMindSkillError(f"cannot open full evidence index: {error}") from error
    require(metadata.get("schema_name") == INDEX_SCHEMA, "invalid full evidence index schema")
    require(metadata.get("schema_version") == 1, "unsupported full evidence index version")
    require(metadata.get("release_id") == "amind-v1", "full evidence index release mismatch")
    return connection


def printable_voice(row: dict[str, Any]) -> str:
    voice = row.get("voice") or {}
    return voice.get("name") or voice.get("organization") or "Unattributed source voice"


def print_evidence(row: dict[str, Any]) -> None:
    theme_ids = row.get("theme_ids") or ([row["theme_id"]] if row.get("theme_id") else [])
    themes = ", ".join(theme_ids) or "unclassified"
    print(f"{row['claim_id']}  [{row['evidence_tier']} / {themes}]")
    print(f"Proposition: {row['proposition']}")
    print(f"Voice: {printable_voice(row)}")
    print(f"Attribution: {row['attribution_class']}")
    print(f"Source: {row['source_title']}")
    if row.get("source_published_at"):
        print(f"Published: {row['source_published_at']}")
    print(f"URL: {row['source_canonical']}")
    print(f"Quote: {row['exact_quote']}")
    print(f"Review: {(row.get('review') or {}).get('semantic_status', 'unknown')}")
    if row.get("passage"):
        print("Passage context:")
        print(row["passage"]["text"])


def tokenize_query(query: str) -> list[str]:
    tokens = re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE)
    return [token for token in tokens if token not in STOPWORDS and (len(token) >= 2 or not token.isascii())]


def ascii_phrase_in_text(phrase: str, text: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text))


def detect_themes(query: str, tokens: list[str], themes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    folded = query.casefold()
    detected: list[dict[str, Any]] = []
    for theme in themes:
        keyword_match = any(ascii_phrase_in_text(str(keyword).casefold(), folded) for keyword in theme.get("keywords") or [])
        chinese_match = any(alias in query for alias in THEME_ALIASES_ZH.get(theme.get("theme_id"), ()))
        identity_match = str(theme.get("theme_id") or "").casefold() in folded
        if keyword_match or chinese_match or identity_match:
            detected.append(theme)
    return detected


def translated_query_concepts(query: str) -> list[tuple[str, tuple[str, ...]]]:
    return [(label, translations) for label, translations in QUERY_CONCEPTS_ZH.items() if label in query]


def expanded_search_tokens(
    query: str,
    detected_themes: list[dict[str, Any]],
    translated_concepts: list[tuple[str, tuple[str, ...]]],
) -> tuple[list[str], list[str]]:
    original = tokenize_query(query)
    semantic = [token for token in original if token not in CURRENT_SIGNALS]
    if semantic:
        original = semantic
    expanded = list(original)
    if not any(token.isascii() for token in original):
        for _, translations in translated_concepts:
            for translation in translations:
                expanded.extend(tokenize_query(translation))
        for theme in detected_themes:
            for keyword in theme.get("keywords") or []:
                expanded.extend(tokenize_query(str(keyword)))
    deduplicated: list[str] = []
    seen: set[str] = set()
    for token in expanded:
        if token in seen:
            continue
        seen.add(token)
        deduplicated.append(token)
    return original, deduplicated[:32]


def fts_expression(tokens: list[str]) -> str:
    require(tokens, "search query has no indexable terms")
    return " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def light_stem(token: str) -> str:
    """Approximate FTS5's Porter behavior for transparent coverage scoring."""
    if not token.isascii() or len(token) < 4:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    for suffix in ("ingly", "edly", "ing", "ed"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            root = token[: -len(suffix)]
            if len(root) >= 2 and root[-1] == root[-2]:
                root = root[:-1]
            return root
    if token.endswith("es") and len(token) > 5:
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss") and len(token) > 4:
        return token[:-1]
    return token


def matched_query_terms(tokens: list[str], searchable: str) -> list[str]:
    searchable_terms = {
        light_stem(token)
        for token in tokenize_query(searchable)
        if token.isascii()
    }
    return [token for token in tokens if token.isascii() and light_stem(token) in searchable_terms]


def matched_theme_keywords(keywords: list[str], searchable: str) -> list[str]:
    matched: list[str] = []
    for keyword in keywords:
        folded = keyword.casefold().strip()
        if not folded:
            continue
        if " " in folded:
            hit = ascii_phrase_in_text(folded, searchable)
        else:
            hit = bool(matched_query_terms([folded], searchable))
        if hit:
            matched.append(keyword)
    return matched


def matched_concepts(
    concepts: list[tuple[str, tuple[str, ...]]], searchable: str
) -> list[str]:
    return [
        label
        for label, translations in concepts
        if matched_theme_keywords(list(translations), searchable)
    ]


def kernel_by_claim(data_root: Path) -> dict[str, dict[str, Any]]:
    return {row["claim_id"]: row for row in load_rows(data_root, "evidence-kernel.jsonl")}


INDEX_COLUMNS = """
    SELECT
        c.id AS row_id,
        c.claim_id,
        c.attribution_class,
        c.synthesis_disposition,
        c.equivalence_component_id,
        c.is_reviewed_kernel,
        c.payload_zlib AS claim_payload_zlib,
        s.analysis_unit_id,
        s.work_id,
        s.edition_id,
        s.title,
        s.canonical,
        s.published_at,
        s.publication_year,
        s.source_host,
        s.payload_zlib AS source_payload_zlib,
        v.name AS voice_name,
        v.organization AS voice_organization,
        v.voice_type,
        v.role_at_time,
        v.attribution_basis
"""
INDEX_FROM = """
    FROM claims c
    JOIN sources s ON s.id = c.source_id
    JOIN voices v ON v.id = c.voice_id
"""
INDEX_SELECT = INDEX_COLUMNS + INDEX_FROM


def enriched_row(row: sqlite3.Row, reviewed: dict[str, dict[str, Any]]) -> dict[str, Any]:
    claim = unpack_json(row["claim_payload_zlib"])
    source = unpack_json(row["source_payload_zlib"])
    claim_id = row["claim_id"]
    kernel = reviewed.get(claim_id)
    human_reviewed = kernel is not None
    if human_reviewed:
        review = dict(kernel["review"])
        review["human_reviewed"] = True
    else:
        review = {
            "human_reviewed": False,
            "semantic_status": "machine_checked_not_human_reviewed",
            "support_mode": "source_bound_exact_quote_with_local_passage_context",
        }
    return {
        "analysis_unit_id": row["analysis_unit_id"],
        "attribution_class": row["attribution_class"],
        "claim_id": claim_id,
        "claim_type": claim.get("claim_type") or "",
        "conditions": claim.get("conditions") or [],
        "domains": claim.get("domains") or [],
        "edition_id": row["edition_id"],
        "epistemic_force": claim.get("epistemic_force") or "",
        "equivalence": {
            "component_id": row["equivalence_component_id"],
            "representative_claim_id": claim.get("equivalence_representative_claim_id") or claim_id,
        },
        "evidence_tier": "gold_human_reviewed" if human_reviewed else "full_release_machine_checked",
        "exact_quote": claim.get("exact_quote") or "",
        "exact_quote_sha256": claim.get("exact_quote_sha256") or "",
        "invalidation_conditions": claim.get("invalidation_conditions") or [],
        "passage_id": claim.get("passage_id") or "",
        "proposition": claim.get("proposition") or "",
        "review": review,
        "schema_name": "amind-retrieval-result",
        "schema_version": 1,
        "source_canonical": row["canonical"],
        "source_host": row["source_host"],
        "source_published_at": row["published_at"],
        "source_record_ids": source.get("source_record_ids") or [],
        "source_title": row["title"],
        "synthesis_disposition": row["synthesis_disposition"],
        "temporal_scope": claim.get("temporal_scope") or {},
        "theme_ids": claim.get("theme_ids") or [],
        "voice": {
            "attribution_basis": row["attribution_basis"],
            "name": row["voice_name"],
            "organization": row["voice_organization"],
            "role_at_time": row["role_at_time"],
            "voice_type": row["voice_type"],
        },
        "work_id": row["work_id"],
    }


def current_mode(query: str, explicit: bool) -> bool:
    folded = query.casefold()
    query_tokens = set(tokenize_query(query))
    return explicit or bool(query_tokens.intersection(CURRENT_SIGNALS)) or any(
        signal in folded for signal in CURRENT_SIGNALS if not signal.isascii()
    )


def search_candidates(connection: sqlite3.Connection, expression: str, args: argparse.Namespace) -> list[sqlite3.Row]:
    dispositions = [DIRECT_DISPOSITION]
    if args.include_reported:
        dispositions.append(REPORTED_DISPOSITION)
    if args.include_agenda:
        dispositions.append(AGENDA_DISPOSITION)
    placeholders = ",".join("?" for _ in dispositions)
    where = [
        "claims_fts MATCH ?",
        f"c.synthesis_disposition IN ({placeholders})",
    ]
    parameters: list[Any] = [expression, *dispositions]
    if args.voice:
        where.append("lower(v.name) LIKE lower(?)")
        parameters.append(f"%{args.voice}%")
    if args.year_from is not None:
        where.append("s.publication_year >= ?")
        parameters.append(args.year_from)
    if args.year_to is not None:
        where.append("s.publication_year <= ?")
        parameters.append(args.year_to)
    parameters.append(min(4000, max(400, args.limit * 100)))
    sql = (
        INDEX_COLUMNS
        + "        , bm25(claims_fts, 8.0, 2.5, 1.5, 1.0, 2.0) AS fts_rank\n"
        + "    FROM claims_fts JOIN claims c ON c.id = claims_fts.rowid\n"
        + "    JOIN sources s ON s.id = c.source_id\n"
        + "    JOIN voices v ON v.id = c.voice_id\n"
        + f"    WHERE {' AND '.join(where)} ORDER BY fts_rank, c.claim_id LIMIT ?"
    )
    return list(connection.execute(sql, parameters))


def rank_candidates(
    rows: list[dict[str, Any]],
    query: str,
    original_tokens: list[str],
    detected_theme_ids: set[str],
    use_current_mode: bool,
    maximum_year: int,
    explicit_voice: bool,
    theme_routed: bool,
    routed_theme_keywords: list[str],
    translated_concepts: list[tuple[str, tuple[str, ...]]],
) -> list[dict[str, Any]]:
    folded_phrase = query.casefold().strip()
    total = max(1, len(rows))
    ascii_tokens = [token for token in original_tokens if token.isascii()]
    strong_match_threshold = 0 if not ascii_tokens else min(len(ascii_tokens), max(1, ceil(len(ascii_tokens) / 2)))
    if len(ascii_tokens) == 2:
        strong_match_threshold = 2
    for index, row in enumerate(rows):
        semantic_searchable = "\n".join(
            [
                row.get("proposition") or "",
                row.get("exact_quote") or "",
                row.get("source_title") or "",
            ]
        ).casefold()
        searchable = semantic_searchable + "\n" + " ".join(row.get("domains") or []).casefold()
        matched_terms = matched_query_terms(ascii_tokens, searchable)
        matched_keywords = matched_theme_keywords(routed_theme_keywords, semantic_searchable) if theme_routed else []
        concept_hits = matched_concepts(translated_concepts, semantic_searchable) if theme_routed else []
        coverage = len(matched_terms) / max(1, len(ascii_tokens)) if ascii_tokens else 0.0
        concept_threshold = min(len(translated_concepts), max(1, ceil(len(translated_concepts) / 2)))
        if len(translated_concepts) == 2:
            concept_threshold = 2
        if theme_routed and translated_concepts:
            strong_match = len(concept_hits) >= concept_threshold
        elif theme_routed:
            strong_match = bool(matched_keywords)
        else:
            strong_match = len(matched_terms) >= strong_match_threshold
        score = 0.8 * (1.0 - index / total) + 2.4 * coverage
        if folded_phrase and folded_phrase in searchable:
            score += 0.8
        if detected_theme_ids.intersection(row.get("theme_ids") or []):
            score += 0.4
        if theme_routed:
            score += min(0.9, 0.3 * len(matched_keywords))
            score += 2.4 * len(concept_hits) / max(1, len(translated_concepts))
        if row.get("evidence_tier") == "gold_human_reviewed" and (strong_match or theme_routed):
            score += 0.1
        if not explicit_voice and (row.get("voice") or {}).get("voice_type") in {"institutional", "document_editorial"}:
            score += 0.1
        if use_current_mode:
            year_match = re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", str(row.get("source_published_at") or ""))
            if year_match:
                age = max(0, maximum_year - int(year_match.group(0)))
                score += 0.75 * max(0.0, 1.0 - age / 6.0)
        row["_score"] = score
        row["_fts_order"] = index
        row["_matched_terms"] = matched_terms
        row["_matched_theme_keywords"] = matched_keywords
        row["_matched_query_concepts"] = concept_hits
        row["_query_term_coverage"] = coverage
        row["_relevance_tier"] = "theme_routed" if theme_routed and strong_match else ("strong" if strong_match else "fallback")
    return sorted(
        rows,
        key=lambda row: (
            row["_relevance_tier"] == "fallback",
            -row["_score"],
            row["_fts_order"],
            row["claim_id"],
        ),
    )


def diversify(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.no_diversify:
        selected = []
        equivalence_keys: set[str] = set()
        for row in rows:
            equivalence_key = (row.get("equivalence") or {}).get("component_id") or row["claim_id"]
            if equivalence_key in equivalence_keys:
                continue
            selected.append(row)
            equivalence_keys.add(equivalence_key)
            row["_diversity_caps_relaxed"] = True
            if len(selected) == args.limit:
                break
    else:
        voice_cap = args.limit if args.voice else args.max_per_voice
        host_cap = args.limit if args.voice else args.max_per_host
        work_cap = args.max_per_work
        selected: list[dict[str, Any]] = []
        selected_ids: set[str] = set()
        voice_counts: Counter[str] = Counter()
        host_counts: Counter[str] = Counter()
        work_counts: Counter[str] = Counter()
        equivalence_keys: set[str] = set()
        for row in rows:
            voice = printable_voice(row)
            host = row.get("source_host") or ""
            work = row.get("work_id") or row.get("analysis_unit_id") or ""
            equivalence_key = (row.get("equivalence") or {}).get("component_id") or row["claim_id"]
            if (
                equivalence_key in equivalence_keys
                or voice_counts[voice] >= voice_cap
                or host_counts[host] >= host_cap
                or work_counts[work] >= work_cap
            ):
                continue
            selected.append(row)
            row["_diversity_caps_relaxed"] = False
            selected_ids.add(row["claim_id"])
            equivalence_keys.add(equivalence_key)
            voice_counts[voice] += 1
            host_counts[host] += 1
            work_counts[work] += 1
            if len(selected) == args.limit:
                break
        if len(selected) < args.limit:
            for row in rows:
                if row["claim_id"] in selected_ids:
                    continue
                work = row.get("work_id") or row.get("analysis_unit_id") or ""
                equivalence_key = (row.get("equivalence") or {}).get("component_id") or row["claim_id"]
                if equivalence_key in equivalence_keys or work_counts[work] >= work_cap:
                    continue
                selected.append(row)
                row["_diversity_caps_relaxed"] = True
                selected_ids.add(row["claim_id"])
                equivalence_keys.add(equivalence_key)
                work_counts[work] += 1
                if len(selected) == args.limit:
                    break
    for rank, row in enumerate(selected, start=1):
        row["retrieval"] = {
            "diversity_caps_relaxed": row.pop("_diversity_caps_relaxed", False),
            "diversified": not args.no_diversify,
            "matched_query_terms": row.pop("_matched_terms", []),
            "matched_query_concepts": row.pop("_matched_query_concepts", []),
            "matched_theme_keywords": row.pop("_matched_theme_keywords", []),
            "query_term_coverage": round(row.pop("_query_term_coverage", 0.0), 6),
            "rank": rank,
            "relevance_tier": row.pop("_relevance_tier", "fallback"),
            "score": round(row.pop("_score", 0.0), 6),
        }
        row.pop("_fts_order", None)
    return selected


def command_summary(data_root: Path, args: argparse.Namespace) -> int:
    del args
    manifest = load_manifest(data_root)
    counts = manifest["counts"]
    print(f"AMind skill {manifest['skill_version']} — full local index from AMind v1")
    print(f"Searchable atomic claims: {counts['full_index_atomic_claims']}")
    print(f"Indexed analysis units: {counts['full_index_analysis_units']}")
    print(f"Bundled passage contexts: {counts['full_index_passages']}")
    print(f"Human-reviewed gold rows: {counts['human_reviewed_evidence_rows']}")
    print(f"Audited equivalence components: {counts['full_index_equivalence_components']}")
    print(f"Themes / voices / tensions: {counts['themes']} / {counts['voice_profiles']} / {counts['preserved_tensions']}")
    return 0


def command_search(data_root: Path, args: argparse.Namespace) -> int:
    query = args.query.strip()
    require(query, "search query must not be empty")
    require(1 <= args.limit <= 50, "--limit must be between 1 and 50")
    themes = load_rows(data_root, "theme-catalog.jsonl")
    original_tokens = tokenize_query(query)
    detected = detect_themes(query, original_tokens, themes)
    concepts = translated_query_concepts(query)
    original_tokens, index_tokens = expanded_search_tokens(query, detected, concepts)
    expression = fts_expression(index_tokens)
    reviewed = kernel_by_claim(data_root)
    connection = open_index(data_root)
    try:
        raw = search_candidates(connection, expression, args)
        maximum_year = connection.execute("SELECT max(publication_year) FROM sources").fetchone()[0] or 0
        results = [enriched_row(row, reviewed) for row in raw]
    finally:
        connection.close()
    if args.theme:
        results = [row for row in results if args.theme in (row.get("theme_ids") or [])]
    pure_cjk_theme_route = bool(detected) and not any(token.isascii() for token in original_tokens)
    if pure_cjk_theme_route:
        detected_theme_ids = {row["theme_id"] for row in detected}
        results = [row for row in results if detected_theme_ids.intersection(row.get("theme_ids") or [])]
    if not results:
        print("No evidence matched the full local index and requested boundaries.", file=sys.stderr)
        return 1
    ranked = rank_candidates(
        results,
        query,
        original_tokens,
        {row["theme_id"] for row in detected},
        current_mode(query, args.current),
        maximum_year,
        bool(args.voice),
        pure_cjk_theme_route,
        [keyword for theme in detected for keyword in (theme.get("keywords") or [])],
        concepts,
    )
    matches = diversify(ranked, args)
    for row in matches:
        row["retrieval"]["current_mode"] = current_mode(query, args.current)
        row["retrieval"]["detected_theme_ids"] = [theme["theme_id"] for theme in detected]
        row["retrieval"]["query"] = query
    if args.json:
        json_output(matches)
    else:
        for index, row in enumerate(matches):
            if index:
                print()
            print_evidence(row)
    return 0


def kernel_searchable_text(row: dict[str, Any], theme: dict[str, Any] | None = None) -> str:
    voice = row.get("voice") or {}
    theme = theme or {}
    values = (
        row.get("claim_id"), row.get("theme_id"), row.get("proposition"), row.get("exact_quote"),
        row.get("source_title"), row.get("source_canonical"), voice.get("name"), voice.get("organization"),
        theme.get("name_zh"), theme.get("thesis_zh"), " ".join(theme.get("keywords") or []),
    )
    return "\n".join(str(value) for value in values if value).casefold()


def command_kernel_search(data_root: Path, args: argparse.Namespace) -> int:
    query = args.query.strip()
    tokens = tokenize_query(query)
    require(tokens, "search query must not be empty")
    require(1 <= args.limit <= 54, "--limit must be between 1 and 54")
    phrase = query.casefold()
    scored: list[tuple[int, str, dict[str, Any]]] = []
    themes = {row["theme_id"]: row for row in load_rows(data_root, "theme-catalog.jsonl")}
    for row in load_rows(data_root, "evidence-kernel.jsonl"):
        text = kernel_searchable_text(row, themes.get(row.get("theme_id")))
        token_hits = sum(1 for token in tokens if token in text)
        if not token_hits:
            continue
        result = dict(row)
        result["evidence_tier"] = "gold_human_reviewed"
        scored.append(((4 if phrase in text else 0) + token_hits, row["claim_id"], result))
    matches = [row for _, _, row in sorted(scored, key=lambda item: (-item[0], item[1]))[: args.limit]]
    if not matches:
        print("No reviewed evidence matched the gold kernel.", file=sys.stderr)
        return 1
    if args.json:
        json_output(matches)
    else:
        for index, row in enumerate(matches):
            if index:
                print()
            print_evidence(row)
    return 0


def load_passages(data_root: Path, passage_ids: set[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(data_root / PASSAGES_NAME):
        passage_id = row.get("passage_id")
        if passage_id in passage_ids:
            found[passage_id] = row
            if len(found) == len(passage_ids):
                break
    return found


def command_show(data_root: Path, args: argparse.Namespace) -> int:
    require(1 <= len(args.claim_ids) <= 20, "show accepts between 1 and 20 claim IDs")
    reviewed = kernel_by_claim(data_root)
    placeholders = ",".join("?" for _ in args.claim_ids)
    connection = open_index(data_root)
    try:
        rows = list(connection.execute(INDEX_SELECT + f" WHERE c.claim_id IN ({placeholders})", args.claim_ids))
    finally:
        connection.close()
    by_claim = {row["claim_id"]: enriched_row(row, reviewed) for row in rows}
    missing = [claim_id for claim_id in args.claim_ids if claim_id not in by_claim]
    if missing:
        print("Unknown claim ID(s): " + ", ".join(missing), file=sys.stderr)
        return 1
    ordered = [by_claim[claim_id] for claim_id in args.claim_ids]
    if args.passage:
        passage_ids = {row["passage_id"] for row in ordered}
        passages = load_passages(data_root, passage_ids)
        require(set(passages) == passage_ids, "missing bundled passage context")
        for row in ordered:
            passage = passages[row["passage_id"]]
            row["passage"] = {
                "section_path": passage.get("section_path") or [],
                "source_line_end": passage.get("source_line_end"),
                "source_line_start": passage.get("source_line_start"),
                "text": passage.get("text") or "",
                "text_sha256": passage.get("text_sha256") or "",
            }
    if args.json:
        json_output(ordered)
    else:
        for index, row in enumerate(ordered):
            if index:
                print()
            print_evidence(row)
    return 0


def command_stats(data_root: Path, args: argparse.Namespace) -> int:
    connection = open_index(data_root)
    try:
        total_claims = connection.execute("SELECT count(*) FROM claims").fetchone()[0]
        total_sources = connection.execute("SELECT count(*) FROM sources").fetchone()[0]
        direct_claims = connection.execute(
            "SELECT count(*) FROM claims WHERE synthesis_disposition = ?", (DIRECT_DISPOSITION,)
        ).fetchone()[0]
        equivalent_extras = connection.execute(
            "SELECT count(*) FROM claims WHERE equivalence_component_id != '' AND is_equivalence_representative = 0"
        ).fetchone()[0]
        voices = [
            {
                "agenda_claims": row[4],
                "claims": row[1],
                "direct_claims": row[2],
                "name": (row[0] or "").strip() or "Unattributed source voice",
                "reported_claims": row[3],
                "sources": row[5],
            }
            for row in connection.execute(
                """
                SELECT
                    v.name,
                    count(*),
                    sum(c.synthesis_disposition = ?),
                    sum(c.synthesis_disposition = ?),
                    sum(c.synthesis_disposition = ?),
                    count(DISTINCT c.source_id)
                FROM claims c JOIN voices v ON v.id = c.voice_id
                GROUP BY v.name ORDER BY count(*) DESC, v.name LIMIT 12
                """,
                (DIRECT_DISPOSITION, REPORTED_DISPOSITION, AGENDA_DISPOSITION),
            )
        ]
        hosts = [
            {
                "claims": row[1],
                "claims_per_source": round(row[1] / row[2], 2),
                "host": row[0],
                "sources": row[2],
            }
            for row in connection.execute(
                """
                SELECT s.source_host, count(*), count(DISTINCT c.source_id)
                FROM claims c JOIN sources s ON s.id = c.source_id
                GROUP BY s.source_host ORDER BY count(*) DESC, s.source_host LIMIT 12
                """
            )
        ]
    finally:
        connection.close()
    result = {
        "equivalence_extra_rows": equivalent_extras,
        "source_hosts": hosts,
        "source_level_direct_claims": direct_claims,
        "total_claims": total_claims,
        "total_sources": total_sources,
        "voices": voices,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"Claims: {total_claims} total / {direct_claims} direct source positions / {total_sources} sources")
        print(f"Audited equivalent rows collapsed by default: {equivalent_extras}")
        print("Top voices:")
        for row in voices:
            print(
                f"  {row['name']}: {row['claims']} claims / {row['direct_claims']} direct / "
                f"{row['reported_claims']} reported / {row['agenda_claims']} agenda / {row['sources']} sources"
            )
        print("Top source hosts:")
        for row in hosts:
            print(
                f"  {row['host']}: {row['claims']} claims / {row['sources']} sources / "
                f"{row['claims_per_source']} claims per source"
            )
    return 0


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


def add_search_boundaries(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--current", action="store_true", help="boost recent sources after relevance matching")
    parser.add_argument("--include-agenda", action="store_true", help="include research questions while preserving their attribution label")
    parser.add_argument("--include-reported", action="store_true", help="include positions merely reported or quoted by the source")
    parser.add_argument("--max-per-host", type=int, default=3)
    parser.add_argument("--max-per-voice", type=int, default=2)
    parser.add_argument("--max-per-work", type=int, default=1)
    parser.add_argument("--no-diversify", action="store_true")
    parser.add_argument("--theme")
    parser.add_argument("--voice")
    parser.add_argument("--year-from", type=int)
    parser.add_argument("--year-to", type=int)


def parser() -> argparse.ArgumentParser:
    answer = argparse.ArgumentParser(description=__doc__)
    answer.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    commands = answer.add_subparsers(dest="command", required=True)

    summary = commands.add_parser("summary", help="show full-index and gold-kernel counts")
    summary.set_defaults(handler=command_summary)

    search = commands.add_parser("search", help="search all 52,225 local claims with attribution and diversity controls")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)
    search.add_argument("--json", action="store_true")
    add_search_boundaries(search)
    search.set_defaults(handler=command_search)

    kernel = commands.add_parser("kernel-search", help="search only the 54 human-reviewed gold rows")
    kernel.add_argument("query")
    kernel.add_argument("--limit", type=int, default=8)
    kernel.add_argument("--json", action="store_true")
    kernel.set_defaults(handler=command_kernel_search)

    show = commands.add_parser("show", help="show one or more claims from the full local index")
    show.add_argument("claim_ids", nargs="+")
    show.add_argument("--json", action="store_true")
    show.add_argument("--passage", action="store_true", help="include the full bound passage context")
    show.set_defaults(handler=command_show)

    stats = commands.add_parser("stats", help="show source and voice distribution in the full index")
    stats.add_argument("--json", action="store_true")
    stats.set_defaults(handler=command_stats)

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
    for field in ("max_per_host", "max_per_voice", "max_per_work"):
        if hasattr(args, field):
            require(getattr(args, field) >= 1, f"--{field.replace('_', '-')} must be positive")
    try:
        return args.handler(data_root, args)
    except sqlite3.Error as error:
        raise AMindSkillError(f"SQLite index error: {error}") from error


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AMindSkillError as error:
        print(f"AMind error: {error}", file=sys.stderr)
        raise SystemExit(2)
