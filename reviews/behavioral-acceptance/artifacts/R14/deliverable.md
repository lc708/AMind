# 长期运行 Agent 生命周期修复与本地事件验证

已提供可运行的 Python/SQLite 参考实现和 22 个测试。原始 `task.json` 未修改。所有机器、文件工作区和写入效果都是本地固定模拟；没有调用模型、SDK 服务、网络或凭据。

原始事件的正确结果不是“成功”：重复事件只创建一个模拟机器，断连保留 checkpoint，取消后拒绝新写入；最后的 `effect_started(write1)` 是已开始效果的通知，因此记录为取消后的异常，进入 `needs_reconciliation`。不能把这条通知改写成“已阻止执行”，也不能宣称已经回滚外部效果。

## 交付文件与复现

在本目录执行，Python 标准库即可，无需安装依赖：

```sh
python3 -m unittest -v
python3 replay.py
```

- `lifecycle.py`：持久化状态机、事件去重、取消栅栏、效果账本、内存授权、保留/归档和 webhook 验证边界。
- `replay.py`：直接读取原始 fixture，输出每一步的决策与最终状态。
- `test_lifecycle.py`：可重复的正反向验证。
- `trace.json`：实际运行的完整事件轨迹。
- `verification.log`：实际测试输出。
- `execution.json`：读取文件、执行命令、工具调用数量及限制说明。

本次实际执行了 `python3 -m unittest -v`，首次 22/22 通过；补充“确认已发生的效果后可再补偿”的断言后执行 `python3 -m unittest -v > verification.log 2>&1`，仍为 22/22 通过（0.079 秒，退出码 0）。执行 `python3 replay.py > trace.json`，再将保存的 JSON 与第二次 `run()` 结果逐项比较，确定性检查及最终状态断言通过。

原始输入 SHA-256：`d384023c45ad00b162994cf1fc30df8fb7ea6c960e4d90e183d138252ec3f37e`。

## 生命周期与边界

| 原缺陷 | 修复规则 | 已运行的验证 |
|---|---|---|
| 每个环境事件都创建机器 | SQLite 中 `(session,event_id)` 去重；相同 ID 不同内容拒绝。每个 session 的机器绑定唯一，重连复用绑定 | 重复 e1、不同 ID 的再次连接、重新打开数据库后重放 |
| idle 等于成功 | 连接状态、会话阶段、取消状态分别保存。`requires_action` 等待动作，`budget_reached` 暂停，`end_turn` 等待独立结果验证，重试耗尽为失败 | idle 四种原因、失败路径、结果验证、取消后的 end_turn |
| 断连删除文件 | 断连只修改 connected；终态、取消确认、效果结算、保留期都满足后，先归档并核验内容哈希，再清理模拟工作区 | 断连保留、提前清理拒绝、取消确认与保留期、归档内容验证 |
| 取消后继续派发效果 | 取消在事务内写入持久化标记并增加 epoch；排队和提交都检查取消、epoch、连接和阶段；已有排队效果转为 blocked | 排队后取消、另一个数据库连接提交、取消后的新写入与重连 |
| 取消等于撤销外部效果 | 已提交效果保留账本；未知的 `effect_started` 需要结算。取消确认不能覆盖未知/未补偿效果 | 先提交后取消、确认取消后又收到效果通知、补偿路径 |
| webhook 未验签 | 原始 bytes 和未改动 headers 交给 verifier；验证成功后才持久化入队，成功入队才返回 204；验证/队列异常向上传递 | 缺失签名、字节改变、旧模拟时间戳、入队失败均不确认 |
| 跨租户或过期 memory 可读 | tenant 必须来自已认证上下文；记录 tenant 匹配且 `expired is False` 才允许使用；缺失过期信息拒绝 | 四种 tenant/过期组合、缺失 expiry、跨租户事件 |

SQLite 的 `BEGIN IMMEDIATE` 将去重记录、状态迁移和本地模拟写入放在同一事务中。失败的事件不会留下“已处理”记录。取消与提交并发时，以事务提交顺序定义边界：取消先提交则阻止效果；效果先提交则记录已发生，取消不抹除它。

`effect_started` 是观察事件，`queue_effect()` 和 `commit_mock_effect()` 才是新的效果入口。两者刻意分开，保留了题目中晚到/越过取消边界的效果证据。需要可信的操作方或服务对账证据，将其结算为未发生、已补偿或已发生未补偿。未知与未补偿状态都阻止清理。

## 原始 fixture 的实际轨迹

原始 `webhook_signature_checked=false`：入口拒绝，入队数量为 0。为验证状态机，另行进行明确标记为**可信本地领域事件重放**的第二条路径；这不代表给原 webhook 补上了真实签名。

| 事件 | 实际决策 | 机器数 / checkpoint 数 / 模拟写入数 |
|---|---|---|
| e1 connection_required | 创建模拟机器 | 1 / 1 / 0 |
| 重复 e1 | duplicate | 1 / 1 / 0 |
| e2 disconnected | 保留文件，连接断开 | 1 / 1 / 0 |
| e3 cancel_requested | cancellation_fenced，等待确认 | 1 / 1 / 0 |
| e4 effect_started(write1) | late_effect_after_cancel_requires_reconciliation | 1 / 1 / 0 |

内存记录同时被 `tenant_mismatch` 和 `expired_or_missing_expiry` 拒绝。额外的取消后写入请求被阻止，清理请求返回 retained；最终阶段 `needs_reconciliation`，不会报告完成。

## 根据所分配技能的接入设计

已阅读分配的 `sources/Q/SKILL.md` 全文，并沿 Managed Agents 路由阅读 overview、webhooks、client-patterns、memory，以及 self-hosted-sandboxes、events、environments 和 Python README 的相关部分。本交付使用这些本地材料，不验证其中 API 的线上版本状态。

- Agent 配置在部署设置阶段创建一次并保存 ID/version；每次执行创建 session，固定配置版本。环境模板、session 与具体机器不是同一个生命周期对象。本地实现用固定 `fixture-agent` / version 1 表示这个边界，不真的创建服务对象。
- 自托管 worker 应依据已领取的 work item 和租约协调机器。环境通知只触发核对/唤醒；重连先查已有绑定。只有确认旧实例无法恢复并有 checkpoint 策略后才做实例替换。当前本地实现只验证绑定与重复投递语义，不实现真实租约和容器。
- 题目中的 `environment_connection_required`、`environment_disconnected`、`cancel_requested`、`effect_started` 是领域事件，不冒充 Anthropic webhook/SSE 类型。真实 webhook 是薄通知：验签后持久化入队，按 verified event.id 去重，再获取最新资源和事件历史；不能用无序通知的到达次序覆盖权威状态。
- 真实验签应注入技能中记录的 `client.beta.webhooks.unwrap(raw.decode(), headers=headers)`。不自行实现一个声称兼容厂商的 HMAC 协议。测试的 verifier 只接受固定 raw bytes/headers，用于证明调用顺序和失败闭合，未测试真实签名算法或 SDK。
- SSE 重连先打开并缓冲 stream，再遍历分页历史，最后合并 live stream。`replay_with_consolidation()` 验证打开顺序和重叠去重。真实 SDK 的 queued/processed 两个阶段要单独更新 acknowledgment，不能用领域事件的一次性 receipt 丢掉 `processed_at` 更新；本实现的领域事件是不可变事件。
- 真实取消先持久化本地栅栏，再发送 interrupt/停止 worker，处理已在途效果并等待确认。技能特别指出 interrupt 后也可能是 `end_turn`，预算暂停时 interrupt 可能被忽略，所以需要本地取消状态与单独确认，不能靠 stop_reason 推断成功。不得在断连通知里 archive/delete session 或资源。
- 真实内存读取前应由服务端认证、租户绑定和可信时钟计算 TTL；本 fixture 只有 tenant 和 expired 布尔值，因此本地策略直接验证这些字段，不把调用方自报的过期状态当成生产授权。

## 证据范围与未完成的外部验证

22 个测试证明的是本地状态转换、持久化去重、事务边界和固定 mock 的失败路径。两个 SQLite 连接测试验证持久化取消可见性，不等于经过压力测试的分布式并发保证。没有实测模型行为、真实 webhook HMAC、SDK 兼容性、网络分区、机器租约、真实存储持久性或部署。

跨数据库与外部 API 无法由本地事务保证 exactly-once。生产效果执行器需要目标服务支持幂等键/栅栏令牌、持久化 outbox、超时后对账和必要补偿；未知结果不可盲目重试。webhook 的 durable_enqueue 是显式接入边界，示例测试队列是 mock，不能直接部署为生产接收器。重连示例使用有限固定流，没有实现网络重试/退避/全局截止时间。归档保存在同一 SQLite 数据库中，仅验证顺序与内容完整性，不是独立备份。所有这些限制都保持可见，没有将本地测试等同于真实服务验证。
