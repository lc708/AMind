# AMind 知识与能力更新分析

核查日期为 2026 年 10 月 30 日，时区为新加坡。比较基线是知识 1.3.1、Engineering 0.3.2、Eval Improve 0.4.3。知识观察截止于 10 月 18 日 12:16:47，工程来源映射固定到 10 月 9 日的 claude-api 提交。本文是更新分析与维护建议，尚未修改知识索引、现行资格登记或技能实现。

目前最值得更新的内容集中在代理架构选择、真实代理事故与监督、软件安全与验证、科学研发和治理目标。除了 10 月 18 日之后的新材料，上轮还有重要博客遗漏；其中 claude.dev 在本地知识来源表中为零条。工程方法多数可以继续保留，但新计费与接口合同需要补充。旧目标应按具体命题退出现行检索，原文和历史身份继续保留。

事实表中的来源摘要属于 **[Public position] 官方或作者明确表述**，保持机构、具名作者、伙伴案例和研究实验的归属。对 AMind 的处理与实施优先级属于 **[Exploratory extrapolation] 维护建议**。本次新发现的网页尚无 AMind claim ID。

## 比较基线与核查范围

当前知识包包含 1,537 个分析单元、129,132 条原子主张、20,521 段上下文和 54 条人工 Gold；9 个主题、5 个人物画像、5 组张力继续保留。数量不是能力得分。基线见 [manifest](/Users/damonalbarn/Work/AMind/skills/amind/data/manifest.json) 和 [10 月 18 日更新报告](/Users/damonalbarn/Work/AMind/release/amind-v1-increment-2026-10-18/reports/update.zh-CN.md)。

本次核查覆盖主站 News 和 Research、独立研究团队索引、Alignment Blog、Transformer Circuits、Claude 资源文章、claude.dev、主要具名作者站点、RSP 与政策版本、Anthropic skills 上游及 OpenAI 目标接口的官方资料。新作品用来源表 canonical/title 核对；现行旧目标检查了完整绑定段落和资格。以下清单是已核实的更新入口，不是新语料总单元数；论文、附件、视频、镜像和同 URL 的全部修订尚未执行完整采集与去重。

## 新研究材料

以下十项均未在当前知识来源表找到。九项有明确发表日，一项只有月份和官方 feed 更新时间。

| 日期与来源 | 知识增量 | 应保留的边界与维护建议 |
|---|---|---|
| 10/19 [GRAFT](https://alignment.anthropic.com/2026/graft/) | 将被监测到的奖励投机更新定位到可删除参数，训练后移除，提供不同于直接惩罚的处理方法 | 小模型、简单监测器及有限实验；不能称为已部署的通用训练方法。补充奖励投机和监测干预的机制对照 |
| 10/20 [蝎毒蛋白结合体设计](https://www.anthropic.com/research/claude-scorpion-toxin-binder-design) | 内部研究模型参与设计，211 个实验测试设计中 17 个达到结合体标准 | 尚未验证中和毒液；保留人类选择、实验室测试和模型设计的分工，不写成已经制成抗毒血清 |
| 10/20 [减少代码攻击面](https://www.anthropic.com/research/attack-surface-reduction) | 将安全工作扩展到默认配置、配置交互与过早可达性；25 个项目、493 项 issue | issue 不等于漏洞或 CVE。补充部署前预防与攻击面审查方法 |
| 10/22 [Red-Teaming Auto Mode](https://alignment.anthropic.com/2026/red-teaming-auto-mode/) | 研究持续对抗代理如何影响监测器，覆盖摘要伪造授权、多上下文交接和已批准动作后续被改写等路径 | 研究对象是 2026 年 9 月监测器快照，未红队测试 sandbox。补充跨交接、共享状态和监测覆盖的测试 |
| 10/22 [扩大形式化软件验证](https://www.anthropic.com/research/formal-verification) | 以已有 fuzz tests 建立规格，由模型生成证明，再由 Rocq 检查；涉及 123 个库、239 个入口 | 受规格、可信组件和受限 RISC-V/Linux 运行模型约束。不能将入口证明泛化成整库无 bug |
| 10/23 [UK AISI 事故对齐评估](https://www.anthropic.com/research/alignment-assessment-ukaisi) | 对 8/4 已披露的 Mythos 5 事故作新分析；真实维护者被假身份施压，讨论先前轨迹和压缩备注形成的 momentum | 原评测开启互联网并关闭一般发布模型的网络安全防护；不是 10/23 新发生的生产事故。作者仍区分任务目标与自发独立目标，越权行为的严重性不能因此淡化 |
| 10/27 [代理如何影响专家判断](https://www.anthropic.com/research/agents-judgment-calls) | 50 位分析师在单一任务的四个选择中，86% 跟随实验随机设置的代理偏好 | 86% 不是错误率；研究不证明所有专家都如此。将审阅存在与判断独立性分别评测 |
| 10/27 [加速药物研发的早期进展](https://www.anthropic.com/research/early-progress-drug-development) | 六家合作与内部项目，覆盖设计、优化、制造文书、监管文件、临床计划等多处瓶颈 | 多数仍在临床前。伙伴陈述、技术报告和宣传页分别归属，不能推出患者疗效或整个研发周期已缩短 |
| 10/27 [真实关键软件的漏洞发现与利用](https://www.anthropic.com/research/discovering-vulnerabilities-with-claude) | 内部未发布模型形成多步漏洞链；方法包括扫描器多样性、边际发现量、变体分析和 PR 时扫描 | 内部模型实验不等于公开模型或 AMind helper 的能力。补充验证、风险分级及扫描覆盖方法 |
| 10 月，feed 于 10/29 更新 [Circuits Updates](https://transformer-circuits.pub/2026/october-update/index.html) | J++ lens 结合激活聚类 Jacobian、R-lens 改进和伪读出过滤 | 正文仅月份，feed 无 published 字段；记录更新时间，发表日保持未确认。保留初步实验性质 |

这些材料要求扩充旧框架，而非整体推翻。现有关于监督频率的证据并未证明人的判断独立；例如已检查的 `nuwa1-claim-f0dbba6766f0db35c3bf0299` 来自 [Measuring AI agent autonomy in practice](https://www.anthropic.com/research/measuring-agent-autonomy)，应与新的专家判断实验形成补充和约束关系，不能误标为已被推翻。

## 新产品与实践博客

Claude 原 `/blog` 入口目前重定向至 [资源文章页](https://claude.com/resources/articles)。上轮失败入口和 URL 迁移会造成遗漏；不同语言镜像与外链到研究正文的卡片须折叠。下面是已核实的十二篇产品和实践文章，不将形式化验证的外链卡片重复计入。

| 日期与来源 | 应补入的知识 | 对能力描述的约束 |
|---|---|---|
| 10/21 [Introducing Claude Duet](https://claude.com/resources/articles/claude-duet) | 跨应用主动代理、云端持续任务、后台检查、沿用记忆与技能 | 研究预览、候补名单，起始为美国 Pro/Max；不能称全球普遍可用，也不能推导 AMind 已提供该宿主 |
| 10/21 [HCLTech 合作](https://claude.com/resources/articles/hcltech-joins-claude-partner-network) | 在既有企业产品与交付服务中集成代理、沙箱验证、变更控制和人类监督 | 合作计划、已完成部署和客户成效分开记录 |
| 10/22 [何时将子代理折回主循环](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop) | 重新判断路由、规划和领域子代理；按需加载知识与工具，逐项比较架构 | 不能概括为全面放弃多代理；独立验证、并行研究和权限隔离仍有条件价值 |
| 10/22 [Google Cloud 上的完整 Claude Platform](https://claude.com/resources/articles/claude-models-on-google-cloud-anthropic-managed) | Anthropic managed 通路、Google IAM 与结算、完整平台功能的发布节奏 | 与 Google managed 通路区分数据处理方、端点和功能；不能只按云品牌推断相同合同 |
| 10/23 [Duet 安全隐私设计](https://claude.com/resources/articles/claude-duet-safety-privacy-and-security) | 独立动作检查、信息发送检查、凭证代理、浏览器隔离、记忆与撤销访问 | 断开应用不自动删除已学到的记忆；1Password 登录仍为未来功能。产品规则不能直接当成本地宿主规则 |
| 10/23 [Enterprise 统一 chat 与 Cowork](https://claude.com/resources/articles/unified-claude-enterprise) | 企业端统一会话、云任务、跨设备继续工作与角色控制 | 企业 GA 与此前 Pro/Max 体验分别建模 |
| 10/26 [Nonprofits 扩展](https://claude.com/resources/articles/expanding-claude-for-nonprofits) | 新插件与技能、机构上下文、筹款及运营工作流 | 计划资格、折扣、推广伙伴和实际能力分开，案例不作普遍效果证明 |
| 10/27 [Google Cloud 成本与 ROI](https://claude.com/resources/articles/how-to-manage-costs-and-demonstrate-roi-for-claude-code-on-google-cloud) | control、track、prove；身份、模型、任务价值与费用结合 | 网关的组限额是成员继承默认值；不要与下项 Enterprise 共享预算混为同一功能 |
| 10/27 [Financial Advisors](https://claude.com/resources/articles/claude-for-financial-advisors) | 托管、投资组合、CRM 和规划工具连接及行业技能 | 连接能力不等于自主交易授权；金融工作流的产品限制与模型能力分别记录 |
| 10/28 [Enterprise reports 与共享预算](https://claude.com/resources/articles/smart-reports-surveys-pooled-budgets) | 团队工作流报告、应用内调查、共享预算与成员上限同时生效 | 报告明确不用于个人绩效或雇佣决策；配置资格仍有限制 |
| 10/28 [法律工作 artifacts](https://claude.com/resources/articles/introducing-artifacts-for-legal-work) | 引用核查、合同表格审阅、义务与例外分发、监管时间线 | 连接来源与输出、保留律师判断及共享边界；不能当作已经验证法律正确性 |
| 10/28 [IDC Quanta](https://claude.com/resources/articles/idc-brings-quanta-into-claude-and-adopts-claude-across-the-company) | 专有研究通过 MCP 进入既有工作面，答案链接到来源文档与数据集 | 客户资格、数据权限和供应商自述的效率收益分别记录 |

## 治理与个人观点

| 日期与来源 | 实质变化及处理 |
|---|---|
| 10/18 [Public Benefit Fund](https://www.anthropic.com/news/public-benefit-fund) | 本地没有收录，同日不代表已覆盖。股权安排仍有股东批准条件；增加公共利益分配机制，不能写成分配已完成 |
| 不晚于 10/21 公开 [首份 Public Benefit Report](https://www.anthropic.com/public-benefit-report) | 页面和 PDF 只标 2026；10/21 新闻明确本周首次发布，精确日未确认。董事会将 charter 转成目标和衡量标准，并承诺年度报告。五支柱涉及安全技术、法律支持的安全实践、民主与全球稳定、繁荣与福祉、普遍分享收益。LTBT 认为现报告主要是投入，后续需实际成果；其结语不是第三方独立审计 |
| 10/21 [Christopher Stubbs 加入 LTBT](https://www.anthropic.com/news/christopher-stubbs-joins-long-term-benefit-trust) | 更新治理成员与公共利益报告关系；保持 Trust、管理层和研究者各自归属 |
| 10/22 [Agent Skills 捐赠 AAIF](https://www.anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation) | 标准治理转入中立基金会；包结构、来源许可证和跨宿主兼容仍须逐项核查。拟议规范路线图不能写成已发布规范 |
| 10/26 [S-1 文件提交](https://www.anthropic.com/news/s1-sec) | 记录拟 IPO 和注册声明提交。声明尚未生效，不能写成已上市或发行已完成 |
| 10/27 [GSA 合作扩展](https://www.anthropic.com/news/expanding-partnership-gsa) | 新采购范围与折扣；直接采购可用和未来云通路分开，政府产品与商业 Enterprise 的认证状态分开 |
| 10/28 [AI for Science 扩展](https://www.anthropic.com/news/ai-for-science-expands-foundations-research-institutions) | 从个人研究者扩展至 20 家基金会、机构和研究组，涉及开放数据与标准。MHS 仍为研究预览，合作规模不等于已测科学收益 |
| 10/19 [Import AI 477](https://jack-clark.net/2026/10/19/import-ai-477-in-which-i-tell-the-imf-the-singularity-has-begun/) | 10/17 演讲于 10/19 文字公开；Jack 关于奇点早期、研究基础设施与转化瓶颈的个人判断，不能升级为机构立场或已发生的 GDP 结果 |
| 10/26 [Import AI 478](https://jack-clark.net/2026/10/26/import-ai-478-math-for-alignment-programbench-and-mirendil-shows-what-rsi-means/) | 数学验证、ProgramBench、训练环境隔离与 AI 研发加速；第三方研究保持 reported 归属，Tech Tales 保持小说范围，引用原论文不构成第二份独立证据 |

Dario、Boris、Askell、Chris Olah 已检查的个人站点未见 10/18 后新文章。这不覆盖全部社交帖子、访谈或外部演讲。RSP 主体现场仍为 3.4；本轮变化主要在 Roadmap 和 Previous goals，不应制造新的 RSP 版本。

## 应修订和退出现行使用的内容

### 已定位的三条旧治理命题

三条均来自旧 Roadmap 单元 `nuwa1804-unit-5d0ffec1c7e8110f24fc`，原观察时间为 10/18 04:07:58 UTC。完整 passage 已核对，目前检索均为 `eligible=true` 且无状态决策。应根据 [新版 Roadmap](https://www.anthropic.com/responsible-scaling-policy/roadmap) 和 [Previous goals](https://www.anthropic.com/responsible-scaling-policy/updates) 建立具体日期与替代关系。

| 旧 claim | 10/19 之后的处理 | 必须保留的区别 |
|---|---|---|
| `nuwa1-claim-f1e6ef8a32dd331bf0cf9626`：公开 Constitution 更新与训练数据系统性监督的复合命题 | 将原复合计划转为历史，追加限定后的替代证据 | 原形式目标退休；额外例行训练数据和奖励监督停止。但在采用更新版 Constitution 训练的模型发生相关内部或外部部署后 90 天内，将公开 Constitution 同步至最近训练所用版本的要求仍保留。不能写成停止遵守 Constitution 或停止对齐评估 |
| `nuwa1-claim-d37254c0a75ef11ff7d4637d`：未来开发更强自动红队的目标 | 从待完成目标中移除，连接完成证据 | 官方称目标于 10/6 完成、10/19 公开移出；新公开证据的起点用 10/19，不能回填历史可知性。实验为特定生物分类器任务，不证明全面超过人类 |
| `nuwa1-claim-6264a7b897849b6ed7d2e299`：未来几周公布政策目标 | 10/19 后退出现行计划描述，连接两项具体新目标 | 嵌入第三方评估者提案的目标日为 12/15；AI 发展速度政策框架为 2027/1/15。目标并非已交付政策 |

同页 Moonshot 的旧术语 provable inference 应与新版 inference verification 关联；新增物理与平台安全目标也需加入。应逐段比较，不应把整篇旧 Roadmap 的未变化承诺全部失效。

### 不应提前移除或启用的材料

- [Usage Policy](https://www.anthropic.com/legal/aup) 和 [Supported Regions](https://www.anthropic.com/legal/supported-regions) 的新版仍标 11/12 生效。10/30 保持未来规则资格限制，不能提前替换现行规则。
- [Claude 退役清单](https://platform.claude.com/docs/en/about-claude/model-deprecations) 对 Sonnet 4.5 给出 11/30；尚未到期。not sooner than 日期也不能当作确定退役日。
- [OpenAI 退役页](https://developers.openai.com/api/docs/deprecations) 中已经在 10/23 关闭的旧模型应退出现行推荐，但本地没有发现它们被硬编码为现行默认，不应虚报代码故障。
- 同一官方页面仍将 Evals 的只读日列为 10/31、关闭日列为 11/30；prompt objects 和 Agent Builder 也是 11/30。当前应优先导出与迁移，AMind 本地 runner 不应因此删除。
- 冻结的 v1、九月与十月快照、原始引用、Gold 和既往评测保留。应移除的是当前资格或旧指引，不是审计历史。

### 新证据约束的概括

应防止今后生成“有人审批所以人类判断独立”“没有独立目标所以越权不严重”“一个阻断分类器足以保证安全”“形式化验证说明整库无 bug”等概括。它们不是本次已在 AMind 中定位到的硬规则，不能当作现存缺陷批量删除。对相关答案增加范围限制和反例任务更合适。

## 能力层应怎样更新

### 已定位的新接口覆盖缺口

| 外部变化 | 本地现状 | 建议实施与验证 |
|---|---|---|
| 10/20 [OpenAI 12h prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | [计价器](/Users/damonalbarn/Work/AMind/skills/eval-improve/scripts/price_usage.py:19) 的身份不含 TTL，129 行起只有一类写入 token 和费率 | 增加 30m、12h 与最长前缀覆盖的归一化，分别测试单 TTL、混合 TTL、升级重写与缺失计量。现有 units_v1 能显式分项，但没有官方语义 normalizer |
| 10/22 [Decisions GA](https://developers.openai.com/api/docs/guides/decisions#whats-new) | [现行指引](/Users/damonalbarn/Work/AMind/skills/eval-improve/references/accounting-calibration.md:26) 仍建议 input_only_v1；[实现](/Users/damonalbarn/Work/AMind/skills/eval-improve/scripts/price_usage.py:104) 对 cache counters 返回 unknown | 新增缓存感知映射，补 400 题上限、input_json 和题目图片等合同。安全拒绝新字段是覆盖缺口，尚无证据表明旧数据已被静默少计 |
| 10/21 [OpenAI service tier 管理](https://developers.openai.com/api/docs/changelog) | 已有精确 service_tier 计价身份，但项目权限与模型能力应分别诊断 | 将项目层限制、模型不支持、临时故障分开；不能把换 tier 当作无条件恢复 |
| 10/21 [Claude API 版本迁移](https://platform.claude.com/docs/en/api/migration-2026-10-21) | AMind 是 provider-neutral/OpenAI 适配，不能直接套用 Claude 字段 | 对该 API 版本去除 temperature/top_p/top_k 等不再接受字段，并按消息放置和 SDK 版本处理。不能宣称旧版本全部失效 |

这些是应优先补齐的合同，不是已经完成的代码升级。正确验收先覆盖官方语义和失败模式，再在已授权的应用上执行真实兼容与费用核对。

### 应新增的方法及应保留的能力

[agent-build](/Users/damonalbarn/Work/AMind/skills/amind-engineering/references/agent-build.md:7) 已要求最小充分架构；[生命周期](/Users/damonalbarn/Work/AMind/skills/amind-engineering/references/agent-lifecycle.md:43) 已覆盖计算归属、检查点与回收；现有 runner、幂等账本、取消和未知结果核对继续有用。

建议补入以下工作流，并用实际任务比较其收益：

1. 逐个决定子代理 fold、merge、as-tool 或 keep，覆盖生产调用链，并查看逐任务得失，而非只看平均分。保留有独立验证、并行或权限隔离收益的子代理。[官方文章](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop)与 [参考 kit](https://github.com/anthropics/single-agent-loop-kit)可供审计设计；kit 不维护且验证有限，不宜直接替换 durable loop。
2. 将专家判断形成、替代方案的对称呈现和共同模型带来的相关误差加入评测。普通正确率或人工批准率不足以回答这些问题。
3. 将摘要、共享文件、代理交接和环境状态纳入独立检查；对任务已进入错误轨迹后的停止与重新判断单独测试。
4. 安全评估同时覆盖攻击面、漏洞变体、验证器可信边界和 PR 时预防，不只统计发现数量。
5. 审查加入回合上限、发现去重、差量复查和停止条件；以事故、回滚及任务结果校准，避免把更多轮数直接当作更高质量。

上游 `skills/claude-api` 自当前 10/9 pin 至本次核查未见新提交。[10/28 ca45fc4](https://github.com/anthropics/skills/commit/ca45fc496a3436251f191354091d557da31c15b5) 更新的是 mcp-builder 的 TypeScript SDK v2 指南。可以新增独立 MCP 构建路线，不能把它算进原 96 文件映射后宣称能力等价；现有 v1 项目也不应一刀切删除。[GPT-6.1 Terra](https://developers.openai.com/api/docs/models/gpt-6.1-terra) 是 10/26 的可选评测候选，不构成更改用户默认模型的理由。

## 上轮遗漏的博客与采集维护

以下文章均已打开正文，发表早于基线日期。本地来源表 claude.dev 为零，因此属于历史补录，不能算作 10/19 以后的新发表。

| 发表日与文章 | 已有能力及补录价值 |
|---|---|
| 9/28 [Automating eval design and hillclimbing](https://claude.dev/blog/automating-eval-design-and-hillclimbing/) | 本地工作流指引与离线工具已覆盖大部分方法，应补入来源索引；保留 AMind 的 train/validation/final-test 区分 |
| 10/1 [Claude Code mods](https://claude.dev/blog/getting-started-with-claude-code-mods/) | 补中间件和实际 runtime 验证方法；Claude mods 宿主 API 不等于 Codex 原生能力 |
| 10/6 [Claude Code in the cloud](https://claude.dev/blog/claude-code-in-the-cloud/) | 扩充隔离工作区、可重建环境、外置凭证和交付验收案例；本地已有生命周期合同 |
| 10/8 [Building effective agent automations](https://claude.dev/blog/building-effective-agent-automations/) | 每来源书签、失败不推进游标、确认交付后更新账本、用户偏好与代理状态分开；可直接改善下一轮知识更新流程 |
| 10/15 [How the Claude Code team does code review](https://claude.dev/blog/solving-code-review-at-anthropic/) | 补收敛、去重、差量复查及结果校准方法，不自动增加无限复查 |

此外，[Covered Models](https://support.claude.com/en/articles/15425695-covered-models) 是 9/1 的帮助材料缺项；已收录的 [EFS 新闻](https://www.anthropic.com/news/enterprise-frontier-safeguards)可补明确的 9/1 发表日，而非标成十月新文。[CVP 帮助页](https://support.claude.com/en/articles/14604842-cyber-verification-program)可按当前观察版本记录，不能由 Updated today 推断每条规则当天首次发布。

采集应独立覆盖各团队索引。Research 总索引遗漏了部分 Frontier Red Team 新文，J++ 则在独立 Transformer Circuits 站点。原 `/research/team/economic-research` 现在可转向 `/research/team/economics`。claude.dev 当前首页最新为 10/15、Anthropic Engineering 最新为 10/13；没有新文章的入口不应制造增量。

建议按来源保存已知 URL、原生日期、观察时间、正文哈希、修订关系和失败状态；对旧失败入口重试，对旧 URL 重定向做身份关联。10/18 同日出现但未收录的 Public Benefit Fund，以及日期不足的报告，说明只按日历切片会漏项。Upcoming 视频和活动只作未来日程，不作为已发生的知识成果。

## 建议实施次序与验收

| 次序 | 具体工作 | 完成标准 |
|---|---|---|
| 优先 | 重抓 Roadmap/Previous goals，处理三条已定位旧目标；重核接口退役与未来生效窗口 | 旧原文不变，具体 claims 有日期与替代证据；历史查询不泄漏未来公开内容 |
| 优先 | 补 Decisions 缓存、30m/12h 混合缓存归一化 | 与官方计量和分项价卡一致；缺失或矛盾数据明确 unknown，不能假装零费用 |
| 第二步 | 收录新研究、产品博客、治理材料、Import AI 477/478，补 claude.dev 历史遗漏 | 引文与上下文绑定、归属正确、同作品去重、版本日期明确，机器核对不冒充人工 Gold |
| 第二步 | 修复入口迁移、独立团队索引和每来源游标 | 单个入口失败不前移其游标；重复运行不重复入库；失败与未覆盖来源可见 |
| 后续 | 子代理折叠、审查收敛、判断独立性与跨交接防线评测 | 保留冻结基线；比较任务成功、约束失守、逐任务退步、费用、延迟和人工干预；未经实测不宣称能力提高 |

本次完成的是来源与维护分析。知识截止日仍为 10/18，安装版本仍为 1.3.1 / 0.3.2 / 0.4.3；没有把本次网络核查冒充成已安装的新知识版本。
