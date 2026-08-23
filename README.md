# AMind

AMind 用可追溯证据重建 Anthropic 的思想结构：先冻结来源、正文、作品与版本边界，再抽取原子主张，最后进行跨文归纳。

## AMind v1

AMind v1 是一份**可验证的研究报告与证据数据包**。它不是模型、聊天应用或 Codex 技能，也不要求安装 Python 包。

截至 2026-08-23，首版发布闸门已经通过：

- 原始权威人口：1,804 个候选；
- 去重后分析人口：1,351 个单位，其中 1,348 个有正文、3 个是有证据边界的 unavailable 例外；
- 证据段：13,436 个；
- 原子主张：52,225 条，全部带逐字引句、passage、work、edition、正文与文件哈希；
- 归属审计：52,225/52,225 恰好一条；
- 等价组件：189 个；显式版本组件：1 个，两个版本均保留；
- 有界词汇对立候选：56 个，全部完成来源上下文裁决；
- 归纳主题：9 个；代表证据：54 条，全部逐条阅读完整绑定段落；
- 发布前分层校准样本：126 条；
- evaluation 与 release gate 均为 PASS。

首版的总体判断是：在这份有界语料中，Anthropic 的思想结构表现为一种制度化的谨慎——认真对待能力快速增长，提高机制和行为的可测性，让治理强度随证据与能力升级，并用相互独立的防线降低单点失败；最终仍以人的能动性、福利和社会分配约束技术目标。

## 怎么用

### 1. 只想看结论

直接阅读：

- [AMind v1 综合报告](release/amind-v1/reports/synthesis.zh-CN.md)
- [评测报告与诚实边界](release/amind-v1/reports/evaluation.zh-CN.md)

不需要克隆仓库，也不需要安装任何东西。

### 2. 想搜索具体观点或证据

克隆仓库后，使用自带的零依赖工具：

```bash
git clone https://github.com/lc708/AMind.git
cd AMind

python3 -B release/amind-v1/amind.py summary
python3 -B release/amind-v1/amind.py themes
python3 -B release/amind-v1/amind.py search "alignment faking" --limit 5
python3 -B release/amind-v1/amind.py show nuwa1-claim-f169332e5fa3d349672a254d
```

工具只使用 Python 标准库，不联网，也不会修改发布数据。`search` 可以检索主张、逐字引句、来源标题、canonical URL 与声部；加上 `--json` 可输出适合其他程序读取的 JSON/JSONL。

### 3. 想接入 AI、RAG 或研究流程

不需要安装技能。推荐按用途选择数据层：

- 小规模问答：读取 [`synthesis-evidence.jsonl`](release/amind-v1/data/synthesis-evidence.jsonl)，其中包含 54 条代表证据；
- 全量主张检索：流式读取 [`atomic-claims.jsonl.gz`](release/amind-v1/data/atomic-claims.jsonl.gz)；
- 补充来源信息：用 `analysis_unit_id` 连接 [`analysis-units.jsonl.gz`](release/amind-v1/data/analysis-units.jsonl.gz)；
- 回看上下文：用 `passage_id` 连接 [`passages.jsonl.gz`](release/amind-v1/data/passages.jsonl.gz)；
- 做主题过滤：连接 [`theme-membership.jsonl.gz`](release/amind-v1/data/theme-membership.jsonl.gz) 与 [`theme-catalog.jsonl`](release/amind-v1/data/theme-catalog.jsonl)。

AI 输出应保留 claim ID、逐字引句、来源标题和 canonical URL，不能只给脱离来源的总结。若未来提供 Codex/Claude 等平台的技能，它应只是这一数据接口的可选适配层，不是 AMind v1 的唯一使用方式。

### 4. 想验证发布包

只需 Python 标准库：

```bash
python3 -B scripts/verify_amind_v1_release.py
```

该命令逐项验证发布清单、字节数、SHA-256、JSONL 行数与确定性 gzip 回放。

## 发布包内容

发布包位于 [`release/amind-v1`](release/amind-v1)：

- `README.md`：包内快速使用说明；
- `amind.py`：零依赖浏览与检索工具；
- `reports/`：综合报告和评测报告；
- `data/`：分析单位、证据段、原子主张、主题、归属、版本和矛盾审计；
- `schemas/`：机器可读 schema；
- `manifest.json`：源文件和发布文件的 SHA-256、字节数与行数；
- `release-audit.json`：发布闸门及完整输出指纹。

## 兼容性命名

机器数据中的 `nuwa1-*`、`nuwa1804-*` 和 `nuwa-v1-*` 是首轮构建阶段形成的稳定内部 ID/schema 前缀。为避免破坏跨文件外键与审计哈希，AMind v1 保留这些兼容性标识；它们不是产品名，也不表示需要安装名为 Nuwa 的组件。

## 方法边界

- 普通引用、related links、导航、代码仓库和任意二跳外链不扩张原始 1,804 人口。
- 同一 URL、抓取记录、manifestation、edition 和 work 分开建模；标题、slug、模糊相似度或单独的正文 hash 不能擅自跨版本合并。
- 主题互不排斥；主张频次表示语料覆盖，不表示组织共识或作者权重。
- 机构口径不自动等同于个人观点；研究问题不当作已经得到的答案。
- 54 条报告代表证据经过完整段落语义复核；不声称 52,225 条主张全部经过逐条人工语义复核。
- 矛盾筛查是有界发现机制，不声称语义完备。
- GitHub 发布包不含约 13GB 的本地原始抓取与历史证据库；它包含复核首版结论所需的来源绑定段落、主张与哈希链。

## 维护者入口

- `release/amind-v1/`：可直接发布、检索和验证的数据包；
- `scripts/amind_v1.py`：包内检索工具的源文件；
- `scripts/verify_amind_v1_release.py`：独立发布校验器；
- `scripts/build_amind_v1_release.py`：公开发布包构建器；
- `corpus/` 与 `reports/`：本地完整证据和构建历史，不进入精简 GitHub 发布。
