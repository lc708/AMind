# 流式与批处理结果判定修复

已提供可直接导入的 Python 判定模块 `result_contract.py`、20 个本地契约测试 `test_result_contract.py`，以及原始固定输入的输出 `fixture-results.json`。当前任务目录最初只有 `task.json`，因此这是一份独立可运行实现，未宣称已接入某个生产客户端。

原始输入的实际结果：

| 对象 | 判定 | 依据 |
|---|---|---|
| stream | `incomplete`，`success=false` | 收到 `Done`，但没有响应终结事件；部分文本原样保留 |
| a | `succeeded` | 按 ID 找到 HTTP 200 且 body.status 为 completed 的响应 |
| b | `expired` | 按 ID 找到原始 expired 错误 |
| c | `missing` | 本次结果集合没有对应记录 |
| batch | `success=false` | 1 成功、1 过期、1 缺失 |

流式判定采用增量状态机 `StreamJudge.feed()` / `finish()`，也可使用 `judge_stream(events)`。文本增量只用于显示进度；只有 `response.completed` 与嵌套 `response.status=completed` 一致，且没有 error/incomplete_details，才成功。空文本响应也能成功。有文本但 EOF、连接中断、failed/incomplete/cancelled、错误事件均不会误判成功。坏格式、相矛盾的终态与终态之后的事件标记为 protocol_error，不会被后来的成功事件覆盖。终态已经有效到达后发生的传输关闭不推翻已确认的结果。

批处理使用 `reconcile_batch(requested, returned)`，按 custom_id 关联并按请求顺序返回每一个请求。重复返回 ID 不覆盖记录；陌生 ID 和无法识别 ID 的记录进入 issues；缺失请求单独标注。逐条检查 error、HTTP 状态、body 状态，HTTP 200 本身不足以判定成功。保留原始返回记录便于排查。重复或非法请求 ID 会直接拒绝。没有自动重试或重新提交。

`fully_reconciled` 仅表示每个请求恰好对应一个返回记录且没有额外记录；它不表示所有记录成功。`success` 还要求每条结果成功。空请求加空结果视为成功的空操作。

在本目录复现：

```sh
python3 -m unittest -v
python3 result_contract.py > fixture-results.json
```

实际执行记录：`python3 -m unittest -v` 返回码 0，输出 `Ran 20 tests in 0.001s`、`OK`；生成结果命令返回码 0。随后通过独立 Python 断言核对了原始流式状态、部分文本以及 a/b/c 对应关系，返回码 0。完整读取记录、命令及约束记录见 `execution.json`。

测试覆盖原始两个回归、增量进度、空流、空成功响应、项目级 done 事件、非成功终态、部分输出后断线、畸形及矛盾终态、重复终态、批结果的全部 6 种排列、HTTP 与 body 状态冲突、重复/陌生/缺失 ID、非法请求 ID 和畸形记录。

技能使用：完整读取指定的 `sources/Q/SKILL.md`，按路由读取 Python README、streaming、batches。采用其中“部分输出不等于最终结果”“流式中断需显式处理”“批结果按 custom_id 关联”的指导。原始输入使用 response.* 事件和 response/status_code/body 结构；保持该结构，没有替换成 Anthropic 的 message_* 或 result.type 格式，没有引入 SDK 调用。

证据边界：所有检查仅使用本地固定数据。补充的终态/异常案例是明确约定的合成契约，并非在线服务采样或实时文档验证。此模块接收已解码的事件及完整读取后的批结果集合，不负责 SSE 字节解码、轮询、SDK 异常适配、跨连接恢复、去重重放或重试。调用方应完整读取成功和错误结果后再汇总；由于未给出批任务生命周期，c 的 missing 只表示本次集合缺失，不证明服务永久失败。协议完成也不证明模型文本的语义质量。

原始 `task.json` 与技能源文件未修改。task.json SHA-256：`c48441c111b35b9810ddb539e97ff4d42548dd254f38db8fb97fefb22cc06023`。无需第三方依赖；未调用目标模型、访问凭据、联网、部署或产生外部副作用。

