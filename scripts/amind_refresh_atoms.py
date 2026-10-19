#!/usr/bin/env python3
"""Source-exact segmentation/atomization helpers adapted from the AMind v1 pipeline.
No network or model calls; retains the original evidence schema and ID algorithm.
"""
from __future__ import annotations
import hashlib,json,re
from dataclasses import dataclass
from typing import Any

HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", re.MULTILINE)
WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)


class BuildError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stable_id(prefix: str, material: str, length: int = 24) -> str:
    return prefix + hashlib.sha256(material.encode("utf-8")).hexdigest()[:length]


@dataclass(frozen=True)
class SourceBlock:
    start: int
    end: int
    line_start: int
    line_end: int
    kind: str
    section_path: tuple[str, ...]


def frontmatter_end(text: str) -> int:
    if not text.startswith("---\n"):
        return 0
    marker = text.find("\n---\n", 4)
    require(marker >= 0, "unterminated Markdown frontmatter")
    return marker + len("\n---\n")


def line_number_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def classify_block(block: str) -> str:
    stripped = block.lstrip()
    if HEADING_RE.match(stripped):
        return "heading"
    if stripped.startswith("```") or stripped.startswith("~~~"):
        return "code"
    if stripped.startswith(">"):
        return "blockquote"
    if re.match(r"(?:[-*+] |\d+[.)] )", stripped):
        return "list"
    lines = [line for line in stripped.splitlines() if line.strip()]
    if lines and all("|" in line for line in lines[: min(3, len(lines))]):
        return "table"
    return "prose"


def split_block_span(text: str, start: int, end: int, max_chars: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    while end - cursor > max_chars:
        limit = cursor + max_chars
        # rfind's end is exclusive. Keeping it at ``limit`` guarantees that
        # adding one for the newline can never produce a max_chars + 1 span.
        boundary = text.rfind("\n", cursor + max_chars // 2, limit)
        if boundary < cursor:
            boundary = limit
        else:
            boundary += 1
        require(boundary > cursor, "long-span splitter did not advance")
        spans.append((cursor, boundary))
        cursor = boundary
    if cursor < end:
        spans.append((cursor, end))
    return spans


def source_blocks(text: str, max_chars: int) -> tuple[int, list[SourceBlock]]:
    body_start = frontmatter_end(text)
    lines = text.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    if not lines and text:
        lines = [text]
        offsets = [0]

    raw_spans: list[tuple[int, int]] = []
    open_start: int | None = None
    for index, line in enumerate(lines):
        start = offsets[index]
        end = start + len(line)
        if end <= body_start:
            continue
        effective_start = max(start, body_start)
        fragment = text[effective_start:end]
        if not fragment.strip():
            if open_start is not None:
                raw_spans.append((open_start, effective_start))
                open_start = None
            continue
        if open_start is None:
            open_start = effective_start
    if open_start is not None:
        raw_spans.append((open_start, len(text)))

    blocks: list[SourceBlock] = []
    headings: list[str] = []
    for raw_start, raw_end in raw_spans:
        raw_text = text[raw_start:raw_end]
        heading_match = HEADING_RE.match(raw_text.lstrip())
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            headings = headings[: level - 1]
            while len(headings) < level - 1:
                headings.append("")
            headings.append(title)
        kind = classify_block(raw_text)
        for start, end in split_block_span(text, raw_start, raw_end, max_chars):
            blocks.append(
                SourceBlock(
                    start=start,
                    end=end,
                    line_start=line_number_at(text, start),
                    line_end=line_number_at(text, max(start, end - 1)),
                    kind=kind,
                    section_path=tuple(item for item in headings if item),
                )
            )
    return body_start, blocks


def segment_text(text: str, unit_id: str, text_sha256: str, max_chars: int) -> tuple[int, list[dict[str, Any]]]:
    body_start, blocks = source_blocks(text, max_chars)
    passages: list[dict[str, Any]] = []
    current: list[SourceBlock] = []

    def flush() -> None:
        nonlocal current
        if not current:
            return
        start = current[0].start
        end = current[-1].end
        passage_text = text[start:end]
        passage_id = stable_id("nuwa1-passage-", f"{unit_id}\0{text_sha256}\0{start}\0{end}")
        passages.append(
            {
                "passage_id": passage_id,
                "passage_sequence": len(passages) + 1,
                "source_char_start": start,
                "source_char_end": end,
                "source_line_start": current[0].line_start,
                "source_line_end": current[-1].line_end,
                "section_path": list(current[-1].section_path),
                "block_kinds": sorted({block.kind for block in current}),
                "text": passage_text,
                "text_sha256": sha256_bytes(passage_text.encode("utf-8")),
                "char_count": len(passage_text),
                "word_count": len(WORD_RE.findall(passage_text)),
            }
        )
        current = []

    for block in blocks:
        section_change = bool(current and block.section_path != current[-1].section_path and block.kind == "heading")
        proposed_start = current[0].start if current else block.start
        proposed_chars = block.end - proposed_start
        if current and (section_change or proposed_chars > max_chars):
            flush()
        current.append(block)
    flush()

    require(all(row["char_count"] <= max_chars for row in passages), f"passage limit exceeded: {unit_id}")
    for previous, following in zip(passages, passages[1:]):
        require(previous["source_char_end"] <= following["source_char_start"], f"passages overlap: {unit_id}")
    covered_nonspace = sum(sum(not char.isspace() for char in row["text"]) for row in passages)
    source_nonspace = sum(not char.isspace() for char in text[body_start:])
    require(covered_nonspace == source_nonspace, f"non-whitespace source coverage mismatch: {unit_id}")
    return body_start, passages


def normalize_proposition(
    text: str,
    voice_name: str,
    voice_type: str,
    *,
    clause_fragment: bool = False,
) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    value = re.sub(r"^(?:[-*+]\s+|\d+[.)]\s+)", "", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"\s*[,;:]+\s*$", "", value)
    subject = voice_name if voice_type == "named_author" else "The document"
    if value.endswith("?"):
        proposition = f"{subject} raises the question: {value}"
        if clause_fragment:
            proposition = f"Within a longer source sentence, {proposition[0].lower() + proposition[1:]}"
        return proposition
    replacements = (
        (r"^We['’]re\b", "The authors are"),
        (r"^we['’]re\b", "The authors are"),
        (r"^We['’]ve\b", "The authors have"),
        (r"^we['’]ve\b", "The authors have"),
        (r"^We['’]ll\b", "The authors will"),
        (r"^we['’]ll\b", "The authors will"),
        (r"^We['’]d\b", "The authors would"),
        (r"^we['’]d\b", "The authors would"),
        (r"^I['’]m\b", f"{subject} is"),
        (r"^I['’]ve\b", f"{subject} has"),
        (r"^I['’]ll\b", f"{subject} will"),
        (r"^I['’]d\b", f"{subject} would"),
        (r"^We\b", "The authors"), (r"^we\b", "The authors"),
        (r"^Our\b", "The authors’"), (r"^our\b", "The authors’"),
        (r"^I\b", subject), (r"^My\b", f"{subject}’s"),
    )
    for pattern, replacement in replacements:
        if re.search(pattern, value):
            value = re.sub(pattern, replacement, value, count=1)
            break
    if value and value[0].islower():
        value = value[0].upper() + value[1:]
    if value and not re.search(r"[.!?](?:[\"'’”)])?$", value):
        value += "."
    if clause_fragment:
        value = f"Within a longer source sentence, the document states: {value}"
    return value


DOMAIN_RULES: tuple[tuple[str, str], ...] = (
    ("interpret", "interpretability"), ("safety", "ai-safety"), ("alignment", "alignment"),
    ("agent", "agents"), ("model", "models"), ("train", "training"), ("evaluat", "evaluation"),
    ("benchmark", "benchmarks"), ("policy", "policy"), ("govern", "governance"),
    ("risk", "risk"), ("capabil", "capabilities"), ("reward", "reward-modeling"),
    ("feature", "features"), ("neuron", "neural-networks"), ("represent", "representations"),
    ("attention", "attention"), ("sparse", "sparse-autoencoders"), ("data", "data"),
    ("compute", "compute"), ("language", "language-models"), ("human", "human-ai"),
    ("economic", "economics"), ("work", "work"), ("security", "security"),
    ("misalign", "misalignment"), ("interpret", "interpretability"), ("forecast", "forecasting"),
)


def domains_for(text: str, title: str) -> list[str]:
    lower = text.lower()
    domains: list[str] = []
    for needle, domain in DOMAIN_RULES:
        if needle in lower and domain not in domains:
            domains.append(domain)
        if len(domains) == 2:
            return domains
    for token in re.findall(r"[a-z0-9]+", title.lower()):
        if len(token) >= 5 and token not in {"about", "their", "using", "findings", "report"}:
            domain = token[:40]
            if domain not in domains:
                domains.append(domain)
        if len(domains) == 2:
            break
    return domains or ["source-claim"]


def classify(text: str) -> tuple[str, str]:
    lower = text.lower()
    if text.rstrip().endswith("?"):
        return "self_description", "qualified"
    if re.search(r"\b(according to|writes?|reports?|said|says|argues?|claims?|the authors note|the researchers (?:write|report|say|argue|claim))\b", lower):
        return "descriptive", "quoted_position"
    if re.search(r"\b(define|defined as|means|refers to|we call|is called|consists of)\b", lower):
        return "definition", "asserted"
    if re.search(r"\b(we use|we train|we evaluate|we measure|we compute|we sample|we collect|we construct|we test|we stress-tested|our method|our approach|we ask|we run)\b", lower):
        return "methodological", "asserted"
    if re.search(r"\b(we release|we introduce|we present|we report|this paper|this post|this report)\b", lower):
        return "self_description", "asserted"
    if re.search(r"\b(we find|we found|we observe|we observed|we show|we demonstrate|results show|the results)\b", lower):
        return "descriptive", "observed_result"
    if re.search(r"\b(should|must|ought|recommend|need to|it is important|it’s important|we want)\b", lower):
        return "normative", "asserted"
    if re.search(r"\b(will|forecast|predict|expect to|going to)\b", lower):
        return "forecast", "forecast"
    if re.search(r"\b(strategy|roadmap|priority|plan to|goal is|objective is)\b", lower):
        return "strategy", "asserted"
    if re.search(r"\b(may|might|could|possible|possibly|plausible|hypothes|suspect|unclear|uncertain)\b", lower):
        return "descriptive", "qualified"
    if re.search(r"\b(because|therefore|thus|leads to|results in|causes|due to|as a result)\b", lower):
        return "causal", "asserted"
    if re.search(r"\b(policy|regulation|law|standard|government)\b", lower):
        return "policy", "asserted"
    return "descriptive", "asserted"


def line_is_noise(line: str, policy: dict[str, Any]) -> bool:
    stripped = line.strip()
    lower = stripped.lower()
    if not stripped:
        return True
    if stripped.startswith("#") or stripped.startswith(">"):
        return True
    if stripped.startswith("|") and stripped.endswith("|"):
        return True
    if re.fullmatch(r"[-=_*#]{3,}", stripped):
        return True
    if any(lower.startswith(prefix) for prefix in policy["skip_line_prefixes"]):
        return True
    if re.fullmatch(r"(?:page\s+)?\d+", lower):
        return True
    alpha = sum(ch.isalpha() for ch in stripped)
    if alpha == 0:
        return True
    if len(stripped) > 20 and alpha / len(stripped) < 0.25:
        return True
    return False


def passage_skip_reason(passage: dict[str, Any], policy: dict[str, Any]) -> str | None:
    text = passage["text"]
    for declared_range in policy["source_external_passage_sequence_ranges"]:
        if (
            passage["analysis_unit_id"] == declared_range["analysis_unit_id"]
            and declared_range["start"] <= passage["passage_sequence"] <= declared_range["end"]
        ):
            return declared_range["basis"]
    nonempty = [line.strip() for line in text.splitlines() if line.strip()]
    if not nonempty:
        return "Empty frozen passage."
    first = nonempty[0].lower().lstrip("# ")
    if all(line.startswith("#") for line in nonempty):
        return "Heading or title only."
    if any(term in first for term in policy["skip_whole_passage_heading_terms"]):
        return "Acknowledgement, reference, interface, or comment-heading material only."
    section_path = " > ".join(passage.get("section_path", [])).lower()
    if any(term in section_path for term in policy["source_external_section_terms"]):
        return "Prompt, transcript, generated example, contribution list, or other source-external artifact; not promoted to an author claim."
    lower = text.lower()
    if lower.count("loading... reply") >= 2 or lower.count(" says:") >= 5:
        return "Repeated comments or trackbacks; not source-author prose."
    if lower.count("info:claude's response:") + lower.count("info:bash's response:") >= 2:
        return "Raw agent/tool transcript; not source-author prose."
    if lower.count("(cited on page") >= 3:
        return "Bibliography-only frozen passage."
    numbered_citations = len(re.findall(r"(?m)^\s*\[\d+\]\s+", text))
    dated_citations = len(re.findall(r"\b(?:19|20)\d{2}[a-z]?\.\s", text))
    if numbered_citations >= 4 or (dated_citations >= 8 and lower.count("http") >= 3):
        return "Bibliography-only frozen passage."
    return None


def eligible_spans(text: str, policy: dict[str, Any], *, initial_fenced: bool = False) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    lines = text.splitlines(keepends=True)
    offset = 0
    fenced = initial_fenced
    paragraph_start: int | None = None
    paragraph_end: int | None = None

    def flush() -> None:
        nonlocal paragraph_start, paragraph_end
        if paragraph_start is not None and paragraph_end is not None and paragraph_end > paragraph_start:
            spans.append((paragraph_start, paragraph_end))
        paragraph_start = None
        paragraph_end = None

    for line in lines:
        raw_end = offset + len(line.rstrip("\r\n"))
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush()
            fenced = not fenced
            offset += len(line)
            continue
        if fenced or line_is_noise(line, policy):
            flush()
            offset += len(line)
            continue
        content_start = offset + len(line) - len(line.lstrip())
        marker = re.match(r"(?:[-*+]\s+|\d+[.)]\s+)", text[content_start:raw_end])
        if marker:
            flush()
            start = content_start + marker.end()
            if raw_end > start:
                spans.append((start, raw_end))
            offset += len(line)
            continue
        if paragraph_start is None:
            paragraph_start = content_start
        paragraph_end = raw_end
        offset += len(line)
    flush()
    return spans


def sentence_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    segment = text[start:end]
    boundaries = [0]
    for match in re.finditer(r"[.!?](?=(?:\s+|$)(?:[A-Z0-9\"“‘(\[]|$))", segment):
        boundaries.append(match.end())
    if boundaries[-1] != len(segment):
        boundaries.append(len(segment))
    result: list[tuple[int, int]] = []
    for left, right in zip(boundaries, boundaries[1:]):
        while left < right and segment[left].isspace():
            left += 1
        while right > left and segment[right - 1].isspace():
            right -= 1
        if right > left:
            result.append((start + left, start + right))
    return result


def split_long_span(text: str, start: int, end: int, maximum: int, target: int) -> list[tuple[int, int]]:
    if end - start <= maximum:
        return [(start, end)]
    result: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        while cursor < end and text[cursor].isspace():
            cursor += 1
        if end - cursor <= maximum:
            cut = end
        else:
            window_end = min(end, cursor + target)
            candidates = [m.end() for m in re.finditer(r"[;:]\s+|[—–]\s+|,\s+", text[cursor:window_end])]
            cut = cursor + (candidates[-1] if candidates else 0)
            if cut - cursor < 40:
                space = text.rfind(" ", cursor + 40, cursor + maximum)
                cut = space if space > cursor else min(end, cursor + maximum)
        while cut > cursor and text[cut - 1].isspace():
            cut -= 1
        if cut > cursor:
            result.append((cursor, cut))
        cursor = cut
        while cursor < end and text[cursor].isspace():
            cursor += 1
    return result


def candidate_is_substantive(quote: str, policy: dict[str, Any]) -> bool:
    stripped = quote.strip()
    if len(stripped) < policy["atomization"]["minimum_quote_chars"]:
        return False
    words = re.findall(r"[A-Za-z][A-Za-z’'-]*", stripped)
    if len(words) < policy["atomization"]["minimum_alpha_words"]:
        return False
    lower = stripped.lower()
    prompt_prefixes = (
        "system prompt:", "user:", "assistant:", "instructions:", "begin your response",
        "your task is", "you are an ai", "you are an automated", "remember: all text",
        "the result is:", "claude's response:", "bash's response:", "tool's response:",
    )
    if lower.startswith(prompt_prefixes):
        return False
    if re.search(r"<(?:/?(?:antml:)?thinking|/?scratchpad_reasoning|/?submit|/?output|/?bash|/?user_input)>", lower):
        return False
    if re.match(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", stripped):
        return False
    if lower.startswith(("figure ", "table ", "source:", "image:", "copyright ")):
        return False
    if lower.count("http") >= 2 or lower.count("doi") >= 3:
        return False
    if re.fullmatch(r"[A-Z][A-Za-z0-9 ,:;()'’\-]+", stripped) and not re.search(r"\b(is|are|was|were|will|can|may|has|have|do|does|we|i|they)\b", lower):
        return False
    return True


def unique_quote(texts: list[str], passage_text: str, start: int, end: int, maximum: int) -> str | None:
    quote = passage_text[start:end]
    if sum(value.count(quote) for value in texts) == 1:
        return quote
    left, right = start, end
    while right - left < maximum and (left > 0 or right < len(passage_text)):
        left = max(0, left - 8)
        right = min(len(passage_text), right + 8)
        candidate = passage_text[left:right]
        if sum(value.count(candidate) for value in texts) == 1:
            return candidate
    return None


def voice_defaults(unit: dict[str, Any]) -> dict[str, str]:
    authors = [re.sub(r"^Authors?\s+", "", value).strip() for value in unit.get("authors", []) if value.strip()]
    combined_author_field = len(authors) == 1 and bool(re.search(r",|\band\b", authors[0], flags=re.IGNORECASE))
    if len(authors) == 1 and not combined_author_field:
        voice_type = "named_author"
        voice_name = authors[0]
    elif authors:
        voice_type = "document_editorial"
        voice_name = ", ".join(authors)
    else:
        voice_type = "document_editorial"
        voice_name = f"{unit['title']} editorial voice"
    canonical = unit.get("canonical", "").lower()
    organization = "Anthropic" if any(host in canonical for host in ("anthropic.com", "alignment.anthropic.com", "transformer-circuits.pub")) else ""
    return {
        "voice_type": voice_type,
        "voice_name": voice_name,
        "organization": organization,
        "role_at_time": "author or source-native editorial voice of the frozen edition",
        "attribution_basis": "Attribution follows the frozen analysis-unit author metadata when present; otherwise it remains at document-editorial level. Source-exact statements, questions, methods, observations, forecasts, and uncertainty are mechanically separated. Fenced code, prompt boilerplate, equations, tables, citations, interface text, and unattributed blockquotes are not promoted to author beliefs.",
    }


def simulation_condition(passage_text: str) -> str | None:
    """Retain the source's own simulated/fictional boundary without downgrading observed results."""
    lower = passage_text.lower()
    markers = (
        "controlled simulations",
        "controlled simulation",
        "fictional scenarios",
        "fictional scenario",
        "fictional settings",
        "fictional setting",
        "simulated deployment",
        "simulated scenarios",
        "simulated scenario",
        "hypothetical future use case",
        "hand-built agentic misalignment testbeds",
    )
    if any(marker in lower for marker in markers):
        return "The source explicitly frames this passage as a controlled simulation, fictional setting, or hypothetical testbed; the claim is scoped to that setting."
    return None


def stable_claim_id(seed: dict[str, Any], quote_sha256: str) -> str:
    material = f"{seed['unit_id']}\0{seed['proposition']}\0{quote_sha256}"
    return "nuwa1-claim-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


def validate_seed(seed: dict[str, Any], claim_types: set[str], forces: set[str], voices: set[str], max_quote: int) -> None:
    required = {
        "seed_id", "unit_id", "proposition", "quote", "claim_type", "epistemic_force",
        "voice_type", "voice_name", "organization", "role_at_time", "attribution_basis",
        "domains", "conditions", "invalidation_conditions",
    }
    require(required <= set(seed), f"seed fields missing: {seed.get('seed_id')}")
    require(seed["claim_type"] in claim_types, f"invalid claim type: {seed['seed_id']}")
    require(seed["epistemic_force"] in forces, f"invalid epistemic force: {seed['seed_id']}")
    require(seed["voice_type"] in voices, f"invalid voice type: {seed['seed_id']}")
    require(0 < len(seed["quote"]) <= max_quote, f"quote length invalid: {seed['seed_id']}")
    require(seed["proposition"].strip() == seed["proposition"] and seed["proposition"], f"proposition invalid: {seed['seed_id']}")
    require(isinstance(seed["domains"], list) and len(seed["domains"]) == len(set(seed["domains"])), f"domains invalid: {seed['seed_id']}")


def extract_claim_records(
    seeds: list[dict[str, Any]],
    units: list[dict[str, Any]],
    passages: list[dict[str, Any]],
    schema: dict[str, Any],
    snapshot_date: str,
    extraction_method: str,
    extractor_version: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Turn source-exact claim seeds into validated claim and evidence rows."""
    properties = schema["properties"]
    claim_types = set(properties["claim_type"]["enum"])
    forces = set(properties["epistemic_force"]["enum"])
    voices = set(properties["voice"]["properties"]["voice_type"]["enum"])
    max_quote = int(properties["evidence"]["items"]["properties"]["exact_quote"]["maxLength"])
    unit_by_id = {row["analysis_unit_id"]: row for row in units}
    passages_by_unit: dict[str, list[dict[str, Any]]] = {}
    for passage in passages:
        passages_by_unit.setdefault(passage["analysis_unit_id"], []).append(passage)

    claims: list[dict[str, Any]] = []
    seed_evidence: list[dict[str, Any]] = []
    quote_mismatches: list[dict[str, Any]] = []
    for seed in seeds:
        validate_seed(seed, claim_types, forces, voices, max_quote)
        unit = unit_by_id.get(seed["unit_id"])
        require(unit is not None and unit["unit_status"] == "body_primary", f"seed unit is not body-backed: {seed['seed_id']}")
        matches: list[tuple[dict[str, Any], int]] = []
        for passage in passages_by_unit.get(seed["unit_id"], []):
            cursor = 0
            while True:
                offset = passage["text"].find(seed["quote"], cursor)
                if offset < 0:
                    break
                matches.append((passage, offset))
                cursor = offset + 1
        if len(matches) != 1:
            quote_mismatches.append({
                "seed_id": seed["seed_id"],
                "unit_id": seed["unit_id"],
                "match_count": len(matches),
                "quote": seed["quote"],
            })
            continue
        passage, local_start = matches[0]
        quote_sha = sha256_bytes(seed["quote"].encode("utf-8"))
        char_start = int(passage["source_char_start"]) + local_start
        line_start = int(passage["source_line_start"]) + passage["text"].count("\n", 0, local_start)
        evidence = {
            "relation": "supports",
            "analysis_unit_id": unit["analysis_unit_id"],
            "passage_id": passage["passage_id"],
            "work_id": unit["work_id"],
            "edition_id": unit["edition_id"],
            "source_record_ids": unit["source_seed_record_ids"],
            "exact_quote": seed["quote"],
            "exact_quote_sha256": quote_sha,
            "source_char_start": char_start,
            "source_char_end": char_start + len(seed["quote"]),
            "source_line_start": line_start,
            "source_line_end": line_start + seed["quote"].count("\n"),
            "text_file_sha256": unit["text_file_sha256"],
            "body_sha256": unit["body_sha256"],
        }
        claim = {
            "schema_name": "nuwa-v1-atomic-claim",
            "schema_version": 1,
            "claim_id": stable_claim_id(seed, quote_sha),
            "proposition": seed["proposition"],
            "claim_type": seed["claim_type"],
            "epistemic_force": seed["epistemic_force"],
            "voice": {
                "voice_type": seed["voice_type"],
                "name": seed["voice_name"],
                "person_id": "",
                "organization": seed["organization"],
                "role_at_time": seed["role_at_time"],
                "attribution_basis": seed["attribution_basis"],
            },
            "domains": seed["domains"],
            "conditions": seed["conditions"],
            "temporal_scope": {
                "valid_from": unit["published_at"],
                "valid_through": "",
                "basis": "source edition publication time; historical claim retained even if later revised",
            },
            "evidence": [evidence],
            "invalidation_conditions": seed["invalidation_conditions"],
            "claim_status": "extracted",
            "provenance": {
                "extraction_method": extraction_method,
                "extractor_version": extractor_version,
                "extracted_at": snapshot_date,
                "review_state": "machine_checked",
            },
        }
        claims.append(claim)
        seed_evidence.append({
            "seed_id": seed["seed_id"],
            "claim_id": claim["claim_id"],
            "unit_id": unit["analysis_unit_id"],
            "passage_id": passage["passage_id"],
        })

    require(not quote_mismatches, "quote mismatches: " + json.dumps(quote_mismatches, ensure_ascii=False, sort_keys=True))
    claims.sort(key=lambda row: row["claim_id"])
    require(len({row["claim_id"] for row in claims}) == len(claims), "duplicate claim ID")
    require(len({row["proposition"] for row in claims}) == len(claims), "duplicate proposition")
    require(all("worldview" not in " ".join(row["domains"]).lower() for row in claims), "worldview labels leaked into extraction")
    return claims, seed_evidence


POLICY = {'schema_name': 'nuwa-v1-remaining-routine-atomization-policy', 'schema_version': 1, 'frozen_plan_path': 'config/nuwa-v1-remaining-routine-plan-157-195.jsonl', 'frozen_plan_sha256': 'aed513d844aa642da33040c85c66536db60ba29811bb22d9e4da9c878c6b404a', 'expected': {'tranches': 39, 'body_units': 46, 'batches': 291, 'passages': 2205}, 'atomization': {'minimum_quote_chars': 28, 'maximum_quote_chars': 320, 'minimum_alpha_words': 5, 'long_clause_target_chars': 280}, 'skip_whole_passage_heading_terms': ['acknowledgement', 'acknowledgment', 'references', 'bibliography', 'table of contents', 'share this', 'like this', 'leave a reply', 'comments to'], 'source_external_section_terms': ['full transcript', 'full steered transcript', 'example transcript', 'examples from emotional stories dataset', 'experiment sandbagging prompts', 'research steering prompts', 'prompts used in', 'appendix a: system prompts', 'system prompt injections', 'example generations', 'author contributions', 'dataset generation', 'example quotes from', 'quotes from synthetic honeypot transcripts', 'meta-judge quotes', 'here are the per-package modules'], 'source_external_passage_sequence_ranges': [], 'skip_line_prefixes': ['read more:', 'subscribe', 'loading... reply', 'http://', 'https://'], 'omitted_material_classes': ['heading_only', 'code_or_prompt_block', 'equation_or_table_detail', 'citation_or_bibliography_detail', 'interface_or_navigation', 'repeated_comment_or_trackback', 'verbatim_third_party_blockquote'], 'claim_contract': {'all_quotes_source_exact': True, 'all_quotes_unique_within_unit': True, 'all_passages_processed': True, 'questions_represented_as_questions_raised': True, 'fiction_and_quoted_material_not_promoted_to_facts': True, 'no_predeclared_worldview_labels': True}, 'network_access': False, 'active_commoncrawl_direct_index': False}
