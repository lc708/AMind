# AMind

## 戴上 Anthropic 的思考帽。

AMind 把 Anthropic 的公开思考方式带给每个人——帮你分析情况、给出建议、审查方案、解释立场、比较不同声音，并把推理回链到证据；但它不会冒充 Anthropic。

它建立在 **1,351 个公开分析单位、52,225 条来源绑定主张和 54 条逐条人工复核的代表证据**之上，而不是一段角色扮演提示词。

[English](README.md) · [阅读综合报告](release/amind-v1/reports/synthesis.zh-CN.md) · [查看人工复核证据](release/amind-v1/data/representative-evidence-review.jsonl)

## 在 Codex 中安装

把下面这行粘贴到 **Codex 对话框**，不是终端：

```text
$skill-installer install https://github.com/lc708/AMind/tree/main/skills/amind
```

安装后重启 Codex，然后直接问：

```text
Use $amind to think through this situation with the Anthropic lens: [描述你的情况]
```

你也可以自然提问；当问题需要 Anthropic 视角时，AMind 支持自动调用。

## 它能做什么

AMind 不只做决策审查：

```text
思考：如果用 Anthropic 的思路，我们应该怎样理解智能体上线问题？
建议：这个模型要不要开源？请给建议、条件和停止线。
审查：压力测试这份 AI 安全政策，它漏掉了什么？
解释：Anthropic 的公开材料如何看待 scaling 的不确定性？
比较：比较 Anthropic 机构口径、Dario Amodei 和 Jack Clark 的治理思路。
溯源：这项结论来自哪里？请给逐字引句、链接和 claim ID。
```

即便公开材料没有完全相同的先例，它也会给出有用建议，只是会诚实标记推断距离：

- **[公开立场 / Public position]**：有公开来源直接支持；
- **[强框架推断 / Strong framework inference]**：来自多份来源反复出现的机制；
- **[探索性外推 / Exploratory extrapolation]**：把公开原则用于一个新情况。

原则是：**建议可以大胆，来源必须透明。**

## 一个典型回答

> **建议**
>
> 分阶段上线。只有在贴近真实任务的评测和独立监控通过后，才扩大自主权限；在主要失败模式仍不可观察时，保留可逆退路。
>
> **[强框架推断]** Anthropic 的公开材料经常把不确定性转化为测量、分阶段承诺和相互独立的防线，而不是盲目加速或无限期停滞。
>
> **[探索性外推]** 对你的项目，这意味着按能力设置晋级闸门，并把终止权限交给上线团队之外的人。
>
> **什么会改变答案**
>
> 如果有强证据证明智能体不能执行不可逆操作，或监控能够稳定发现违规，就可以更快扩大范围。

## 它为什么不只是一段 prompt

AMind 用一套内部提炼方法把公开材料变成可用判断：

```text
有界公开语料
  → 来源绑定的原子主张
  → 声部与版本边界
  → 反复出现的机制与张力
  → 面向新情况的压力测试与建议
```

这套内部方法叫 **Nuwa / 女娲**。它只是一种构建方法，公开产品名始终是 **AMind**。

## Skill 里有什么

[`skills/amind`](skills/amind) 是一个约百 KB、可离线工作的紧凑包：

- 54 条逐条人工复核、带来源的代表证据；
- 9 个 Anthropic 公开思考主题；
- 5 个有界声部画像；
- 5 组不能被强行抹平的核心张力；
- 零依赖检索与完整性校验工具；
- 面向思考、建议、审查、解释、比较和溯源的回答规范。

直接检查证据：

```bash
python3 -B skills/amind/scripts/query.py summary
python3 -B skills/amind/scripts/query.py search "alignment faking" --limit 5
python3 -B skills/amind/scripts/query.py tensions
python3 -B skills/amind/scripts/verify.py
```

这些工具只使用 Python 标准库，不联网，也不会修改数据。

## 完整 AMind v1 研究包

Skill 是推理与使用界面；[`release/amind-v1`](release/amind-v1) 是完整审计与研究层：

- 1,804 个权威候选；
- 1,351 个去重分析单位，其中 1,348 个有正文、3 个为有证据边界的 unavailable 例外；
- 13,436 个证据段；
- 52,225 条带逐字引句、作品/版本身份和文件哈希的原子主张；
- 主题、声部、版本、矛盾、归属、评测和发布审计。

克隆后可检索全量数据：

```bash
git clone https://github.com/lc708/AMind.git
cd AMind

python3 -B release/amind-v1/amind.py summary
python3 -B release/amind-v1/amind.py search "model welfare" --limit 5
```

轻量 RAG 优先读取 [`representative-evidence-review.jsonl`](release/amind-v1/data/representative-evidence-review.jsonl)；全量检索则流式读取 [`atomic-claims.jsonl.gz`](release/amind-v1/data/atomic-claims.jsonl.gz)，并用 `analysis_unit_id` 连接 [`analysis-units.jsonl.gz`](release/amind-v1/data/analysis-units.jsonl.gz)。

## 其他支持 Agent Skills 的客户端

整个 Skill 是一个自包含目录。把 [`skills/amind`](skills/amind) 安装或复制到相应客户端的 skills 目录，再调用 `amind` 即可。不同客户端的目录和调用语法不同，但证据工具本身只需要 Python 3。

## 验证

```bash
python3 -B scripts/build_amind_skill.py --check
python3 -B scripts/test_amind_skill.py
python3 -B scripts/verify_amind_v1_release.py
```

紧凑证据内核由冻结的 AMind v1 确定性生成，每个数据文件都有 SHA-256 和行数清单。

## 许可证

AMind 的软件、原创文档、构建逻辑和 Skill 指令采用 [Apache License 2.0](LICENSE)。公开来源引句与第三方事实元数据的权利仍属于各自作者和出版方，不因本仓库而被重新授权；证据与商标边界见 [NOTICE](NOTICE)。

## 边界

- AMind 重建的是公开思考方式，没有 Anthropic 内部信息；
- 不以 Anthropic 第一人称说话，也不虚构未公开决定；
- 语料频次不等于组织共识或个人影响力；
- 机构口径不自动等于个人观点，个人文章也不自动等于机构政策；
- 紧凑 Skill 是代表性证据内核，对完备性敏感的研究请使用完整发布包；
- AMind 是独立公开研究项目，与 Anthropic 没有隶属或背书关系。

如果 AMind 让你的判断多了一层真正有用的视角，欢迎 **Star 这个仓库**，并分享一个“因为看清了证据距离而得到更好答案”的问题。
