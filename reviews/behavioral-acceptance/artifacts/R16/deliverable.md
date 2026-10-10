已完成可运行的本地解析与续传适配器。给定响应现在显示 `Working`，标记为 `tool_required`，完整保留推理项、`phase=commentary` 和 `call_id=c1`；写入固定工具结果后可以恢复并构造下一次请求。给定中断响应保留 `max_output_tokens` 原因及 `output_tokens=100`，不会被判为成功，也不会自动重试。

全部证据来自固定数据。没有调用模型、网络、真实工具或部署服务；演示中的 `Lookup complete.` 是明示的本地模拟响应。

| 文件 | 用途 |
| --- | --- |
| [integration.py](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/integration.py) | `parse_response`、客户端状态 `Session`、工具结果关联、快照与恢复 |
| [legacy.py](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/legacy.py) | 保留任务给定的旧解析和文本历史策略，供对照 |
| [demo.py](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/demo.py) | 使用原始 task.json 的离线入口；lookup 仅允许固定 `{}` 参数 |
| [test_integration.py](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/test_integration.py) | 27 项回归与失败路径测试 |
| [verify.py](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/verify.py) | 一次运行编译、测试、演示和可选技能轨迹审计，保存真实输出 |
| [migration-plan.md](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/migration-plan.md) | 实现前确定的合同、调用面分类和回退边界 |

产品行为与实现变化：

| 场景 | 旧行为 / 问题 | 新行为与证据 |
| --- | --- | --- |
| 普通单消息文本 | 返回第一段文本 | 保持相同文本；`test_legacy_plain_text_contract_is_unchanged` |
| 给定 reasoning → commentary → call | 第一项没有 content，抛 `KeyError` | 遍历全部项；显示 Working，待工具结果；原始项顺序及内容完全相等 |
| 只保存渲染文本 | 丢失 opaque、phase、工具调用 | 完整 output 作为客户端历史；文本仅用于 UI 投影 |
| commentary 后 final | 容易把中间状态当最终答案 | `display_text` 保留文本顺序，`final_text` 只在完成、无调用、无拒绝时提供 |
| 未完成 / 失败 / 取消 | 索引错误或把部分文本当成功 | 原始响应、usage、error、原因进入诊断记录；失败 output 不自动进入可续传历史 |
| 多工具 / 畸形参数 / 重复结果 | 关联不完整 | 校验 JSON 对象参数和 call_id；全部结果齐备才可构造下一请求；重复相同结果无操作，冲突拒绝 |
| 恢复或重放 | 文本历史无法恢复协议状态 | JSON 快照保存配置、完整历史和响应记录；稳定 delivery_id 抑制重复追加 |
| 不同资源的快照 | 所有者不明确 | 只允许客户端历史；拒绝 server state 混用及 expected_scope 不匹配 |
| opaque / 未知字段 | 容易被简化器丢弃 | 深拷贝原样保存；不解密、不重写、不生成推理或压缩项 |

在任务目录运行：

```sh
cd /Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16
python3 demo.py
python3 verify.py --skill-root /Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/sources/P/amind-engineering
```

无需技能包的独立复跑可用 `python3 verify.py`，执行前三项检查。Python 3.9.6 标准库即可，无依赖安装。

真实验证结果如下，完整命令、stdout、stderr、退出码和本地耗时见 [verification.json](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/verification.json)：

| 检查 | 实际结果 |
| --- | --- |
| `python3 -m py_compile integration.py legacy.py demo.py test_integration.py verify.py` | 退出码 0 |
| `python3 -m unittest -v test_integration.py` | 27 tests，OK，退出码 0 |
| `python3 demo.py` | 初次 tool_required；固定后续 final；失败 incomplete；保留 100 output_tokens；退出码 0 |
| 技能 `context_audit.py --trace continuation-trace.jsonl` | 2 turns，findings=[]，errors=0，退出码 0 |

[demo-output.json](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/demo-output.json) 保存新旧对照、原始响应、完整续传请求和快照；[continuation-trace.jsonl](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/continuation-trace.jsonl) 与 [context-audit.json](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/context-audit.json) 保存结构检查。最初的 24 项测试也通过，随后补充了输入边界、旧历史丢失及 final+tool 用例，并复跑完整检查。

集成方式：调用方将现有响应序列化为 JSON 字典后交给 `parse_response` 或 `Session.accept`；UI 使用 `display_text` 展示文本，使用 `task_complete` 和 `outcome` 决定流程。由 `Session.request()` 生成客户端续传输入，调用方提供的模型、指令、预算和其他设置均保留。任务未提供真实模型配置，演示不设置模型；测试中的模型名只用于确认配置不被替换。保留已有指令的重发行为，每个请求使用相同显式配置。

材料限制：

- 任务目录原先只有 task.json，没有实际应用源码、SDK 或锁文件。因此交付是可移植的 JSON 边界适配器，尚未接入真实产品，也不是已验证的 SDK 版本升级。
- 固定测试证明本地解析、顺序、结果关联和恢复合同；不能证明服务端接受性、模型质量、真实延迟/成本、真实压缩效果。`output_tokens=100` 来自给定数据，不是实际消费。
- 工具函数不在适配器中执行。真实工具的超时、权限、取消及外部副作用幂等由集成方实现；重复结果保护不等于跨进程“恰好一次”执行。工具执行后、结果持久化前崩溃需要外部幂等键或状态核对。
- 快照假定来自可信本地存储，expected_scope 是资源一致性检查，不替代认证授权。这里验证了恢复与 scope 拒绝，没有实现服务端会话认证。
- 已存在的 compaction 项仅测试原样传递；没有调用 compaction API、执行流式恢复、批量处理或服务端链式历史。非 completed 响应停止在诊断状态，生产恢复需要明确策略及已知安全检查点。

原始 task.json 和技能文件均未修改。回退时停止使用新增适配器即可；[legacy.py](/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R16/legacy.py) 保留对照，已知旧策略存在缺陷，不建议将它作为生产恢复策略。
