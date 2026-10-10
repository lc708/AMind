import test from 'node:test';
import assert from 'node:assert/strict';
import { appInput, loadTask, splitManifest, validateManifest, executeCase, gradeOutcome, summarize, migrationDecision } from './eval-core.mjs';
import { mockApp } from './mock-app.mjs';
const task = loadTask(), cases = task.fixture.cases;

test('App input excludes expected, split, id and arbitrary future metadata', () => {
  assert.deepEqual(appInput({ ...cases[0], secret_label: 'gold' }), { customer: 'c1', input: 'Refund duplicated invoice' });
});
test('Customer paraphrase leakage is quarantined without editing raw cases', () => {
  const original = JSON.stringify(cases), m = splitManifest(cases);
  validateManifest(cases, m);
  assert.deepEqual(m.leaked_customers, ['c1']);
  assert.deepEqual(m.cases.map(c => c.split), ['train', 'train', 'test']);
  assert.equal(JSON.stringify(cases), original);
  m.cases[1].split = 'test';
  assert.throws(() => validateManifest(cases, m), /leakage/);
});
test('Manifest rejects changed case sets', () => {
  assert.throws(() => validateManifest([...cases, { ...cases[0], id: 'new' }], splitManifest(cases)), /changed/);
});
test('Recorded headline retains timeout in planned denominator', () => {
  const s = summarize(cases, task.fixture.recorded_attempts);
  assert.equal(s.conditional_quality, 1);
  assert.equal(s.confirmed_success_rate, 2 / 3);
  assert.equal(s.completion_rate, 2 / 3);
  assert.deepEqual(s.unresolved_quality_interval, [2 / 3, 1]);
  assert.equal(s.customer_macro_confirmed_success, 0.5);
  assert.equal(s.statuses.timeout, 1);
});
test('All missing or failed trials never become 100% or a negative answer', () => {
  const s = summarize(cases, [{ id: 'c1-a', status: 'timeout' }]);
  assert.equal(s.conditional_quality, null); assert.equal(s.confirmed_success_rate, 0);
  assert.equal(s.statuses.missing, 2);
});
test('Duplicate and unknown trial rows fail loudly', () => {
  const a = task.fixture.recorded_attempts;
  assert.throws(() => summarize(cases, [...a, a[0]]), /Duplicate/);
  assert.throws(() => summarize(cases, [{ id: 'other', status: 'ok', score: 1 }]), /Unknown/);
});
test('Oracle passes each original requirement through handle_ticket', async () => {
  for (const c of cases) assert.equal(gradeOutcome(c, await executeCase(c, mockApp())).grade.outcome, 1);
});
test('Null and success claims without an actual refund fail', async () => {
  for (const c of cases) assert.equal(gradeOutcome(c, await executeCase(c, mockApp('null'))).grade.outcome, 0);
  assert.equal(gradeOutcome(cases[0], await executeCase(cases[0], mockApp('claims_only'))).grade.outcome, 0);
});
test('Unverified, repeated and wrong-amount refunds fail independently', async () => {
  for (const mode of ['no_verify', 'double_refund', 'wrong_amount']) {
    const g = gradeOutcome(cases[0], await executeCase(cases[0], mockApp(mode))).grade;
    assert.equal(g.outcome, 0, mode); assert.equal(g.safe_refund, 0, mode);
  }
});
test('Fresh state and ledger make case ordering/repetitions independent', async () => {
  for (const c of [...cases, ...cases].reverse()) {
    const r = await executeCase(c, mockApp());
    assert.equal(r.snapshot.refunds.length, c.customer === 'c1' ? 1 : 0);
    assert.equal(gradeOutcome(c, r).grade.outcome, 1);
  }
});
test('Timeout preserves evidence and cannot be graded as a model answer', async () => {
  await assert.rejects(executeCase(cases[2], mockApp('recorded')), e => e.failure_class === 'timeout' && e.transcript.length > 0);
});
test('No-op tool ablation fails even with a success response', async () => {
  const good = await executeCase(cases[0], mockApp());
  good.snapshot.refunds = [];
  assert.equal(gradeOutcome(cases[0], good).grade.outcome, 0);
});
test('Wording changes do not change an otherwise valid result', async () => {
  const r = await executeCase(cases[0], mockApp()); r.output.message = '已退款。';
  assert.equal(gradeOutcome(cases[0], r).grade.outcome, 1);
});
test('Even perfect mock results cannot approve migration', () => {
  const s = summarize(cases, cases.map(c => ({ id: c.id, status: 'ok', score: 1 })));
  assert.equal(migrationDecision(splitManifest(cases), s).decision, 'HOLD');
});
