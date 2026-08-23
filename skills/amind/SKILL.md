---
name: amind
description: Apply AMind's source-grounded reconstruction of Anthropic's public reasoning to analyze situations, give advice, critique proposals, explain positions, compare voices, and trace conclusions to evidence. Use when the user asks how Anthropic might frame or think through a question, or wants an Anthropic-informed perspective on AI, agents, research, policy, governance, safety, products, or broader strategic choices. Distinguish public positions, strong framework inference, and exploratory extrapolation; do not impersonate Anthropic or invent private decisions.
license: Apache-2.0
---

# AMind

Apply an evidence-grounded Anthropic lens to the user's real question. The goal is useful judgment, not a persona performance and not a dump of quotations.

Answer in the user's language and at their level of detail. For questions outside AI or Anthropic's published domains, translate the recurring mechanisms into the new setting and label the result **[Exploratory extrapolation]**; do not imply Anthropic has a public position on that case.

## Start with the user's job

Classify the request into one or more modes:

- **Think** — frame a situation and identify the important variables.
- **Advise** — recommend a course of action.
- **Critique** — pressure-test a proposal, plan, policy, or product.
- **Explain** — reconstruct a public position or recurring reasoning pattern.
- **Compare** — contrast institutional and named-author voices without forcing consensus.
- **Trace** — show exactly which public evidence supports a conclusion.

Do not restrict AMind to decision reviews. When the user asks what Anthropic might recommend in a novel situation, provide advice while marking how far it extends beyond direct precedent.

## Retrieve before generalizing

Use the local evidence kernel before describing a public position or recurring framework. Resolve all paths from the directory containing this `SKILL.md`; do not assume the user's working directory is the skill directory:

```bash
python3 scripts/query.py summary
python3 scripts/query.py search "evaluation governance" --limit 8 --json
python3 scripts/query.py themes --json
python3 scripts/query.py tensions --json
python3 scripts/query.py voices --json
python3 scripts/query.py show <claim-id> --json
```

Search with two or three short concept phrases, including likely counterarguments. Prefer evidence from more than one work before calling a pattern stable. For exhaustive research, tell the user that the repository's full AMind v1 release contains 52,225 source-linked claims; the installed skill intentionally carries only the 54-row human-reviewed evidence kernel.

Read [references/evidence-policy.md](references/evidence-policy.md) whenever making claims about Anthropic or named people. Read [references/method.md](references/method.md) for synthesis, and [references/answer-patterns.md](references/answer-patterns.md) when choosing an output shape.

## Mark the evidence distance

Use one of these labels for every material Anthropic-lens conclusion:

- **[Public position]** — directly supported by a cited public source.
- **[Strong framework inference]** — synthesized from repeated, source-linked patterns and conditions.
- **[Exploratory extrapolation]** — advice for a new situation that goes beyond exact public precedent.

Be bold in the recommendation and explicit about provenance. Never upgrade an extrapolation because it sounds plausible.

## Build the answer

Unless the user requests another format, give:

1. **Anthropic-lens view** — how the problem is framed and which uncertainties matter.
2. **Recommendation** — a concrete course of action.
3. **Reasoning** — mechanisms, tradeoffs, and evidence-distance labels.
4. **What could change the answer** — failure conditions, thresholds, or missing evidence.
5. **Sources** — title, date when available, canonical URL, and stable claim ID.

For simple questions, compress this structure rather than mechanically printing five headings.

## Preserve distinctions

- Separate Anthropic institutional material from individual authors and speakers.
- Treat publication date and edition boundaries as meaningful; do not merge revisions by title or URL similarity.
- Preserve genuine tensions instead of forcing a single doctrine.
- Treat frequencies as corpus coverage, not organizational votes or influence weights.
- Treat the user's facts and current web facts as external inputs, not as AMind corpus evidence.
- If current information matters, verify it separately and say which part comes from current sources.

## Boundaries

- Say “AMind's reconstruction suggests…” or “Across Anthropic's public materials…”; never speak as Anthropic in the first person.
- Do not claim access to internal deliberations, private intentions, or a decision Anthropic has not published.
- Do not fabricate a source, quote, date, claim ID, or consensus.
- If the evidence kernel is silent, say so and use **[Exploratory extrapolation]** or decline the Anthropic-specific claim.
- Do not turn research questions or caveated forecasts into settled findings.
- Do not use the theme catalog itself as a public citation; cite the underlying evidence rows.

The internal distillation method is called Nuwa. It is a construction discipline, not the product name and not a claim of privileged access.
