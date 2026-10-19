# Retrieval policy

The current package includes the 2026-10-18 refresh. Exact counts are in the manifest and `query.py stats`; distribution figures below that refer to older releases are historical audits. Default search filters recorded corrections, supersessions and effective windows, and labels each retained result. Use `--include-inactive` to inspect historical or future-effective evidence; `--as-of` changes the dated eligibility view. Neither option creates a live source connection.


AMind separates recall from trust. The full index finds candidates; the gold kernel and bound passages help decide which candidates can support an answer.

## Evidence layers

```text
Full machine-checked claim population -> full local FTS recall
All source-bound passages             -> context verification
54 human-reviewed representative rows -> gold calibration
9 themes / 5 voices / 5 tensions      -> synthesis navigation
```

The themes, voice profiles, and tensions are derived navigation aids. They are not independent evidence and must not replace underlying citations.

## Default search boundaries

`query.py search` defaults to:

- direct source positions eligible for source-level synthesis;
- one representative from each audited equivalence component;
- at most one result from the same work;
- at most two results from the same voice;
- at most three results from the same source host.

If a narrow query cannot fill the requested limit under the voice or host caps, retrieval may relax those two caps after the strict diversity pass. It never relaxes the one-result-per-work boundary unless the caller explicitly changes it.

Bounded simulation findings require `--include-simulated` and retain their experimental conditions. In the increment, routine PDF and newsletter extraction is conservatively reported; only individually context-reviewed PDF findings enter the direct-source scope.

Merely reported or quoted positions are excluded by default. Add `--include-reported` only when the distinction itself matters. Research questions are excluded unless `--include-agenda` is supplied; they remain questions, not answers.

Attribution filtering happens before equivalence collapse. If an equivalence component's canonical representative is a reported position but an eligible direct-source member remains, search keeps one eligible member instead of dropping the component.

## Recency and named voices

Use `--current` when the user asks about the latest policy, current practice, recent research, or a versioned document. Default search already applies dated correction and edition eligibility; historical evidence remains accessible with `show` or `--include-history`. `--current` adds a recency boost after lexical relevance, not a replacement for relevance or a live source check.

Use `--voice "Name"` when the user explicitly asks about a named person. This relaxes voice and host diversity caps because concentration is then intentional. Without an explicit named-person request, do not center one author merely because that author occupies a large share of the corpus.

## Verification workflow

1. Search the full index with two or three short concept queries.
2. Inspect the evidence tier, attribution class, epistemic force, date, and source diversity.
3. Run `show <claim-id> ... --passage --json` for the material candidates.
4. Confirm that the exact quote supports the proposition in its full bound passage.
5. Corroborate a strong framework inference across more than one work when practical.

`gold_human_reviewed` means the representative row was individually reviewed in passage context. `full_release_machine_checked` means the row passed structural, source-binding, and attribution audits but still requires contextual inspection before material use.

## Corpus-distribution caveat

The distribution audit below describes the frozen v1 baseline. The September snapshot then added four Import AI issues and one Transformer Circuits article; its counts were Jack Clark 11,223 claims (3,690 reported) and Transformer Circuits 12,693 claims across 52 units. Those are historical snapshot counts. Current counts come from `query.py stats`. No frequency is an influence weight.

Claim counts measure corpus coverage and extraction density, not influence. The frozen source population includes 480 Import AI issues, so Jack Clark has 10,835 extracted claims; 3,302 of those are reported or quoted positions rather than Clark's own source-level position. Long technical works create a different distortion: 51 transformer-circuits documents produce 12,248 claims because some papers are atomized very densely.

The index therefore diversifies by work, voice, and host and collapses audited equivalence components. Do not use raw claim frequency as an author ranking, organizational vote, or importance score.

### Distribution audit

The apparent concentration comes mainly from the sampling frame and claim density, not from exact duplication:

| Slice | Claims | Analysis units | Interpretation |
|---|---:|---:|---|
| `transformer-circuits.pub` | 12,248 | 51 | A small number of long technical works, atomized densely |
| `anthropic.com` | 11,689 | 432 | Large institutional publication surface |
| `jack-clark.net` | 11,168 | 480 | The collection deliberately includes the full Import AI series; some claims use non-Jack quoted voices |
| Jack Clark voice | 10,835 | 480 | 7,532 direct source positions, 3,302 reported or quoted positions, and 1 agenda/question |

All 1,348 body-bearing analysis units have distinct primary body hashes; the other three units are explicitly unavailable. The narrower exact proposition-plus-quote check finds 35 duplicate groups containing 71 rows. The semantic equivalence audit finds 189 components containing 406 rows, or 217 extra rows after one representative per component is retained—about 0.42% of the corpus. This is too small to explain the author pattern.

The source configuration explicitly seeds Jack Clark's sitemap, feed, homepage, and historical archive. It therefore samples publication populations rather than equal quotas per author. Raw counts should be read as “how much material this collection captured and how finely it was atomized,” never “how important this voice is.”

The old 54-row-only retrieval path amplified the effect: 11 Gold rows use Jack Clark's voice, spread across six of the nine themes, and three of the six scaling Gold rows are his. Those rows were selected for thematic representation, not recency balance. Full-index retrieval keeps the Gold rows as calibration but applies query relevance, optional recency, and a default two-result-per-voice cap instead of repeatedly drawing from that fixed pool.
