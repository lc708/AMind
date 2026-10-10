已复现并修复本地样例的续接状态错误。交付包含可运行的状态适配层、固定数据重放入口和 26 项回归测试；没有调用真实模型、SDK、工具服务或网络。

执行契约：保留原始 task.json、全部原始响应项和约束；使用响应 ID 链作为本次续接的唯一历史所有者；错误结果必须在请求构造时拒绝；工具调用按 call_id 对应；不把 commentary 当最终答案；压缩内容只做完整保存和完整性检查。延迟与模型质量不作推断。没有应用源码、SDK 版本或模型配置，因此这是可集成的本地修复模块，不是已部署应用的修复。

| 定位 | 证据与影响 | 修复 |
| --- | --- | --- |
| 链式状态又重放助手输出 | task.json:23 使用 r1，task.json:29–33 又包含与 r1 相同的 Working 助手消息。可见链式状态与手工历史混用。 | 只发送明确的新用户事件和工具结果；存储完整响应，但不重发其输出。 |
| phase 丢失 | task.json:11 的 commentary 在 input[1] 消失；artifacts/phase-diff.json 给出 /phase removed。 | 整项保存和恢复响应，不从纯文本重建；只有 completed 且明确 final_answer、没有新工具调用时才输出最终消息。 |
| 工具结果无法关联 | task.json:16 是 c1，task.json:36 是 wrong；c1 仍未完成。 | 原始结果被拒绝。固定 dispatcher mock 持有原始 c1 调用，由它生成绑定 c1 的 invoice 完成结果；不凭输出内容猜测或自动改写错误 ID。 |
| 后续压缩风险 | task.json:41–44 只提供单个 compaction 项，没有完整压缩响应或后续请求。 | 原样归档 opaque-2；当前 r1 请求不拼入该项。提供独立的客户端压缩边界函数并用合成完整输出信封测试，未声称样例已经发生压缩损坏。 |

修复后生成的请求位于 artifacts/fixed-request.json：

```json
{
  "previous_response_id": "r1",
  "input": [
    {"role": "user", "content": "Find invoice"},
    {"type": "function_call_output", "call_id": "c1", "output": "invoice"}
  ]
}
```

原始样例没有 r1 的初始请求或事件来源，无法判定 Find invoice 是历史消息还是新事件。本次保留该消息，避免删除用户输入。接入应用时，new_input 必须来自可信事件记录；若证明它已发送，应只续接工具结果。相同文本不足以证明两条用户事件相同。状态检测中助手文本相似仅用于提示，构造器不会做文本去重。

state.py 的 ResponseChain 保存完整响应、显式父 ID、未完成调用和本地作用域；prepare 构造请求，accept 在获得对应后继响应后推进，snapshot/restore 支持断线恢复。同一父响应的已准备请求只能保持结构一致；重复结果、未知调用、错误父 ID、混用状态所有者、跨作用域和取消后的推进均被拒绝。需要所有并行调用结果到齐才续接，不支持部分结果提交。调用者每轮显式提供 instructions/model 等配置，模块不选择或更换模型。

client_compaction_request 是独立的客户端数组边界：使用完整 compact output 原样作为前缀，再附加新输入，且禁止 previous_response_id/conversation。真实使用必须先取得兼容的完整压缩输出与可信完整性记录；不能用样例中的单个 opaque 项推断完整历史或移植到其他资源。响应链路径则保存服务返回的完整项并继续使用其响应 ID。

在任务目录执行：

```sh
python3 -B -m unittest -v test_state
python3 -B replay.py --task task.json --out artifacts --audit-script ../../sources/P/amind-engineering/scripts/context_audit.py
python3 -B ../../sources/P/amind-engineering/scripts/context_audit.py --trace artifacts/baseline.jsonl
python3 -B ../../sources/P/amind-engineering/scripts/context_audit.py --trace artifacts/fixed.jsonl
```

实测 Python 3.9.6，26 项测试通过。replay.py 退出 0，报告原始任务未变、原始状态四类发现、修复后零发现。基线审计退出 2，含 orphan_tool_result 警告和 unresolved_tool_calls 错误；修复审计退出 0，零发现。基线退出 2 是预期复现，不是执行失败。原始 task.json 字节 SHA-256 为 7044074843610eb034c310af31c47396cfdfb6105a809e71eb881ce27df82ddc。

测试覆盖原始失败与精确修复信封、普通五轮续接无输入累积、单工具/多工具按 ID 对应、两轮工具后 commentary→final、坏参数、坏结果、失败/超时结果保留、取消、恢复、显式配置更新、跨租户/资源拒绝、重复调用与响应拒绝、长文本压缩输出顺序和 opaque 内容保留，以及压缩内容变化或丢失的拒绝。单变量消融还验证：只修 phase 仍有重放和工具错误，只修 ID 仍有重放及 phase 错误，只移除助手重放仍有孤立工具结果。

审计工具按完整项哈希发现重复，丢失 phase 后不再匹配原哈希，单靠它会漏掉助手重放。交付额外使用逐项 phase 差异和请求构造边界补上这一证据；没有修改技能审计器或降低检查要求。标准化 trace 中未知的初始 request 记为空数组，terminal 仅表示检查此时工具结果是否齐全，并不代表模型任务成功。

证据文件：test-results.txt、replay-results.txt、baseline-cli-audit.json、fixed-cli-audit.json、artifacts/diagnosis.json、artifacts/phase-diff.json、artifacts/original-fixture.json、artifacts/state-snapshot.json、artifacts/saved-compaction-item.json。execution.json 记录读取范围、实际命令和约束执行情况。原始 task.json 与技能源码未改；回退时直接停用本地适配层即可，原始固定输入仍完整保留。

所有结论限于固定数据的结构和控制流。未验证服务端接受、真实模型答案、压缩后的事实记忆、计费、延迟或服务端取消。样例缺少 status，因此允许进行结构诊断但从不将它认定为 completed/final。这里的作用域检查和可信本地快照不是认证系统；生产环境仍需由宿主绑定身份、保护存储并建立真实请求关联。没有执行外部副作用，也未实现外部操作恰好一次保证；断线后重用请求结构不代表可以安全重试真实写操作。
