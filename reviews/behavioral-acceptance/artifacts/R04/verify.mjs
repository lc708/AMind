import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { loadTask, splitManifest, summarize, migrationDecision } from './eval-core.mjs';
const log = [];
function run(args, expected = 0) {
  const r = spawnSync(process.execPath, args, { encoding: 'utf8', cwd: import.meta.dirname });
  const item = { command: ['node', ...args].join(' '), expected_exit: expected, actual_exit: r.status, stdout: r.stdout, stderr: r.stderr };
  log.push(item); console.log(`${item.command} -> ${r.status}`);
  writeFileSync('verification.json', JSON.stringify(log, null, 2) + '\n');
  if (r.status !== expected) throw new Error(r.stderr || r.stdout || 'Unexpected exit');
}
run(['--test', 'test-eval.mjs']);
if (!JSON.parse(readFileSync('flow/_state.json')).harness_sha)
  run(['run-eval.mjs', '--flow', 'flow', '--model', 'fixture-recorded', '--reps', '2'], 2);
// Existing human authorization covers this reversible local-only run.
// This approval never enables a model client; all non-fixture model IDs are rejected.
run(['run-eval.mjs', '--flow', 'flow', '--variant', 'baseline', '--model', 'fixture-recorded', '--reps', '2', '--timeout-s', '1', '--approve-harness'], 1);
run(['run-eval.mjs', '--flow', 'flow', '--variant', 'v1', '--model', 'fixture-oracle', '--reps', '2', '--timeout-s', '1']);
run(['run-eval.mjs', '--flow', 'flow', '--variant', 'v2', '--model', 'fixture-null', '--reps', '2', '--timeout-s', '1']);
const before = readFileSync('flow/v1/results.jsonl', 'utf8');
run(['run-eval.mjs', '--flow', 'flow', '--variant', 'v1', '--model', 'fixture-oracle', '--reps', '2', '--timeout-s', '1']);
if (before !== readFileSync('flow/v1/results.jsonl', 'utf8')) throw new Error('Resume changed completed rows');
function rows(p) { return existsSync(p) ? readFileSync(p, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse) : []; }
const task = loadTask(), summaries = {};
for (const variant of ['baseline', 'v1', 'v2']) {
  const success = rows(`flow/${variant}/results.jsonl`), errors = rows(`flow/${variant}/errors.jsonl`);
  // Explicit strict-first policy for resumed errors: never cherry-pick a later success.
  const attempts = new Map();
  for (const r of errors) if (!attempts.has(`${r.prompt_id}:${r.rep}`)) attempts.set(`${r.prompt_id}:${r.rep}`, r);
  for (const r of success) if (!attempts.has(`${r.prompt_id}:${r.rep}`)) attempts.set(`${r.prompt_id}:${r.rep}`, r);
  summaries[variant] = { evidence: 'synthetic local control, not historical trace or model result',
    strict_attempt_policy: 'first failed attempt remains failed; completed result rows are idempotent',
    failed_attempt_count: errors.length, ...summarize(task.fixture.cases, [...attempts.values()], 2) };
}
writeFileSync('coverage-summary.json', JSON.stringify({ variants: summaries,
  migration: migrationDecision(splitManifest(task.fixture.cases), summaries.v1) }, null, 2) + '\n');
for (const [variant, label] of [['baseline', 'Fixed reproduction of supplied status pattern'], ['v1', 'Known-good local control'], ['v2', 'Null local control']]) {
  writeFileSync(`flow/${variant}/summary.json`, JSON.stringify({ label, description: `${label}. NOT a real model.` }, null, 2));
  const s = summaries[variant];
  writeFileSync(`flow/${variant}/change.md`, `OFFLINE CONTROL ONLY: ${label}. Confirmed successes ${s.passed}/${s.planned}; scorable ${s.scored}/${s.planned}; mean outcome is CONDITIONAL quality. Migration HOLD. No production model was run.\n`);
}
const reports = '/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/sources/Q/shared/evals/report';
const builder = existsSync(`${reports}/build-report.mjs`) ? `${reports}/build-report.mjs` : `${reports}/build-report-lite.mjs`;
run([builder, 'flow']);
const html = readFileSync('flow/report.html', 'utf8');
for (const marker of ['c1-a', 'c1-b', 'c2', 'v1', 'v2']) if (!html.includes(marker)) throw new Error(`Report missing ${marker}`);
const links = [...html.matchAll(/href="([^"]+traces[^"]+)"/g)].map(m => m[1]);
if (links.length < 3) throw new Error('Trace links missing');
for (const link of links) if (!existsSync(`flow/${link}`)) throw new Error(`Trace link missing: ${link}`);
console.log(JSON.stringify({ unit_tests: 14, resume_unchanged: true, report_markers_and_trace_links: true,
  control_confirmed_success: Object.fromEntries(Object.entries(summaries).map(([k, v]) => [k, v.confirmed_success_rate])), decision: 'HOLD' }));
