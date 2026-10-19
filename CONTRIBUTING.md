# Contributing to AMind

Thank you for helping make AMind more useful, traceable, and honest about its limits.

AMind welcomes four kinds of contributions:

- **Evidence corrections** — wrong source, quote, date, attribution, version, or claim boundary.
- **Use cases and evaluations** — realistic questions that expose a missing mode, weak answer pattern, or boundary failure.
- **Compatibility improvements** — clearer installation or packaging for Agent Skills-compatible clients.
- **Documentation and translations** — clearer explanations without overstating the evidence.

## Before opening an issue

1. Search existing issues for the source, claim ID, or feature.
2. For evidence problems, include the canonical public URL, exact relevant passage, publication date, and affected claim ID or file path.
3. Do not submit private, leaked, paywalled-without-permission, or personally sensitive material.
4. Use the [security policy](SECURITY.md) for vulnerabilities; do not disclose them in a public issue.

## Evidence standard

An evidence contribution should be independently checkable. Prefer a primary source and preserve enough surrounding context to show what the passage actually supports.

AMind distinguishes:

- a public position from a research question;
- an institution's publication from a named person's view;
- an original work from a later version or restatement;
- a direct claim from a strong inference or exploratory extrapolation.

Preserve publication time, observation time and effective time separately. A correction or superseding source changes current-answer eligibility; it does not authorize rewriting an old quote, claim identity or frozen release. Bind lifecycle decisions to their actual source/claim targets and evidence, retain unknown dates as unknown, and label scoped simulations and reported views. An observed-current page is not proof that its contents were published on the observation day.

If a proposed row cannot preserve those boundaries, it should remain a research note rather than enter the reviewed evidence kernel.

## Development checks

AMind's evidence tools use only the Python standard library. Install Git LFS before cloning, then run `git lfs pull` so the manifest-bound SQLite index is materialized. Source archives can contain only an LFS pointer; verify the payload before installing or testing. From the repository root, run:

```bash
python3 -B scripts/test_amind_skill.py
python3 -B scripts/verify_amind_increment.py
python3 -B scripts/verify_amind_refresh.py
python3 -B scripts/test_amind_refresh.py
python3 -B scripts/test_amind_refresh_sources.py
python3 -B scripts/verify_amind_increment.py --historical
python3 -B scripts/verify_amind_v1_release.py
```

Changes to packaged Skill data must remain deterministically generated from the selected release and preserve manifest hashes and row counts. Current totals and the collection cutoff are authoritative in `skills/amind/data/manifest.json`; inspect them with `query.py summary` and `stats --json` instead of copying an old total into prose. Keep original v1 and dated increments immutable; append reviewed updates and dated eligibility decisions in a new release.

The current knowledge package is **1.3.1**, observed through **2026-10-18**. `verify_amind_increment.py` selects its matching verifier; `--historical` independently checks the September 1.2.1 snapshot. `build_amind_skill.py --check` targets original `amind-v1` and is not a check of an incremented package. Test current eligibility, earlier `--as-of` dates, explicitly included history, corrections and future-effective material without deleting the underlying evidence. `--current` never implies a web fetch or verification beyond the recorded cutoff.

For **Engineering 0.3.2 / Eval Improve 0.4.3**, run:

```bash
python3 -B scripts/test_amind_app_skills.py
python3 -B scripts/test_amind_capability_kernel.py
python3 -B scripts/test_amind_behavior_regressions.py
python3 -B scripts/test_amind_eval_reporting.py
python3 -B scripts/check_amind_capability_map.py
python3 -B scripts/verify_amind_application_skills.py --output .codex-tmp/application-checks.json
```

The combined verifier runs four application suites (currently 160 checks) and records package hashes. Together with 60 knowledge/source checks, current offline verification totals 220 tests. These checks need Python 3.9+ and Node.js 18+, use local/synthetic fixtures and make no live model calls. Cover root/child output attribution, injection/recovery races, unknown hosted items, stage populations, cancellation and reconciliation, exact billing identities, negative controls and failure budgets when changing those contracts. A cropped successful subset is not full coverage, and a model name alone is not a complete billing scope.

Keep licenses/source pins current. The current engineering inventory covers 96 files/1,346 sections at `dbd4588f9e1033efb41dad4bef2f7947c8993d44`; retain the old 81-file inventory and September acceptance reports as historical evidence. Use `check_amind_capability_map.py --upstream /path/to/pinned/claude-api` to verify actual source hashes, since the default check validates metadata/local resources only. Distinguish coverage, local tests, live service compatibility and independent model/skill behavior; none can silently substitute for another. Do not run paid target/judge calls without an established task budget.

Maintain application skill sources here, then use `scripts/install_amind_series.py --apply --replace` to update personal copies with backups. See [AMind series](AMIND-SERIES.md) for version boundaries and the [October application report](reviews/2026-10-18-application-update.zh-CN.md) for implemented contracts, runnable examples and unmeasured limits. The historical [October 18 comparison](reviews/2026-10-18-comparison/report.zh-CN.md) records measured knowledge/timeliness and helper-contract gains; skill-guided model engineering and evaluation tasks tied. Its 24 CLI task executions cover 12 paired tasks with one repetition per task and version, so do not generalize them into a broad superiority claim.

Three repetitions on work-like projects found one gateway-contract difference and ties on the other engineering and evaluation tasks after semantic grader corrections. Policy citation support improved in the tested task. The [workplace report](reviews/2026-10-19-workplace/report.zh-CN.md) retains 42 main executions, six confirmations, measurement repairs and the runtime configuration deviation.

The original raw execution files are preserved in [checksum-bound review archives](reviews/2026-10-19-shipping/README.md). Run `python3 -B scripts/restore_amind_review_artifacts.py --apply` before opening raw-run links in a fresh checkout; restoration copies regular files only and executes no captured code.

For target trials, record the effective tool inventory and audit both command and MCP calls; configuration intent alone is insufficient. Validate behavior required by the public application contract, allowing equivalent internal labels. When a grader needs correction after outcomes are visible, retain the frozen original lane, calibrate the revision with positive and negative controls, and rescore every arm equally.

## Pull request checklist

- [ ] The change has a single, clear purpose.
- [ ] Public claims include a canonical source and appropriate context.
- [ ] Institutional, individual, and version boundaries are preserved.
- [ ] No text implies access to private Anthropic deliberations or official endorsement.
- [ ] Relevant tests and verifiers pass.
- [ ] User-facing changes update both `README.md` and `README.zh-CN.md` when applicable.

## 中文说明

AMind 欢迎证据修正、真实用例与评测、Agent Skills 客户端兼容性改进，以及文档和翻译贡献。

提交证据问题时，请提供权威公开来源、相关段落的完整语境、发布日期，以及受影响的 claim ID 或文件路径。不要提交私密、泄露、未经许可的付费内容或个人敏感信息。

所有贡献都必须保留四条边界：研究问题不等于公开结论，机构材料不自动等于个人观点，原始作品与后续版本不能混写，直接证据与推断必须分开。安全问题请按 [`SECURITY.md`](SECURITY.md) 私下报告。

当前知识 1.3.1、Engineering 0.3.2、Eval Improve 0.4.3 独立版本化。知识数量以 manifest／`summary`／`stats` 为准；更正和取代通过带来源、日期与目标身份的资格记录处理，保留原始证据和历史发布。当前离线检查数量和分项见上文。10 月 18 日对照中，所测知识／时效与 helper 合同改善，技能引导的模型工程与评估任务持平；24 次 CLI 执行覆盖 12 个配对任务，每个任务每版仅一次。真实 API、生产质量及实际费用需另行测量，9 月未达整体优于标准的结论不因新增测试而改写。工作场景三轮对照经评分语义修正后，工程仅网关出现一次拒绝合同差异，其余工程／评测任务持平；政策题的引用支持有所改善。42 次主执行、6 次确认、评分器修正与工具配置偏差见[工作场景评估报告](reviews/2026-10-19-workplace/report.zh-CN.md)。
