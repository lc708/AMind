流式和批处理判定已实现，26 个本地契约测试通过。原始输入保留在 `task.json`，没有修改。

| 原始 fixture | 修复后的判定 |
| --- | --- |
| 收到文本 `Done`，随后结束且没有终止事件 | `disconnected`，`transport_success=false`；文本仅作为 `display_deltas` 保留 |
| 首条返回属于 `b`，请求首条是 `a` | 按 `custom_id` 关联，保持请求顺序，不使用 `zip` |
| `a`：HTTP 200，响应状态 completed | `completed` |
| `b`：error.code = expired | `batch_error`，完整保留过期错误 |
| `c`：没有返回记录 | `missing`，不会被截断或丢弃 |

批处理汇总为 1 完成、1 失败、1 缺失，`all_transport_success=false`。

执行契约：只使用 Python 标准库及本地固定数据；修改范围仅为当前任务目录中的新增代码、测试和报告；正确性要求是禁止将部分文本、HTTP 成功或错误的结果配对误判为成功。没有现有应用源码，因此交付的是可直接导入或运行的契约实现，没有声称已接入生产应用。未指定模型或 SDK，也没有引入或更改模型配置。

交付文件：

- `response_contract.py`：公开函数 `terminal_stream(events)`、`match_batch(request_ids, results)` 及命令行入口。
- `test_contracts.py`：26 个测试，包括原始回归、全排列乱序匹配、完成/失败/未完成、错误事件、空流、错误终止状态、重复/未知 ID、缺失结果、HTTP 错误、HTTP 200 但响应未完成、数据保留与命令行入口。
- `fixture_result.json`：原始 fixture 的实际执行结果。
- `verification.log`：实际测试输出。
- `execution.json`：读取文件、运行命令、工具调用统计和约束记录。

复现命令（在本目录执行）：

```sh
python3 -m unittest -v
python3 response_contract.py task.json --output fixture_result.json
```

实际环境是 Python 3.9.6。第一条命令退出码 0，输出 `Ran 26 tests in 0.051s / OK`；第二条命令退出码 0，写出上述结果。CLI 的退出码 0 表示成功解析和生成报告；模型响应是否成功必须查看报告中的状态，不能根据 CLI 退出码判断。

成功必须来自 `response.completed` 且其响应状态也是 `completed`。失败或未完成的终止事件保留原因、usage 和完整响应；无终止事件即断连；终止后再出现事件或终止类型与响应状态矛盾会抛出 `ContractError`。保留全部原始事件与响应、refusal、工具调用及未知输出项；展示增量不作为最终文本。批处理需合并服务的输出和错误记录后传入匹配函数；重复请求 ID、重复返回 ID 或未知 ID 会抛出异常，调用方必须将异常作为失败处理，不能吞掉后当作成功。HTTP 2xx 还必须有明确的 `completed` 响应状态。

`transport_success` 只描述响应传输完成；refusal 或工具调用均保留为独立内容，不代表用户任务成功，也不代表答案质量合格。

限制：所有测试都是固定 fixture，包括模拟的 timeout 错误事件。没有网络、SDK、凭据、真实模型请求、实时流、轮询、重试、计费或部署验证。解析器接收有限的、已经解码的事件；实际接入时由传输层负责读超时、独立截止时间、取消与关闭连接。结果与服务实时兼容性、模型质量和延迟没有比较证据。

实现参考了指定 skill 包的 `scripts/response_contract.py`、`references/response-recipes.md` 与 `references/platform-operations.md`。原始错误规则仍在 `task.json`，测试中复现了这两条规则作为回归证据。回滚只需移除新增文件；没有修改原始输入或 skill 源码。
