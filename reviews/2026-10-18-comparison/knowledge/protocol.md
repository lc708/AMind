# Preregistered local CLI comparison

Frozen before executing either public query CLI. This is a constructed challenge from native release passages, not a blind external benchmark. No model or network trials are run here. After-results discoveries are diagnostic only and never promoted to holdout.

## Inputs and authority

Old: `.codex-tmp/contrast-2026-10-18/old/skills/amind` (knowledge 1.2.1). New: `.codex-tmp/contrast-2026-10-18/new/skills/amind` (1.3.0). Both are immutable. Native source evidence: `release/amind-v1-increment-2026-10-18/data/passages.jsonl.gz`, stable claim bindings and dated source-native corrections captured in native-exhibits.jsonl. Frozen old gold rows are controls. Source passages, not package size, establish expected facts.

## Fixed execution

Run every cases.jsonl command against each side with Python and its absolute query.py path from a temporary cwd. Capture exact argv, exit code, stdout JSONL, stderr and duration. No CLI output is used to change this protocol. Also compare original gold claim IDs/propositions/exact quotes directly; a no-op is a valid result.

## Scoring

One qualified-result point per case (20 maximum), judged against its stated rubric. K01-K07 require the preselected source-bound material to be available with correct source/voice/epistemic/conditions when specified; material claims must be supported by exact quotes in the bound passage. K08 requires excluded prompt/model-reply evidence, not a fabricated institutional belief. T01-T08 require correct dated eligibility, history preservation, cutoff or explicit unknown-date handling. C01-C04 require preservation or calibrated bounded refusal. Coverage miss / unsupported option / unknown source is zero qualified coverage, never counted as false factual content. Search source recall@20 is a separate secondary measure and cannot replace support.

Report: paired qualified counts by group; exact-quote support among observed shown claims; citation identity mismatches (claim ID, source URL or bound passage identity); reasonable refusals for absent/unknown evidence. An unsupported old --as-of option is a capability gap, not hallucination. No generated user-facing answers are inferred from CLI metadata.

## Conditions and limitations

Gold human review remains 54 unchanged rows; new rows are machine checked with selected AI review. Multiple carriers or claims from one work are not independent evidence. Unknown publication days are not errors unless a precise date is invented or temporal certainty asserted. Retrieval absence is not evidence that Anthropic holds the opposite position. Native snapshots support bounded captured-source findings, not independently verified live web truth.
