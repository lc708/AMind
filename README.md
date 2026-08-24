# AMind

## Think with the Anthropic lens.

**AMind is an evidence-grounded Agent Skill that turns Anthropic's public reasoning into useful, source-traceable judgment for your own AI decisions.** It does not impersonate Anthropic.

Generic persona prompts blur facts and inference. AMind makes the distance visible—then still gives you a recommendation.

<p align="center">
  <a href="https://github.com/lc708/AMind/stargazers"><img src="https://img.shields.io/github/stars/lc708/AMind?style=flat-square&color=D97757" alt="GitHub stars"></a>
  <a href="skills/amind"><img src="https://img.shields.io/badge/Agent%20Skill-AMind-D97757?style=flat-square" alt="AMind Agent Skill"></a>
  <a href="skills/amind/data/manifest.json"><img src="https://img.shields.io/badge/evidence-offline-71C4A5?style=flat-square" alt="Offline evidence kernel"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-8D96A5?style=flat-square" alt="Apache License 2.0"></a>
</p>

<p align="center">
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="#start-in-60-seconds">Install</a> ·
  <a href="#what-an-answer-looks-like">See an answer</a> ·
  <a href="release/amind-v1/reports/synthesis.zh-CN.md">Read the synthesis</a> ·
  <a href="release/amind-v1/data/representative-evidence-review.jsonl">Inspect reviewed evidence</a>
</p>

![AMind turns a question into a recommendation with visible evidence distance and traceable sources](assets/amind-hero.svg)

## Start in 60 seconds

Paste this into **Codex chat**—not a terminal:

```text
$skill-installer install https://github.com/lc708/AMind/tree/main/skills/amind
```

Restart Codex once, then ask a real question:

```text
Use $amind to pressure-test our autonomous-agent rollout.
Give me a recommendation, failure conditions, and sources.
```

That is the whole setup. The bundled evidence tools use only the Python standard library, make no network requests, and require no extra API key.

> [!TIP]
> AMind can invoke automatically when a question calls for an Anthropic-informed perspective, but naming `$amind` is the most predictable first test.

## What an answer looks like

Ask whether an autonomous agent is ready for broader deployment and AMind answers like this:

> **Recommendation**
>
> Stage the deployment. Expand autonomy only after the system passes task-realistic evaluations and independent monitoring; keep a reversible fallback until the failure modes are observable.
>
> **[Strong framework inference]** Across Anthropic's public materials, uncertainty is repeatedly converted into measurement, staged commitment, and multiple independent defenses—not blind acceleration or indefinite paralysis.
>
> **[Exploratory extrapolation]** For your rollout, that implies capability-based promotion gates and a kill path owned outside the shipping team.
>
> **What could change the answer**
>
> Strong evidence that the agent cannot take irreversible actions, or that monitoring reliably catches policy violations, would justify faster expansion.
>
> **Source example**
>
> *Auditing language models for hidden objectives* · 2025-03-13 · [source](https://www.anthropic.com/research/auditing-hidden-objectives) · `nuwa1-claim-04ed2efdb6c2574083bf375d`

Every material conclusion carries one of three evidence-distance labels:

| Label | What it means |
|---|---|
| **[Public position]** | A cited public source supports the conclusion directly. |
| **[Strong framework inference]** | Repeated, source-linked patterns support the reasoning. |
| **[Exploratory extrapolation]** | AMind applies those patterns to a new case beyond exact precedent. |

The operating rule is simple: **bold in advice, explicit about provenance**.

## One Skill, six jobs

```text
Think:    How would the Anthropic lens frame our autonomous-agent rollout?
Advise:   Should we open-source this model? Give a recommendation and stop conditions.
Critique: Pressure-test this AI safety policy. What would it miss?
Explain:  How does Anthropic's public reasoning treat scaling uncertainty?
Compare:  Compare the institutional voice with Dario Amodei and Jack Clark on governance.
Trace:    Show the evidence behind this conclusion, including quotes and claim IDs.
```

For a novel case, AMind still gives advice. It simply tells you how far that advice travels beyond direct public precedent.

## Why not just use a persona prompt?

| | Persona prompt | Generic search / RAG | AMind |
|---|---|---|---|
| Gives a direct recommendation | Yes | Depends on your setup | **Yes** |
| Separates public fact from inference | Rarely | You build it | **Built in** |
| Preserves institution, person, and version boundaries | No | You build it | **Built in** |
| Retains tensions and counterevidence | Rarely | You build it | **Built in** |
| Traces conclusions to exact quotes and stable IDs | No | Possible | **Built in** |
| Works from a bounded, inspectable corpus | No | Depends | **Yes** |
| Best for live, up-to-the-minute facts | No | **Yes, with live sources** | No—AMind v1 is frozen |

AMind is deliberately bounded. It trades the false freshness of an untraceable persona for a corpus you can inspect, challenge, and reproduce.

## Pick your path

| If you want to… | Start here |
|---|---|
| Think through a real decision | [Install the Skill](#start-in-60-seconds) |
| Understand the reconstructed framework | [Read the synthesis](release/amind-v1/reports/synthesis.zh-CN.md) |
| Build lightweight RAG or an evaluation | [Use the 54 reviewed evidence rows](release/amind-v1/data/representative-evidence-review.jsonl) |
| Search the full corpus | [Open the AMind v1 release](release/amind-v1) |
| Audit the construction and limits | [Read the evaluation](release/amind-v1/reports/evaluation.zh-CN.md) and [release audit](release/amind-v1/release-audit.json) |

## How it works

AMind uses an internal distillation method called **Nuwa**:

```text
bounded public corpus
  → source-linked atomic claims
  → voice and version boundaries
  → recurring mechanisms, counterevidence, and tensions
  → stress-tested advice for a new situation
```

The method keeps institutional positions separate from named people, preserves explicit revisions, retains counterevidence, and refuses to turn research questions into settled answers.

The public product is **AMind**. Nuwa is only the construction methodology.

## Evidence you can inspect

The compact Skill is the reasoning interface. The full release is the audit and research layer.

| Layer | What ships |
|---|---:|
| Authoritative candidates | 1,804 |
| Deduplicated analysis units | 1,351 |
| Source-bound evidence passages | 13,436 |
| Atomic claims with exact quotes and source identity | 52,225 |
| Human-reviewed representative evidence rows | 54 |
| Recurring themes | 9 |
| Bounded voice profiles | 5 |
| Preserved tensions | 5 |

The human-review claim is intentionally narrow: all 54 representative kernel rows were reviewed in passage context. The full 52,225-claim release is structured and audited, but not individually human-reviewed.

### Inspect the compact Skill

```bash
python3 -B skills/amind/scripts/query.py summary
python3 -B skills/amind/scripts/query.py search "alignment faking" --limit 5
python3 -B skills/amind/scripts/query.py tensions
python3 -B skills/amind/scripts/verify.py
```

### Search the full release

```bash
git clone https://github.com/lc708/AMind.git
cd AMind

python3 -B release/amind-v1/amind.py summary
python3 -B release/amind-v1/amind.py search "model welfare" --limit 5
python3 -B release/amind-v1/amind.py show nuwa1-claim-f169332e5fa3d349672a254d
```

For lightweight RAG, start with [`representative-evidence-review.jsonl`](release/amind-v1/data/representative-evidence-review.jsonl). For exhaustive retrieval, stream [`atomic-claims.jsonl.gz`](release/amind-v1/data/atomic-claims.jsonl.gz) and join it to [`analysis-units.jsonl.gz`](release/amind-v1/data/analysis-units.jsonl.gz).

## Works beyond Codex

The installable package at [`skills/amind`](skills/amind) is a self-contained Agent Skill. If your client supports the Agent Skills folder format, copy or install that folder into its skills directory and invoke `amind`. Client directory locations and invocation syntax vary; the evidence tools themselves require only Python 3.

## Verify or develop

```bash
python3 -B scripts/build_amind_skill.py --check
python3 -B scripts/test_amind_skill.py
python3 -B scripts/verify_amind_v1_release.py
```

The compact kernel is deterministically generated from the frozen AMind v1 release. Every packaged data artifact carries a SHA-256 digest and row count.

## Boundaries

- AMind reconstructs public reasoning; it has no access to Anthropic's private deliberations.
- It never speaks in Anthropic's first person or invents an unpublished decision.
- AMind v1 is a frozen research release, not a live source of current Anthropic policy.
- Theme frequency measures corpus coverage, not organizational consensus or personal influence.
- Institutional material is not automatically attributed to an individual, and individual writing is not automatically institutional policy.
- The compact Skill is representative, not exhaustive. Use the full release for completeness-sensitive research.
- AMind is an independent public-research project and is not affiliated with or endorsed by Anthropic.

<details>
<summary><strong>Frequently asked questions</strong></summary>

### Is AMind official Anthropic software?

No. It is an independent open-source project built only from public material.

### Is AMind a model?

No. It is an Agent Skill, evidence kernel, retrieval policy, and auditable research release that works with a capable host model.

### Does it claim to reproduce private reasoning?

No. It reconstructs recurring patterns in public evidence and labels every step beyond that evidence.

### Can I use the dataset without installing the Skill?

Yes. The compact and full evidence tools are standalone, use the Python standard library, and can be used directly in research or RAG workflows.

</details>

## Contribute, cite, or report a problem

- Found a source, attribution, or version issue? Open an [evidence correction](https://github.com/lc708/AMind/issues/new?template=evidence_correction.yml).
- Have a useful question or integration idea? Read [CONTRIBUTING.md](CONTRIBUTING.md) and open a [feature request](https://github.com/lc708/AMind/issues/new?template=feature_request.yml).
- Using AMind in research? See [`CITATION.cff`](CITATION.cff).
- Found a security issue? Follow [`SECURITY.md`](SECURITY.md) instead of opening a public issue.

## License

AMind's software, original documentation, build logic, and Skill instructions are licensed under the [Apache License 2.0](LICENSE). Public-source quotations and third-party factual metadata remain with their respective authors and publishers and are not relicensed; see [NOTICE](NOTICE) for the evidence and trademark boundary.

If AMind gives you a useful new lens, **[star the repository](https://github.com/lc708/AMind)** and share the question where visible evidence distance changed your answer.
