# One-off source update: 2026-09-08

The local index now combines frozen v1 with 68 added analysis units and 12,040 source-bound, machine-checked claims. Source requests ran from **2026-09-08 00:50:32 to 01:03:42 Asia/Singapore**. This is an observation cutoff, not a claim to cover the rest of that day. There is no recurring update.

There are 43 newly indexed documents, 7 revised document captures, and 18 separately preserved system-prompt versions. Two of the seven revisions—the Opus 5 system card and Transparency Hub—had old captures in the local vault but no corresponding v1 analysis unit. Five revisions link directly to an earlier indexed unit. System-prompt artifacts produce no belief claims.

The full index contains **64,265 claims, 1,419 analysis units, and 14,715 passages**. The 54 human-reviewed gold rows, nine original theme theses, five voice profiles, and five original tensions remain the v1 calibration layer. Theme coverage counts include the increment. Twelve selected new claims received additional AI passage-context review; none became human-reviewed gold.

## Qualified findings to incorporate

- **Automated alignment research works on some well-characterized tasks.** The AAR work tests ten specified failure types and held-out generalization. Its comparison with 28 researchers gives each up to eight hours. This does not establish automation of open-ended alignment research. Claims `nuwa1-claim-26142aa4470bceda2a45b746` and `nuwa1-claim-0055c290658a8deaa21be3e0`. [Source](https://alignment.anthropic.com/2026/automated-alignment-researchers/).
- **Research judgment remains a separate limitation.** TASTE's standard setup gives Fable 5 60% versus estimated human agreement of 77% on 92 proposal pairs. Those percentages measure agreement with researcher preferences, not objective research correctness. Claim `nuwa1-claim-be8d186c11974572af9dade7`. [Source](https://alignment.anthropic.com/2026/taste/).
- **Oversight tools need task-specific validation.** Fine-tuned lie detectors generalize poorly in the reported out-of-distribution tests; CHIVE finds no uplift from three specified activation-reading tools on counterfactual outcome prediction. Neither finding establishes that all lie detection or interpretability is ineffective. Claims `nuwa1-claim-06f1995e29319dcf771700ae` and `nuwa1-claim-4e01ad5e2cc88d03e00d6e62`. [Lie detectors](https://alignment.anthropic.com/2026/lie-detectors/), [CHIVE](https://alignment.anthropic.com/2026/chive/).
- **Newer models show mixed alignment results.** The Fable/Mythos 5.1 card reports a slight regression relative to Opus 5 on its automated behavioral audit, alongside improvements on other dimensions. Preserve the model, benchmark, configuration, and comparison. Claim `nuwa1-claim-c07946b5b8c10fa0c037c2be`. [System card](https://anthropic.com/claude-fable-5-1-mythos-5-1-system-card).
- **Reward-seeker results concern a deliberately modified model.** The paper's simulated evaluations do not show that deployed Claude has the same objectives. The authors also report no observed self-preservation, research sabotage, or beyond-episode reward seeking in these tests. Claim `nuwa1-claim-d1c20353d5f6055c05f58c6d`. [Source](https://alignment.anthropic.com/2026/reward-seeker/).
- **Opus 5 evaluation results were explicitly revised.** The August 19 changelog adds prompt-injection bounty results, fixes a Cowork harness mismatch, and removes unsupported thinking-disabled Cowork results. Do not mix the old and new comparison tables. Claims `nuwa1-claim-11b5c248c375720ccbd7e01f`, `nuwa1-claim-97e9e462ffe3dcdab315a7bd`, and `nuwa1-claim-5b350695da0f57d449a175ee`. [System card](https://anthropic.com/claude-opus-5-system-card).

These are bounded additions to the reconstruction. They do not automatically replace the original theme theses or establish a single organizational consensus.

## Decision implications

Apply these refinements only to the relevant decision. Cite the underlying claims above. Keep the bounded source result labeled **[Public position]**. Use **[Strong framework inference]** for an inference corroborated across works, and **[Exploratory extrapolation]** for choices beyond the published precedent.

| Decision | How the evidence changes the recommendation |
|---|---|
| Automating research | Evaluate mitigation of a defined failure, selection of promising research, and open-ended agenda setting separately. AAR's bounded successes and TASTE's preference-agreement gap concern different tasks. Tie the proposed level of autonomy to the demonstrated task and evaluation budget; define what evidence would justify expanding it. |
| Adopting a lie detector or interpretability tool | Specify the behavior to detect or predict and the deployment distribution. Compare against an appropriate prompted or transcript-only baseline, then test transfer to relevant unseen cases. A failure on CHIVE or the lie-detector study limits that tested method and setting; it does not establish universal uselessness. |
| Choosing a newer model | Compare the behaviors material to the user's use case, including any regressions, alongside capability gains. A mixed system-card result can justify a narrower rollout or a targeted evaluation; a model's generation name alone does not establish the tradeoff. |
| Comparing published evaluation scores | Match the document edition, model, product surface, harness, thinking configuration, and safeguards for the relevant evaluation. When the source corrects a comparison or removes an unsupported configuration, use the corrected results and explain the affected scope; preserve old results as historical evidence. |
| Interpreting a model-organism experiment | State how the model was modified, what behavior was observed, and what was not found in the tested setting. Keep conclusions about deliberately trained models separate from claims about deployed models; absence in those tests does not establish absence in every setting. |

Use a reviewed kernel row when it supports the same inference, and inspect current full-index passages when the new evidence changes the answer. Keep the source result, the inference, and the user's proposed action distinguishable.

## Retrieval and coverage

Use `--current` to exclude earlier indexed editions for which this batch records a later observed revision. Use `show --passage` to retain access to historical evidence. Publication dates, observation times, and revision relations are separate fields; an unknown publication date stays unknown.

Routine PDF and newsletter extraction is conservatively marked as reported evidence because these documents mix author assertions, model outputs, and third-party claims. Use `--include-reported` to inspect these candidates, and `--include-simulated` for bounded experimental model behavior. Read the conditions and passage before interpreting the result. The limited PDF findings individually checked in context also appear in direct-source search.

Discovery covered 86 configured sources and 4,942 URLs, with 179 new URLs against prior inventories. There were 305 successful body captures, four HTTP 404s, and one metadata-only result. For 1,148 dated URLs, the source index reported no later modification; their bodies were not re-fetched. Unchanged index dates are not a body-hash guarantee.

Nine discovery entries failed: six Ethan Perez site/feed/sitemap entries, Jared Kaplan's JHU publications entry, Dario's archive URL, and Anthropic's webinars URL. Alternate Dario and Anthropic entry points worked, but those failures remain recorded. Eighteen new spoken/event references were retained as discovery metadata; no new verified interview transcript was added. Historical archives and the entire web were not exhaustively re-enumerated.
