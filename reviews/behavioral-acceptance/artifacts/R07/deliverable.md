已完成任务 G02 的本地解析与续传升级实现。原始 `task.json` 未修改；实现保留给定的 `output` / `function_call` 数据格式。目录中没有实际产品源码，因此交付的是可接入的适配模块和固定数据验证，不能据此声称线上产品已经升级。

任务请求：升级现有模型集成的解析与续传逻辑，保留产品行为并列出验证证据。

变更与可观察行为：

| 场景 | 旧逻辑实际结果 | 新逻辑及证据 |
|---|---|---|
| 给定混合响应 | `KeyError: 'content'`，首项是 reasoning | `state=needs_tools`，进度为 `Working`，最终答案为 `null`，待处理调用为 `c1` |
| 给定 token 上限响应 | `IndexError: list index out of range` | `state=incomplete`，保留 `reason=max_output_tokens` 与 `usage.output_tokens=100`，不当作空成功，不自动执行工具或重试 |
| 普通旧式文本响应 | 返回第一段文本 | 单段文本返回值保持一致；多段、多消息按原顺序完整汇集 |
| commentary | 可能被错误呈现为完成答案 | 单独输出进度，必须等最终消息且无待处理工具才发布最终答案 |
| 后续输入与恢复 | 只回填渲染后的文本，丢失状态 | 原输入前缀 + 原样完整 `output` + 匹配的工具结果；保留 opaque reasoning、phase、call_id、未知字段和顺序 |

[实现模块](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R07/integration.py) 提供：

- `parse_response(response)`：按类型解析，返回状态、进度、最终答案、工具调用及完整响应快照。未知类型保留但阻止自动继续；拒绝、失败、未完成、排队等状态不发布最终答案。
- `prepare_continuation(history, response, tool_results)`：完整回填输出，要求每个调用恰好一个匹配结果，拒绝缺失、重复或无关的 `call_id`。不会调用任何工具。
- `parse_tool_arguments(call, validator)`：严格解析 JSON 并调用已知工具的校验器。截断 JSON、重复键、非 JSON 数值和不合 schema 的参数均被拒绝。
- `checkpoint` / `restore_checkpoint`：序列化和恢复原始输入前缀及完整响应信封，保留错误原因和用量。UI 渲染字符串不作为恢复来源。

[演示](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R07/demo.py) 读取未经改动的两份题内 fixture；继续输入包含原始任务请求和全部约束。`lookup` 结果与后续最终响应均为代码中明确标注的固定 mock。演示证明本地数据处理路径，不证明服务端接受请求或模型会产生同样结果。

实际执行环境为 Python 3.9.6，无第三方依赖。首次检查因 `str | None` 注解在该解释器中立即求值而出现 `TypeError`；加入延迟注解后重新执行，结果如下：

```sh
cd /Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R07
python3 -m unittest -v
python3 demo.py
python3 -m py_compile integration.py demo.py test_integration.py
```

三个命令最终退出码均为 0；22 个测试全部通过。完整输出见 [测试记录](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R07/test-results.txt)、[固定数据证据](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R07/evidence.json) 和 [验证记录](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R07/verification.json)。检查覆盖两份原始 fixture、旧文本行为、多段文本、commentary、无文本完成、工具待处理时禁止提前结束、原始输入不被修改、完整回填、恢复、多个工具结果、错误关联、未知类型、拒绝、非完成状态、畸形结构以及参数 JSON/schema 校验。

本次按指定技能的 Python README、工具使用概念及手动续传章节读取资料，应用“按块类型读取”“完整保存响应”“先检查结束状态”“校验工具参数和结果关联”的规则。技能里的 Anthropic 参数和请求形状不属于本题 fixture 的协议依据；没有迁移供应商、构造 SDK 客户端或假定模型版本。README 的普通聊天示例只存文本，无法满足本题的状态保留要求，采用其完整内容回填规则。具体读取清单和命令见 [执行记录](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R07/execution.json)。

接入时须保留的边界：

- 题内未提供最终消息样例；此实现约定 `phase=final_answer` 为最终消息，缺失 phase 支持旧式文本。这个兼容约定已用本地测试固定，尚未用真实服务验证。
- 工具结果采用本地约定 `function_call_output`，真实 SDK 请求序列化、流式事件/SSE 重连及服务端续传能力均未验证。未知输出状态需要显式支持后再继续。
- checkpoint 的 `turn_key` 由调用者提供。生产调用方需要持久化、按该键去重、事务提交工具结果并设置总轮数上限；本模块没有执行器，也不承诺进程崩溃后的外部工具恰好执行一次。
- `max_output_tokens` 只产生明确诊断，不提高预算、不循环重试、不丢弃已有输入。若产品决定重试，需从原请求恢复并由调用方设置有界策略。
- 没有网络、模型/API 调用、凭据访问、部署或外部副作用。证据只覆盖本地代码与固定数据，未测量模型质量、真实 token 消耗、费用或延迟。
