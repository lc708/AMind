# AMind

## Think with the Anthropic lens.

**AMind is an evidence-grounded Agent Skill that turns Anthropic's public reasoning into useful, source-traceable judgment for your own AI decisions.** It does not impersonate Anthropic.

Generic persona prompts blur facts and inference. AMind makes the distance visible—then still gives you a recommendation.

<p align="center">
  <a href="https://github.com/lc708/AMind/stargazers"><img src="https://img.shields.io/github/stars/lc708/AMind?style=flat-square&color=D97757" alt="GitHub stars"></a>
  <a href="skills/amind"><img src="https://img.shields.io/badge/Agent%20Skill-AMind-D97757?style=flat-square" alt="AMind Agent Skill"></a>
  <a href="skills/amind/data/manifest.json"><img src="https://img.shields.io/badge/source--bound%20evidence-offline%20index-71C4A5?style=flat-square" alt="Offline full evidence index; current counts in manifest"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-8D96A5?style=flat-square" alt="Apache License 2.0"></a>
</p>

<p align="center">
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="#start-in-60-seconds">Install</a> ·
  <a href="#what-an-answer-looks-like">See an answer</a> ·
  <a href="release/amind-v1/reports/synthesis.zh-CN.md">Read the synthesis (Chinese)</a> ·
  <a href="release/amind-v1/data/representative-evidence-review.jsonl">Inspect reviewed evidence</a>
</p>

![AMind turns a question into a recommendation with visible evidence distance and traceable sources](assets/amind-hero.svg)

## Start in 60 seconds

AMind also includes an **AI engineering and evaluation skill series**: [`amind-engineering` 0.4.1](skills/amind-engineering/SKILL.md) for prompt audits, migrations, multi-agent contracts, durable staged workflows and 13 task templates, plus [`eval-improve` 0.5.1](skills/eval-improve/SKILL.md) for application/grader evaluations, exact billing scope, calibrated judges and strict comparisons. They work with AI products regardless of whether those products use a Codex harness; neither requires Claude. See [installation and usage](AMIND-SERIES.md) and the [October 30 application update](reviews/2026-10-30-update/report.zh-CN.md). The knowledge skill below retains its own version and evidence boundary.

AMind **1.4.0** records public evidence observed through **2026-10-30**. It adds agent oversight, architecture, science and governance research, product/developer blogs and historical omissions; claim-specific dated eligibility retains corrected and superseded material as history. Read the [October 30 knowledge update](release/amind-v1-increment-2026-10-30/reports/update.zh-CN.md); the [September 1.2.1 update](release/amind-v1-increment-2026-09-08/reports/update.zh-CN.md) and original v1 release remain historical snapshots. The installed [manifest](skills/amind/data/manifest.json), `summary` and `stats` commands are authoritative for the current packaged counts and observation cutoff. No recurring web refresh is implied.

Install [Git LFS](https://git-lfs.com/) first, then materialize the knowledge index:

```bash
git lfs install
git clone https://github.com/lc708/AMind.git
cd AMind
git lfs pull --include="skills/amind/data/amind-full-index.sqlite3"
python3 -B skills/amind/scripts/verify.py
```

Ask your **Agent** to install the local `skills/amind` folder from that verified checkout, or copy it into your client's skills directory. The index must be the SQLite payload, not an LFS pointer. A source ZIP or an installer using GitHub archives may contain only the pointer; use the Git LFS checkout above if verification fails.

Once installation finishes, reload the Agent or start a new session if needed, then ask a real question:

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
| Best for live, up-to-the-minute facts | No | **Yes, with live sources** | No—each AMind evidence package has a recorded cutoff |

AMind is deliberately bounded. It trades the false freshness of an untraceable persona for a corpus you can inspect, challenge, and reproduce.

## Pick your path

| If you want to… | Start here |
|---|---|
| Think through a real decision | [Install the Skill](#start-in-60-seconds) |
| Understand the reconstructed framework | [Read the synthesis (Chinese)](release/amind-v1/reports/synthesis.zh-CN.md) |
| Build lightweight RAG or an evaluation | [Use the 54 reviewed gold rows](release/amind-v1/data/representative-evidence-review.jsonl) |
| Search the full corpus | [Use the Skill's local index](#inspect-the-indexed-skill) |
| Audit the construction and limits | [Read the evaluation (Chinese)](release/amind-v1/reports/evaluation.zh-CN.md) and [release audit](release/amind-v1/release-audit.json) |

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

The installed Skill includes a complete local search index. The 54-row kernel remains its individually reviewed gold layer. Current totals, hashes and the observation cutoff live in the [manifest](skills/amind/data/manifest.json); dated release packages preserve raw audit and research history.

| Layer | Authoritative record |
|---|---|
| Current analysis units, passages and indexed claims | Manifest `counts`; `query.py summary` |
| Source and voice distributions | `query.py stats --json` |
| Human-reviewed representative evidence rows | 54; the reviewed gold layer is preserved |
| Themes, voices and tensions | Manifest `counts`; the matching query commands |
| Corrections, supersession and effective dates | Manifest-bound `current-status.jsonl` |
| Historical candidate populations and totals | Original v1 and dated increment reports |

The human-review claim is intentionally narrow: all 54 representative gold rows were reviewed in passage context. Other indexed claims are structured, source-bound and attribution-audited, but are not all individually human-reviewed. Search uses them as candidates and includes bound passages for context verification. New machine-checked content does not become human-reviewed gold merely by being indexed.

### Inspect the indexed Skill

```bash
python3 -B skills/amind/scripts/query.py summary
python3 -B skills/amind/scripts/query.py search "alignment faking" --limit 5
python3 -B skills/amind/scripts/query.py search "latest responsible scaling policy" --current --limit 5
python3 -B skills/amind/scripts/query.py search "responsible scaling policy" --as-of 2026-09-08 --limit 5
python3 -B skills/amind/scripts/query.py search "cybersecurity incidents" --as-of 2026-10-18 --include-history --limit 5
python3 -B skills/amind/scripts/query.py kernel-search "alignment faking" --limit 5
python3 -B skills/amind/scripts/query.py stats
python3 -B skills/amind/scripts/query.py tensions
python3 -B skills/amind/scripts/verify.py
```

Default search uses the full index while filtering current-answer eligibility at the manifest cutoff, collapsing audited equivalents, excluding merely reported positions and diversifying works, voices and hosts. `--current` favors recent eligible evidence within that boundary; it does not fetch the web. `--as-of YYYY-MM-DD` changes the eligibility date using recorded publication/correction/effective-date evidence. `--include-history` includes inactive or future-effective material with status labels instead of deleting it. A date beyond the collection cutoff requires fresh verification. Use `show <claim-id> --passage` to inspect the original context and status before material use.

### Audit the raw release

```bash
git clone https://github.com/lc708/AMind.git
cd AMind

python3 -B release/amind-v1/amind.py summary
python3 -B release/amind-v1/amind.py search "model welfare" --limit 5
python3 -B release/amind-v1/amind.py show nuwa1-claim-f169332e5fa3d349672a254d
```

The commands above audit the original v1 historical snapshot. For a small high-trust evaluation, start with [`representative-evidence-review.jsonl`](release/amind-v1/data/representative-evidence-review.jsonl). For current custom retrieval, use the release selected by the [manifest](skills/amind/data/manifest.json): currently [`atomic-claims.jsonl.gz`](release/amind-v1-increment-2026-10-30/data/atomic-claims.jsonl.gz) joined to [`analysis-units.jsonl.gz`](release/amind-v1-increment-2026-10-30/data/analysis-units.jsonl.gz). Apply the manifest-bound lifecycle decisions and attribution filters described in the [retrieval policy](skills/amind/references/retrieval.md), or use `query.py`, which applies them. An unfiltered raw stream includes historical and reported material that is ineligible for a current institutional answer.

## Works across Agents

The installable package at [`skills/amind`](skills/amind) is a self-contained Agent Skill. A capable Agent can install it using its own conventions; clients that support the Agent Skills folder format can also copy or install that folder into their skills directory and invoke `amind`. Client directory locations and invocation syntax vary; the evidence tools themselves require only Python 3.

## Verify or develop

```bash
python3 -B skills/amind/scripts/verify.py
python3 -B scripts/verify_amind_increment.py
python3 -B scripts/verify_amind_refresh.py
python3 -B -m unittest scripts.test_amind_skill scripts.test_amind_increment scripts.test_amind_refresh scripts.test_amind_refresh_sources
python3 -B scripts/verify_amind_v1_release.py
python3 -B scripts/verify_amind_increment.py --historical
python3 -B scripts/verify_amind_application_skills.py --output .codex-tmp/application-checks.json
```

The SQLite index combines original v1 with dated increments through the current manifest cutoff. The 54-row reviewed kernel is preserved from v1; corrected and superseded evidence retains its original identity and passage. Every packaged data artifact carries a SHA-256 digest and row count. `verify_amind_increment.py` selects the current package verifier; `--historical` checks the September snapshot independently. The [October 30 verification receipt](reviews/2026-10-30-update/validation/final.json) records current application and knowledge checks. The October 19 baseline had 220 tests. Application checks use local fixtures and make no live model calls. The historical [October 18 comparison](reviews/2026-10-18-comparison/report.zh-CN.md) records measured knowledge/timeliness and helper-contract gains; skill-guided model engineering and evaluation tasks tied. It covers 24 CLI task executions across 12 paired tasks, with one repetition per task and version. These bounded results do not establish general superiority.

Three repetitions on work-like projects found one gateway-contract difference and ties on the other engineering and evaluation tasks after semantic grader corrections. Policy citation support improved in the tested task. The [workplace report](reviews/2026-10-19-workplace/report.zh-CN.md) retains 42 main executions, six confirmations, measurement repairs and the runtime configuration deviation.

The original raw execution files are preserved in [checksum-bound review archives](reviews/2026-10-19-shipping/README.md). Run `python3 -B scripts/restore_amind_review_artifacts.py --apply` before opening raw-run links in a fresh checkout; restoration copies regular files only and executes no captured code.

## Boundaries

- AMind reconstructs public reasoning; it has no access to Anthropic's private deliberations.
- It never speaks in Anthropic's first person or invents an unpublished decision.
- Original v1 and each increment are dated research snapshots. Current-answer filtering uses recorded status evidence and cannot verify policy after the observation cutoff.
- Theme frequency measures corpus coverage, not organizational consensus or personal influence.
- Institutional material is not automatically attributed to an individual, and individual writing is not automatically institutional policy.
- Only the 54 gold rows were individually reviewed; full-index results require passage inspection before material use.
- AMind is an independent public-research project and is not affiliated with or endorsed by Anthropic.

<details>
<summary><strong>Frequently asked questions</strong></summary>

### Is AMind official Anthropic software?

No. It is an independent open-source project built only from public material.

### Is AMind a model?

No. It is an Agent Skill, full local evidence index, reviewed gold kernel, retrieval policy, and auditable research release that works with a capable host model.

### Does the Skill contain only 54 evidence rows?

No. It searches the full locally indexed corpus and carries bound passages; use `query.py summary` or the manifest for current totals. The 54 rows are the smaller set reviewed individually by a human and used as a Gold calibration layer.

### Why does Jack Clark appear so often?

Import AI contributes many issues, while some long technical papers produce hundreds of atomic claims. Raw volume is not a measure of personal influence: reported or quoted positions remain distinct from Jack Clark's own views. Use `query.py stats --json` for the current distribution; default retrieval excludes reported positions and caps results per work, voice and host. Historical distributions remain in dated reports. See the [retrieval policy](skills/amind/references/retrieval.md#distribution-audit).

### Does it claim to reproduce private reasoning?

No. It reconstructs recurring patterns in public evidence and labels every step beyond that evidence.

### Can I use the dataset without installing the Skill?

Yes. The indexed Skill and raw release tools are standalone, use the Python standard library, and can be used directly in research or RAG workflows.

</details>

## Contribute, cite, or report a problem

- Found a source, attribution, or version issue? Open an [evidence correction](https://github.com/lc708/AMind/issues/new?template=evidence_correction.yml).
- Have a useful question or integration idea? Read [CONTRIBUTING.md](CONTRIBUTING.md) and open a [feature request](https://github.com/lc708/AMind/issues/new?template=feature_request.yml).
- Using AMind in research? See [`CITATION.cff`](CITATION.cff).
- Found a security issue? Follow [`SECURITY.md`](SECURITY.md) instead of opening a public issue.

## License

AMind's software, original documentation, build logic, and Skill instructions are licensed under the [Apache License 2.0](LICENSE). Third-party quotations, public captures, extracted texts and factual metadata retain their respective authors’ and publishers’ rights and are not relicensed; see [NOTICE](NOTICE) for the evidence and trademark boundary.

If AMind gives you a useful new lens, **[star the repository](https://github.com/lc708/AMind)** and share the question where visible evidence distance changed your answer.
