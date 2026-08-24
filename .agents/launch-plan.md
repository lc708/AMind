# AMind 7-Day GitHub Launch Plan

**Prepared:** 2026-08-24

**Goal:** Give AMind a credible path from 0 to 1,000 GitHub stars in seven days.

**Primary conversion:** A qualified visitor tries one real question, understands the evidence boundary, and stars the repository if the result is useful.

## Assumptions

- This is AMind's first coordinated public launch.
- The starting point is 0 stars, 0 forks, no repository description, and no topics.
- No existing email list, community size, or prior launch performance was supplied, so the plan does not assume a large owned audience.
- AMind is an open-source Agent Skill and research release, not a hosted SaaS product.
- Product Hunt is secondary. Hacker News, technical social posts, Agent Skills directories, and credible practitioner sharing are better initial fits.

## Launch thesis

The story is not "we made an Anthropic persona." The story is:

> Most persona prompts hide the line between evidence and invention. AMind still gives you a recommendation, but labels how far every material conclusion travels from Anthropic's public evidence—and lets you inspect the corpus yourself.

The memorable proof stack is:

1. **Useful:** Think, Advise, Critique, Explain, Compare, and Trace.
2. **Different:** Public position / Strong framework inference / Exploratory extrapolation.
3. **Substantial:** 52,225 source-linked claims across 1,351 analysis units.
4. **Honest:** 54 representative rows are human-reviewed; AMind does not claim all 52,225 were manually reviewed.
5. **Inspectible:** Offline standard-library tools, stable IDs, manifests, hashes, and audits.

## Working launch math

One thousand stars requires reach, not only better copy. As simple planning math—not an industry benchmark—10% qualified visitor-to-star conversion would require roughly 10,000 qualified repository visitors in the week. Track both traffic and conversion so a distribution problem is not mistaken for a README problem.

## Pre-launch gate

Do not send broad traffic until all items pass:

- [ ] README, Chinese README, contribution, security, citation, and issue templates are merged to `main`.
- [ ] GitHub description and topics are live.
- [ ] `assets/amind-social-preview.png` is uploaded in **Settings → General → Social preview**.
- [ ] GitHub private vulnerability reporting is enabled so the security links resolve.
- [ ] A clean Codex install from the public `main` branch succeeds.
- [ ] The three repository verification commands pass on a fresh clone.
- [ ] A `v1.0.0` GitHub Release exists with a short changelog and install command.
- [ ] Three real demo questions have been tested: rollout advice, policy critique, and evidence trace.
- [ ] The maintainer can be present for the first 6–8 launch hours to answer every substantive comment.

The current Codex session is authenticated as a Write-level collaborator, so a repository admin must run the metadata changes:

```bash
gh repo edit lc708/AMind \
  --description "An evidence-grounded Anthropic lens for AI decisions—an installable Agent Skill backed by 52,225 source-linked claims and an auditable offline corpus." \
  --add-topic agent-skills --add-topic anthropic --add-topic codex \
  --add-topic openai-codex --add-topic claude --add-topic ai-agents \
  --add-topic ai-safety --add-topic ai-governance --add-topic decision-making \
  --add-topic rag --add-topic research-dataset --add-topic evidence-provenance

gh api --method PUT repos/lc708/AMind/private-vulnerability-reporting
```

## ORB channel strategy

### Owned

- GitHub README, Release, Issues, and repository Insights.
- Pin one issue inviting users to share the question they tried and what was missing.
- Turn the strongest real use case from launch week into an example in the README.

### Rented

Use two primary channels well instead of posting the same copy everywhere:

1. **Hacker News** — technical build story, honest limitations, no inflated claims.
2. **X or LinkedIn** — a visual explanation of the three evidence-distance labels plus one concrete example.

For the Chinese-language audience, adapt the story for V2EX, 即刻, or a relevant AI builder community; do not paste the English announcement unchanged.

### Borrowed

- Submit a focused PR to credible Agent Skills directories and lists after the public release is stable.
- Ask 15–25 relevant AI safety, agent engineering, governance, and research practitioners for critique—not for a blind star.
- Offer newsletter writers or community maintainers a compact evidence demo tailored to a question their audience already discusses.

Do not buy stars, trade stars, mass-DM strangers, or manufacture testimonials. Those tactics damage the trust AMind's positioning depends on.

## Seven-day cadence

### Day 0 — Make the repository launchable

- Merge the launch branch, update metadata, upload the social preview, and publish `v1.0.0`.
- Test installation from the public default branch, not the local checkout.
- Prepare three screenshots or short clips from real AMind answers.

### Day 1 — Lead with the core tension

- Publish the Hacker News Show HN post.
- Publish one X/LinkedIn post using the social preview and a single real question.
- Reply quickly with evidence, boundaries, implementation details, and concrete examples.
- Record the exact phrases people use to describe the value or confusion.

### Day 2 — Show the mechanism

- Post a short technical walkthrough: corpus → atomic claims → voice/version boundaries → three inference labels.
- Share a before/after comparison between a persona-prompt answer and an AMind answer without humiliating another project.
- Fix any installation or first-use friction immediately.

### Day 3 — Reach the Chinese builder audience

- Publish the Chinese narrative, focused on why "证据距离" matters for AI decisions.
- Use one locally relevant example and link directly to `README.zh-CN.md`.
- Ask for difficult questions, not generic praise.

### Day 4 — Borrow trusted distribution

- Open well-researched submissions to 3–5 relevant Agent Skills directories or curated lists.
- Send individual critique requests to practitioners whose public work directly overlaps one of AMind's nine themes.
- Include the exact question AMind can help them test.

### Day 5 — Open the evidence layer

- Publish a technical thread or article showing one claim ID from source passage through synthesis to recommendation.
- Highlight the narrow human-review claim and frozen-v1 boundary; honesty is part of the product.

### Day 6 — Turn feedback into a second launch

- Ship one visible improvement based on launch feedback: a new example, compatibility note, corrected evidence row, or clearer answer pattern.
- Publish a short changelog and thank the reporter with permission.

### Day 7 — Close with evidence, not hype

- Share a transparent retrospective: stars, qualified visitors, clones, installs if measurable, most-tested questions, corrections, and next release.
- Invite contributors into one concrete next milestone rather than posting a generic "more coming soon."

## Metrics and decision rules

Record daily:

- GitHub unique visitors and referrers;
- stars gained and visitor-to-star conversion;
- clones and unique cloners;
- successful fresh installs reported or observed;
- substantive issues, evidence corrections, and contributions;
- which announcement and example generated qualified discussion.

Decision rules:

- **Traffic low, conversion healthy:** spend the next day on borrowed/rented distribution, not another README rewrite.
- **Traffic high, conversion below 5%:** test the first-screen value proposition, demo, and install clarity.
- **Repeated install failure:** pause promotion and fix onboarding before adding more traffic.
- **Users mistake AMind for an official Anthropic project:** strengthen the independent-project boundary immediately.
- **A use case repeatedly resonates:** promote it into the first demo and next announcement.

## Copy bank

### GitHub description — preferred

> An evidence-grounded Anthropic lens for AI decisions—an installable Agent Skill backed by 52,225 source-linked claims and an auditable offline corpus.

### GitHub description — shorter alternative

> Think with Anthropic's public reasoning—without the role-play. An Agent Skill with visible inference distance and traceable sources.

### Recommended topics

`agent-skills`, `anthropic`, `codex`, `openai-codex`, `claude`, `ai-agents`, `ai-safety`, `ai-governance`, `decision-making`, `rag`, `research-dataset`, `evidence-provenance`

### Show HN title

> Show HN: AMind – Think with Anthropic's public reasoning, with sources

### GitHub Release

**Title:** `AMind v1.0.0 — useful judgment with visible evidence distance`

> AMind v1.0.0 turns a bounded reconstruction of Anthropic's public reasoning into an installable Agent Skill for Think, Advise, Critique, Explain, Compare, and Trace.
>
> The Skill searches all 52,225 source-linked claims through a complete offline index and carries all 13,436 bound passages for context checks. A separate 54-row gold kernel is individually human reviewed across 9 themes, 5 voices, and 5 preserved tensions.
>
> Install in Codex chat:
>
> `$skill-installer install https://github.com/lc708/AMind/tree/main/skills/amind`
>
> AMind is independent, uses public evidence only, and distinguishes Public position, Strong framework inference, and Exploratory extrapolation.

### Show HN opening

> I kept running into the same problem with "think like X" prompts: the answer could sound plausible, but I could not tell where public evidence ended and the model's invention began.
>
> AMind is an open-source Agent Skill that makes that distance explicit. It labels material conclusions as a public position, strong framework inference, or exploratory extrapolation, then links the reasoning back to exact quotes, URLs, dates, and stable claim IDs.
>
> The installable Skill ships a complete offline index of 52,225 source-linked claims, all 13,436 bound passages, and a 54-row human-reviewed gold kernel. It is independent, uses only public material, and does not claim to speak for Anthropic.
>
> I would especially value hard questions, evidence corrections, and feedback on whether the three labels make the answer more useful—not just more cautious.

### X / LinkedIn launch post

> Persona prompts have a provenance problem: they blur public facts, repeated patterns, and fresh invention into one confident voice.
>
> I built AMind to keep those layers visible while still giving a recommendation.
>
> - Public position
> - Strong framework inference
> - Exploratory extrapolation
>
> Underneath: 52,225 source-linked claims, 1,351 analysis units, a 54-row human-reviewed evidence kernel, and an offline audit trail.
>
> Try it on one difficult AI decision. If the visible evidence distance improves the answer, star it—and send me the question that broke it.
>
> https://github.com/lc708/AMind

### 中文发布文案

> “像某家公司一样思考”的 Persona Prompt 有个根本问题：公开事实、反复出现的思路和模型临场发挥，最后都会混成同一种自信语气。
>
> 我做了 AMind，把这三层明确标出来，同时仍然给出建议：
>
> - 公开立场
> - 强框架推断
> - 探索性外推
>
> 底层是 1,351 个分析单位、52,225 条来源绑定主张、54 条逐条人工复核的代表证据，以及可以离线检查的审计链。
>
> 拿一个真正困难的 AI 决策试试。如果“看清证据距离”让答案变好了，欢迎 Star；如果没有，请把那个问题发给我。
>
> https://github.com/lc708/AMind/blob/main/README.zh-CN.md

### Directory submission

> **AMind** — An evidence-grounded Agent Skill for applying Anthropic's public reasoning to AI decisions. Supports Think, Advise, Critique, Explain, Compare, and Trace; distinguishes public positions from inference and exploratory extrapolation; ships a complete offline index, reviewed gold kernel, and auditable corpus. Independent and not affiliated with Anthropic.
