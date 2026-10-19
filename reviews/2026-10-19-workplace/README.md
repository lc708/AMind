# AMind workplace comparison, 2026-10-19

This study follows the 2026-10-18 comparison without replacing its records. It tests more realistic offline work: patching multi-file applications, replaying incidents, preserving durable state, and auditing complete evaluation artifacts. The tasks are constructed work simulations, not sampled production traffic.

The immutable main design is [protocol.json](protocol.json): four application tasks × three repetitions × two skill versions = 24 target executions, plus two citation tasks × three repetitions × three treatments = 18. Up to six further target executions are reserved for explicitly after-discovery validation. There are no automatic retries. The requested host configuration remains `gpt-6.1-sol` / `ultra`; actual served identity is not independently attested.

Application scoring uses the real CLI from a fresh portable copy of the delivered repository, with assigned skills, original repository/output, private references and network inaccessible to the application subprocess. Each of 14 probes belongs to a rubric domain; a domain passes only if all its probes pass. Fatal guardrails remain separate from means. Three repeats of a task do not become three independent task families.

Citation scoring compares pre-refinement, documentation-only refinement, and the full refinement including the curation reason. All use the same source collection/SQLite/passages, cutoff 2026-10-18. A fresh anonymous AI grader passed 40/40 pre-registered criterion judgments across eight known-answer controls. This is not human calibration. The source-support contract distinguishes a real curation interval from independent primary evidence and checks a directly supported paper as a positive control against over-refusal.

The main treatment snapshots were copied into all 42 task directories before product repair. Independent product diagnostics can therefore be repaired in the product checkout without replacing the target used for the main comparison. Primary outputs are not inspected until all 42 main executions finish. Repair validation is recorded separately and cannot be presented as untouched test evidence.

`measurement-files.json`, `snapshots.json`, the per-lane frozen protocols and per-run source hashes preserve provenance. Runtime path-deny policies block private references, known host histories and sibling runs; canaries verify selected boundaries. This is not a full host read or inference egress allowlist. Native usage is retained; unknown dollar cost is never reported as zero.

See the final Chinese report and validation receipts after completion. The previous [comparison report](../2026-10-18-comparison/report.zh-CN.md) remains historical.
