范围与假设：本次仅审查 `task.json:5` 的提示词，以 `task.json:6–16` 的工具清单、来源说明和目标约束为依据。目标保持 **current configured model, preserve provider**；没有提供实际模型 ID、提供方配置、工具实现或消费者源码，因此不推定模型、不迁移 SDK，也不引用某款模型的新行为来证明删改有效。采用指定技能 `sources/Q/SKILL.md` 路由的 `shared/prompt-audit.md`：盘点、查来源、逐条分类、提出独立补丁、验证。原始 `task.json` 保持不变，全部新文件均为任务目录中的审查与验证材料。

建议先删除与实际工具清单矛盾的 `You have no tools.`，并把删除“三句话”要求作为第二项独立提案。支付状态检查、禁止重复扣款和 `RESULT:` 前缀全部保留。既有支付事故是保留规则的理由；没有模型实测证据支持削弱这些规则。`RESULT:` 恰好是七个 ASCII 字符，消费者截取前七个字符后应完整保留正文，包括原有空白。

盘点结果：一个提示词字段、两个工具名称、四条来源记录、一个目标约束。没有工具描述、请求构造代码、模型配置、代理配置或应用测试。未访问任务目录外的仓库历史和消费者，因为任务明确限制范围；来源证据取自 fixture，未用文件时间推断。模式扫描命中 `IMPORTANT`、`NEVER`、无工具声明、前缀和句数限制。Group 1：一项修改、一项低置信度观察；Group 2：一项修改；Group 3：不适用（仅有名称，无描述）；Group 4：不适用（没有请求或运行代码）。

| 位置与原文 | 模式 | 证据与判断 | 置信度 / 行动 |
|---|---|---|---|
| `task.json:5` — `You have no tools.` | Group 2，过期环境事实 | 与 `task.json:7–8` 的 `lookup_payment`、`charge_once` 矛盾，且 `task.json:12` 明确其来自旧文本集成。删除该句即可；不把工具名称再复制进系统提示词。 | 高；remove，补丁 01 |
| `task.json:5` — `output exactly three sentences.` | Group 1f，输出数量限制 | `task.json:14` 没有记录业务要求；固定句数与需要返回的支付结果没有已知对应关系。删除可作为独立假设，不能声称已改善目标模型。没有读取到的其他消费者可能仍依赖句数。 | 中；remove，补丁 02，仅候选 |
| `task.json:5` — `IMPORTANT`、`NEVER` | Group 1a，强调语言信号 | 大写本身不足以证明过期。`task.json:11` 记录真实重复扣款事故，目标模型是否仍需强调未知。 | 低；flag，不改 |

保留项：`always check payment status before retrying`、`NEVER charge twice` 是支付行为约束，不能因看起来像禁止性措辞而删除。`Begin every answer with RESULT:` 是消费者契约，不能当作格式噪音删除，也不擅自替换为 JSON 或别的 API 格式。

完整候选提示词见 `candidate_prompt.txt`：

```text
IMPORTANT: always check payment status before retrying. NEVER charge twice. Begin every answer with RESULT:
```

以下两份补丁依次作用于本地审查快照，每份只表达一个修改。它们没有应用到 `task.json` 或任何生产文件。第一阶段 `01_tools_corrected.txt` 保留“三句话”要求，适用于只接受确定性纠错的审查决定。

```diff
--- original_prompt.txt
+++ 01_tools_corrected.txt
@@ -1 +1 @@
-IMPORTANT: always check payment status before retrying. NEVER charge twice. You have no tools. Begin every answer with RESULT: and output exactly three sentences.
+IMPORTANT: always check payment status before retrying. NEVER charge twice. Begin every answer with RESULT: and output exactly three sentences.
```

```diff
--- 01_tools_corrected.txt
+++ candidate_prompt.txt
@@ -1 +1 @@
-IMPORTANT: always check payment status before retrying. NEVER charge twice. Begin every answer with RESULT: and output exactly three sentences.
+IMPORTANT: always check payment status before retrying. NEVER charge twice. Begin every answer with RESULT:
```

验证使用 Python 标准库，工作目录为本任务目录，实际执行：

```sh
python3 -m unittest -v test_regression.py
python3 regression.py
```

两条命令最终均退出 0；第一条报告 **12 tests, OK**，第二条报告 **22 synthetic trace expectations checked; all met: True**。测试包含多个子场景，不把 22 个固定轨迹算作 22 次模型运行。`verification.json` 保存逐项结果及原版、只纠正工具声明版、完整候选版的静态对照；`input_manifest.json` 的 SHA-256 验证 `task.json` 未被修改。

| 检查 | 覆盖范围 | 证据性质 |
|---|---|---|
| 修改隔离 | 第一步只删无工具声明，第二步只删句数限制；支付规则逐字不变；不加入提供方或工具参数假设 | 静态回归 |
| 消费者兼容 | 真实执行 `response[7:]`；中文、换行、原有空格、1/3/4 句正文完整保留；拒绝前导空白、代码围栏、小写或全角冒号等错误前缀 | 按 fixture 描述重建的本地消费者断言；未运行真实消费者 |
| 支付轨迹 | 已支付不重扣；未支付先查再扣；pending/unknown/error 不扣款；超时后查询为已支付不重扣；失败后重新查询；不同支付独立处理 | 人工固定轨迹与独立断言，未执行真实工具 |
| 负例与变异 | 未查询直接扣款、错支付 ID、盲重试、已成功后重复扣款、陈旧查询覆盖已付款结果、未知工具及畸形状态全部被检测 | 证明断言能发现这些违规轨迹，不证明模型会避免它们 |

`regression.py` 是离线轨迹检查器，不是支付应用或 LLM 替身。`traces.json` 的状态名、支付 ID 和记录形状是显式的测试词汇，不能视为已知的真实工具 schema。它保守要求每次扣款前有新的 unpaid 查询，并检查已确认支付不能再扣款；这是本地回归契约，不能替代服务端幂等和并发控制。工具叫 `charge_once` 并不构成幂等保证；未检查真实工具的键作用域、超时语义、查询一致性、并发请求或持久化行为。

原版和候选没有接受模型调用。静态对照能证明文本矛盾消失及关键规则保留；固定轨迹测试能证明检查器和前缀消费规则在这些样本上工作。它们不能证明修改后模型真的调用工具、不会重复扣款、输出更好或句数解除没有行为回归。未做网络访问、凭据读取、目标模型 API 调用或真实支付操作。

后续实际集成验证应使用同一配置模型、真实工具 schema 和无副作用环境，保持案例与验收条件固定，先比较原版与阶段一，再单独比较阶段一与句数删除版；检查工具事件而非“我已检查”的口头声明。只要出现漏查、重复扣款或前缀破坏，该改动就不能通过；若仅句数删除导致消费者回归，恢复该条要求，保留阶段一纠错。本次交付完整给出候选、补丁和可运行离线回归，不作生产就绪声明。
