# Application-skill evidence

These records support AMind Engineering 0.2.1 and AMind Eval Improve 0.3.0. Start with the [paired behavior results](2026-09-30-behavioral-acceptance-results.zh-CN.md) and the [latest release checks](2026-10-11-release-checks.json). The preregistered overall-superiority criterion was not met; the release does not claim that the two skills universally outperform claude-api.

The archived tasks, transcripts, reference answers, tools, receipts and SQLite databases are synthetic local fixtures. The `private/` name in one task denotes the evaluation's reference-answer boundary, not production customer data. Logs and SQLite companion files are intentionally retained because the original execution ledger hashes them. Absolute `/Users/...` and `.codex-tmp/...` paths describe the historical execution host; they are evidence, not paths a new user must have. Preserve these original records when reproducing a run and write new results to disposable copies.

The current skill tests are self-contained. From the repository root:

```sh
python3 -B scripts/verify_amind_application_skills.py --output .codex-tmp/local-checks.json
python3 -B scripts/test_amind_skill.py
```

They make no live target-model or judge-model calls. The published test evidence records package hashes; changes to a package require new evidence. An offline pass is not evidence of real-model quality, costs, provider compatibility or general behavioral superiority.

Historical independent-agent runs used frozen AMind Engineering 0.2.0 / Eval Improve 0.3.0, and the complete claude-api tree at Anthropic commit `8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4`. Their source hashes and assignments are in [execution-ledger.json](behavioral-acceptance/execution-ledger.json). Local source caches are excluded from the repository.

To reconstruct the AMind snapshot, copy the two published packages into a disposable `sources/P/` directory, then run the following from that directory, replacing the repository path:

```sh
patch -R -p1 < /path/to/AMind/reviews/behavioral-acceptance/skill-repair.patch
```

The reverse patch restores the seven changed Engineering files; Eval Improve is unchanged. All 48 reconstructed source-file hashes were checked against the execution ledger before publication. Restore `sources/Q/` from the [pinned upstream skill](https://github.com/anthropics/skills/tree/8a1541c4a3ffa5a20a5a91de0dcf3f0bab1d1ef4/skills/claude-api), then verify its 81 files with:

```sh
python3 -B scripts/check_amind_capability_map.py --upstream /path/to/sources/Q
```

When replaying an archived worker, substitute these reconstructed source paths for historical absolute paths and execute a copy of the worker directory. Some worker commands rely on the original `runs/Rxx` and `sources/` relative layout. Root reproduction commands and outputs are retained under [checks/](behavioral-acceptance/checks/). Replaying a local implementation cannot reproduce the stochastic agent's original decision process.

The archived claude-api-side scaffolds, including R04's adapted runner, derive from the pinned Anthropic skill under Apache-2.0. Their deliverables identify the source. Retained upstream code and AMind adaptations carry the [Apache license](../skills/amind-engineering/LICENSE.txt) and package attribution in [Engineering NOTICE](../skills/amind-engineering/NOTICE.txt) and [Eval Improve NOTICE](../skills/eval-improve/NOTICE.txt). The preserved lite reporter's upstream provenance and hash are documented in [upstream.md](../skills/eval-improve/references/upstream.md).
