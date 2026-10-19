# AMind increment — 2026-10-18

Append-only evidence refresh after `amind-v1-increment-2026-09-08`, packaged as AMind knowledge skill 1.3.0.

- [Chinese update report](reports/update.zh-CN.md)
- [Source inventory](reports/source-inventory.md)
- [Discovery audit](audits/discovery-summary.json)
- [Extraction audit and review boundary](audits/extraction-audit.json)
- [Current-answer decisions](data/current-status.jsonl)
- [Source/claim deterministic replay audit](audits/replay-determinism.json)
- [Application update report](../../reviews/2026-10-18-application-update.zh-CN.md)
- [Final validation](../../reviews/2026-10-18-refresh-validation.json)

`sources/` retains selected raw captures, extracted full texts and acquisition metadata. `delta/` holds new evidence and decisions; `data/` contains the combined portable release. `manifest.json` binds these artifacts by hash. The frozen v1 and September releases are unchanged.

All new claims remain machine checked; selected AI context and page reviews are separately recorded and do not create human Gold. Current eligibility is a dated sidecar: corrected or superseded claims remain accessible through `show` and `search --include-history`. Query dates after the recorded observation cutoff require fresh verification.
