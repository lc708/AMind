# Evaluation platform lifecycle and export

Status checked against official documentation on 2026-10-18. Recheck the linked lifecycle pages before an actual migration; dates and available migration tools can change.

The [OpenAI Evals/datasets guide](https://developers.openai.com/api/docs/guides/evaluation-getting-started) says the Evals platform becomes read-only for existing users on **2026-10-31** and is scheduled to shut down on **2026-11-30**. The [deprecations page](https://developers.openai.com/api/docs/deprecations) is the current timeline authority. Keep these interfaces as compatibility/export sources for existing projects. Use the existing project evaluator or AMind's provider-neutral runner for a new evaluation by default. This changes hosting guidance, not the value of evaluation itself.

The official [Agent Builder migration guide](https://developers.openai.com/api/docs/guides/agent-builder/migrate-from-agent-builder) describes moving existing workflows into a maintained application. Preserve the project's selected provider and public entry point, and route implementation to `amind-engineering`. Agent Builder is a legacy compatibility/migration path, not a new default in this skill. Do not delete working workflows merely because a migration guide exists.

For a concrete migration:

1. Export datasets, human adjudications, rubrics/graders, prompt/configuration versions, run outputs, traces and native usage. Record resource IDs, export time, ownership and actual gaps. Preserve source exports.
2. Recreate the real application adapter and grader in the target environment. Preserve splits, independent groups, model/interface/tier/region and tool effects. An old dashboard result is not automatically compatible with a newly constructed runner identity.
3. Replay an authorized small fixture through both paths. Check case/repetition denominators, terminal states, stage/item coverage, grades, all-attempt cost and result identity. Separate deterministic migration checks from fresh model-quality evidence.
4. Regrade or rerun both sides when the rubric, task or evaluator changes. Keep unmeasured or unexported items explicit. Retain rollback/export access until the replacement and recovery path have been verified.

No migration or model call is launched merely by reading this reference. Existing project authorization governs execution; the runner still plans by default and preserves unknown spend.
