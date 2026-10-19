# Eval主交付评分契约复核与修订

两项任务的旧/当前各3次交付在原冻结评分下均为4/5；原结果完整保留。逐项复核发现，两项共同失败来自未公开限定的输出选择：release参考保留重复key首行，而六份交付都剔除该key全部行；calibrate要求`false_positive_rate`，六份交付使用公开字段名`fpr`。六份release均invalid并hold，六份calibrate均FPR=null并hold，均未违反相应安全要求。

新增修订评分仅接受这两类语义等价选择，并区分缺字段与显式null。原14个probe、5个domain及guardrail映射保留，stage/身份/费用/完整人口/paired/drift等检查不变。新lane在重评前冻结144份源文件，保留原私有grader来源和新旧SHA。20个完整应用controls校准通过：参考与两类等价实现4份为14/14；starter、empty、fluent、injection及重复漏invalid/膨胀计数、stage人口、缺negative假通过、标签正确但FPR0/ready、省略FPR字段、配对交集丢样本等16份错误实现均被拒绝。另2个含真实negative、真实FPR=0的CLI正控仍正确已测量并可review。

全部12份交付在新的独立`grade-revised-repo`中重评，共168个真实CLI probe，均14/14、5/5、guardrails=true。每份只有上述一个probe从false变true，两个版本继续持平。每个app子进程都使用相同portable/断网政策，另禁止读取原`grade-repo`；32次隔离preflight确认自有新repo可读、私有grader及原repo/skills/output（存在时）不可读、网络bind被拒绝。没有新模型调用、产品改动或工程任务重评。

原175份measurement文件和65份Eval冻结文件hash核对不变，原12份capture及原Eval grade逐文件before/after inventory相同。原评分4/5和修订评分5/5应并列报告。这是查看主结果后的评分契约修正，不能称产品能力提升、新holdout或独立工作分布泛化证据。

证据：`main-diagnosis.json`；`revised-private/original-sources.json`、`grader-revision.diff`、`revision-freeze.json`、`calibration/summary.json`、`revision-receipt.json`；工作场景根目录`main-plan-evaluation-scores-revised.json`与`app-grades-revised/`。工程原评分未改。
