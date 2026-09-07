# AMind single increment — 2026-09-08

This local release combines the immutable `amind-v1` baseline with one source update. No scheduler or recurring job is configured.

Read the [Chinese update report](reports/update.zh-CN.md) for source changes, scope, qualified findings, and collection gaps. The [manifest](manifest.json) records artifact hashes, counts, capture times, and review limits.

Skill 1.2.1 adds decision guidance and retrieval/scenario regressions. The [skill update record](reports/skill-update.zh-CN.md) distinguishes automated checks from the independent draft trial and its unrerun label correction.

- `data/`: complete combined evidence, with every baseline claim and passage retained.
- `delta/`: new units, passages and claims; source decisions; version relations; attribution and theme assignments; artifact exclusions; selected AI context reviews; lexical opposition candidates.
- `audits/`: frozen baseline fingerprints and collection/extraction summaries.
- `reports/source-inventory.md`: source decisions with original URLs.

The project skill at `skills/amind` includes the combined SQLite index and passage bundle. Its runtime uses only the Python standard library:

```bash
python3 skills/amind/scripts/query.py summary
python3 skills/amind/scripts/query.py search "mythos 5.1 regression" --current --json
python3 skills/amind/scripts/query.py search "reward seeker" --include-simulated --json
python3 skills/amind/scripts/query.py show nuwa1-claim-c07946b5b8c10fa0c037c2be --passage --json
python3 scripts/verify_amind_increment.py
```

Run these commands from the repository root. `verify_amind_increment.py --local-vault` additionally verifies the private capture workspace and derivative texts when they are available.

The construction controllers `run_amind_increment.py` and `build_amind_increment.py` reuse the existing local source-building workspace and its private capture inputs. They are not standalone web crawlers in a minimal public checkout. The release and skill runtime are self-contained. Rebuild stages are `prepare`, `extract`, and `package`; they do not fetch the web. Network stages use cached, hashed observations and preserve the v1 baseline.

New records are machine checked. Twelve selected claims were additionally reviewed by AI in passage context. The 54 human-reviewed gold rows remain unchanged. SQLite binary layout can vary by SQLite runtime version; record-level IDs, source hashes, and evidence bindings are the cross-runtime contract.
