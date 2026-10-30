# AMind 全面更新与交付报告 · 2026-10-30

本次按[知识与能力差距分析](../2026-10-30-knowledge-capability-analysis.zh-CN.md)完成更新。知识观察截止日推进至 **2026-10-30（Asia/Singapore）**，三项技能版本为 **AMind 1.4.0、Engineering 0.4.0、Eval Improve 0.5.0**。本地已安装副本已替换并通过哈希和实际命令核验；原版本保存在技能发现目录之外。源工作区同步结果见[同步收据](validation/workspace-sync.json)，总体交付状态见[最终收据](validation/final.json)。

## 知识更新与历史漏项

| 项目 | 更新前 | 更新后 | 本轮增加 |
|---|---:|---:|---:|
| 分析单元 | 1,537 | 1,607 | 70 |
| 原子claim | 129,132 | 140,665 | 11,533 |
| passage | 20,521 | 21,516 | 995 |
| 人工Gold | 54 | 54 | 0 |
| 现行资格登记 | 38 | 134 | 96 |

70个单元由29个10/19–10/30发表单元、16个更早历史回补、1个10/18当天漏录、19个日期未确认的首次索引和5个已有作品修订组成。它们包含正文与附件，不能解释为70篇十月新文章。已补齐当前claude.dev入口中的10篇博客，覆盖可靠自动化、代码评审、评测设计与hillclimbing、effort、任务成本、mods、云会话和性能工程；这10篇发表于9/22–10/15，均属于上次漏项。

新增研究覆盖GRAFT、Auto Mode红队、代码攻击面缩减、形式化验证、UK AISI事故再评估、专家判断影响、漏洞链、蛋白结合物与药物开发。治理、产品和人物材料补齐公共利益报告／基金、LTBT、路线图、新产品与托管边界、Import AI 477–478及Circuits October。另回补Contextual Retrieval、早期Circuits更新、Claude Code最佳实践、sandboxing及MCP代码执行等历史材料。

逐项标题、日期、作者和真实来源URL见[70单元来源清单](../../release/amind-v1-increment-2026-10-30/reports/source-inventory.md)；内容含义和限制见[知识更新说明](../../release/amind-v1-increment-2026-10-30/reports/update.zh-CN.md)。30个已核实的迁移别名没有重复算新作品；4份正文未变、1份模板／元数据变化和3份团队导航均保留判断依据。

本轮枚举90个入口、观察6,319个唯一URL；5,138个“新增URL”是发现层的候选计数。105份选定捕获全部成功，另有3份早先捕获的导航留存，共108份原始记录；选定捕获含17个附件。Dario archive和Jared Kaplan publications两个入口仍失败，不能据此声称全网或所有口述材料已覆盖。六组静态种子仅重新枚举，未当成HTTP重抓成功。完整验证后，82个入口推进入库游标；其余8个保留原游标。[发现记录](../../release/amind-v1-increment-2026-10-30/audits/discovery-summary.json)、[采集记录](../../release/amind-v1-increment-2026-10-30/audits/collection-summary.json)、[游标收据](../../release/amind-v1-increment-2026-10-30/audits/checkpoint-verification.json)

## 过时内容退出当前检索，原证据保留

- 9条旧Roadmap计划与项目表述按具体claim在10/19退出当前资格，连到相应完成、退休或替代证据。新增档案中54条原Version目标文字也单独历史化，后续Update报告保持独立资格。
- 原额外routine监督承诺、红队待完成目标、笼统政策新目标及旧Moonshot阶段描述按范围更新。Constitution同步的条件与90天承诺、持续alignment assessments和weakest-link机制继续保留。内部完成日期、公开披露日期和未来交付期限分别记录。
- AUP与Supported Regions继续以11/12为生效边界，兼容新版法律页跨行的缩写日期。旧版模型弃用操作手册在10/30观察日退出，新版同日可用；没有把模型退役日或API版本号当成文档发表日。
- 未知发表日仍为空。`available_by`证明最迟在观察日已公开可见，不证明当天发表。J++更新的月份标题和feed更新时间没有被伪造为精确发表日；公共利益报告中的目标、序言与LTBT结语分别归属。

旧129,132条claim逐条保留，旧38条资格决策逐字保留，v1／9月／10月18日共1,874个冻结文件哈希不变。默认现行检索应用资格过滤；`show`仍能显示原claim及失效原因，`--as-of`和`search --include-history`支持历史检查。原54条人工Gold字节不变。60条精选claim另经AI上下文复核、33个来源加入范围说明，均未冒充人工语义Gold。[策展审计](../../release/amind-v1-increment-2026-10-30/curation/curation-audit.json)

## 工程与评测能力修复

Engineering增加可执行的[method diagnostics](../../skills/amind-engineering/references/method-diagnostics.md)，并接入技能路由：

| 模式 | 实际提供的检查 | 保留的限制 |
|---|---|---|
| architecture | 组件fold／merge／as-tool／keep建议，完整配对任务与生产路径覆盖，逐任务退化、约束、费用与时延 | 依赖可信采集；建议本身不证明更好，不自动改架构 |
| review | 稳定finding键、相同补丁的检查证据、修改面覆盖、轮数预算与明确解决记录 | 达到轮数不自动批准，问题在下一轮消失不等于解决 |
| oversight | 冻结分母、偏好跟随、事前判断与转向、随机分配和替代方案记录 | 跟随率不是错误率，不自动建立因果或判断独立性 |
| handoff | 动作／资源版本绑定、摘要授权来源、共享文件哈希和监测覆盖 | 不认证外部证据或签名；权限执行仍须在应用层落实 |
| claude-api | 显式Anthropic 2026-10-21版本的若干已移除请求模式 | 不是完整SDK迁移或线上兼容证明 |

Eval Improve增加[原生计量适配与Decisions子集预检](../../skills/eval-improve/references/accounting-calibration.md)：

- Responses缓存读取与30m／12h写入分别核算，输入各子集只计费一次；Decisions使用自己的30m、输入计费合同，保留服务返回的原生usage。
- 费用身份绑定provider、endpoint、model、region、tier及cache policy。未知计量、冲突子集或缺失费率保持unknown，旧适配器保持兼容。缓存前缀规划仅是显式输入下的离线情景，不替代真实用量。
- Decisions支持本地消息／JSON／图像／问题子集，1–400个问题、类型明确的choices与有界JSON；不下载图片，不推断模型可用性，不代替完整SDK校验。
- 评测runner在进程组终止被拒绝时保留timeout／output_limit这一原始失败，尝试回收适配器leader，明确记录未确认的进程组清理，并禁止在这种情况下自动重试。没有把leader退出等同于所有后代已停止。

原工程上游固定版本、旧评测与行为对照报告保留。本轮增加的是上述离线方法、合同与实现，未把Anthropic产品功能移植等同于AMind功能，也未宣称完整上游SDK或托管产品能力同步。

## 验证证据

最终 **337项检查全部通过**：应用210项、知识与采集127项。安装后另完成9项实际命令检查，包括知识包验证、摘要、历史claim日期切换、原生usage→费用计算、Decisions预检、能识别配对任务退化的架构诊断及重复安装预览。三包共102个文件与被测源包哈希一致；安装备份与更新前个人副本指纹一致。

- [应用210项及确切包哈希](validation/application-checks.json)
- [知识127项及确切包哈希](validation/knowledge-checks.json)
- [当前完整来源／引文／索引／历史验证](validation/snapshot-current.json)
- [9月历史独立验证](validation/historical-september.json)、[10月18日历史独立验证](validation/historical-october.json)
- [实际安装](validation/installation.json)、[安装后核验](validation/installed-verification.json)

验证中发现并修复了法律缩写日期漏识别、附件未完成却可推进游标、符号链接可指向冻结输出，以及进程回收的失败分类问题。早期运行的失败证据保留；一次知识检查在文档重封清单前启动，按预期拒绝临时不匹配的清单，已在停止发布写入、重封后完整重跑通过。见[该中间失败记录](validation/intermediate-knowledge-before-seal.json)与[进程诊断](validation/runner-termination-race.json)。

上述均为本地进程、确定性夹具、真实当前索引和安装副本检查。没有调用付费target／judge API，没有做新一轮独立技能Agent质量对照，不能据此宣布整体问答、生产效果或费用收益已提高。原有行为对照的平局、有限优势和未达到总体优于标准的结论保留。

## 本地交付与维护

已安装位置为 `~/.codex/skills/amind`、`amind-engineering`、`eval-improve`，分别为1.4.0／0.4.0／0.5.0。旧副本备份位于 `/Users/damonalbarn/.codex/skill-backups/amind-series-lbf6cr7c`。客户端若仍缓存旧技能，需要新会话或重新加载；安装目录内容已实际核验。

源文件在隔离worktree完成，按更新前指纹检查后同步回 `/Users/damonalbarn/Work/AMind`；无关文件保留，Git提交与远端由用户后续管理。本轮worktree保留供检查。同步写入、备份与逐文件哈希以[workspace-sync.json](validation/workspace-sync.json)为准。

复核入口：

```bash
python3 -B scripts/verify_amind_increment.py
python3 -B scripts/verify_amind_refresh.py --release release/amind-v1-increment-2026-10-18
python3 -B skills/amind/scripts/verify.py
python3 -B scripts/install_amind_series.py --with-knowledge
```

后续修改应在源工作区进行。采集、构建、AI策展、封包、完整验证、游标提交、重封清单和最终验证按顺序执行；安装用 `scripts/install_amind_series.py --with-knowledge --apply --replace`，先暂存、验证并保留备份。静态种子、失败来源或未解决正文／附件不得用一次发现成功替代入库完成。本轮没有配置周期性刷新。
