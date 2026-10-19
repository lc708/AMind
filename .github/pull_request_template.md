## What changed

Describe the user-visible or evidence-level change in one or two sentences.

## Why

Link the issue or explain the concrete problem this solves.

## Verification

- [ ] `python3 -B skills/amind/scripts/verify.py` (after `git lfs pull`)
- [ ] `python3 -B scripts/verify_amind_increment.py`
- [ ] `python3 -B scripts/verify_amind_refresh.py`
- [ ] `python3 -B -m unittest scripts.test_amind_skill scripts.test_amind_increment scripts.test_amind_refresh scripts.test_amind_refresh_sources`
- [ ] `python3 -B scripts/verify_amind_application_skills.py --output .codex-tmp/application-checks.json` (when application skills change)
- [ ] `python3 -B scripts/verify_amind_v1_release.py` (historical snapshot)
- [ ] Public claims include a canonical source and adequate context.
- [ ] Institution/person/version and evidence/inference boundaries remain explicit.
- [ ] Relevant English and Chinese documentation stays aligned.
