# Thirteen packaged task routes

These local templates adapt workflow intentions from the October upstream quickstarts. They contain provider-neutral stages and task-specific output checks, not copied Claude prompts, console behavior or credentials. The actual source is `assets/templates/*.json`; list it with `onboarding_contract.py --list` and read the selected file.

| Name | Work and key check |
|---|---|
| `bug-hunter` | Inspect → reproduce → combine; verified defects with file/line evidence |
| `contract-tracker` | Extract → crosscheck → combine; clauses, dates, document versions |
| `data-analyst` | Profile → validate → combine; provenance, units, missingness, reproducible calculations |
| `deep-researcher` | Research → challenge → combine; primary sources and competing explanations |
| `explainer-video-maker` | Outline → review → combine; checked script/storyboard, media generation needs an actual adapter |
| `field-monitor` | Observe → compare → combine; dated snapshots, meaningful changes |
| `incident-commander` | Triage → verify → combine; forensic facts and authorized recovery |
| `performance-tuner` | Baseline → verify → combine; correctness and representative measurements |
| `sprint-retro-facilitator` | Collect → challenge → combine; attributable facts and measurable actions |
| `structured-extractor` | Extract → validate → combine; schema plus business meaning and input evidence |
| `support-agent` | Investigate → check → combine; current policy and verified outcomes |
| `support-to-eng-escalator` | Diagnose → deduplicate → combine; reproducible reports and full case counts |
| `watchlist-scanner` | Scan → crosscheck → combine; dated evidence and complete watchlist denominator |

Start with one item or a deterministic workflow when adequate. A second review phase adds work and cost: measure its value, preserve failures in coverage and avoid automatic retries or silent budget expansion. Recurring routes leave schedules off until the user requests recurrence. Templates do not authorize external replies, tickets, recovery mutations or deployment. Use the user's selected inputs, language, model and existing infrastructure.
