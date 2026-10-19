# AMind 应用技能更新报告

日期：2026-10-18（新加坡）。本报告覆盖 **AMind Engineering 0.3.0 / AMind Eval Improve 0.4.0** 的实际实现、来源与验证边界。知识语料的新增数量、覆盖日期与清理结果由本轮知识更新报告单独记录，不计入本报告的应用能力增量。

**本轮已交付可执行的多代理响应合同、持久分阶段工作流、13 个任务模板与配置生成器，以及更严格的费用、评分器和阶段覆盖检查。当前离线检查共 127 项通过；没有运行真实目标／judge API、额外收费模型评测或新一轮独立技能行为比较。** 因此本轮证明的是具体本地合同已经实现并通过回归，不能据此宣称模型质量、实际费用、延迟或整体技能优于上游。

主要证据：[统一应用检查与包哈希](2026-10-18-application-checks.json)、[34 项工程回归](2026-10-18-engineering-checks.json)、[本轮总验证](2026-10-18-refresh-validation.json)。入口与实现：[Engineering](../skills/amind-engineering/SKILL.md)、[Eval Improve](../skills/eval-improve/SKILL.md)、[统一验证器](../scripts/verify_amind_application_skills.py)。

## 与上一版本相比

| 范围 | 上一版本 | 当前版本与实质变化 |
|---|---|---|
| 工程 | Engineering 0.2.1；已有工具循环、SQLite 副作用账本、状态／流式／批处理诊断 | **0.3.0**；根／子代理结果分离，原生 Multi-agent 模式限制与注入恢复合同；持久分阶段执行；来源／模板 onboarding；缓存和探针覆盖诊断 |
| 评测 | Eval Improve 0.3.0；已有应用／grader 运行器、配对比较、冻结选择、全尝试费用与报告 | **0.4.0**；精确计费范围与适配器、正负对照／基率／成对 judge／漂移、固定阶段分母、失败预算与结果身份 |
| 上游审计 | 2026-09-29 pin；81 文件、1,005 个章节定位项 | 工程审计更新至 2026-10-09 pin；**96 文件、1,346 个章节定位项**，保留旧 81 文件资料 |
| 离线检查 | 2026-09-30 修复后 **84 项** | 当前 **127 项**：应用／内核 93 项，工程行为合同 34 项 |
| 独立行为结论 | 12 组、24 次执行；未达到预登记的整体优于标准 | 本轮没有重做该比较，原结论保留 |

旧 84 项包含当时的 74 项应用／内核检查和 10 项工程问题回归。当前为 26 项应用技能检查＋67 项能力内核检查＋34 项工程问题回归，共 **127 项**；净增加 43 项检查。数量增加用于说明覆盖变化，不换算为能力提升比例。[旧 84 项记录](2026-09-30-post-behavior-kernel-checks.json)、[旧成对行为结果](2026-09-30-behavioral-acceptance-results.zh-CN.md)。

## Engineering 0.3.0：已实现的能力

### 1. 原生多代理响应、流式结果与工具合同

[response_contract.py](../skills/amind-engineering/scripts/response_contract.py) 现在区分单代理与 Multi-agent。多代理用户最终答案只取 `/root` 的 `phase:"final_answer"`；子代理的 final 不再误报任务完成，也不会拼入根代理答案。没有归属的信息保留在证据中，不猜测成根代理最终结果。

SSE 文本按事件或 output index 的 agent 归属分别投影；子代理文本进入独立轨迹。流事件之间、以及流事件与终态 output 的归属矛盾会被拒绝。完整原始响应、事件、hosted items 和未知 output items 仍被保留；未知项不会被误执行，未理解的项也不会自动使回答被认定为完整。

`multi_agent_call`、`multi_agent_call_output`、加密 `agent_message` 由托管运行时处理，不作为应用函数派发。现有工具循环只处理实际的 `function_call`，仍要求参数验证、授权、幂等键、预算和未知副作用核实；根／子代理的函数调用均计入应用派发预算。

新增 `validate_mode()` 在发请求前检查当前 Multi-agent 的明确限制：不支持独立 `/responses/compact`、`reasoning.summary` 或 provider `max_tool_calls`。该模式隐式启用各代理独立的自动压缩；并发数量不是费用或工具总次数上限。现有单代理压缩配方保留，但增加了适用模式边界。[具体配方](../skills/amind-engineering/references/response-recipes.md)、[当前官方 Multi-agent 文档](https://developers.openai.com/api/docs/guides/responses-multi-agent)。

新增 `InjectionTracker` 记录 WebSocket 注入、确认和 completion race。它保留未确认输出；`response_already_completed` 对应的准确输入进入后续 continuation；断连不成为重新执行外部工具的理由。参考实现一次只保留一个待确认注入，避免为没有 call ID 的确认事件猜测归属。它是离线状态合同，网络客户端、外部执行账本和 provider 取消仍由应用负责。

### 2. 可执行的分阶段工作流、恢复与覆盖率

[workflow_contract.py](../skills/amind-engineering/scripts/workflow_contract.py) 是真实的本地执行与 SQLite journal，不只是流程说明。规格固定 tenant、run、完整 item 集合、顺序阶段、依赖关系和原始尝试／时间预算。item 阶段只接收自身依赖结果；aggregate 阶段取得完整依赖结果和覆盖报告。

已实现并实测的失败合同包括：

- 调用前持久记录 `running`；崩溃或异常后保留未知结果，重启不盲目重放。外部结果查证后才可用证据进行 reconcile。
- 执行与 reconcile 共用 coordinator 排他锁；核实操作不能覆盖仍在执行的 handler。该实现使用 Unix 文件锁，生产分布式 worker 需采用相应租约／存储方案。
- 尝试次数跨重启累计，deadline 从首次开始时间计算且包含停机时间。授权后、派发前再次检查取消和时间。
- 取消事实持久保存；普通重启不会继续派发，只有显式恢复才能在原预算内继续。取消不能撤销已经发生的远端写入。
- 失败依赖使后续 item 保持 `not_covered`；未知依赖等待查证。成功的 synthesis 不会抹掉失败、遗漏或未知 item。
- 显式重试还要求 `retry_safe`、剩余预算及没有消费旧结果的下游执行；存在旧 synthesis 时要求新 run，防止复用过期汇总。

覆盖率取所有 required item 阶段成功集合的交集，报告保留每阶段计数、未覆盖 ID、剩余预算和停止原因。handler 必须验证实际产物；返回成功不构成模型质量证明。代码已通过公共 CLI 的 plan → 本地 demo 执行 → 重启复用路径检查。[运行与恢复说明](../skills/amind-engineering/references/workflow-recipes.md)。

### 3. 来源／模板 onboarding 与 13 条任务路线

[onboarding_contract.py](../skills/amind-engineering/scripts/onboarding_contract.py) 根据真实随包模板或已核查 URL 的设计提取，生成 `agent-config.json`、`workflow.json` 和说明文件。默认打印完整计划而不写目录；显式 `--write` 只写新的本地目录，已有目录被拒绝。它不抓取页面、不执行页面脚本、不复制凭证／远端资源 ID，也不创建云端部署或计划任务。

生成的是可提交的**应用配置合同和本地阶段规格**。它们不是未经验证的托管 API payload。实际 provider、模型、SDK、工具与凭证范围仍须结合用户已有应用实现 adapter；来源提出的工具或网络地址保持未启用状态。更新既有配置前，要求核查每个字段的 merge／replace／null-reset 语义，并分别核查容器、托管 web 工具和 MCP 网络范围。[onboarding 说明](../skills/amind-engineering/references/onboarding.md)。

13 个真实随包路线见 [模板索引](../skills/amind-engineering/references/templates.md) 和 [模板目录](../skills/amind-engineering/assets/templates/)：

| 路线 | 主要结果 |
|---|---|
| `bug-hunter` | 有文件／行与重现证据的缺陷 |
| `contract-tracker` | 条款、义务、日期与版本核对 |
| `data-analyst` | 数据质量与可重现计算 |
| `deep-researcher` | 一手来源、反证和未决问题 |
| `explainer-video-maker` | 核实后的脚本／分镜与媒体方案 |
| `field-monitor` | 有日期的快照与变化 |
| `incident-commander` | 事件证据、假设和获授权的恢复方案 |
| `performance-tuner` | 可比基线与正确性／性能核验 |
| `sprint-retro-facilitator` | 可归因证据与可衡量行动 |
| `structured-extractor` | 格式、业务含义与来源核验 |
| `support-agent` | 当前政策、真实账户证据与结果核实 |
| `support-to-eng-escalator` | 去重后的可重现工程报告 |
| `watchlist-scanner` | 完整 watchlist 分母与变化证据 |

这些模板改写了任务方法与检查项，不宣称复制 Claude Console 的完整产品能力。视频渲染、外部工单／回复、事故恢复和持续监测仍需实际适配器及对应任务授权；模板本身不会执行它们。

### 4. 缓存诊断与“没有测到”的识别

[cache_diagnostics.py](../skills/amind-engineering/scripts/cache_diagnostics.py) 检查捕获的 comparison identity、诊断状态及实际 cached token 计数。不存在、过期、不可用或身份不符的诊断保持未测／未定；`cache_hit` 不能单独证明实际复用或费用下降。comparison 参数不加载历史，也不改变缓存行为。[平台配方](../skills/amind-engineering/references/platform-operations.md)、[官方缓存诊断](https://developers.openai.com/api/docs/guides/prompt-caching/diagnostics)。

同一脚本的 `probe_coverage()` 检查目标是否出现、检查是否实际应用、账户／模型等范围是否兼容，以及整个预定样本是否有观测。API 200、零缺陷或状态项先被丢弃均不能自动通过。该方法吸收上游探针的有效性修正，但没有虚构 OpenAI 与 Claude 专属 reasoning-binding 字段等价。[状态诊断](../skills/amind-engineering/references/context-state.md)。

## Eval Improve 0.4.0：已实现的能力

### 1. 按实际计费范围核算

[price_usage.py](../skills/eval-improve/scripts/price_usage.py) 新增完整 `billing_identity`：provider、interface、model、service tier、region，及可选 context band。事件与价卡必须精确对应；重复平铺字段发生矛盾会被拒绝，同名模型不能跨 endpoint 或 tier 混价。

支持三个显式规范化适配器：文本 token、仅输入 token、指定计量单位。缓存写入必须声明是输入总量的子集还是独立计数；缓存／推理的重复字段必须一致。未知模态、未知单位、缺失价格／用量保持 unknown，不默认记零。工具、存储等可通过有价单位或已核实的额外费用计入，但不得重复计费。

旧三项文本价卡保留为 `legacy_model_only` 兼容路径。新接口／tier／region 需要完整身份，不强行套旧公式。[费用与校准说明](../skills/eval-improve/references/accounting-calibration.md)、[合成价卡](../skills/eval-improve/assets/accounting-demo/rates.json)。随包金额都是合成夹具，不是当前供应商报价；Decisions 的输入计费规则按[官方资料](https://developers.openai.com/api/docs/guides/decisions#pricing-and-availability)建立独立适配边界。

### 2. 校准评分器，也审查评分器本身

[calibrate_grader.py](../skills/eval-improve/scripts/calibrate_grader.py) 增加正／负对照分母、FPR／FNR、precision／recall、基率情景、成对 judge 改变和固定 judge 的 cohort 漂移检查。数据、grader、rubric hash 和 judge model 构成身份；混合身份、成对缺失和重复人类裁定冲突会被拒绝。

缺少干净阴性、顺序交换或重复稳定性检查时明确标为 unmeasured。基率参数只计算给定 prevalence 下的情景精度，不估计实际用户流量；paired／drift 输出是描述性证据，不自动给出总体提升或显著性结论。`ready_for_review` 也不等于人工认可。相关指南加入“奖励发现数量可能促使审计器编造问题／利用 rubric”的反例要求。

### 3. 固定阶段分母、失败预算与结果身份

[run_eval.py](../skills/eval-improve/scripts/run_eval.py) 的 coverage 合同同时固定 required stage 和来自原任务／工作流规格的 `expected_totals`。应用报告必须有对应阶段、完整成功计数和空的未覆盖清单；把两个 worker 裁成一个后自报 1/1 不能通过。逐 item 身份仍应由保存的工作流与产物证据核查，单纯数量相同不能证明成员相同。

新增 `limits.max_failed_attempts`，从持久尝试账本重建，失败、已核实的 abandoned／cancelled 尝试跨 resume 继续计数。并发中已启动的工作可能在达到上限后结束，限额不承诺取消已运行远端请求。

应用和 judge 可分别钉住实际 model／billing identity，结果行绑定 comparison hash、treatment hash、case 和 repetition。严格比较器核对行身份，报告显示计费身份、阶段检查与剩余失败预算。[运行合同](../skills/eval-improve/references/runner.md)、[结果与比较合同](../skills/eval-improve/references/artifacts.md)。

### 4. 退役服务保留迁移路径

新增[平台生命周期与导出指南](../skills/eval-improve/references/platform-lifecycle.md)：现有 Evals／Agent Builder 项目先导出数据、人工标签、rubric、配置、结果、轨迹和用量，再验证替代应用入口；不删除历史结果，也不把旧 dashboard 分数直接冒充新运行器的兼容结果。

截至本轮核查，[官方退役页](https://developers.openai.com/api/docs/deprecations)仍列 Evals 2026-10-31 只读、2026-11-30 关闭；reusable prompt objects／`v1/prompts` 和 Agent Builder 计划于 2026-11-30 关闭。此类接口保留兼容／导出用途，新评测优先使用现有项目评测器或本地运行器。本地技能没有因此失去数据集、grader 或 prompt 优化方法，也没有引入这些退役服务作为新依赖。

## 相向审查发现与修复

两名实现者相互只读审查另一侧新增代码，并以具体失败输入复现后由对应作者修复。它不是外部独立盲评，也不替代后续真实应用验收。

| 发现 | 修复及验证 |
|---|---|
| 流事件将 index 归为 root，终态同一 index 却为 child，子文本仍可能进入流视图 | 终态 output 归属与流 index 核对，矛盾拒绝；加入专门回归 |
| reconcile 可覆盖仍处于执行中的 handler | reconcile 取得同一 coordinator 锁；活跃执行时拒绝并发核实写入 |
| 阶段只核对自报 total，裁掉 worker 后仍可声称完美覆盖 | 固定卡内 expected totals；短分母和失败／未知阶段进入 coverage error |
| 完整 billing identity 与重复平铺的 endpoint／tier／region 等矛盾，仍可能被当作精确费用 | 逐项拒绝矛盾；同时核对重复 cache／reasoning 计数 |

工程自查还补充了持久取消、显式恢复、item 依赖上下文范围及旧 synthesis 不随上游重试复用等合同。全部修复进入当前回归；没有通过修改旧 84 项报告或旧成对成绩来制造提升。

## 来源固定、历史与许可证

工程当前上游为 [`dbd4588f9e1033efb41dad4bef2f7947c8993d44`](https://github.com/anthropics/skills/tree/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/claude-api)，时间 2026-10-09T18:45:49Z。相对 2026-09-29 pin 是 3 个提交、48 个修改文件＋15 个新增文件。新增包含两份 onboarding 指南和 13 份 quickstart；实质方法包括 URL／模板建模、动态分阶段工作、探针未测状态、网络作用域和配置替换语义。[不可变差异](https://github.com/anthropics/skills/compare/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4...dbd4588f9e1033efb41dad4bef2f7947c8993d44)。

当前完整索引包含 **96 个文件的 SHA-256 和 1,346 个 Markdown 章节定位项**；本轮已使用该固定提交的实际文件核对哈希。[当前能力地图](../skills/amind-engineering/references/capability-map.md)、[机器索引](../skills/amind-engineering/references/upstream-capabilities.json)、[检查脚本](../scripts/check_amind_capability_map.py)。文件和章节数量是来源覆盖证据，不是每项服务已实跑或逐条语义等价。

旧提交 `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4` 的 [81 文件索引](../skills/amind-engineering/references/upstream-capabilities-2026-09-29.json) 和[原能力地图](../skills/amind-engineering/references/capability-map-2026-09-29.md)原样保留；9 月行为验收仍对应当时的冻结技能。Eval 的原工作流和未改字节的 lite reporter 保留原来源归属；0.4.0 的本地新方法另行说明，不把其历史来源悄悄改成新版本。[工程来源](../skills/amind-engineering/references/sources.md)、[评测来源](../skills/eval-improve/references/upstream.md)。

两套技能均保留 Apache-2.0 许可证和来源声明。Claude 的固定模型默认值、字段、headers、托管工作流事件、限制数字及 CLI 审批流程没有被当作 OpenAI 等价复制。

## 复现命令

以下命令从仓库根目录运行。变量仅指向本仓库和新建的临时输出，不需要 SDK、模型凭证或云端部署。

```bash
python3 -B scripts/verify_amind_application_skills.py --output reviews/2026-10-18-application-checks.json
python3 -B scripts/test_amind_behavior_regressions.py --json reviews/2026-10-18-engineering-checks.json
python3 -B scripts/check_amind_capability_map.py
python3 -B scripts/check_amind_capability_map.py --inventory skills/amind-engineering/references/upstream-capabilities-2026-09-29.json
```

来源检查默认核对索引及本地资源引用。若要再次核实上游字节，取得上述固定 SHA 的 `skills/claude-api/` 目录，传入 `check_amind_capability_map.py --upstream /absolute/path/to/claude-api`；不要使用移动中的 main 内容来校验固定索引。

生成配置、运行本地阶段并重启复用：

```bash
ENGINEERING=skills/amind-engineering
DEMO_DIR="$(mktemp -d)"
python3 -B "$ENGINEERING/scripts/onboarding_contract.py" --list
python3 -B "$ENGINEERING/scripts/onboarding_contract.py" --template contract-tracker --output "$DEMO_DIR/draft"
python3 -B "$ENGINEERING/scripts/onboarding_contract.py" --template contract-tracker --output "$DEMO_DIR/draft" --write
python3 -B "$ENGINEERING/scripts/workflow_contract.py" --spec "$DEMO_DIR/draft/workflow.json" --db "$DEMO_DIR/draft/demo.sqlite"
python3 -B "$ENGINEERING/scripts/workflow_contract.py" --spec "$DEMO_DIR/draft/workflow.json" --db "$DEMO_DIR/draft/demo.sqlite" --execute-demo
python3 -B "$ENGINEERING/scripts/workflow_contract.py" --spec "$DEMO_DIR/draft/workflow.json" --db "$DEMO_DIR/draft/demo.sqlite" --execute-demo
```

两次 demo 的成功项和尝试计数保持复用，不创建模型调用。占位 tenant／run 和示例 item 只用于该本地 demo；真实接入应使用认证后的身份、选定输入和实际 adapter。

费用／校准示例与完整离线评测：

```bash
EVAL=skills/eval-improve
python3 -B "$EVAL/scripts/price_usage.py" --events "$EVAL/assets/accounting-demo/events.jsonl" --rates "$EVAL/assets/accounting-demo/rates.json"
python3 -B "$EVAL/scripts/calibrate_grader.py" "$EVAL/assets/accounting-demo/labels.jsonl" --population-prevalence 0.01
FLOW_DIR="$(mktemp -d)/validation"
python3 -B "$EVAL/scripts/run_eval.py" --card "$EVAL/assets/offline-demo/experiment.json" --flow "$FLOW_DIR" --variant baseline --split val
python3 -B "$EVAL/scripts/run_eval.py" --card "$EVAL/assets/offline-demo/experiment.json" --flow "$FLOW_DIR" --variant baseline --split val --execute
python3 -B "$EVAL/scripts/run_eval.py" --card "$EVAL/assets/offline-demo/experiment.json" --flow "$FLOW_DIR" --variant v1 --split val --execute
python3 -B "$EVAL/scripts/compare_runs.py" --flow "$FLOW_DIR" --candidate v1 --split val --all-metrics --reps 1
python3 -B "$EVAL/scripts/report_eval.py" "$FLOW_DIR"
```

这些命令运行随包合成 Python 应用、确定性评分器和本地报告；结果仅说明运行链和合同成立。真实应用的评分器校准、费用和质量比较需另有实际数据与获授权预算。

## 尚未由本轮证据证明的事项

- 没有调用真实目标／judge API，未验证当前账户对 Beta、托管 Agents、Decisions、Multi-agent、Ultrafast 等的实际访问或生产运行。接口细节来自当前一手文档；本地夹具验证不等于真实 provider 兼容。
- 没有运行额外收费模型评测、新一轮独立技能行为验收或性能基准；正常编排会话自身的资源消耗不作为应用 API 账单或比较证据。
- 本地 CLI `0.163.0 --help` 已核对相关 flags，但没有因此宣称 JSONL schema、取消、hooks 或全语言 SDK 已实跑兼容。八语言资料仍不是八语言编译证明。
- Workflow 是本地顺序协调参考；生产并发、分布式租约、传输中断、远端取消、工具副作用和完整账单须由实际 adapter／基础设施验证。预算限制新派发，不能撤销已发生的远端动作或保证发票上限。
- 本地测试、配置生成与文件哈希不能证明模型任务质量。原 24 次成对执行未达成整体优于标准的结论保留，本轮未作新的全面优越性判断。
