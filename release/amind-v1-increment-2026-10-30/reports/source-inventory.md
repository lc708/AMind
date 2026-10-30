# 本轮来源清单

本清单逐项列出实际入库的 **70个分析单元**。分区取自[准备审计](../audits/preparation-audit.json)，标题、作者、日期与URL取自本轮delta及绑定抓取。相同作品的正文与附件可以是不同分析单元，因此单元数不等于独立作品数；未确认的作者与日期不补造。完整逐项版本判断见[来源决策](../delta/source-decisions.jsonl)。

| 分区 | 单元数 |
|---|---:|
| 窗口内发表：2026-10-19至10-30 | 29 |
| 历史回补：早于2026-10-18 | 16 |
| 上次截止日当天首次补录：2026-10-18 | 1 |
| 日期未确认的首次索引 | 19 |
| 既有作品修订 | 5 |
| 合计 | 70 |

抓取留存为 **108条records：105份选定捕获+3份只作元数据留存的团队导航**。选定捕获由88个正文入口与17个附件组成；按全部records计有91个正文入口记录，其中3个是被排除的导航。17个附件不全部是新增单元：正文未变、别名与其他排除判断另计。不能把抓取数、URL发现数或附件数当成新文章数。

除具备原生发表日的46个单元外，24个单元的精确 `published_at` 仍为空。Roadmap及目标档案的10/19是原生修订证据；法律11/12是生效日；模型退役手册10/30是观察起点。未知日期来源的 `available_by` 只表示最迟已观察到，不代表当天发表。来源范围和日期决策见[策展记录](../curation/source-availability.jsonl)与[现行资格登记](../data/current-status.jsonl)。

## 窗口内发表（29）


| 原生发表日 | 标题与真实来源 | 原生作者 | 日期／载体说明 | 分析单元 |
|---|---|---|---|---|
| 2026-10-19 | [Reducing Reward Hacking by Localizing Bad Behavior Instead of Penalizing It](https://alignment.anthropic.com/2026/graft) | Shawn Hu、Jake Ward、Aria Wong、Nathan Hu、Bryce Woodworth、Alexander Matt Turner、Alex Cloud | 原生精确发表日 | `nuwa1804-unit-c77cbe6753fc595cfe8a` |
| 2026-10-19 | [Import AI 477: In which I tell the IMF the Singularity has begun](https://jack-clark.net/2026/10/19/import-ai-477-in-which-i-tell-the-imf-the-singularity-has-begun) | Jack Clark | 原生精确发表日 | `nuwa1804-unit-9a855335edb066f69a98` |
| 2026-10-20 | [Using Claude to reduce the attack surface of code](https://anthropic.com/research/attack-surface-reduction) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-ff5662d39c8871346087` |
| 2026-10-20 | [How Claude designed protein binders against scorpion neurotoxins](https://anthropic.com/research/claude-scorpion-toxin-binder-design) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-be94a193a81ed97d99f9` |
| 2026-10-21 | [Physicist Christopher Stubbs joins Anthropic's Long-Term Benefit Trust](https://anthropic.com/news/christopher-stubbs-joins-long-term-benefit-trust) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-bbd8d31bc1abb6c3e4da` |
| 2026-10-21 | [Introducing Claude Duet](https://claude.com/resources/articles/claude-duet) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-990fee0a7ab0c72ab8fe` |
| 2026-10-21 | [HCLTech joins the Claude Partner Network as a Global Premier partner](https://claude.com/resources/articles/hcltech-joins-claude-partner-network) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-fe2cc782439005b921de` |
| 2026-10-22 | [Red-Teaming Auto Mode: Improving Blocking Classifiers Against Malign Coding Agents](https://alignment.anthropic.com/2026/red-teaming-auto-mode) | Alex Remedios、Simon Storf、Fabien Roger、John Hughes | 原生精确发表日 | `nuwa1804-unit-6d19b835c5c54f2efa91` |
| 2026-10-22 | [Donating Agent Skills to the Agentic AI Foundation](https://anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-40303043b2b0c84af735` |
| 2026-10-22 | [Open call for guest investigators in the life sciences](https://anthropic.com/news/open-call-guest-investigators-life-sciences) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-25b33663d6ebec1659f8` |
| 2026-10-22 | [LLMs are making formal software verification feasible at a much larger scale](https://anthropic.com/research/formal-verification) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-c99bc63428db4386d4c2` |
| 2026-10-22 | [Building agents: When to fold subagents into your main agent loop](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop) | Diane Sarkis | 原生精确发表日 | `nuwa1804-unit-d9fc60a7c92ec89c4c0f` |
| 2026-10-22 | [The full Claude Platform, available on Google Cloud](https://claude.com/resources/articles/claude-models-on-google-cloud-anthropic-managed) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-76bdac790de19c60a92d` |
| 2026-10-23 | [An alignment assessment of the UK AISI cybertesting incident](https://anthropic.com/research/alignment-assessment-ukaisi) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-2c8b11355fdba4839a29` |
| 2026-10-23 | [Claude Duet Safety, Privacy, and Security](https://claude.com/resources/articles/claude-duet-safety-privacy-and-security) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-99ebd834350f5fe7a0f3` |
| 2026-10-23 | [Claude Cowork and chat come together for Enterprise](https://claude.com/resources/articles/unified-claude-enterprise) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-4f2a801ad8e7d7927d57` |
| 2026-10-26 | [Anthropic files S-1 with the SEC for proposed initial public offering](https://anthropic.com/news/s1-sec) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-8d8d236ab04e75d34d1a` |
| 2026-10-26 | [Expanding Claude for Nonprofits](https://claude.com/resources/articles/expanding-claude-for-nonprofits) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-daaa3868aa893db74b2b` |
| 2026-10-26 | [Import AI 478: Math for alignment; ProgramBench; and Mirendil shows what RSI means](https://jack-clark.net/2026/10/26/import-ai-478-math-for-alignment-programbench-and-mirendil-shows-what-rsi-means) | Jack Clark | 原生精确发表日 | `nuwa1804-unit-55cc9ac08f0643c0ca95` |
| 2026-10-27 | [Expanding our partnership with GSA to bring Claude to all levels of government](https://anthropic.com/news/expanding-partnership-gsa) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-225e047ddefa96b3d0fb` |
| 2026-10-27 | [How AI agents shape experts’ judgment calls](https://anthropic.com/research/agents-judgment-calls) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-22cd36c8a605287cf709` |
| 2026-10-27 | [Discovering and exploiting vulnerabilities in critical, real-world software with Claude](https://anthropic.com/research/discovering-vulnerabilities-with-claude) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-ae51dfa36b464ce39b14` |
| 2026-10-27 | [Early progress on accelerating drug development with Claude](https://anthropic.com/research/early-progress-drug-development) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-819ed37375107aba41fe` |
| 2026-10-27 | [Claude for Financial Advisors](https://claude.com/resources/articles/claude-for-financial-advisors) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-7c148f09fcf13a06c85b` |
| 2026-10-27 | [Manage costs and demonstrate ROI for Claude Code on Google Cloud](https://claude.com/resources/articles/how-to-manage-costs-and-demonstrate-roi-for-claude-code-on-google-cloud) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-b8e09b71ec63717a02de` |
| 2026-10-28 | [AI for Science expands to foundations and research institutions](https://anthropic.com/news/ai-for-science-expands-foundations-research-institutions) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-ceba01d87b09d43828b8` |
| 2026-10-28 | [IDC brings Quanta into Claude and adopts Claude across the company](https://claude.com/resources/articles/idc-brings-quanta-into-claude-and-adopts-claude-across-the-company) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-69888e937983a4497581` |
| 2026-10-28 | [Introducing artifacts for legal work](https://claude.com/resources/articles/introducing-artifacts-for-legal-work) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-55fee813a37ee8b1381a` |
| 2026-10-28 | [Smart reports, surveys, and pooled group budgets for Claude Enterprise](https://claude.com/resources/articles/smart-reports-surveys-pooled-budgets) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-f24bb7b59f19d5020352` |


## 历史回补（16）

### claude.dev历史博客（10）

这些文章发表于9/22至10/15；本轮补齐漏项，不计作10/19以后的新博客。保留原生具名作者与产品实践范围。


| 原生发表日 | 标题与真实来源 | 原生作者 | 日期／载体说明 | 分析单元 |
|---|---|---|---|---|
| 2026-09-22 | [Getting the most out of Opus 5.5 in Claude and Claude Code](https://claude.dev/blog/getting-the-most-out-of-opus-5-5) | Addy Osmani | 原生精确发表日 | `nuwa1804-unit-d22ee589c4c993715317` |
| 2026-09-23 | [How we made claude.ai 3x faster in two weeks](https://claude.dev/blog/how-we-made-claude-ai-faster) | Raymond Wang、Sam Attard、Issac G. | 原生精确发表日 | `nuwa1804-unit-3c381bb7f422cab0acda` |
| 2026-09-25 | [Using Claude Code: Spending your effort](https://claude.dev/blog/spending-your-effort) | Thariq Shihipar | 原生精确发表日 | `nuwa1804-unit-cef3ae2ce12b2cadff38` |
| 2026-09-25 | [What a task costs on Opus 5.5](https://claude.dev/blog/what-a-task-costs-on-opus-5-5) | Addy Osmani | 原生精确发表日 | `nuwa1804-unit-3c84841c353479734661` |
| 2026-09-28 | [Automating eval design and hillclimbing with Claude](https://claude.dev/blog/automating-eval-design-and-hillclimbing) | Lance Martin | 原生精确发表日 | `nuwa1804-unit-cf1aa0c1d84f67da28e1` |
| 2026-09-28 | [Building with Claude Sonnet 5.5](https://claude.dev/blog/building-with-claude-sonnet-5-5) | Addy Osmani | 原生精确发表日 | `nuwa1804-unit-fa0e682dfc51b7572837` |
| 2026-10-01 | [Getting started with Claude Code mods](https://claude.dev/blog/getting-started-with-claude-code-mods) | Addy Osmani | 原生精确发表日 | `nuwa1804-unit-10af16630b06b278eaea` |
| 2026-10-06 | [Claude Code in the cloud: a field guide to cloud sessions](https://claude.dev/blog/claude-code-in-the-cloud) | Addy Osmani | 原生精确发表日 | `nuwa1804-unit-6287c6480cf710c7d5dd` |
| 2026-10-08 | [Building effective agent automations](https://claude.dev/blog/building-effective-agent-automations) | Lance Martin、CJ Avilla | 原生精确发表日 | `nuwa1804-unit-c1246c28bb5411389302` |
| 2026-10-15 | [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic) | Addy Osmani、Morgan Westlee Lunt、Qing Wang | 原生精确发表日 | `nuwa1804-unit-035bb3006541b3920f52` |


### 其他历史正文（6）


| 原生发表日 | 标题与真实来源 | 原生作者 | 日期／载体说明 | 分析单元 |
|---|---|---|---|---|
| 2024-04-26 | [Circuits Updates – April 2024](https://anthropic.com/research/circuits-updates-april-2024) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-4509310ab679fd91f1cc` |
| 2024-07-31 | [Circuits Updates – July 2024](https://anthropic.com/research/circuits-updates-july-2024) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-b35406475a19dda42580` |
| 2024-09-19 | [Introducing Contextual Retrieval](https://anthropic.com/research/contextual-retrieval) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-b335390142d96f5df639` |
| 2025-04-18 | [Claude Code: Best practices for agentic coding](https://anthropic.com/research/claude-code-best-practices) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-e52dcaf8abc19271a39d` |
| 2025-10-20 | [Beyond permission prompts: making Claude Code more secure and autonomous](https://anthropic.com/research/claude-code-sandboxing) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-63d2df8fbf975fe1d021` |
| 2025-11-04 | [Code execution with MCP: Building more efficient agents](https://anthropic.com/research/code-execution-with-mcp) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-0d172272ecf19b3f2181` |


## 上次截止日当天补录（1）


| 原生发表日 | 标题与真实来源 | 原生作者 | 日期／载体说明 | 分析单元 |
|---|---|---|---|---|
| 2026-10-18 | [Investing in the public benefit](https://anthropic.com/news/public-benefit-fund) | 未列出；不据此推定作者 | 原生精确发表日 | `nuwa1804-unit-c00c7de05339e73b89b7` |


## 日期未确认的首次索引（19）


| 原生发表日 | 标题与真实来源 | 原生作者 | 日期／载体说明 | 分析单元 |
|---|---|---|---|---|
| 未确认 | [Summer 2025 Sabotage Risk Report](https://alignment.anthropic.com/2025/sabotage-risk-report/2025_pilot_risk_report.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://www.anthropic.com/responsible-scaling-policy/roadmap)；附件发表日未确认 | `nuwa1804-unit-af6961853bcdbc1c6d77` |
| 未确认 | [Public Benefit Report](https://anthropic.com/public-benefit-report) | 未列出；不据此推定作者 | 报告精确发表日未确认；10/21新闻为“本周已发布”的旁证 | `nuwa1804-unit-c5100d95ab668cc3262d` |
| 未确认 | [Migrating to API version 2026-10-21](https://platform.claude.com/docs/en/api/migration-2026-10-21) | 未列出；不据此推定作者 | 10/21是API版本号；文档发表日未确认 | `nuwa1804-unit-399fcce06fee5c9708d1` |
| 未确认 | [Cyber Verification Program](https://support.claude.com/en/articles/14604842-cyber-verification-program) | 未列出；不据此推定作者 | 发表日未确认；最迟10/30捕获可见 | `nuwa1804-unit-07ab8047b7afafda1bdd` |
| 未确认 | [Covered Models](https://support.claude.com/en/articles/15425695-covered-models) | 未列出；不据此推定作者 | 发表日未确认；最迟10/30捕获可见 | `nuwa1804-unit-41ee4f26faf264c8cc59` |
| 未确认 | [Circuits Updates – October 2026](https://transformer-circuits.pub/2026/october-update/index.html) | 未列出；不据此推定作者 | 只有October 2026标题；10/29更新时间不作发表日 | `nuwa1804-unit-5f2b5654198ac4834087` |
| 未确认 | [De novo design of protein binders against scorpion toxins with Claude](https://www-cdn.anthropic.com/31ac578806cffd8b3d92d8affe6edc4c04d502e1.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://www.anthropic.com/research/claude-scorpion-toxin-binder-design)；附件发表日未确认 | `nuwa1804-unit-a2f99c9801c5a1ba42c3` |
| 未确认 | [Anthropic_PredictabilityAndSurprise.pdf](https://www-cdn.anthropic.com/4ff80d7f8a98bf096cd543ec61ddc50de3ad8b16/Anthropic_PredictabilityAndSurprise.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://anthropic.com/research/predictability-and-surprise-in-large-generative-models)；附件发表日未确认 | `nuwa1804-unit-f121cfc7cccde82f5ea5` |
| 未确认 | [519c17a5d23a794e8b6d50a854048d0b61e0d73a.pdf](https://www-cdn.anthropic.com/519c17a5d23a794e8b6d50a854048d0b61e0d73a.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://www.anthropic.com/research/agents-judgment-calls)；附件发表日未确认 | `nuwa1804-unit-fbd39bb3572e0d8ba155` |
| 未确认 | [Preclinical Characterization of a Bispecific Bridging Antibody for the Treatment of LAMA2-Related Congenital Muscular Dystrophy](https://www-cdn.anthropic.com/52e1f5d50c47ca3818f56704c27cf19e59b62e77.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://www.anthropic.com/research/early-progress-drug-development)；附件发表日未确认 | `nuwa1804-unit-df4cbc305a37f47ea529` |
| 未确认 | [Contextual Retrieval Appendix II](https://www-cdn.anthropic.com/5722e7658c9302d8b97a3238de1bb8e6afdf04b9.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://anthropic.com/research/contextual-retrieval)；附件发表日未确认 | `nuwa1804-unit-20f98af49024064c34d0` |
| 未确认 | [ActivatingASL-3_2025.05](https://www-cdn.anthropic.com/807c59454757214bfd37592d6e048079cd7a7728.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://www.anthropic.com/responsible-scaling-policy/roadmap)；附件发表日未确认 | `nuwa1804-unit-27eed739bcfa22e3295e` |
| 未确认 | [Public Benefit Report（PDF；元数据标题为文件名）](https://www-cdn.anthropic.com/a9ceec76a54d28d27affffcdab6faf7c142cd587.pdf) | 未列出；不据此推定作者 | 报告精确发表日未确认；10/21新闻为“本周已发布”的旁证 | `nuwa1804-unit-52d0f1cf4abc10232719` |
| 未确认 | [Appendix](https://www-cdn.anthropic.com/bb224ffec0bd87a4f885bd30b187606064a86ea5.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://anthropic.com/research/political-even-handedness)；附件发表日未确认 | `nuwa1804-unit-581b8566fb181c08254f` |
| 未确认 | [Appendix to “How People Use Claude for Support, Advice, and Companionship”](https://www-cdn.anthropic.com/bd374a9430babc8f165af95c0db9799bdaf64900.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://anthropic.com/research/how-people-use-claude-for-support-advice-and-companionship)；附件发表日未确认 | `nuwa1804-unit-ee14d7401ed814636b55` |
| 未确认 | [Anthropic_MoralSelfCorrection_v3.pdf](https://www-cdn.anthropic.com/d14f58fe8f611858bc37ff8686bbda71e4927ce6/Anthropic_MoralSelfCorrection_v3.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://anthropic.com/research/the-capacity-for-moral-self-correction-in-large-language-models)；附件发表日未确认 | `nuwa1804-unit-c09ff33de2a41bf8946f` |
| 未确认 | [0a58d567024a8b448ff15158ebc3625328dfcc1f.pdf](https://www-cdn.anthropic.com/files/4zrzovbb/website/0a58d567024a8b448ff15158ebc3625328dfcc1f.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://www.anthropic.com/responsible-scaling-policy/roadmap)；附件发表日未确认 | `nuwa1804-unit-44aef4ea40363c2bd39e` |
| 未确认 | [5f5bf833a83e4c85550768e8b16ff282f268d7a3.pdf](https://www-cdn.anthropic.com/files/4zrzovbb/website/5f5bf833a83e4c85550768e8b16ff282f268d7a3.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://anthropic.com/research/measuring-model-persuasiveness)；附件发表日未确认 | `nuwa1804-unit-5105f8a9bbde5ba98436` |
| 未确认 | [Appendix: LLMs are making formal software verification feasible at a much larger scale](https://www-cdn.anthropic.com/files/4zrzovbb/website/6867eadf760258fa8b42a504600cd3c036d16358.pdf) | 未列出；不据此推定作者 | [正文所链附件](https://www.anthropic.com/research/formal-verification)；附件发表日未确认 | `nuwa1804-unit-a486bcd5e61770e658ef` |


## 既有作品修订（5）


| 原生发表日 | 标题与真实来源 | 原生作者 | 日期／载体说明 | 分析单元 |
|---|---|---|---|---|
| 未确认 | [Usage Policy](https://anthropic.com/legal/aup) | 未列出；不据此推定作者 | 原生生效日2026-11-12；与发表日分开 | `nuwa1804-unit-383207b0e602c2d6d415` |
| 未确认 | [Supported Regions Policy](https://anthropic.com/legal/supported-regions) | 未列出；不据此推定作者 | 原生生效日2026-11-12；与发表日分开 | `nuwa1804-unit-8b6f8b2a9ac8eee34d84` |
| 未确认 | [Anthropic's Frontier Safety Roadmap](https://anthropic.com/responsible-scaling-policy/roadmap) | 未列出；不据此推定作者 | 原生10/19变更记录支持新版起点；不作原作品发表日 | `nuwa1804-unit-4cae45af9cef95100f71` |
| 未确认 | [Previous goals](https://anthropic.com/responsible-scaling-policy/updates) | 未列出；不据此推定作者 | 原生10/19变更记录支持新版起点；不作原作品发表日 | `nuwa1804-unit-60d478f8f0df629d82aa` |
| 未确认 | [Model deprecations](https://platform.claude.com/docs/en/about-claude/model-deprecations) | 未列出；不据此推定作者 | 旧运行手册在10/30观察日退出，新版同日起可用 | `nuwa1804-unit-ef36093b5aee9b2a5518` |


## 保留捕获但不增加分析单元（38条）

| 处置 | 数量 | 说明 |
|---|---:|---|
| 旧作品重定向别名 | 30 | `baseline_redirect_alias`；不重复计作新作品，逐项URL与旧单元绑定见来源决策 |
| 正文未变 | 4 | 已有系统卡／附件的重抓，不产生新正文版本 |
| 元数据／模板变化 | 1 | Enterprise Frontier Safeguards正文的机构表述未发生实质变化；新页头、日期及具名testimonial标签不算新机构立场 |
| 团队导航元数据 | 3 | 导航原始捕获保留，个别研究正文分别索引，不将团队入口当文章 |

三条导航分别为[Frontier Red Team](https://anthropic.com/research/team/frontier-red-team)、[Interpretability](https://anthropic.com/research/team/interpretability)与[Societal Impacts](https://anthropic.com/research/team/societal-impacts)。元数据／模板页为[Enterprise Frontier Safeguards](https://anthropic.com/news/enterprise-frontier-safeguards)。这些处置以[最终来源决策](../delta/source-decisions.jsonl)为准；抓取和提取的中间阶段统计不可相加当成最终总数。

配置入口重枚举有两个未解决失败：Dario archive和Jared Kaplan publications。早期原始探测中的其他失败及超时单独保留在审计中；本清单只承诺列明已选定、成功绑定并入库的材料，不宣称完整覆盖互联网、所有播客或访谈。

## 证据与验证入口

每个单元可经 `source_seed_record_ids` 连接到 `sources/records/` 内的原始抓取记录，再连接到原始文件和完整衍生正文。文章中的关联附件通过抓取记录的 `parent_url` 保留来源关系；不因同一正文与附件分别计数而宣称独立佐证。

- [来源绑定核对](../audits/source-binding-verification.json)
- [提取审计](../audits/extraction-audit.json)
- [AI上下文复核](../curation/claim-reviews.jsonl)与[来源范围说明](../curation/source-scope-notes.jsonl)
- [知识检查](../../../reviews/2026-10-30-update/validation/knowledge-checks.json)与[最终验证](../../../reviews/2026-10-30-update/validation/final.json)
- [发布总报告](../../../reviews/2026-10-30-update/report.zh-CN.md)
