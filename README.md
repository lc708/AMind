# AMind

AMind 用可追溯证据重建 Anthropic 的思想结构。它先冻结来源、正文、作品与版本边界，再抽取原子主张；只有在主张账本完成后，才用 Nuwa 做跨文归纳。

## Nuwa v1 已完成

截至 2026-08-21，首版发布闸门已经通过：

- 原始权威人口：1,804 个候选；
- 去重后分析人口：1,351 个单位，其中 1,348 个有正文、3 个是有证据边界的 unavailable 例外；
- 证据段：13,436 个；
- 原子主张：52,225 条，全部带逐字引句、passage、work、edition、正文与文件哈希；
- 归属审计：52,225/52,225 恰好一条；机构口径、个人声音、第三方引语、模拟证据、研究问题和嵌入样例分开处理；
- 等价组件：189 个；显式版本组件：1 个，两个版本均保留且不推断替代方向；
- 有界词汇对立候选：56 个，全部完成来源上下文裁决；
- 归纳主题：9 个；代表证据：54 条，全部逐条阅读完整绑定段落；
- 发布前分层校准样本：126 条；
- Nuwa v1 evaluation 与 release gate 均为 PASS。

首版的总体判断是：在这份有界语料中，Anthropic 的思想结构表现为一种制度化的谨慎——认真对待能力快速增长，提高机制和行为的可测性，让治理强度随证据与能力升级，并用相互独立的防线降低单点失败；最终仍以人的能动性、福利和社会分配约束技术目标。

## 读取发布包

发布包位于 [`release/nuwa-v1`](release/nuwa-v1)：

- [`reports/synthesis.zh-CN.md`](release/nuwa-v1/reports/synthesis.zh-CN.md)：Nuwa v1 首版综合；
- [`reports/evaluation.zh-CN.md`](release/nuwa-v1/reports/evaluation.zh-CN.md)：评测结果与诚实边界；
- [`data/synthesis-evidence.jsonl`](release/nuwa-v1/data/synthesis-evidence.jsonl)：54 条代表证据；
- [`data/atomic-claims.jsonl.gz`](release/nuwa-v1/data/atomic-claims.jsonl.gz)：52,225 条原子主张；
- [`data/passages.jsonl.gz`](release/nuwa-v1/data/passages.jsonl.gz)：来源绑定段落；
- [`manifest.json`](release/nuwa-v1/manifest.json)：每个源文件与发布文件的 SHA-256、字节数和行数；
- [`release-audit.json`](release/nuwa-v1/release-audit.json)：发布闸门。

校验发布包只需要 Python 标准库：

```bash
python3 -B scripts/verify_nuwa_v1_release.py
```

维护者在拥有完整本地证据库时，可重新构建最终各层：

```bash
python3 -B scripts/build_nuwa_v1_claim_audit.py --check
python3 -B scripts/build_nuwa_v1_synthesis.py --check
python3 -B scripts/build_nuwa_v1_evaluation.py --check
python3 -B scripts/build_nuwa_v1_release.py --check
```

## 方法边界

- 普通引用、related links、导航、代码仓库和任意二跳外链不扩张原始 1,804 人口。
- 同一 URL、抓取记录、manifestation、edition 和 work 分开建模；标题、slug、模糊相似度或单独的正文 hash 不能擅自跨版本合并。
- 主题互不排斥；主张频次表示语料覆盖，不表示组织共识或作者权重。
- 机构口径不自动等同于个人观点；研究问题不当作已经得到的答案。
- 54 条报告代表证据经过完整段落语义复核；不声称 52,225 条主张全部经过逐条人工语义复核。
- 矛盾筛查是有界发现机制，不声称语义完备。
- 本仓库的 GitHub 发布包不含约 13GB 的本地原始抓取与历史证据库；它包含复核首版结论所需的来源绑定段落、主张与哈希链。

## 与 `anthropic-mind` 的关系

AMind 没有用外部仓库预设的分类来生成结论。与 `bozhouDev/anthropic-mind` 相比，AMind 的主要优势是先做候选人口闭合、作品/版本去重、逐字证据回链、归属边界和可复算审计，再做归纳。参考项目可以在未来作为盲测对照，用于发现我们遗漏的主题或表达方式；它不是本版分类或结论的来源。

## 仓库结构

- `release/nuwa-v1/`：可直接发布和验证的首版数据包；
- `scripts/verify_nuwa_v1_release.py`：独立发布校验器；
- `scripts/build_nuwa_v1_{claim_audit,synthesis,evaluation,release}.py`：最终四层构建器；
- `config/nuwa-v1-*.json`：对应策略与 schema；
- `corpus/`：本地证据库，不进入 GitHub 提交；
- `reports/`：本地构建历史，不进入精简发布提交。
