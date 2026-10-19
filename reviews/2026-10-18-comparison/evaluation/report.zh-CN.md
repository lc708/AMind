# AMind Eval 实际行为对比（2026-10-18）

预登记22个离线行为挑战，以公共 CLI 对等入口实际执行。冻结旧版0.3.0与冻结新版0.4.0均未改；修复版单列为 validation。没有调用模型、网络或子agent。

| 测量 | 旧版 | 冻结新版 | 修复新版（validation） |
|---|---:|---:|---:|
| 共享合同 | 6/12 | 11/12 | 12/12 |
| 旧已有controls | 6/6 | 6/6 | 6/6 |
| 新扩展 | 10 unsupported | 9/10 | 10/10 |

不能把旧版未提供的10项扩展当成整体质量失败。共享合同旧6/12、冻结新11/12；6个控制三组均6/6，显示没有靠改变既有正确答案制造增益。冻结新共20/22；修复后22/22仅表示这些观察过的挑战通过。

## 成对明细

| ID | 契约 | 类型 | 旧 | 冻结新 | 修复新 |
|---|---|---|---|---|---|
| E01 | legacy-text-subsets | control | pass | pass | pass |
| E02 | unknown-and-partial | control | pass | pass | pass |
| E03 | distinct-endpoint-rates | extension | unsupported | pass | pass |
| E04 | explicit-endpoint-no-legacy-fallback | shared | fail | pass | pass |
| E05 | native-modality-not-free | shared | fail | pass | pass |
| E06 | duplicate-normalization-conflict | shared | fail | pass | pass |
| E07 | cache-write-subset | extension | unsupported | pass | pass |
| E08 | clean-confusion-matrix | control | pass | pass | pass |
| E09 | absent-negative-controls | shared | fail | pass | pass |
| E10 | contradictory-adjudication | shared | fail | pass | pass |
| E11 | rare-base-rate | extension | unsupported | pass | pass |
| E12 | fixed-judge-drift | extension | unsupported | pass | pass |
| E13 | paired-judge-change | extension | unsupported | pass | pass |
| E14 | clean-real-run-and-compare | control | pass | pass | pass |
| E15 | served-model-substitution | control | pass | pass | pass |
| E16 | short-stage-population | extension | unsupported | pass | pass |
| E17 | served-tier-substitution | extension | unsupported | pass | pass |
| E18 | failure-budget-and-resume | extension | unsupported | pass | pass |
| E19 | interrupted-report-accounting | shared | fail | fail | pass |
| E20 | transplanted-report-ownership | extension | unsupported | fail | pass |
| E21 | unreconciled-resume | control | pass | pass | pass |
| E22 | abandoned-reconciliation-budget | extension | unsupported | pass | pass |

## 真实缺陷与最小修复

E19：report 只读取 finished 费用。存在 started、无 finished/result 的中断记录时，冻结旧/新均输出 total_cost_usd=0、unknown_cost_attempts=0、attempts=null。修复后输出 total=null、unknown=1、attempts=1，并保留中断明细。已完成调用的已知费用仍保留为 subtotal。

E20：新 runner 的逐行 result_identity 已能防止 compare 中的产物移植，但 report 未校验这个绑定。把结果 treatment_hash 改为 foreign，并更新字节hash，冻结新 report 仍显示 hashes match export。修复后 integrity 为 unverified: result identity differs...。旧没有逐行绑定，记录为扩展 unsupported。

仅改当前 Eval reporter 与对应 artifact 文档；新增4个公共 CLI 回归。83项已有/新增 Eval 测试全部通过，记录在 validation-checks.json；修复 diff 在 repair.diff。冻结副本和58输入文件/hash复核无变化。

## 未提升和边界

6个原有正确控制没有提升：子集不重复计量、unknown/partial保留、混淆矩阵、真实adapter成对运行、served model校验、未reconcile恢复阻断均旧有正确。中断费用和报告产物绑定是这次挑战发现的新缺陷；不能将修复后的成绩追记为冻结新版成绩。

这些结果不证明模型能力、生产定价、总体泛化或盲测效果。stage人口挑战核对预登记总数；它不能证明每个worker成员真实存在。Runner没有提供文件系统/网络/凭据隔离。价格为合成夹具，没有真实provider账单。

## 证据

- protocol.json：执行前挑战、评分和controls；sha256 5a6a4c75441cc8f843791889999646fb4758f1b9caae0861e1037739d05c755b
- freeze.json：协议、58输入、harness与新旧技能文件hash；sha256 f6396b81bc800138924ab6aa6ac3fa564421a8b1d15ca750013d143c54fc5fff
- old-results.json / frozen_new-results.json / repaired_new-results.json：三组独立观测。
- runs/<variant>/<challenge>/evidence/*.command.json：每次公共CLI完整argv、exit、stdout/stderr。
- runs/<variant>/<challenge>/flow：runner原始manifests、attempts、results、errors、trace与工作区。
- agent-prompts.json：给root统一隔离执行的2项agent任务与可确定rubric；本子任务未调用它们。
- summary.json：成对矩阵、分母与边界；repair.diff / validation-checks.json：修复与回归。

## Post-review fixes (separate validation, frozen score unchanged)

Independent engineering review found three further reporting defects: copying v1 to the baseline directory mislabelled its high scores; duplicating a finished event then rehashing inflated cost from $0.04 to $0.06; duplicating a result then rehashing allowed scored3 > planned2. The final reporter rejects schema-2 variant/directory mismatches, duplicate (case,rep), duplicate attempt IDs, and finish/start case or repetition mismatch before aggregation.

post-review/results.json retains public-CLI evidence for seven additional scenarios against frozen-new and final-repair. Frozen-new still aggregates all five invalid scenarios; final-repair returns controlled exit2 for each. Clean and legacy-no-journal controls both retain $0.04. The reporting regression file adds six independent variants, ten reporting tests total; all 89 relevant Eval tests pass. engineering_contrast independently reran the original counterexamples and controls successfully.

These are post-diagnostic validation cases. The 22 registered challenge scores, old/frozen-new/first-repair raw evidence, first-repair diff and original 83-test record are unchanged. Final diff, source hashes and 89-test logs are in post-review/final-repair.diff, post-review/validation-checks.json and post-review/regression-stderr.txt.
