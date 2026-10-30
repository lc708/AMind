# Accounting and judge calibration

These helpers run offline. They consume explicit normalized records; they do not contact providers, infer SDK field mappings or certify a complete invoice. The bundled accounting demo is synthetic and contains deliberately different rates for the same mock model on two endpoints.

```bash
python3 "$SKILL_ROOT/scripts/price_usage.py" --events "$SKILL_ROOT/assets/accounting-demo/events.jsonl" --rates "$SKILL_ROOT/assets/accounting-demo/rates.json"
python3 "$SKILL_ROOT/scripts/calibrate_grader.py" "$SKILL_ROOT/assets/accounting-demo/labels.jsonl" --population-prevalence 0.01
```

## Exact price scope

A dated card has `version`, `effective_date`, `source` and `rates:[...]`. Each rate declares `billing_identity:{provider,interface,model,service_tier,region}`, optional `context_band` and `cache_policy`, and `usage_adapter`. Every scope value must be explicit; `global` is a declared region, not an inferred default. The event repeats the exact identity and adapter. An unmatched endpoint, tier, region, context band or cache policy returns unknown even when the model matches. Bake any documented regional/context multiplier into that scoped rate; the helper does not invent multipliers. Duplicate scopes are rejected.

If a record also repeats flat `provider/interface/model/service_tier/region/context_band/cache_policy` fields, they must agree with its billing identity. Repeated flat/detail cache and reasoning counters must also agree; contradictory normalization is rejected before pricing.

| Adapter | Normalized usage | Rates |
|---|---|---|
| `text_tokens_v1` | `input_tokens`, explicit `cached_input_tokens`, `output_tokens`; optional `reasoning_tokens` | `input_per_million`, `cached_input_per_million`, `output_per_million` |
| `input_only_v1` | `input_tokens`; output/cache counters are rejected | `input_per_million` |
| `units_v1` | `units:{unit_name:quantity}` only | `unit_rates:{unit_name:{usd,per}}` |
| `cache_text_v1` | `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens_by_ttl:{"30m":n,"12h":n}`, `output_tokens`; optional `reasoning_tokens` | Input/read/output rates plus `cache_write_input_per_million_by_ttl:{"30m":rate,"12h":rate}` |
| `cache_input_v1` | The same disjoint input/read/write fields, without output counters | Input/read/write rates; output is not charged by this endpoint-specific adapter |

Text input includes cache-read tokens; reasoning is a subset of output, so neither is added twice. Optional `cache_write_input_tokens` requires `cache_write_accounting:"input_subset"` or `"separate"`. In subset mode subtract writes from ordinary input before applying `cache_write_input_per_million`; separate mode adds their independent charge. This distinction must come from provider evidence. Every adapter can include explicit `units` and corresponding rates for tools, storage or other charges. Unknown units/native modality fields remain unpriced. Keep original native usage alongside the normalized record.

Legacy `models:{model:{input_per_million,cached_input_per_million,output_per_million}}` cards still price the original normalized text records. They are labelled `legacy_model_only`. Supplying an explicit interface/tier/region requires the new complete scope; do not silently mix endpoint prices. Missing usage/rate stays null. `external_charges_usd` contains already reconciled separate charges, not duplicates of normalized units. Mark `all_billable_usage_included:true` only when all relevant charges, including retries and judges, are accounted for.

## OpenAI cache and Decisions normalization

Checked 2026-10-30: the [Decisions guide](https://developers.openai.com/api/docs/guides/decisions#pricing-and-availability) still defines input-only pricing, but now includes discounted cache reads and charged cache writes. Use the cache-aware `cache_input_v1` adapter for current Decisions usage. Historical `input_only_v1` records remain supported; that adapter deliberately refuses cache counters and must not be used to erase them.

`scripts/openai_billing.py normalize native-envelope.json` reads an object containing `response`, exact `billing_identity`, and optional explicit `all_billable_usage_included`. It preserves native usage, validates the served model and any served tier, and emits an event consumable by `price_usage.py`. It never tokenizes a prompt, fetches rates, or calls an API. A failed normalization exits 2 with null cost; retain it as an unknown-cost event.

For Responses, the [official caching guide](https://developers.openai.com/api/docs/guides/prompt-caching#monitor-cache-performance) binds `usage.input_tokens_details.cache_write_tokens_details.ttl_30m_tokens` and `ttl_12h_tokens` to non-overlapping write counters. Both must be present and sum to `cache_write_tokens`; reads plus writes cannot exceed `input_tokens`. The normalized identity adds `cache_policy:"openai_30m_12h_v1"`. The endpoint's rate card must declare total write rates separately by TTL. At the documented ordinary-input rate of 1, the example write rates are 1.25 for 30m and 2.5 for 12h; these are total rates, not additive surcharges. Use actual model/tier/region/context-band rates, including the actual cached-input rate.

For Decisions, the [current API reference](https://developers.openai.com/api/reference/resources/decisions/methods/create) supports only request-level 30m TTL and reports aggregate `cache_write_tokens`. Its normalizer assigns those writes to 30m and adds `cache_policy:"openai_decisions_30m_v1"`; it does not borrow Responses' 12h or breakpoint TTL override schema. Native output/reasoning counters are validated and retained but omitted from the input-only normalized charge. Missing counters, unknown modalities and contradictory sums are rejected rather than assumed zero. Check current [pricing](https://developers.openai.com/api/docs/pricing) before constructing a real card. The bundled rates remain synthetic.

For example, this normalized Responses event requires 1,000 ordinary input tokens, 4,000 reads, 3,000 30m writes and 4,000 12h writes:

```json
{
  "input_tokens": 12000,
  "cached_input_tokens": 4000,
  "cache_write_input_tokens_by_ttl": {"30m": 3000, "12h": 4000},
  "output_tokens": 100
}
```

At synthetic per-million rates input=1, read=0.1, 30m write=1.25, 12h write=2.5 and output=2, the input costs 0.01515 and the output costs 0.0002. Each input token is counted once. `units_v1` remains available for explicitly normalized additional charges; do not duplicate TTL write charges as extra units.

`scripts/openai_billing.py plan-cache scenario.json` is an offline scenario helper. Supply `input_tokens`, up to four selected `breakpoints:[{end_tokens,ttl}]`, and `available_prefixes` in the same form. Available prefixes must already be known to match an eligible lookup boundary and have valid coverage. The helper applies the longest selected TTL covering each token: a later 12h write covers the earlier prefix, a 30m-to-12h upgrade charges a full new write without credit, and valid 12h coverage can be read by a 30m request. It does not predict routing, expiry, cache hits or latency, and its output must never replace measured native usage. No selected breakpoint in explicit-only mode means no cache use.

## Decisions GA request preflight

`scripts/decisions_contract.py request.json` checks a documented local subset of the native request: user/developer/system messages, 1–400 predicate/choice/score questions, JSON evidence, shared images, and question-specific images. `input_json` belongs in user content; keys inside its data remain data. Image URLs may be inline data or HTTP(S), and are not fetched by the preflight. Question instructions contain content parts directly, without a message wrapper or cache breakpoint. Score levels require labels; choice values retain string/boolean types.

This preflight leaves the caller's model unchanged and does not certify model availability, all image limits or complete SDK/server validation. Tool-history and other unsupported surfaces fail explicitly and should be validated using the installed SDK's full current schema. Decisions TTL remains 30m. Both the [guide](https://developers.openai.com/api/docs/guides/decisions) and the exact API reference should be checked before enabling additional surfaces. A well-formed request is not a calibrated grader or authorization to execute its selected action.

Cache diagnostics belong to the engineering skill; a hit rate alone is not a cost saving.

## Calibrate the auditor

Label 1 means the declared event. For issue detection it may mean a genuine issue; for quality it may mean a satisfactory answer. Define this before interpreting FP/FN. Include both adjudicated positive and clean negative controls. Finding more issues can reward an auditor for inventing findings, prompting the judge or exploiting a narrow rubric; use independently reviewed clean cases and material near misses to detect that behavior.

Each identified calibration row carries `evaluation_identity:{dataset_version,grader_version,rubric_sha256,judge_model}`. Mixed or incomplete identities are rejected. Legacy rows remain descriptive and unverified. Repetitions cannot change human adjudication; disagreements must be resolved before freezing a revised dataset. The helper reports class denominators, FPR/FNR, precision, recall, order bias and repeat instability. An absent class/check is **unmeasured**, never a zero error rate. Its `ready_for_review` flag still does not constitute human approval or validity.

`--population-prevalence P` calculates a scenario precision from measured sensitivity/FPR and the supplied deployment base rate. It is not an inferred traffic statistic or a confidence bound. At rare prevalence even a small FPR can dominate true detections; preserve this alongside sample precision.

`--baseline prior-labels.jsonl` compares two judges on identical `(id,rep,human)` sets with the same dataset/rubric. It reports paired improvements/regressions and both label hashes; missing pairs are rejected. Results are descriptive, not a significance claim. `--drift-reference prior-cohort.jsonl --max-fpr-increase 0.02` instead keeps the same judge/rubric across cohorts and checks a predeclared FPR increase. Missing negative controls yields unmeasured drift. Explain population changes and independent sampling before drawing broader conclusions.
