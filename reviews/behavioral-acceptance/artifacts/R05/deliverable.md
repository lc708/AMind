# 副作用工具恢复与取消

已实现可运行的 Python 标准库版本：`recovery.py`；`test_recovery.py` 的 20 项测试全部通过。所有远端行为均来自本地固定 SQLite mock，没有调用模型、支付服务或网络，也没有实际扣款。

## 原始场景与恢复结果

原输入保持在 `task.json`：租户 `t1`、任务 `job1`、调用 `c1`、`charge`、金额 `20`。测试真实启动子进程，在远端 mock 提交 `op1` 后执行 `os._exit(77)`，因此本地只留下 `dispatched`。新实例处理相同事件时，使用同一键 `lookup_operation` 找回 `op1` 并提交 `succeeded`；再次投递直接返回本地结果。

该用例断言：子进程退出码 **77**；恢复结果 **succeeded / op1**；远端 mock **1 次 charge 请求、1 次 lookup、1 个扣款效果**。这验证本实现及 mock 契约下的恢复，不是对真实服务恰好一次语义的证明。

## 协议与状态

幂等键为版本前缀、已认证租户、任务、调用 ID 的规范 JSON 的 SHA-256。金额及 action 等完整请求单独保存；同一调用身份携带不同参数会触发 `KeyConflict`，不会生成新键重新扣款。每次执行、查询、取消都先校验身份、任务对应发票的所有权和严格输入类型；重复调用也不能绕过授权。

| 状态/触发条件 | 行为 |
| --- | --- |
| 新调用 | 先持久化 `ready`，再在事务内提交 `dispatched` 和尝试次数，之后才调用远端 |
| `dispatched` / `unknown` 重投 | 先按原幂等键查询；找到匹配凭证才写 `succeeded` |
| 查询返回 not-found | 保留不确定性；未取消、预算未用完且到达重试时间后，才允许同键重发 |
| `succeeded` | 重放已保存的 operation ID；不再次扣款 |
| 明确且权威的拒绝 | `failed`，不自动重试 |
| 未派发时取消 | 原子写入 `cancelled` 墓碑；后续重复执行仍不扣款 |
| 派发之后取消 | 持久化取消意图，停止新的扣款尝试，保留查询对账；返回 `pending_outcome_unknown` |
| 取消后查询到成功 | 返回成功及 `too_late_charge_succeeded`；不能谎称撤销了扣款 |
| 自动预算耗尽 | `manual_review`，停止自动调用；显式 `reconcile()` 只查询，绝不发起扣款 |

SQLite 事务采用 `BEGIN IMMEDIATE` 和 `synchronous=FULL`，使本地派发、取消及尝试预算更新串行化。远端 mock 独立数据库的唯一键约束保证同键并发重发只形成一个效果。事务不跨远端调用；并发错误更新带状态条件，防止晚到的异常覆盖已确认成功。

取消的线性化边界是本地派发事务：若取消先提交，扣款不会派发；若派发先提交，已开始的请求仍可能成功。测试通过线程屏障明确覆盖该竞争。远端只给出了幂等和查询能力，没有取消/退款能力，因此本实现不自动退款、不删除流水、不把停止等待当成回滚。

## 重试与人工恢复

原先“每个异常立即重试”已替换为分类处理：

- 超时及限流：结果可能未知，先查询；最多 3 次扣款尝试，指数退避加确定性键抖动，并尊重 `retry_after`。
- 查询暂不可用：退避，最多 3 次失败后转人工复核，不触发新的扣款。
- 参数、授权、幂等参数冲突：直接拒绝，不进行远端调用。
- 权威业务拒绝：终止；适配器只能将**保证该键对应操作未被接受**的响应映射为 `PermanentRejection`。
- 编程错误等未分类异常：向上抛出，保留派发记录供排查，不在 catch-all 中自动重试。

人工复核先核实同一键的真实流水及保留期限，然后调用 `Recovery.reconcile(operation, principal)`。该入口在查到匹配成功凭证时恢复本地完成状态；查不到则仍保留原状态。没有证据时不生成新键，不推断失败。如业务需要退款，必须通过独立授权和独立幂等协议处理，当前能力未实现退款。

## 调用方式

`Principal` 必须来自可信服务端认证上下文，不能来自模型参数。当前 mock 将 `task` 视为服务器已绑定发票的标识，固定 `Principal("t1", frozenset({"job1"}))` 对应题目给定授权。

```python
from recovery import Recovery, MockRemote, Principal

principal = Principal("t1", frozenset({"job1"}))
service = Recovery("journal.db", MockRemote("remote.db"), clock=your_clock)
result = service.run(operation, principal)
# 取消调用与执行使用同一完整 operation；重投必须保持 call_id 不变。
cancellation = service.cancel(operation, principal)
# 自动预算耗尽后的显式只读恢复：
reconciled = service.reconcile(operation, principal)
```

`run()` 每次推进有限的一步，没有后台忙循环；调度器应按返回的 `retry_at` / `lookup_after` 再调用。默认时钟为固定 0，便于离线确定性验证，集成时必须注入可信时钟。示例相对数据库路径应在当前任务目录运行；测试所有临时数据也限于本目录，并在结束后清理。

## 实际验证

在当前目录执行：

```text
python3 -m unittest -v test_recovery.py
# 首轮：18 tests，0.151s，OK。

python3 -m unittest -v test_recovery.py > verification.log 2>&1
# 增加人工只读恢复与取消竞争测试后：20 tests，0.212s，OK。

python3 -m py_compile recovery.py test_recovery.py
# exit 0，无输出。
```

最终完整输出保存在 `verification.log`。覆盖真实子进程崩溃重启、顺序与并发重投、跨租户隔离、参数冲突、授权失败、严格金额校验、派发前取消、请求进行中取消、成功后取消、未知结果取消、查不到记录、超时重试、限流等待、永久失败、预算耗尽和人工只读对账。

## 使用的技能与边界

读取了指定 `sources/Q/SKILL.md` 全文，并按其工具开发路由读取 Python README、Python tool-use、shared tool-use-concepts、agent-design、error-codes 中相关章节。应用了输入校验、在工具执行处实施权限控制、使用专用副作用工具入口、分类错误及有界重试。任务未指定语言，选择技能的 Python 默认；任务需要本地恢复协议，不需要模型推理，因此没有创建 SDK 客户端或模型调用。所有本地实现与测试已获授权。

远端原子幂等、查询凭证可靠性、同键参数冲突、键的保留期限必须由真实服务契约保证；本题只声明支持能力，没有提供这些生产细节。真实鉴权、发票映射、币种/金额单位、服务超时、进程协调、SQLite 文件系统故障、跨区域一致性、长期数据保留与真实支付适配器均未验证。金额 `20` 原样保留为题目单位。该实现提供可审查的恢复协议及离线证据，不声称已经完成生产支付集成。
