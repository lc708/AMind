# AMind increment — 2026-10-30

本发布以 `amind-v1-increment-2026-10-18` 为基线，将知识观察截止日推进到 **2026-10-30（Asia/Singapore）**，对应 AMind 知识技能 **1.4.0**。

- [中文更新说明](reports/update.zh-CN.md)
- [70个新增分析单元的来源清单](reports/source-inventory.md)
- [采集与分区审计](audits/preparation-audit.json)
- [逐来源判断](delta/source-decisions.jsonl)
- [AI上下文复核与生命周期策展](curation/curation-audit.json)
- [现行检索资格登记](data/current-status.jsonl)
- [工程、评测与交付总报告](../../reviews/2026-10-30-update/report.zh-CN.md)
- [知识检查](../../reviews/2026-10-30-update/validation/knowledge-checks.json)、[应用检查](../../reviews/2026-10-30-update/validation/application-checks.json)、[最终验证](../../reviews/2026-10-30-update/validation/final.json)
- [安装验证](../../reviews/2026-10-30-update/validation/installation.json)、[工作区同步验证](../../reviews/2026-10-30-update/validation/workspace-sync.json)

本轮新增70个分析单元、995个passage、11,533条claim；合并后为1,607个分析单元、21,516个passage、140,665条claim。70个单元分为29个窗口内发表、16个历史回补、1个上次截止日当天补录、19个日期未确认的首次索引和5个既有作品修订。它们不等同于70篇十月新文章。

`sources/` 保留108份抓取记录：105份选定正文或附件捕获，另加3份只作元数据留存的团队导航；选定捕获中含17个附件。`delta/` 保存本轮新增证据，`data/` 提供自包含的合并数据，`curation/` 保留可重放的逐段复核与日期决策；`manifest.json` 绑定发布文件。冻结历史不改写，日常查询无需读取旧vault。

现行资格登记共有134条，保留原38条并追加96条。9条旧Roadmap表述和54条新增归档目标文字按具体claim退出当前检索；旧引用和ID保留。新法律文本在2026-11-12前不生效，模型退役文档以10/30观察日切换版本。未知发表日保留未知，观察日只证明最迟公开可见。

新增证据经过机器核对，60条精选claim另有AI上下文复核，33个来源有范围说明；人工Gold仍为54条。测试与同步状态以链接的验证记录为准，本说明不预先宣告安装完成或整体问答质量提升。
