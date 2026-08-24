# Product Marketing Context

**Document version:** v1
**Last updated:** 2026-08-24

## Product Overview

**One-liner:** AMind is an evidence-grounded Agent Skill that applies Anthropic's public reasoning to real decisions while showing the evidence distance behind every material conclusion.

**What it does:** AMind helps people think through, advise on, critique, explain, compare, and trace questions using a bounded reconstruction of Anthropic's public reasoning. It combines an installable, offline evidence kernel with a full auditable research release and explicitly separates public positions, strong framework inferences, and exploratory extrapolations.

**Product category:** Evidence-grounded Agent Skill; AI decision-support and public-reasoning research corpus.

**Product type:** Open-source software and research dataset.

**Business model:** Free and open source. Original software and documentation use Apache-2.0; public-source quotations and third-party factual metadata retain their original rights as documented in NOTICE.

## Target Audience

**Target companies:** AI labs, agent/product teams, AI safety and governance organizations, research groups, policy teams, and technically sophisticated independent builders.

**Decision-makers:** AI founders, product and engineering leads, safety/governance leads, researchers, policy strategists, and developers building Agent Skills or RAG systems.

**Primary use case:** Get a useful Anthropic-informed perspective on a real question without relying on role-play or losing the boundary between public evidence and inference.

**Jobs to be done:**

- Pressure-test an AI product, deployment, safety, governance, or research decision.
- Reconstruct and compare public positions across the Anthropic institution and named voices.
- Trace a conclusion back to exact public evidence, source URLs, dates, and stable claim IDs.
- Reuse a compact reviewed evidence kernel or the full release in an agent or RAG workflow.

**Use cases:**

- Decide whether and how to stage an autonomous-agent rollout.
- Critique an AI safety policy or model-release plan.
- Explain a recurring Anthropic reasoning pattern under uncertainty.
- Compare institutional language with Dario Amodei, Jack Clark, Chris Olah, or Amanda Askell.
- Audit evidence provenance or build research tooling on the released corpus.

## Personas

| Persona | Cares about | Challenge | Value we promise |
|---------|-------------|-----------|------------------|
| AI product or agent lead | Shipping useful systems without hiding risk | Generic advice is confident but hard to audit | Concrete recommendations, stop conditions, and visible inference distance |
| Safety or governance practitioner | Accurate public positions and defensible policy reasoning | Sources, versions, and institutional versus individual voices get flattened | Bounded voices, preserved tensions, and claim-level traceability |
| Researcher or RAG builder | Reusable structured evidence | Manual corpus work is slow and ordinary search lacks synthesis boundaries | A compact reviewed kernel plus a full, deterministic, auditable release |
| Curious technical user | A better lens on a difficult AI question | Persona prompts feel plausible but offer no provenance | A 60-second install and answers that distinguish fact from inference |

## Problems & Pain Points

**Core problem:** People want to use Anthropic's public thinking as a lens, but the practical alternatives either require reading a large corpus manually or asking a model to imitate a persona without showing where the reasoning came from.

**Why alternatives fall short:**

- Persona prompts collapse public fact, interpretation, and invention into one voice.
- Generic web search retrieves documents but does not preserve recurring mechanisms, counterevidence, voice boundaries, or version changes by default.
- Custom RAG can work, but users must build the corpus, evidence policy, evaluation, and audit layer themselves.
- Reading primary sources manually is high quality but slow and difficult to repeat consistently.

**What it costs them:** Time, weak decision accountability, misplaced confidence, and avoidable misattribution.

**Emotional tension:** Users want a decisive answer but do not want confidence theater or false claims of private institutional knowledge.

## Competitive Landscape

**Direct:** Persona and system prompts that ask an assistant to "think like Anthropic" — fast, but provenance and inference distance are usually absent.

**Secondary:** Search engines, generic RAG, and research assistants — strong for retrieval, but the user must supply the synthesis method and voice/version boundaries.

**Indirect:** Reading and synthesizing the public corpus manually — highest control, but slow and hard to make repeatable.

## Differentiation

**Key differentiators:**

- Three explicit evidence-distance labels: Public position, Strong framework inference, and Exploratory extrapolation.
- 52,225 source-linked atomic claims across 1,351 deduplicated analysis units in the full release.
- A compact kernel of 54 human-reviewed evidence rows spanning 9 themes, 5 voices, and 5 preserved tensions.
- Institution, named-author, version, contradiction, and attribution boundaries are preserved.
- Offline, zero-third-party-dependency evidence query and integrity tools.
- Deterministic manifests, hashes, audits, and stable claim IDs.

**How we do it differently:** AMind distills a bounded public corpus into atomic claims, separates voices and versions, retains tensions and counterevidence, and then turns those patterns into advice while labeling how far each conclusion travels beyond direct precedent.

**Why that's better:** Users get judgment that remains useful without disguising uncertainty or source distance.

**Why customers choose us:** AMind offers the convenience of an Agent Skill with the inspectability of a research release.

## Objections

| Objection | Response |
|-----------|----------|
| "Is this just a clever persona prompt?" | No. The Skill ships a reviewed evidence kernel, retrieval rules, answer patterns, and a full source-linked audit release. |
| "Does this speak for Anthropic?" | No. AMind is independent, uses only public material, never claims private deliberations, and marks inference explicitly. |
| "Is a frozen corpus current enough?" | AMind v1 is a bounded research release, not live search. Source dates and version boundaries are preserved; time-sensitive claims should be checked against newer primary sources. |
| "Were all 52,225 claims manually reviewed?" | No. The human-review claim is limited to the 54-row representative kernel; the full corpus is machine-structured and extensively audited, not individually human-reviewed. |

**Anti-persona:** Anyone seeking private Anthropic information, an official Anthropic position, real-time news coverage, unqualified imitation, or a substitute for high-stakes professional judgment.

## Switching Dynamics

**Push:** Generic answers feel plausible but cannot show whether a conclusion is a public position, a repeated pattern, or a novel guess.

**Pull:** A one-step install, concrete recommendations, exact citations, stable claim IDs, and transparent inference labels.

**Habit:** Persona prompts and ordinary search are familiar and require no new workflow.

**Anxiety:** Users may worry that the project overclaims affiliation, is stale, or hides another prompt behind large numbers. The README must answer these concerns early with boundaries, an inspectable demo, and reproducible verification.

## Customer Language

**How they describe the problem:**

- "How would the Anthropic lens frame our autonomous-agent rollout?"
- "Should we open-source this model? Give a recommendation and stop conditions."
- "Show the evidence behind this conclusion, including quotes and claim IDs."

**How they describe us:**

- No validated customer quotes yet. Until real users are interviewed, use the factual phrase "an evidence-grounded Anthropic lens" and do not invent testimonials.

**Words to use:** evidence-grounded, public reasoning, source-linked, traceable, inspectable, inference distance, bounded, independent, offline, auditable, recommendation, stop conditions.

**Words to avoid:** clone, replica, digital twin, official, insider, authentic Anthropic voice, consciousness, perfect reconstruction, guaranteed.

**Glossary:**

| Term | Meaning |
|------|---------|
| Public position | A conclusion directly supported by a cited public source |
| Strong framework inference | A conclusion reconstructed from repeated, source-linked patterns |
| Exploratory extrapolation | Advice applying public principles to a new case beyond exact precedent |
| Analysis unit | A deduplicated, version-bounded unit in the public corpus |
| Evidence kernel | The compact 54-row reviewed evidence package shipped with the Skill |
| Nuwa | AMind's internal corpus-distillation and synthesis methodology, not the public product name |

## Brand Voice

**Tone:** Rigorous, calm, confident, and candid.

**Style:** Lead with the decision or benefit; use plain language; make evidence and limits visible; prefer concrete verbs and numbers over AI marketing language.

**Personality:** Independent, intellectually honest, practical, technical but accessible, quietly bold.

## Proof Points

**Metrics:**

- 1,804 authoritative candidates.
- 1,351 deduplicated analysis units, including 1,348 with primary bodies and 3 bounded unavailable exceptions.
- 13,436 evidence passages.
- 52,225 source-linked atomic claims.
- 54 human-reviewed representative evidence rows across 9 themes.
- 5 bounded voice profiles and 5 preserved synthesis tensions.
- 16 passing Skill regression tests and a release audit verdict of PASS as of 2026-08-24.

**Customers:** No customer or organization logos claimed.

**Testimonials:** No validated testimonials yet.

**Value themes:**

| Theme | Proof |
|-------|-------|
| Useful judgment | Think, Advise, Critique, Explain, Compare, and Trace modes |
| Visible provenance | Three evidence-distance labels, source URLs, exact quotes, and stable claim IDs |
| Inspectability | Full corpus, schemas, audits, manifests, and deterministic hashes are public |
| Low-friction use | Installable Agent Skill; compact evidence tools use only the Python standard library |

## Goals

**Business goal:** Give the repository a credible chance to reach 1,000 GitHub stars in the seven days following launch.

**Conversion action:** Primary — star the repository after trying AMind on a real question. Secondary — install the Skill, share a useful output, or contribute an evidence correction/use case.

**Current metrics:** 0 stars, 0 forks, empty GitHub description, and no repository topics observed on 2026-08-24 before this launch pass.

## Changelog

*Newest first. One line per revision: what changed and why.*

- v1 (2026-08-24) — Initial positioning derived from the repository, release manifests, tests, and current GitHub metadata for the README and launch rewrite.
