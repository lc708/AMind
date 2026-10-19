# Accounting and judge calibration

These helpers run offline. They consume explicit normalized records; they do not contact providers, infer SDK field mappings or certify a complete invoice. The bundled accounting demo is synthetic and contains deliberately different rates for the same mock model on two endpoints.

```bash
python3 "$SKILL_ROOT/scripts/price_usage.py" --events "$SKILL_ROOT/assets/accounting-demo/events.jsonl" --rates "$SKILL_ROOT/assets/accounting-demo/rates.json"
python3 "$SKILL_ROOT/scripts/calibrate_grader.py" "$SKILL_ROOT/assets/accounting-demo/labels.jsonl" --population-prevalence 0.01
```

## Exact price scope

A dated card has `version`, `effective_date`, `source` and `rates:[...]`. Each rate declares `billing_identity:{provider,interface,model,service_tier,region}`, optional `context_band`, and `usage_adapter`. Every scope value must be explicit; `global` is a declared region, not an inferred default. The event repeats the exact identity and adapter. An unmatched endpoint, tier, region or context band returns unknown even when the model matches. Bake any documented regional/context multiplier into that scoped rate; the helper does not invent multipliers. Duplicate scopes are rejected.

If a record also repeats flat `provider/interface/model/service_tier/region/context_band` fields, they must agree with its billing identity. Repeated flat/detail cache and reasoning counters must also agree; contradictory normalization is rejected before pricing.

| Adapter | Normalized usage | Rates |
|---|---|---|
| `text_tokens_v1` | `input_tokens`, explicit `cached_input_tokens`, `output_tokens`; optional `reasoning_tokens` | `input_per_million`, `cached_input_per_million`, `output_per_million` |
| `input_only_v1` | `input_tokens`; output/cache counters are rejected | `input_per_million` |
| `units_v1` | `units:{unit_name:quantity}` only | `unit_rates:{unit_name:{usd,per}}` |

Text input includes cache-read tokens; reasoning is a subset of output, so neither is added twice. Optional `cache_write_input_tokens` requires `cache_write_accounting:"input_subset"` or `"separate"`. In subset mode subtract writes from ordinary input before applying `cache_write_input_per_million`; separate mode adds their independent charge. This distinction must come from provider evidence. Every adapter can include explicit `units` and corresponding rates for tools, storage or other charges. Unknown units/native modality fields remain unpriced. Keep original native usage alongside the normalized record.

Legacy `models:{model:{input_per_million,cached_input_per_million,output_per_million}}` cards still price the original normalized text records. They are labelled `legacy_model_only`. Supplying an explicit interface/tier/region requires the new complete scope; do not silently mix endpoint prices. Missing usage/rate stays null. `external_charges_usd` contains already reconciled separate charges, not duplicates of normalized units. Mark `all_billable_usage_included:true` only when all relevant charges, including retries and judges, are accounted for.

Checked 2026-10-18: the [Decisions guide](https://developers.openai.com/api/docs/guides/decisions#pricing-and-availability) defines input-only pricing for that endpoint and distinguishes it from other calls using the same model. Normalize Decisions through an exact endpoint-scoped `input_only_v1` rate. Current [pricing](https://developers.openai.com/api/docs/pricing) and [cache diagnostics](https://developers.openai.com/api/docs/guides/prompt-caching/diagnostics) must be checked for the actual provider/configuration; the synthetic fixture is not a live price card. Cache diagnostics belong to the engineering skill; a hit rate alone is not a cost saving.

## Calibrate the auditor

Label 1 means the declared event. For issue detection it may mean a genuine issue; for quality it may mean a satisfactory answer. Define this before interpreting FP/FN. Include both adjudicated positive and clean negative controls. Finding more issues can reward an auditor for inventing findings, prompting the judge or exploiting a narrow rubric; use independently reviewed clean cases and material near misses to detect that behavior.

Each identified calibration row carries `evaluation_identity:{dataset_version,grader_version,rubric_sha256,judge_model}`. Mixed or incomplete identities are rejected. Legacy rows remain descriptive and unverified. Repetitions cannot change human adjudication; disagreements must be resolved before freezing a revised dataset. The helper reports class denominators, FPR/FNR, precision, recall, order bias and repeat instability. An absent class/check is **unmeasured**, never a zero error rate. Its `ready_for_review` flag still does not constitute human approval or validity.

`--population-prevalence P` calculates a scenario precision from measured sensitivity/FPR and the supplied deployment base rate. It is not an inferred traffic statistic or a confidence bound. At rare prevalence even a small FPR can dominate true detections; preserve this alongside sample precision.

`--baseline prior-labels.jsonl` compares two judges on identical `(id,rep,human)` sets with the same dataset/rubric. It reports paired improvements/regressions and both label hashes; missing pairs are rejected. Results are descriptive, not a significance claim. `--drift-reference prior-cohort.jsonl --max-fpr-increase 0.02` instead keeps the same judge/rubric across cohorts and checks a predeclared FPR increase. Missing negative controls yields unmeasured drift. Explain population changes and independent sampling before drawing broader conclusions.
