# AMind skill series

AMind now has a knowledge skill and two application skills. The application layer provides reusable AI engineering and evaluation methods, executable diagnostics and a provider-neutral experiment runner. It learns from the pinned `claude-api` workflows and requires no Claude runtime or account. Codex is the current host; the target application need not use a Codex harness. Attribution and Apache-2.0 notices remain with the adapted source.

| Skill | Version | Purpose |
|---|---|---|
| [`amind`](skills/amind/SKILL.md) | 1.4.0 | Source-grounded judgment from public evidence observed through 2026-10-30, with dated eligibility and retained history |
| [`amind-engineering`](skills/amind-engineering/SKILL.md) | 0.4.1 | Prompt/contract audits, migrations, native multi-agent contracts, durable phased work, 13 templates and cache/state diagnostics |
| [`eval-improve`](skills/eval-improve/SKILL.md) | 0.5.1 | Application/grader runner, exact billing scope, judge calibration/drift, fixed stage coverage, persistent failure limits and strict comparison |

The evidence release and application skills have independent versions. Engineering instructions are not new evidence about Anthropic's public position. `eval-improve` keeps its existing invocation name and appears as **AMind Eval Improve** in skill UI metadata.

The knowledge [manifest](skills/amind/data/manifest.json), `query.py summary` and `stats --json` define the current packaged counts and observation boundary. `--current` prioritizes eligible recent evidence within that boundary; `--as-of YYYY-MM-DD` applies recorded publication/correction/effective dates, while `--include-history` exposes inactive or future-effective records with labels. These are offline retrieval controls, not a live model/policy registry or recurring refresh. Original v1 and the [September 1.2.1 increment](release/amind-v1-increment-2026-09-08/reports/update.zh-CN.md) remain historical snapshots.

## Install from this checkout

Materialize the knowledge index with `git lfs pull` after cloning; see the bilingual README for prerequisites and the payload verification command. The installer handles the two application skills by default; add `--with-knowledge` to validate and install all three together with one rollback backup. Python 3.9+ is needed for the local helpers; Node.js 18+ is needed only for the retained upstream lite reporter and its tests. The new full reporter uses Python alone. Actual Codex collection additionally needs a compatible Codex CLI and an existing working login. No extra package or model call is needed for installation, comparison or report generation.

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
用 $amind-engineering agent-onboard contract-tracker 生成可提交配置和 dry-run，再验证本地分阶段工作流。
用 $eval-improve build 为这个应用建立真实任务评测。
用 $eval-improve improve 根据已有评测迭代，并保留最终测试集。
用 $eval-improve cost-search 在质量约束下搜索成本更低的配置，验证节省机制与组合效果。
```

`$amind-engineering build-eval` and `hillclimb` also route to `eval-improve`. These words select workflows; they are not separately billed API endpoints. Running a skill uses the active agent's normal usage path. Real target/judge model calls may consume additional subscription capacity or API spend. The optional Codex collector shows a plan first and requires `--execute` to run.

Engineering's template planner also plans by default. Its explicit local write produces an application configuration contract and workflow specification; it does not deploy a hosted agent, attach credentials or enable a schedule. The staged journal persists item/aggregate outcomes, original budgets, cancellation and unknown effects. A final summary cannot replace missing worker evidence. Read [onboarding](skills/amind-engineering/references/onboarding.md), [13 task routes](skills/amind-engineering/references/templates.md) and [workflow execution/recovery](skills/amind-engineering/references/workflow-recipes.md).

## Check and maintain

```bash
python3 -B scripts/test_amind_app_skills.py
python3 -B scripts/test_amind_capability_kernel.py
python3 -B scripts/test_amind_behavior_regressions.py
python3 -B scripts/test_amind_eval_reporting.py
python3 -B scripts/check_amind_capability_map.py
python3 -B scripts/verify_amind_application_skills.py --output .codex-tmp/application-checks.json
```

Current offline verification is recorded in the [October 30 receipt](reviews/2026-10-30-update/validation/final.json). The previous shipping baseline had 220 tests; this refresh adds native cache/Decisions, method diagnostics, all-package installation, portable-source replay, curation and index-transition checks. They use local fixtures and make no live model calls.

The current engineering [source map](skills/amind-engineering/references/capability-map.md) pins `dbd4588f9e1033efb41dad4bef2f7947c8993d44` (2026-10-09): 96 files and 1,346 Markdown section locators. Its [original 81-file/1,005-section inventory](skills/amind-engineering/references/upstream-capabilities-2026-09-29.json) remains historical evidence. The map checker validates metadata/resources by default; `--upstream` adds byte/hash validation against a checkout of that exact pin. File coverage does not establish hosted-feature parity or behavioral superiority.

Read the current [runner and offline demo](skills/eval-improve/references/runner.md), [accounting and calibration](skills/eval-improve/references/accounting-calibration.md), and [platform lifecycle/export guidance](skills/eval-improve/references/platform-lifecycle.md). Historical comparison evidence remains in the [September verification report](reviews/2026-09-30-capability-core-verification.zh-CN.md), [pre-registered behavior plan](reviews/2026-09-30-behavioral-acceptance-plan.zh-CN.md) and [completed paired results](reviews/2026-09-30-behavioral-acceptance-results.zh-CN.md).

In the September comparison, 24 authorized independent executions completed: ten task pairs tied, and two engineering pairs showed narrow advantages on symmetric reviewer follow-up probes. All six evaluation pairs tied, so the preregistered overall-superiority criterion was **not met**. That repair produced Engineering 0.2.1 and 84 passing local checks. The initial October 0.3.0/0.4.0 refresh added local contracts and checks. The subsequent [October 18 comparison](reviews/2026-10-18-comparison/report.zh-CN.md) records measured knowledge/timeliness and helper-contract gains, followed by the current patch repairs. Skill-guided model engineering and evaluation tasks tied: 24 CLI task executions covered 12 paired tasks, with one repetition per task and version. These bounded results do not establish general superiority or overwrite the September findings.

Three repetitions on work-like projects found one gateway-contract difference and ties on the other engineering and evaluation tasks after semantic grader corrections. Policy citation support improved in the tested task. The [workplace report](reviews/2026-10-19-workplace/report.zh-CN.md) retains 42 main executions, six confirmations, measurement repairs and the runtime configuration deviation.

The original raw execution files are preserved in [checksum-bound review archives](reviews/2026-10-19-shipping/README.md). Run `python3 -B scripts/restore_amind_review_artifacts.py --apply` before opening raw-run links in a fresh checkout; restoration copies regular files only and executes no captured code.

当前版本为知识 1.4.0 / Engineering 0.4.1 / Eval Improve 0.5.1，离线检查数量和分项见上文。分阶段执行、多代理归属、费用身份、评分器、覆盖率和报告合同有本地回归；10 月 18 日对照记录了所测知识／时效与 helper 合同的改善，技能引导的模型工程与评估任务持平。24 次 CLI 任务执行覆盖 12 个配对任务，每个任务每版仅运行一次，不足以推出普遍优势。真实 API 兼容与生产质量、成本仍需另行验证；9 月未达到整体优于标准的结论保留。知识覆盖量与截止日期以独立 manifest 为准。工作场景三轮对照经评分语义修正后，工程仅网关出现一次拒绝合同差异，其余工程／评测任务持平；政策题的引用支持有所改善。42 次主执行、6 次确认、评分器修正与工具配置偏差见[工作场景评估报告](reviews/2026-10-19-workplace/report.zh-CN.md)。

## October 30 update

Knowledge 1.4.0 appends the October 30 observation to the immutable October 18 release. Engineering 0.4.0 adds executable architecture/review/oversight/handoff diagnostics; Eval Improve 0.5.0 adds native cache/Decisions contracts. See the [update and verification report](reviews/2026-10-30-update/report.zh-CN.md).

To validate and install all three packages together, including the materialized knowledge index, use `python3 -B scripts/install_amind_series.py --with-knowledge --apply --replace`. The installer stages the complete set, keeps previous copies outside skill discovery and rolls back publication failures. Omit `--apply` to preview.
