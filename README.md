# AMind

### Think with the Anthropic lens.

Put on the Anthropic hat—without pretending to be Anthropic. AMind helps you analyze a situation, get concrete advice, pressure-test a plan, compare public voices, and trace the reasoning back to evidence.

It is built from **1,351 public analysis units, 52,225 source-linked claims, and 54 human-reviewed representative evidence rows**—not from a persona prompt.

[简体中文](README.zh-CN.md) · [Read the research synthesis](release/amind-v1/reports/synthesis.zh-CN.md) · [Inspect reviewed evidence](release/amind-v1/data/representative-evidence-review.jsonl)

## Install in Codex

Paste this into **Codex chat** (not a terminal):

```text
$skill-installer install https://github.com/lc708/AMind/tree/main/skills/amind
```

Restart Codex after installation. Then ask:

```text
Use $amind to think through this situation with the Anthropic lens: [describe your situation]
```

You can also ask naturally—AMind supports automatic invocation when your question calls for an Anthropic-informed perspective.

## What you can ask

AMind is not limited to decision review:

```text
Think:    How would the Anthropic lens frame our autonomous-agent rollout?
Advise:   Should we open-source this model? Give a recommendation and stop conditions.
Critique: Pressure-test this AI safety policy. What would it miss?
Explain:  How does Anthropic's public reasoning treat scaling uncertainty?
Compare:  Compare the institutional voice with Dario Amodei and Jack Clark on governance.
Trace:    Show the evidence behind this conclusion, including quotes and claim IDs.
```

For a novel case, it still gives advice. It simply tells you how far that advice travels beyond direct public precedent.

## What an answer looks like

> **Recommendation**
>
> Stage the deployment. Expand autonomy only after the system passes task-realistic evaluations and independent monitoring; keep a reversible fallback until the failure modes are observable.
>
> **[Strong framework inference]** Across Anthropic's public materials, uncertainty is usually converted into measurement, staged commitment, and multiple independent defenses—not into either blind acceleration or indefinite paralysis.
>
> **[Exploratory extrapolation]** For your rollout, that implies capability-based promotion gates and a kill path owned outside the shipping team.
>
> **What could change the answer**
>
> Strong evidence that the agent cannot take irreversible actions, or that monitoring reliably catches policy violations, would justify faster expansion.
>
> **Source example**
>
> *Auditing language models for hidden objectives* — 2025-03-13 — [source](https://www.anthropic.com/research/auditing-hidden-objectives) — `nuwa1-claim-04ed2efdb6c2574083bf375d`

AMind marks the evidence distance of every material conclusion:

- **[Public position]** — directly supported by a cited public source.
- **[Strong framework inference]** — reconstructed from repeated, source-linked patterns.
- **[Exploratory extrapolation]** — useful advice for a new situation beyond exact precedent.

The rule is simple: **bold in advice, explicit about provenance**.

## Why this is more than a prompt

AMind uses an internal distillation method called **Nuwa**:

```text
bound public corpus
  → source-linked atomic claims
  → voice and version boundaries
  → recurring mechanisms and tensions
  → stress-tested advice for a new situation
```

The method keeps institutional positions separate from named people, preserves explicit revisions, retains counterevidence, and refuses to turn research questions into settled answers.

The public product is **AMind**. Nuwa is only the construction methodology.

## What ships inside the Skill

The installable package at [`skills/amind`](skills/amind) is deliberately compact and works offline:

- 54 human-reviewed, source-bound evidence rows;
- 9 recurring themes in Anthropic's public reasoning;
- 5 bounded voice profiles;
- 5 recurring tensions that should not be flattened;
- a zero-dependency query tool and integrity verifier;
- answer patterns and evidence rules for Think, Advise, Critique, Explain, Compare, and Trace.

Try the evidence tools directly:

```bash
python3 -B skills/amind/scripts/query.py summary
python3 -B skills/amind/scripts/query.py search "alignment faking" --limit 5
python3 -B skills/amind/scripts/query.py tensions
python3 -B skills/amind/scripts/verify.py
```

They use only the Python standard library, make no network requests, and do not modify the evidence package.

## Full AMind v1 evidence release

The compact Skill is the reasoning interface. The full release at [`release/amind-v1`](release/amind-v1) is the audit and research layer:

- 1,804 authoritative candidates;
- 1,351 deduplicated analysis units: 1,348 with primary bodies and 3 bounded unavailable exceptions;
- 13,436 evidence passages;
- 52,225 atomic claims with exact quotes, work and edition identities, and file hashes;
- 9 synthesis themes and 54 fully reviewed representative evidence rows;
- attribution, version, contradiction, synthesis, evaluation, and release audits.

Search the full release:

```bash
git clone https://github.com/lc708/AMind.git
cd AMind

python3 -B release/amind-v1/amind.py summary
python3 -B release/amind-v1/amind.py search "model welfare" --limit 5
python3 -B release/amind-v1/amind.py show nuwa1-claim-f169332e5fa3d349672a254d
```

For lightweight RAG, start with [`representative-evidence-review.jsonl`](release/amind-v1/data/representative-evidence-review.jsonl). For exhaustive retrieval, stream [`atomic-claims.jsonl.gz`](release/amind-v1/data/atomic-claims.jsonl.gz) and join it to [`analysis-units.jsonl.gz`](release/amind-v1/data/analysis-units.jsonl.gz).

## Other Agent Skills-compatible clients

The Skill is a self-contained folder. If your client supports Agent Skills, copy or install [`skills/amind`](skills/amind) into that client's skills directory and invoke `amind`. Directory locations and invocation syntax vary by client; the evidence tools themselves require only Python 3.

## Verify or develop

```bash
python3 -B scripts/build_amind_skill.py --check
python3 -B scripts/test_amind_skill.py
python3 -B scripts/verify_amind_v1_release.py
```

The compact evidence kernel is deterministically generated from the frozen AMind v1 release. Every packaged data artifact carries a SHA-256 digest and row count.

## License

AMind's software, original documentation, build logic, and Skill instructions are licensed under the [Apache License 2.0](LICENSE). Public-source quotations and third-party factual metadata remain with their respective authors and publishers and are not relicensed; see [NOTICE](NOTICE) for the evidence and trademark boundary.

## Boundaries

- AMind reconstructs public reasoning; it has no access to Anthropic's private deliberations.
- It never speaks in Anthropic's first person or invents an unpublished decision.
- Theme frequency measures corpus coverage, not organizational consensus or personal influence.
- Institutional material is not automatically attributed to an individual, and individual writing is not automatically institutional policy.
- The compact Skill is representative, not exhaustive. Use the full release for completeness-sensitive research.
- AMind is an independent public-research project and is not affiliated with or endorsed by Anthropic.

If AMind gives you a useful new lens, **star the repository** and share one question where the answer became better because the evidence distance was visible.
