# 知识与时效成对 CLI 对照

本轮在冻结的知识 1.2.1 与 1.3.0 上实际运行了同一批 45 条公共 CLI 命令，各 45 次，共 90 次。主挑战结果为旧版 5/20、新版 20/20 个合格任务。这个分数衡量本次有意面向新增事实及日期边界构造的任务，不能外推为一般回答质量提升，也不意味着新版没有缺陷。后续诊断实际发现并修复了一项月精度日期错误。

## 冻结与评分依据

在执行两边 query CLI 前，冻结了 `protocol.md`、`cases.jsonl` 与 `native-exhibits.jsonl`，组合 SHA256 为 `714e9551b73688422322157cd7baecc795dc6b3f6785c72ea97487d947eeb4fb`；各文件哈希见 `preregistration.json`。事实依据来自原生来源的保留 passage、元数据及明确更正/生效日期，不来自新版 CLI 结果，也不以条目数量评分。构造任务不是外部盲测。冻结目录未修改。

`score_cli.py` 可从原始捕获重新评分，`case-scores.jsonl` 保存逐项结果。缺知识、未知 claim、无匹配和不支持选项分别记录；它们不计为错误事实或幻觉。合格结果包含覆盖与边界能力，因此不能与已有输出的事实准确率混读。

| 项目 | 旧 1.2.1 | 新 1.3.0 |
|---|---:|---:|
| 准确性挑战合格 | 1/8 | 8/8 |
| 时效挑战合格 | 0/8 | 8/8 |
| 旧知识 / no-op / unknown 控制 | 4/4 | 4/4 |
| 正向可用来源任务的默认 source recall@20 | 0/11 | 9/11 |
| 已展示且 exact quote 被 bound passage 支持的独立 claim | 2/2 | 17/17 |
| 已展示 claim 的 URL / passage identity 错配 | 0 | 0 |
| CLI 退出码 0 / 1 / 2 | 21 / 16 / 8 | 42 / 3 / 0 |

正向来源召回分母排除三个按原 rubric 应当被过滤的负例：系统提示、未来 AUP、归档 goals。它们单独判断排除行为。旧版的八次退出码 2 均为不支持日期选项的能力缺口；没有把它们算作事实错误。双方对不存在的查询/claim 都正确返回有界无匹配。

## 固定挑战逐项结果

| ID | 可核验任务 | 旧 | 新 |
|---|---|---:|---:|
| K01 | Matthew Schwartz 客座、BootLoops 归属，不升级为机构所有权 | 0 | 1 |
| K02 | RL auditor 的 pointwise reward hacking、pairwise 与 benign calibration 条件 | 0 | 1 |
| K03 | 独立 evaluator 的分层信息与出版权限 | 0 | 1 |
| K04 | 员工内部预期不是 Anthropic headcount 计划 | 0 | 1 |
| K05 | 不可能任务、scope、permitted actions 与 network boundaries | 0 | 1 |
| K06 | 跨卡 sandbox 的 14 次 / 7 次、rerun 与 CI 条件保留 | 0 | 1 |
| K07 | 蛋白设计 PDF 仍是机器/报告证据，不晋升 human-gold | 0 | 1 |
| K08 | 系统提示及指定模型回复不变成机构信念 | 1 | 1 |
| T01 | 7 月 simulation-belief 解释在截止日标为 corrected | 0 | 1 |
| T02 | 更正前日期的原解释及原 passage 可保留 | 0 | 1 |
| T03 | 10/8 公告与 11/12 生效区分 | 0 | 1 |
| T04 | AUP 在 10/18 未生效，11/12 的状态需截止日后核验 | 0 | 1 |
| T05 | 10/16 METR clarification 不泄漏到 10/15 | 0 | 1 |
| T06 | 截止日之后查询保留 verification_required | 0 | 1 |
| T07 | Dario 月日期无精确日时不虚构 publication day | 0 | 1 |
| T08 | previous goals 属历史，不能证明当前目标或完成 | 0 | 1 |
| C01 | 原有 gold claim 原文仍可 show | 1 | 1 |
| C02 | 原有 54 gold rows byte-identical | 1 | 1 |
| C03 | 不存在的无匹配查询合理拒绝 | 1 | 1 |
| C04 | 不存在的 stable claim ID 合理拒绝 | 1 | 1 |

支持性是本地绑定层面的检查：quote 确实出现在绑定 passage，claim 的 canonical URL 与 passage ID 对上原生 exhibits。没有实际生成用户答案，因此这里不能声称测得模型的回答幻觉率或引用选择率。K05 的原始 atom 将含 “have observed ... will pursue” 的表述标为 forecast；本轮只确认完整 passage 保留观察与边界，不把词法标签改写为新的研究结论。

## 没有提升及仍需扩大范围的地方

原有 54 条 human-gold 逐字节未变，双方 SHA256 均为 `a80170900edaa7a41c8583090ad87a14ee06cc95140b725ea6b47a5b32a40a3a`。旧知识的支持性、未知拒绝、指定模型示例排除均未显示提升。旧版缺新增来源时的 unknown 处理没有被判成错误。

新版默认 source recall 仍漏掉 K06 跨卡条件和 K07 PDF 条件；预注册的 `show --passage` 路径可以显示它们。事后扩大 `--include-reported --include-simulated` 的六次实际 CLI 调用单独保留在 `diagnostic-scopes.jsonl`，不混入主评分。三卡原生材料对照为 Opus 28 场景×7 次、Sonnet 28×7 次、Haiku 28×14 次；后两卡明确是当前评测 rerun，不能将不同卡百分比拼成统一安全排名。

## 诊断发现与修复：月精度不能制造更早可得性

原生《We Must Pace the Frontier》正文明确标为 “September 2026”，但 index 的 `source_published_at` 留空。冻结新版在 `--as-of 2026-08-31` 仍给 `eligible=true`，且未说明月内可得性不确定。首次证据保留于 `diagnostic-before.jsonl`。预注册 T07 只检验“不虚构精确日”，没有覆盖“该月之前”或“月内具体日已公开”的条件；这是主挑战未捕获的问题，不能把诊断当 holdout 提升。

修复仅修改知识运行时、derived registry/manifest、package 生成逻辑、知识说明与相关 tests。未改 locked 原文、claims 或 index payload。package 仅使用显式标注的 visible publication month 元数据生成 `publication_window`；任意 PDF cover/CV 日期不被升级为发布月。当前生成两条窗口：Dario 文章和 September threat-intelligence report。

| 实际变体 | 冻结新版 | 修复后工作版 |
|---|---|---|
| Dario as-of 8/31 | eligible=true | false，not_yet_published |
| Dario as-of 9/17 | eligible=true | false，publication_day_unconfirmed / uncertain |
| Dario as-of 10/1 | eligible=true | true，available；仍 unknown exact day |
| 独立 9 月报告 as-of 9/11 | eligible=true | false，publication_day_unconfirmed / uncertain |

月初只是 earliest possible bound，不被写成精确发布日期。月内不确定证据继续可通过 `show --passage` 或历史 scope 检查，默认搜索不把它认证为当日已公开。保留 wholly unknown 日期为 unknown。变体在执行前另登记并哈希，见 `diagnostic-variants.jsonl` 和 `.sha256`，其结果见 `diagnostic-month-boundary.jsonl`。新增 leap-year / 不同月份 / 非出版 PDF 日期控制。20 个知识 tests 及 bundled skill verifier 均通过；tests 输出见 `tests.json`。

本 worker 已更新工作 skill 的 registry 与 artifact hash，最终 release derived 数据和 manifest 链由 root 统一运行 `scripts/package_amind_refresh.py` 后验证；不需要改 source index payload。冻结旧/新比较输入保持不动。

跨审另发现 D04：package 原先把所有 status 的 target unit 都视为已经终止的旧版，新增 publication_window 会使未来月日期单位的修订漏掉 superseded。实际两个月单位与当前 revision prior 无交集，当前包没有触发；这是确定的规则交互回归。最小修复将跳过集合收窄到有 valid_until 的实际终止记录；publication_window 与 start-only effective_window 都不再挡住修订退出规则。保留已有政策 11/12 的明确终止日。独立 August 2026→10/18（含新加坡跨日）及 February 2024→3/4 合成版本链验证旧版按 until 退出、新版在观察日前不回溯，且保留月份窗口。前后生成与状态证据见 `diagnostic-revision-before.json` 和 `diagnostic-revision-after.json`，新增回归通过；该项仍属诊断，不改主挑战分数。

## 证据与后续实际 agent trials

- `raw-cli.jsonl`：90 次原始 argv、JSONL stdout、stderr、退出码和耗时。
- `native-exhibits.jsonl`：固定评分的来源、claim 与 passage 依据。
- `paired-scores.json` / `case-scores.jsonl` / `score_cli.py`：可重复分数。
- `diagnostic-*.jsonl`：事后缺陷及 scope 探索，明确不作 holdout。
- `agent-trials.jsonl`：知识 2 题、时效 2 题的用户输入与评分要点；已交 root 做隔离的实际模型试验，本 worker 未调用模型或网络。

限制：此次验证有界本地保留来源及检索能力，没有独立验证全网实时真实性、全部新 claims 的语义正确性或模型最终答案；不能以新增数据量证明质量，不能以 full score 宣称没有其他问题。
