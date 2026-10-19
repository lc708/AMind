# 工程诊断修复：共享终态校验与兼容性验证

初次修复通过 41 项工程回归后，Root 的全量验证发现一个实际兼容回归：工具循环此前允许原样保留 `message.content='done'`，但调用完整显示 normalizer 额外要求 content 数组。原 kernel fixture 和失败收据均未被修改或删除。

现已把 `response_contract.validate_terminal(response)` 提取为共享入口，仅检查 response 为字典及 completed 响应的 error/incomplete_details 是否为非 None。`normalize` 复用这一检查，并继续严格验证消息／投射内容；`run_loop` 复用同一终态检查，随后只执行其既有的 output-item、函数参数和授权验证，保留原始消息、phase 与 opaque 数据。

最终验证：

- 工程行为回归 42/42；包含四种非空／空对象的矛盾完成字段，均无第二次 adapter 调用、授权或副作用收据。
- 能力 kernel 回归 67/67；原来失败的 raw `content='done'` fixture 保持不变并通过。
- 新增 legacy raw-message 两轮 continuation 控制通过，同时证明 `normalize` 仍严格拒绝这种显示内容格式；None 健康终态与现代 phase/opaque 保留控制继续通过。
- 原三个诊断现场仍已修复：同数据库文件软链接不能绕过协调器锁，矛盾终态不执行副作用，晚 handler 冲突保留外部已确认结果并抛出明确异常。
- 真正 `os._exit(17)` 后重启、拒绝重发和核对外部收据后复用的控制继续通过。

证据另存为 `after-compatibility-{regression,kernel,evidence,summary}.*`，没有覆盖修复前 `evidence.json` 或初次 41 项中间记录。原始修复前证据 SHA-256 保持 `ed92ac76c84bf6e2c40bbd4b33d32ad5e03b5d0cd2c3efc64b7a50f7fa3e8f09`。

```bash
python3 -B scripts/test_amind_behavior_regressions.py --json reviews/2026-10-19-workplace/product-diagnostics/engineering/after-compatibility-regression.json
python3 -B scripts/test_amind_capability_kernel.py
python3 -B reviews/2026-10-19-workplace/product-diagnostics/engineering/reproduce.py --output reviews/2026-10-19-workplace/product-diagnostics/engineering/after-compatibility-evidence.json
```

这是冻结主试验之外的本地产品修复和兼容验证。未读取主试验结果、未改变冻结处理组、未新增目标模型或网络调用，不并入主任务比较成绩。Root 负责总体测试计数、版本、安装和发布记录。
