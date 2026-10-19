# 工程产品独立诊断（主试验冻结后，未读取试验结果）

本目录只检查当前产品模块及旧产品包。没有读取 2026-10-19 workplace target runs/captures，没有调用目标模型或网络，没有改产品源码、测试或冻结工程任务。以下是诊断发现，不属于冻结任务的计分或新旧能力提升证据。所有结果通过实际模块公共 API、独立 Python 子进程、SQLite 和本地副作用收据复现；`evidence.json` 保存命令、stdout/stderr、完整返回值及产品文件哈希。

复现：

```bash
python3 -B reviews/2026-10-19-workplace/product-diagnostics/engineering/reproduce.py
```

## 1. 同一 journal 的文件软链接别名绕过活动协调器锁

合同：`references/workflow-recipes.md` 明确要求一个活动协调器，并说明 `reconcile` 获取同一把锁、拒绝覆盖仍在运行的 handler。实际收据已到达外部接收器时，handler 仍可能在验证输出；外部收据存在并不允许第二协调器绕过活动 handler 的生命周期所有权。

最小现场：活动 worker 用 `delivery.sqlite` 打开日志；恢复控制器用 `active.sqlite -> delivery.sqlite` 文件软链接打开同一日志。`os.path.samefile` 为 true。在 `deliver` handler 内先真实落盘接收器收据，再由第二个 `Workflow` 实例调用 `reconcile`。

观察：当前 0.3.1 接受了正在运行期间的 reconciliation，并在 handler 尚未返回时报告 `status=completed`、`coverage=1.0`。同一路径控制正确抛出 `RuntimeError: stop the active coordinator before reconciling an operation`。handler 随后完成，最终 work 结果覆盖了恢复控制器先写入的结果。旧 0.2.1 没有对应 staged Workflow 公共入口，单列 unsupported，未判为质量失败。

定位：`workflow_contract.py` 构造器保存未经规范化的 `Path(path)` 并用原路径打开 SQLite；`run`/`reconcile` 以该路径追加 `.coordinator`。两个文件名指向同一数据库，却创建不同锁文件。

建议：在构造时先解析到固定的规范数据库路径，并让 SQLite 连接和协调器锁共同使用该路径；增加“活动 worker 用真实路径、恢复控制器用文件软链接”的回归。当前尚未实施。

## 2. 响应 normalizer 的失败合同未接入 side-effect dispatch

合同：同包 `response_contract.normalize` 明确拒绝 completed 同时携带 error 或 incomplete_details 的矛盾响应。应用工具循环应在 dispatch 之前应用这一终态校验。

最小现场：给 `run_loop` 的注入 adapter 返回一个离线保存的 `status=completed`、`error={code:provider_adapter_failure}`、`output=[function_call send_invoice]`。`send_invoice` handler 真实向临时 JSONL 追加发送收据；没有调用任何模型或外部服务。

观察：旧 0.2.1 与当前 0.3.1 的 `normalize` 都正确抛出 ValueError；两版 `run_loop` 却都继续授权并执行了一次发送副作用，随后消费第二个保存响应并返回 completed。将第一个 fixture 的 status 改为 failed 的控制场景，两版均不执行副作用。这是共同存在的集成缺口，不是新版本引入的回归，也不是本次比较中的能力差异。

定位：`tool_loop.run_loop` 只检查 `response.status != completed`，未检查 completed/error 或 completed/incomplete_details 的矛盾，随后直接提取 function_call 并 dispatch。

建议：在 history 更新、授权和副作用前，对完成响应应用与 public normalizer 一致的终态一致性校验；用真实本地收据验证矛盾响应不会调用 handler。当前尚未实施。

## 3. 较窄的收据竞态：晚返回 handler 覆盖已 reconciliation 的结果

同一 `EffectLedger` 的第二连接可以在第一个 handler 尚活动时，以真实落盘接收器收据完成 reconciliation。随后活动 handler 返回不同的本地结果，`perform` 的无条件 UPDATE 将状态已为 complete 的结果再次覆盖。`perform` 的缓存读取因此返回 late-worker 结果，而 reconciliation 审计仍保存 receipt-controller 的结果。旧版和当前版均如此。

这个现场只有一次外部发送；发现的是已确认结果的稳定性问题，并非重复发送。它比第 1 项的明确“禁止覆盖活动 handler”合同窄，因为 EffectLedger 尚未声明同样的协调器锁。建议至少使用 pending 状态条件更新或协调机制，防止晚提交默默覆盖已确认结果，并明确并发 reconciliation 的合同。当前尚未实施。

## 控制与边界

- Workflow 同一路径的活动 handler reconciliation 被拒绝，证明现有保护存在，缺口在数据库路径身份。
- failed response 在工具循环中不执行副作用，证明 dispatch 故障集中在矛盾 completed 响应。
- 旧版与当前版均通过真正的崩溃控制：子进程先 fsync 接收器收据再 `os._exit(17)`；重启后的 `perform` 拒绝自动重试，外部证据 reconciliation 后复用原收据，全程只有一张外部收据。
- 以上使用可信调用者提供的身份和本地收据，不声称完成安全审计或生产 SDK 兼容验证。
- 所有产品修复和回归等待主任务确认全部主试验完成后再进行；冻结输入保持原样。
