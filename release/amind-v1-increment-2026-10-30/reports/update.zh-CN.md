# AMind 2026-10-30 更新说明

本发布把知识观察截止日从2026-10-18推进到 **2026-10-30（Asia/Singapore）**，对应知识技能1.4.0。以本轮实际数据表为准，新增 **70个分析单元、995个passage、11,533条claim**；合并后为 **1,607个分析单元、21,516个passage、140,665条claim**。人工校准Gold仍为 **54条**，本轮没有新增人工Gold。统计见[发布清单](../manifest.json)与[提取审计](../audits/extraction-audit.json)。

## 本轮覆盖如何计算

| 分区 | 分析单元数 | 含义 |
|---|---:|---|
| 窗口内发表 | 29 | 具备原生发表日，落在2026-10-19至10-30窗口内 |
| 历史回补 | 16 | 发表早于上次截止日，本轮才完整入库；含10篇claude.dev博客 |
| 上次截止日当天补录 | 1 | 10/18发表的Public Benefit Fund文章，不计入10/19以后的新发表 |
| 日期未确认的首次索引 | 19 | 首次索引的报告、附件或支持文档，缺少可信精确发表日 |
| 既有作品修订 | 5 | Roadmap、目标档案、AUP、Supported Regions和模型退役手册的新捕获版本 |

分区来自[准备审计](../audits/preparation-audit.json)，逐项日期、作者与真实URL见[来源清单](source-inventory.md)。新增claim数量反映正文和附件的提取规模，不能作为新知识重要性、观点共识或质量提升的倍数。

本轮重枚举90个配置入口，观察到6,319个唯一URL，其中5,138个被发现流程标为新增URL。最终留存108份抓取记录：**105份选定捕获，另有3份团队导航仅作元数据留存**；105份中含17个附件。选定捕获无未解决失败。Dario archive与Jared Kaplan publications两个发现入口仍失败；部分早期探测也有404、403或超时，不能据选定正文成功宣称所有公开材料均已覆盖。见[发现审计](../audits/discovery-summary.json)、[抓取审计](../audits/collection-summary.json)与[早期原始探测记录](../audits/node-raw-capture.json)。

## 新博客与回补内容

研究与安全新增覆盖GRAFT、Auto Mode红队、代码攻击面缩减、蝎毒蛋白结合物、形式化验证、UK AISI事故再评估、agent对专家判断的影响、漏洞发现和药物开发。策展保留各自实验边界：GRAFT是具名合作研究；结合不等于毒素中和或临床治疗；形式化证明受规格和可信计算基约束；判断实验的86%不能写成错误率；UK AISI文章是对先前披露事件的分析。[GRAFT](https://alignment.anthropic.com/2026/graft/)、[形式化验证](https://anthropic.com/research/formal-verification)、[判断实验](https://anthropic.com/research/agents-judgment-calls)、[事故评估](https://anthropic.com/research/alignment-assessment-ukaisi)

产品与开发材料覆盖Claude Duet及其隐私安全边界、Google Cloud两种托管路线、Enterprise报告与汇总预算、非营利组织和金融顾问场景等。产品公告保留计划、预览、地区、配置和权限条件；客户引文不能自动成为Anthropic机构立场，供应商产品能力也不等于本地AMind已具备该功能。[Duet安全说明](https://claude.com/resources/articles/claude-duet-safety-privacy-and-security)、[Google Cloud路线](https://claude.com/resources/articles/claude-models-on-google-cloud-anthropic-managed)、[Enterprise报告与预算](https://claude.com/resources/articles/smart-reports-surveys-pooled-budgets)

补齐的10篇claude.dev博客发表于9/22至10/15，属于历史漏项，覆盖评测设计与hillclimbing、可靠自动化、代码评审、任务成本、effort、mods、云会话和性能工程。作者名单逐篇保留；这些实践不自动升级为跨产品通用结论。[自动化](https://claude.dev/blog/building-effective-agent-automations)、[评测设计](https://claude.dev/blog/automating-eval-design-and-hillclimbing)、[代码评审](https://claude.dev/blog/solving-code-review-at-anthropic)、[任务成本](https://claude.dev/blog/what-a-task-costs-on-opus-5-5)

新纳入的子agent架构文章要求按任务和测量结果判断哪些边界应折叠；独立验证、并行研究及模块化权限仍有适用场景。它不会使所有子agent架构自动过时，文章附带迁移材料也保留其验证和维护限制。[When to fold subagents](https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop)

另补齐2024年的两篇Circuits Updates与Contextual Retrieval、2025年的Claude Code最佳实践、sandboxing和MCP代码执行文章。旧工程载体的30个重定向别名不重复计作30篇新作品；4份正文未变附件、1份仅模板／元数据变化页面及3份团队导航也不进入70个新增分析单元。[Contextual Retrieval](https://anthropic.com/research/contextual-retrieval)、[MCP代码执行](https://anthropic.com/research/code-execution-with-mcp)、[逐项来源判断](../delta/source-decisions.jsonl)

治理资料加入Public Benefit Fund、首份Public Benefit Report、LTBT人员变化及拟议IPO的S-1公告。报告中的公司自述、Daniela Amodei序言、Buddy Shah代表LTBT的结语和附录目标分别归属；理想终态不会被抽成已经实现的事实。LTBT结语不等于外部独立结果审计，基金安排仍有股东批准条件，S-1提交也不等于发行完成。[报告](https://anthropic.com/public-benefit-report)、[基金](https://anthropic.com/news/public-benefit-fund)、[LTBT新闻](https://anthropic.com/news/christopher-stubbs-joins-long-term-benefit-trust)、[S-1公告](https://anthropic.com/news/s1-sec)

Jack Clark的Import AI 477–478保留个人观点、研究转述和虚构材料的区别。Circuits October更新的月份标题与Atom更新时间不足以证明具体发表日，因此没有把10/29更新时间改成发表日。[Import AI 477](https://jack-clark.net/2026/10/19/import-ai-477-in-which-i-tell-the-imf-the-singularity-has-begun/)、[Import AI 478](https://jack-clark.net/2026/10/26/import-ai-478-math-for-alignment-programbench-and-mirendil-shows-what-rsi-means/)、[Circuits October](https://transformer-circuits.pub/2026/october-update/index.html)

## 过时内容如何退出现行检索

[现行资格登记](../data/current-status.jsonl)共有 **134条**：原38条逐字保留，本轮追加96条。以下 **9条旧Roadmap claims** 自10/19起被具体替代证据取代；每条保留原ID、引文和历史查询能力。这里只处理发生变化的承诺，不整页退出旧Roadmap。

| 旧claim | 已过时的表述范围 | 当前依据 |
|---|---|---|
| `nuwa1-claim-f1e6ef8a32dd331bf0cf9626` | Constitution同步与额外routine训练数据监督的组合承诺 | [10/19退休说明](https://anthropic.com/responsible-scaling-policy/updates) |
| `nuwa1-claim-6fb3e77ed055c2ead71426cb` | 将上述原目标补齐、系统化的待完成总述 | [原目标退休、持续评估另述](https://anthropic.com/responsible-scaling-policy/updates) |
| `nuwa1-claim-d37254c0a75ef11ff7d4637d` | 未来开发超过bug bounty贡献的红队方法 | [限定实验的完成报告](https://anthropic.com/responsible-scaling-policy/updates) |
| `nuwa1-claim-8ee14bfdbbe0532e4b5b5b5e` | 该待开发方法的前瞻延伸表述 | [限定实验的完成报告](https://anthropic.com/responsible-scaling-policy/updates) |
| `nuwa1-claim-6264a7b897849b6ed7d2e299` | 未来几周发布一个新政策目标 | [两项具体后继目标](https://anthropic.com/responsible-scaling-policy/roadmap) |
| `nuwa1-claim-8fcff4fd6e2cf7ea69490c27` | 计划另发一个政策目标的笼统表述 | [两项具体后继目标](https://anthropic.com/responsible-scaling-policy/roadmap) |
| `nuwa1-claim-2782a51527ea0a7a4aab4ea0` | Moonshot仍待完成Phase 1 | [原型进展与后续部署范围](https://anthropic.com/responsible-scaling-policy/updates) |
| `nuwa1-claim-db5db21e2b92bbc22f7abe24` | Phase 1旧截止日期作为当前计划 | [10/19完成情况](https://anthropic.com/responsible-scaling-policy/updates) |
| `nuwa1-claim-d9eed40a33fc2bf392c2129e` | 旧provable inference／mock环境的当前项目描述 | [inference verification与已实现范围](https://anthropic.com/responsible-scaling-policy/updates) |

新增目标档案中，**54条位于原Version文字内的claims**单独标为历史；每个Version区块在自己的Update处终止，后面的完成／退休报告仍有独立资格。红队内部完成日是10/6，公开证据边界是10/19；比较仅涉及8个问题、3代生物武器分类器形成的24对，不能泛化为全面超过人类。Constitution的额外routine监督退休，但相关模型部署后90天内同步公开Constitution的承诺和持续alignment assessments保留；旧weakest-link一般机制也继续可用。两项新政策目标的12/15与次年1/15是未来交付期限。[原生目标与更新](https://anthropic.com/responsible-scaling-policy/roadmap)、[档案与完成范围](https://anthropic.com/responsible-scaling-policy/updates)

[AUP](https://anthropic.com/legal/aup)与[Supported Regions](https://anthropic.com/legal/supported-regions)的原生生效日仍为 **2026-11-12**。新Legal Center模板将日期写成跨行的“Effective / Nov 12, 2026”，不会因此提前生效。[模型退役手册](https://platform.claude.com/docs/en/about-claude/model-deprecations)新增Anthropic-managed和Google-managed路线边界，旧版整单元在 **10/30观察日**退出当前检索，新版从同日可用；文中的模型退役日和API版本日期不会被当成这份手册的发布日期。

未知发表日继续留空。捕获证据的 `available_by` 只证明最迟在观察日可见，不伪造 `published_at`。Roadmap与目标档案有原生10/19变更记录，使用该修订起点；PBR精确发表日未确认，10/21新闻仅提供“本周已发布”的旁证。10/18基金文章中的“即将发布报告”计划按该旁证最迟于10/21退出当前计划。[日期证据与范围](../curation/source-availability.jsonl)、[带日期的新闻旁证](https://anthropic.com/news/christopher-stubbs-joins-long-term-benefit-trust)

## 复核、工程与验证边界

新增引文按原始抓取、完整衍生正文、passage偏移、引文SHA-256和claim绑定核对；**60条精选claim**另有AI上下文复核，**33个来源**有范围说明。这不等于所有新增句子经过人工语义审阅，人工Gold仍保持54条。[来源绑定验证](../audits/source-binding-verification.json)、[AI复核](../curation/claim-reviews.jsonl)、[来源范围](../curation/source-scope-notes.jsonl)

工程与评测部分的实现、实际运行证据及剩余限制由[总报告](../../../reviews/2026-10-30-update/report.zh-CN.md)记录；知识检查见[knowledge-checks.json](../../../reviews/2026-10-30-update/validation/knowledge-checks.json)，应用检查见[application-checks.json](../../../reviews/2026-10-30-update/validation/application-checks.json)，最终结论以[final.json](../../../reviews/2026-10-30-update/validation/final.json)为准。本说明不预填最终测试总数，不宣告整体问答质量、线上成本或生产效果已提升。

安装与本地工作区同步的实际结果分别以[installation.json](../../../reviews/2026-10-30-update/validation/installation.json)和[workspace-sync.json](../../../reviews/2026-10-30-update/validation/workspace-sync.json)为准。来源原始捕获、旧版本、旧状态登记和冻结发布均保留；日常查询使用自包含包，无需回读旧vault。默认检索按日期资格过滤，`show`可查原记录，`search --include-history`可显式查看历史；超过本轮截止日的查询需要重新核验。
