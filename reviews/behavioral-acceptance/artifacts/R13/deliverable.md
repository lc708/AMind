# 多轮状态回归：离线定位与修复

已复现给定 fixture 的状态断裂，并交付可运行的修复构造器和 11 个通过的回归测试。没有真实模型请求、网络访问、凭据读取或外部副作用；`task.json` 保持原样。

## 定位

| 证据 | 缺陷及影响 | 修复 |
|---|---|---|
| `task.json:11` 的 `phase: commentary` 在 `task.json:29` 开始的重建消息中消失 | 重建历史丢失消息阶段，无法再区分过程消息与最终答复；具体模型会如何解释尚未测量 | 手动回放时保留完整输出对象，包括 `phase`，不能只提取 `role/content` |
| `task.json:23` 引用 `r1`，同时 `input[1]` 又回放该响应的 `Working` | 同一历史同时由响应引用和客户端副本提供，有重复上下文风险 | 选择引用模式，或完整手动回放模式；不要把旧输出混进引用模式的新输入 |
| `task.json:16` 的调用 ID 是 `c1`，`task.json:36` 的结果却绑定 `wrong` | 结果没有对应调用，`c1` 仍未得到结果 | 从实际调用对象复制 ID，拒绝未知、重复或缺失的结果；不能按位置猜配 |
| `task.json:41` 提供了后续 `compaction` | 当前 fixture 尚未显示它被丢弃，但仅保留文本的序列化会丢失它 | 对所有输出项目做完整复制，保留 `encrypted_content: opaque-2` 和未知字段 |

前三项是当前 fixture 的可见问题。输出中的 `MISSING_RESULT` 是错绑 ID 的后果，不是第四个独立根因。未提供原应用源码，不能证明是哪个生产函数引入了回归；应在“响应持久化 → 下一请求组装”的边界接入这些检查。

## 可审查修复

`state_regression.py` 提供：

- `check_results`：按 ID 检查待完成调用和结果一一对应。并行调用的结果顺序可以不同。
- `build_stateful`：保留响应引用，仅加入本次工具结果与明确标记的新用户输入。
- `build_manual`：不使用响应引用，按顺序复制调用方提供的历史、完整前序输出、结果和新输入。
- `append_response`：完整复制响应项目，保留 `commentary`、`final_answer`、工具调用、压缩项目与未来字段。
- `diagnose`：报告本 fixture 的状态不变量违例。它是本地检查器，不是远端 API 的完整 schema validator。

若 `Find invoice` 是生成 `r1` 的原用户输入，引用模式的最小修复为：

```json
{
  "previous_response_id": "r1",
  "input": [
    {"type": "function_call_output", "call_id": "c1", "output": "invoice"}
  ]
}
```

手动回放模式为：

```json
{
  "input": [
    {"role": "user", "content": "Find invoice"},
    {"type": "message", "role": "assistant", "phase": "commentary", "content": "Working"},
    {"type": "function_call", "call_id": "c1", "name": "read", "arguments": "{}"},
    {"type": "function_call_output", "call_id": "c1", "output": "invoice"}
  ]
}
```

**该用户输入的归属是显式假设。** fixture 没有给出生成 `r1` 的原请求。如果 `Find invoice` 实际是新用户输入，应传给 `new_input`；`verification.json` 中的 `fresh_user_variant` 展示了保留它的方案。实现不会依据相同文本自动删除用户输入。

`wrong` 结果会被校验器拒绝。演示通过纯本地 `mock_read` 对原调用 `c1` 返回固定字符串 `invoice`，从调用对象取得 ID；这不能证明线上错误结果原本属于哪个调用。接入真实应用时必须从执行记录确认归属或重新执行允许重试的工具，不能批量替换错误 ID。

后续压缩项目作为完整对象进入 `later_history_with_compaction`，JSON 序列化再反序列化后逐字段一致。没有解密、解读、重新生成密文，也没有把它替换成自然语言摘要。本示例不推断何时删除旧历史；服务端压缩策略及其返回项目范围需按实际接口契约处理。

## 实际验证

工作目录：`/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/runs/R13`，运行时 Python 3.9.6，标准库即可运行。

```sh
python3 -m unittest -v test_state_regression.py
python3 state_regression.py
```

第一条实际输出 `Ran 11 tests in 0.001s`、`OK`，退出码 0。覆盖原始问题、引用/手动两种模式、新用户输入保留、错误响应引用、并行结果乱序、缺失/重复结果、重复调用 ID、`phase` 与未知字段保存、压缩对象保存、不修改原输入、受限 mock 工具，以及 socket 被阻断时的完整演示。

第二条实际输出：

```text
Offline reproduction: PHASE_CHANGED_OR_LOST, REPLAY_WITH_REFERENCE, UNKNOWN_CALL_ID, MISSING_RESULT
Fixed requests: 0 local contract findings; opaque compaction round-trip preserved.
Wrote verification.json; no network or SDK clients are present.
```

修复前/后的诊断、两种请求、用户输入另一解释和压缩后的历史均保存在 `verification.json`。`task.json` SHA-256 为 `7044074843610eb034c310af31c47396cfdfb6105a809e71eb881ce27df82ddc`，测试核对了原文件未改变。

## 所用 skill 与证据边界

按分配读取了 `sources/Q/SKILL.md`（`claude-api`），并路由读取 Python README 的初始化、多轮、压缩章节，以及 Python 工具使用和共享工具概念的相关章节。采用其中“保留完整响应内容”和“工具结果必须匹配原调用 ID”的原则。

fixture 使用 `previous_response_id/output/function_call_output/phase`，与所读 skill 的 Claude Messages 示例字段不同。本任务不要求切换供应商，因此没有把它转换成 Anthropic 请求，也没有添加 SDK 客户端。引用模式规则是为该 fixture 明确建立的本地状态契约，不宣称这些 payload 已经获得任何线上 API 接受。

当前证据证明的是确定性状态组装与保存，不证明真实模型答复质量、服务端状态有效期、重试幂等性、密文有效性、远端压缩语义或生产修复已经部署。没有执行额外模型评测或改动评测要求。
