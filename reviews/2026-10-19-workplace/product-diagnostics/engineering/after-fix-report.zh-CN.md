# 工程诊断修复验证

> 本文记录初次 41 项定向验证的中间状态。随后全量验证发现原始 message content 透传兼容问题，已修正；最终证据见 `after-compatibility-report.zh-CN.md`。原始中间测试和复现记录保留。

Root 在 42 份主试验的应用／source 副本全部准备并冻结后，授权修改当前工作树。主处理组仍为被冻结的 Engineering 0.3.1。本次没有读取主试验 runs/captures，没有修改冻结任务或快照，也没有新增目标模型调用。

修复前 `evidence.json` 原样保留；`before-product/` 的三份源文件哈希与该证据里的修复前哈希匹配。原复现脚本保存在 `reproduce-original.py`。修复后结果另写 `after-fix-evidence.json` 与 `after-fix-summary.json`。

三个修复：

1. `Workflow` 先解析数据库的规范文件路径，SQLite 连接和 `.coordinator` 锁都使用这个路径。原文件软链接现场现在与同路径控制一致，拒绝活动 handler 期间的 reconciliation。
2. `run_loop` 在更新 history、授权和 dispatch 之前调用真实的 `response_contract.normalize`，复用其 completed 终态一致性校验。非空或空对象的 error/incomplete_details 都会拒绝；值为 None 的健康完成响应仍正常。传给后续 continuation 的原始 phase、reasoning 和未知 opaque items 保持完整。
3. `EffectLedger` 只允许仍为 pending 的记录接收 handler 完成提交。若外部 reconciliation 已确认相同结果，复用它；若晚返回结果不同，则保留已确认结果并明确抛出 `ReconciliationRequired`，由调用方检查收据后继续。它不会声称发生第二次发送，也不新增通用分布式协调承诺。

验证：6 个新增集成回归使工程 suite 从 35 项变为 41 项，全部通过。新增覆盖软链接锁、四种矛盾完成字段、None 健康路径和 phase/opaque 保留、晚提交冲突、匹配晚收据及真正 `os._exit(17)` 后的恢复。三个原缺陷现场均得到预期修复；同路径协调、failed response、真实崩溃后拒绝重发和外部核对后复用的控制继续通过。一次外部收据始终保持一次。

```bash
python3 -B scripts/test_amind_behavior_regressions.py --json reviews/2026-10-19-workplace/product-diagnostics/engineering/after-fix-regression.json
python3 -B reviews/2026-10-19-workplace/product-diagnostics/engineering/reproduce.py --output reviews/2026-10-19-workplace/product-diagnostics/engineering/after-fix-evidence.json
```

以上是诊断后的本地产品修复验证，不并入冻结任务成绩，不构成目标模型或技能质量提升结论。Root 负责后续版本、顶层文档、安装及总体发布核验。
