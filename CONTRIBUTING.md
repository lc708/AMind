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

If a proposed row cannot preserve those boundaries, it should remain a research note rather than enter the reviewed evidence kernel.

## Development checks

AMind uses only the Python standard library. From the repository root, run:

```bash
python3 -B scripts/build_amind_skill.py --check
python3 -B scripts/test_amind_skill.py
python3 -B scripts/verify_amind_v1_release.py
```

Changes to the compact Skill data must remain deterministically generated from the frozen release and keep the manifest hashes and row counts current.

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
