# AMind skill series

AMind now has a knowledge skill and two application skills. The application layer provides reusable AI engineering and evaluation methods, executable diagnostics and a provider-neutral experiment runner. It learns from the pinned `claude-api` workflows and requires no Claude runtime or account. Codex is the current host; the target application need not use a Codex harness. Attribution and Apache-2.0 notices remain with the adapted source.

| Skill | Version | Purpose |
|---|---|---|
| [`amind`](skills/amind/SKILL.md) | 1.2.1 | Source-grounded judgment from the bounded public corpus, last evidence update 2026-09-08 |
| [`amind-engineering`](skills/amind-engineering/SKILL.md) | 0.2.1 | Prompt/contract audits, cost search, migration, state diagnostics, durable tool loop and agent operations |
| [`eval-improve`](skills/eval-improve/SKILL.md) | 0.3.0 | Application/grader runner, calibration, group-aware strict comparison, guardrails, cost ledger, final selection and full reports |

The evidence release and application skills have independent versions. Engineering instructions are not new evidence about Anthropic's public position. `eval-improve` keeps its existing invocation name and appears as **AMind Eval Improve** in skill UI metadata.

## Install from this checkout

The installer handles the two application skills. The original knowledge skill keeps its existing installation instructions. Python 3.9+ is needed for the local helpers; Node.js 18+ is needed only for the retained upstream lite reporter and its tests. The new full reporter uses Python alone. Actual Codex collection additionally needs a compatible Codex CLI and an existing working login. No extra package or model call is needed for installation, comparison or report generation.

```bash
python3 scripts/install_amind_series.py
python3 scripts/install_amind_series.py --apply --replace
```

The first command previews. The second installs to `$CODEX_HOME/skills` (default `~/.codex/skills`), backs up differing existing copies under the adjacent `skill-backups/` directory, verifies hashes and leaves identical copies untouched. Backups are outside skill discovery to avoid duplicate names. Use `--dest /your/skill-directory` for another destination. If a running client does not refresh skills automatically, start a new session or reload it.

The source directories are independently installable, but installing both preserves the evaluation routing. Maintain changes here, run checks, then reinstall; personal copies are deployment artifacts.

## Use / 使用

```text
用 $amind-engineering prompt-audit 检查这个项目的提示词和工具说明，给出问题与修改建议。
用 $amind-engineering cost-optimize 分析当前应用的开销，并在质量达标的前提下优化。
用 $amind-engineering migrate 把指定集成迁移到我选定的 OpenAI 模型和 API。
用 $amind-engineering upgrade 升级本项目的 SDK，修复兼容问题并验证。
用 $amind-engineering context-migrate 检查多轮状态、工具结果与上下文压缩。
用 $amind-engineering agent-build 为这个任务实现可运行的 Agent。
用 $eval-improve build 为这个应用建立真实任务评测。
用 $eval-improve improve 根据已有评测迭代，并保留最终测试集。
用 $eval-improve cost-search 在质量约束下搜索成本更低的配置，验证节省机制与组合效果。
```

`$amind-engineering build-eval` and `hillclimb` also route to `eval-improve`. These words select workflows; they are not separately billed API endpoints. Running a skill uses the active agent's normal usage path. Real target/judge model calls may consume additional subscription capacity or API spend. The optional Codex collector shows a plan first and requires `--execute` to run.

## Check and maintain

```bash
python3 -B scripts/test_amind_app_skills.py
python3 -B scripts/test_amind_capability_kernel.py
python3 -B scripts/test_amind_behavior_regressions.py
python3 -B scripts/check_amind_capability_map.py
```

The checks exercise synthetic application/grader processes, retries and complete attempt costs, resume/reconciliation, file and configuration drift, independent groups, guardrail vetoes, final-test freezing, state/stream/batch handling, durable effects, reports and installation. They make no live model calls. The source map indexes all 81 pinned upstream files and 1,005 Markdown section locators; those counts establish an audit index, not behavioral superiority.

Read [runner and offline demo](skills/eval-improve/references/runner.md), [capability map](skills/amind-engineering/references/capability-map.md), [verification report](reviews/2026-09-30-capability-core-verification.zh-CN.md), the [pre-registered skill behavior acceptance plan](reviews/2026-09-30-behavioral-acceptance-plan.zh-CN.md), and the [completed paired results](reviews/2026-09-30-behavioral-acceptance-results.zh-CN.md).

The 24 authorized independent executions are complete: ten task pairs tie, and two engineering pairs show narrow advantages on symmetric reviewer follow-up probes. All six evaluation pairs tie, so the preregistered overall-superiority criterion is **not met**. Nine engineering kernel gaps were repaired; 84 local application checks pass. Engineering 0.2.1 is installed, but the repaired package has not undergone a new independent-agent comparison.

本次升级补强的是能力内核：可运行的评测/评分流程、严格的实验比较、完整成本搜索、提示词与迁移方法、状态诊断、Agent 副作用及运行管理。软件适配不计作能力优势。已实测的局部优势、方法覆盖和未验证的真实模型效果分别记录；不把工具测试或源码索引冒充“全面优于”的证明。
