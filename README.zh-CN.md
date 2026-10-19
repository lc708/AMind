# AMind

## 戴上 Anthropic 的思考帽。

**AMind 是一个有证据链的 Agent Skill：它把 Anthropic 的公开思考方式变成可用于你自己 AI 决策的判断，并让每一步推断都能回到来源。** 它不会冒充 Anthropic。

普通角色提示词会把事实和猜测混在一起。AMind 会把两者之间的距离标出来，同时仍然给你明确建议。

<p align="center">
  <a href="https://github.com/lc708/AMind/stargazers"><img src="https://img.shields.io/github/stars/lc708/AMind?style=flat-square&color=D97757" alt="GitHub stars"></a>
  <a href="skills/amind"><img src="https://img.shields.io/badge/Agent%20Skill-AMind-D97757?style=flat-square" alt="AMind Agent Skill"></a>
  <a href="skills/amind/data/manifest.json"><img src="https://img.shields.io/badge/source--bound%20evidence-offline%20index-71C4A5?style=flat-square" alt="离线完整证据索引；当前数量见 manifest"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-8D96A5?style=flat-square" alt="Apache License 2.0"></a>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="#60-秒开始">安装</a> ·
  <a href="#一个回答是什么样">查看回答</a> ·
  <a href="release/amind-v1/reports/synthesis.zh-CN.md">阅读综合报告</a> ·
  <a href="release/amind-v1/data/representative-evidence-review.jsonl">检查人工复核证据</a>
</p>

![AMind 把一个问题转化为带证据距离标签和可追溯来源的建议](assets/amind-hero.svg)

## 60 秒开始

AMind 现已包含 **AI 工程与评测技能系列**：[`amind-engineering` 0.3.2](skills/amind-engineering/SKILL.md) 负责提示词审查、迁移、多代理合同、持久分阶段工作流及 13 个任务模板；[`eval-improve` 0.4.3](skills/eval-improve/SKILL.md) 负责应用／评分器评测、精确计费范围、评分器校准和严格比较。对象是 AI 产品及其行为，不要求产品使用 Codex harness；两者都无需 Claude。安装和中文用例见[系列说明](AMIND-SERIES.md)，实际实现与验证见[10 月应用更新报告](reviews/2026-10-18-application-update.zh-CN.md)。下方知识技能保留独立版本与资料边界。

AMind **1.3.1** 的公开资料观察截止到 **2026-10-18**，增加带日期的当前回答资格判断，同时保留被更正或取代的历史证据。详见[10 月知识更新报告](release/amind-v1-increment-2026-10-18/reports/update.zh-CN.md)；[9 月 1.2.1 更新](release/amind-v1-increment-2026-09-08/reports/update.zh-CN.md)与原始 v1 继续作为历史快照保留。当前包的总量、哈希和截止日期以 [manifest](skills/amind/data/manifest.json)、`summary` 和 `stats` 命令为准；这不意味着已经配置周期联网更新。

先安装 [Git LFS](https://git-lfs.com/)，再获取完整知识索引：

```bash
git lfs install
git clone https://github.com/lc708/AMind.git
cd AMind
git lfs pull --include="skills/amind/data/amind-full-index.sqlite3"
python3 -B skills/amind/scripts/verify.py
```

让 **Agent** 安装这个已验证工作区中的本地 `skills/amind` 文件夹，或将它复制到客户端的 skills 目录。索引必须是完整 SQLite 文件，不能是 LFS 指针。源码 ZIP 或使用 GitHub 归档的安装器可能只取得指针；验证失败时请改用上面的 Git LFS 工作区。

安装完成后，如有需要就重新加载 Agent 或开启新会话，然后拿一个真实问题来试：

```text
用 $amind 压力测试我们的自主智能体上线方案。
请给出明确建议、失败条件和来源。
```

安装就是这些。随 Skill 附带的证据工具只使用 Python 标准库，查询时不联网，也不需要额外 API Key。

> [!TIP]
> 当问题确实需要 Anthropic 视角时，AMind 支持自动调用；第一次体验时直接点名 `$amind` 最稳定。

## 一个回答是什么样

如果你问一个自主智能体是否应该扩大上线范围，AMind 会这样回答：

> **建议**
>
> 分阶段上线。只有在贴近真实任务的评测和独立监控通过后，才扩大自主权限；在主要失败模式仍不可观察时，保留可逆退路。
>
> **[强框架推断 / Strong framework inference]** Anthropic 的公开材料反复把不确定性转化为测量、分阶段承诺和相互独立的防线，而不是盲目加速或无限期停滞。
>
> **[探索性外推 / Exploratory extrapolation]** 对你的项目，这意味着按能力设置晋级闸门，并把终止权限交给上线团队之外的人。
>
> **什么会改变答案**
>
> 如果有强证据证明智能体不能执行不可逆操作，或监控能够稳定发现违规，就可以更快扩大范围。
>
> **来源示例**
>
> *Auditing language models for hidden objectives* · 2025-03-13 · [原始来源](https://www.anthropic.com/research/auditing-hidden-objectives) · `nuwa1-claim-04ed2efdb6c2574083bf375d`

每一项关键结论都会带一个证据距离标签：

| 标签 | 含义 |
|---|---|
| **[公开立场 / Public position]** | 有带引文的公开来源直接支持。 |
| **[强框架推断 / Strong framework inference]** | 来自多份来源反复出现的机制。 |
| **[探索性外推 / Exploratory extrapolation]** | 把公开原则用于没有完全相同先例的新情况。 |

它的工作原则很简单：**建议可以大胆，来源必须透明。**

## 一个 Skill，六种用法

```text
思考：如果用 Anthropic 的思路，我们应该怎样理解自主智能体上线问题？
建议：这个模型要不要开源？请给建议、条件和停止线。
审查：压力测试这份 AI 安全政策，它漏掉了什么？
解释：Anthropic 的公开材料如何看待 scaling 的不确定性？
比较：比较 Anthropic 机构口径、Dario Amodei 和 Jack Clark 的治理思路。
溯源：这项结论来自哪里？请给逐字引句、链接和 claim ID。
```

即使公开材料里没有完全相同的先例，AMind 也会给出建议，只是会诚实标记它走出了直接证据多远。

## 为什么不直接用角色提示词

| | 角色提示词 | 通用搜索 / RAG | AMind |
|---|---|---|---|
| 给出明确建议 | 可以 | 取决于你的实现 | **可以** |
| 区分公开事实与推断 | 很少 | 需要自己构建 | **内置** |
| 区分机构、个人与版本 | 不会 | 需要自己构建 | **内置** |
| 保留张力与反向证据 | 很少 | 需要自己构建 | **内置** |
| 回链逐字引句和稳定 ID | 不会 | 可以实现 | **内置** |
| 使用有界、可检查的语料 | 不会 | 取决于实现 | **会** |
| 最适合实时新事实 | 不适合 | **接入实时来源后适合** | 不适合——每份证据包都有明确截止日期 |

AMind 有意保持边界：它不要一个看似新鲜却无法溯源的人格表演，而要一套你能检查、质疑和复算的证据。

## 按你的目标选择入口

| 你想做什么 | 从这里开始 |
|---|---|
| 分析一个真实决策 | [安装 Skill](#60-秒开始) |
| 理解重建出的思考框架 | [阅读综合报告](release/amind-v1/reports/synthesis.zh-CN.md) |
| 做轻量 RAG 或评测 | [使用 54 条人工复核 Gold 证据](release/amind-v1/data/representative-evidence-review.jsonl) |
| 检索完整语料 | [使用 Skill 的本地索引](#检查带索引的-skill) |
| 审计构建方法和边界 | [阅读评测报告](release/amind-v1/reports/evaluation.zh-CN.md)和[发布审计](release/amind-v1/release-audit.json) |

## 它怎样工作

AMind 用一套内部提炼方法把公开材料变成可用判断：

```text
有界公开语料
  → 来源绑定的原子主张
  → 声部与版本边界
  → 反复出现的机制、反向证据与张力
  → 面向新情况的压力测试与建议
```

这套方法会把机构立场与个人声音分开，保留明确修订和反向证据，也不会把研究问题包装成已经确定的答案。

内部方法叫 **Nuwa / 女娲**；公开产品名始终是 **AMind**。

## 可检查的证据与明确的边界

安装后的 Skill 已包含完整本地搜索索引；54 条证据仍是逐条人工复核的 Gold 层。当前数量、哈希与观察截止日期记录在 [manifest](skills/amind/data/manifest.json)，各日期发布包保留原始审计和研究历史。

| 数据层 | 权威口径 |
|---|---|
| 当前分析单位、证据段与索引主张 | manifest 的 `counts`；`query.py summary` |
| 来源与声部分布 | `query.py stats --json` |
| 人工复核的代表证据 | 54 条，保留原 Gold 层 |
| 主题、声部与张力 | manifest 的 `counts`；对应查询命令 |
| 更正、取代与生效日期 | manifest 绑定的 `current-status.jsonl` |
| 历史候选与数量 | 原始 v1 及各日期增量报告 |

这里对“人工复核”的表述是刻意收紧的：54 条 Gold 证据全部在完整段落语境中逐条复核；其余索引主张经过结构化、来源绑定和归属审计，没有声称全部由人逐条复核。Skill 同时携带绑定段落，供使用前检查上下文；新增机器检查资料不会因为进入索引就变成人工 Gold。

### 检查带索引的 Skill

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

默认查询使用完整索引，按 manifest 截止日期过滤当前回答资格，并折叠已审计等价项、排除来源仅仅转述的观点、分散文章／声部／域名占比。`--current` 在这个边界内优先近期可用证据，不会联网取新事实；`--as-of YYYY-MM-DD` 根据记录的发表、更正和生效日期判断指定日期的资格；`--include-history` 保留并标记失效或尚未生效的资料，原文不会被删除。指定日期晚于资料截止时仍需另行核实。引用前可用 `show <claim-id> --passage` 检查原始绑定段落与状态。

### 审计原始发布包

```bash
git clone https://github.com/lc708/AMind.git
cd AMind

python3 -B release/amind-v1/amind.py summary
python3 -B release/amind-v1/amind.py search "model welfare" --limit 5
python3 -B release/amind-v1/amind.py show nuwa1-claim-f169332e5fa3d349672a254d
```

以上命令审计的是原始 v1 历史快照。小型高可信评测优先读取 [`representative-evidence-review.jsonl`](release/amind-v1/data/representative-evidence-review.jsonl)。自定义当前检索应选择 [manifest](skills/amind/data/manifest.json) 指向的发布包：目前为 [`atomic-claims.jsonl.gz`](release/amind-v1-increment-2026-10-18/data/atomic-claims.jsonl.gz) 连接 [`analysis-units.jsonl.gz`](release/amind-v1-increment-2026-10-18/data/analysis-units.jsonl.gz)，并应用 manifest 绑定的时效资格与归属过滤，详见[检索规则](skills/amind/references/retrieval.md)；也可以直接使用已实现这些规则的 `query.py`。未经筛选的原始流包含历史与转述内容，不能直接用于回答当前机构立场。

## 跨 Agent 使用

[`skills/amind`](skills/amind) 是一个自包含的 Agent Skill。有能力的 Agent 可以按照自己的约定完成安装；支持 Agent Skills 文件夹格式的客户端，也可以把该目录复制或安装到对应的 skills 目录，然后调用 `amind`。不同客户端的目录和调用语法不同；证据工具本身只需要 Python 3。

## 验证或开发

```bash
python3 -B skills/amind/scripts/verify.py
python3 -B scripts/verify_amind_increment.py
python3 -B scripts/verify_amind_refresh.py
python3 -B -m unittest scripts.test_amind_skill scripts.test_amind_increment scripts.test_amind_refresh scripts.test_amind_refresh_sources
python3 -B scripts/verify_amind_v1_release.py
python3 -B scripts/verify_amind_increment.py --historical
python3 -B scripts/verify_amind_application_skills.py --output .codex-tmp/application-checks.json
```

完整 SQLite 索引合并原始 v1 与截至当前 manifest 的各日期增量；54 条 Gold 保留原样，被更正或取代的证据也保留原始身份与段落。每个数据文件都有 SHA-256 和行数清单。`verify_amind_increment.py` 选择当前包的验证器，`--historical` 独立检查 9 月快照。当前离线验证合计 **220 项测试**：160 项应用检查和 60 项知识／来源检查。应用检查使用本地夹具、没有真实模型调用。历史[10 月 18 日新旧对照报告](reviews/2026-10-18-comparison/report.zh-CN.md)记录了所测知识／时效任务和 helper 合同的改善；技能引导的模型工程与评估任务持平。对照共 24 次 CLI 任务执行，覆盖 12 个配对任务，每个任务每版仅运行一次，不能据此声称普遍优于旧版。

工作场景三轮对照经评分语义修正后，工程仅网关出现一次拒绝合同差异，其余工程／评测任务持平；政策题的引用支持有所改善。42 次主执行、6 次确认、评分器修正与工具配置偏差见[工作场景评估报告](reviews/2026-10-19-workplace/report.zh-CN.md)。

原始执行文件以[带校验清单的评审归档](reviews/2026-10-19-shipping/README.md)保留；新工作区打开原始运行链接前，先执行 `python3 -B scripts/restore_amind_review_artifacts.py --apply`。恢复只复制普通文件，不执行捕获的代码。

## 边界

- AMind 重建的是公开思考方式，没有 Anthropic 内部信息；
- 它不以 Anthropic 第一人称说话，也不虚构未公开决定；
- 原始 v1 和各次增量都是有日期的研究快照，当前回答过滤依据已记录的状态，不能核实截止日期之后的政策；
- 语料频次不等于组织共识或个人影响力；
- 机构口径不自动等于个人观点，个人文章也不自动等于机构政策；
- 只有 54 条 Gold 证据经过逐条人工复核；全量索引结果在关键使用前仍需检查绑定段落；
- AMind 是独立公开研究项目，与 Anthropic 没有隶属或背书关系。

<details>
<summary><strong>常见问题</strong></summary>

### AMind 是 Anthropic 官方软件吗？

不是。它是一个完全基于公开材料的独立开源项目。

### AMind 是一个模型吗？

不是。它由 Agent Skill、完整本地证据索引、Gold 证据内核、检索规范和可审计研究发布组成，需要在有能力的宿主模型中使用。

### Skill 里是不是只有 54 条证据？

不是。Skill 检索完整本地索引并携带绑定段落，当前总量请查看 `query.py summary` 或 manifest。54 条只是经过人工逐条复核、用于校准与评测的 Gold 层。

### 为什么 Jack Clark 经常出现？

Import AI 包含许多期刊，而部分长篇技术论文又会被拆成数百条主张。原子主张数量不代表个人影响力；Jack Clark 自己的观点与他转述、引用的观点仍有区分。当前分布请运行 `query.py stats --json`，历史分布保留在各日期报告中。默认检索排除转述，并限制同一文章、声部和域名的结果数量。详见[检索规范](skills/amind/references/retrieval.md#distribution-audit)。

### 它会声称还原 Anthropic 的内部思考吗？

不会。它只重建公开证据中反复出现的模式，并标记每一步超出直接证据的距离。

### 不安装 Skill，也能使用数据吗？

可以。带索引的 Skill 与原始发布工具都可独立运行，只依赖 Python 标准库，也能直接接入研究或 RAG 工作流。

</details>

## 参与、引用或报告问题

- 发现来源、归属或版本问题？提交一条[证据修正](https://github.com/lc708/AMind/issues/new?template=evidence_correction.yml)。
- 有值得加入的真实问题或集成想法？阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，再提交[功能建议](https://github.com/lc708/AMind/issues/new?template=feature_request.yml)。
- 在研究中使用 AMind？引用信息见 [`CITATION.cff`](CITATION.cff)。
- 发现安全问题？请按 [`SECURITY.md`](SECURITY.md) 私下报告，不要公开开 Issue。

## 许可证

AMind 的软件、原创文档、构建逻辑和 Skill 指令采用 [Apache License 2.0](LICENSE)。第三方引句、公开网页／PDF 抓取件、提取文本与事实元数据的权利仍属于各自作者和出版方，不因本仓库而被重新授权；证据与商标边界见 [NOTICE](NOTICE)。

如果 AMind 让你的判断多了一层真正有用的视角，欢迎 **[Star 这个仓库](https://github.com/lc708/AMind)**，并分享那个“因为看清证据距离而改变答案”的问题。
