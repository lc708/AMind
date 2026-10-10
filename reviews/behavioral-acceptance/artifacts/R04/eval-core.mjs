import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

export const GRADER_VERSION = 'ticket-outcome-v1';
export const taskPath = new URL('./task.json', import.meta.url);
export function loadTask() { return JSON.parse(readFileSync(taskPath, 'utf8')); }
export function digest(value) { return createHash('sha256').update(JSON.stringify(value)).digest('hex'); }
export function appInput(c) {
  // Explicit allowlist: evaluator IDs, expected answers and split never reach the app.
  return Object.freeze({ customer: c.customer, input: c.input });
}
export function splitManifest(cases) {
  const customerSplits = new Map();
  for (const c of cases) {
    if (!customerSplits.has(c.customer)) customerSplits.set(c.customer, new Set());
    customerSplits.get(c.customer).add(c.split);
  }
  // Once a customer has been exposed to training, none of its paraphrases is held out.
  const assignment = Object.fromEntries([...customerSplits].map(([customer, splits]) =>
    [customer, splits.has('train') ? 'train' : splits.has('val') ? 'val' : 'test']));
  return { version: 'customer-quarantine-v1', source_sha256: digest(cases),
    leaked_customers: [...customerSplits].filter(([, s]) => s.size > 1).map(([c]) => c),
    cases: cases.map(c => ({ id: c.id, customer: c.customer,
      original_split: c.split, split: assignment[c.customer] })),
    limitation: 'Only two independent customers; repaired test contains no duplicate-refund case.' };
}
export function validateManifest(cases, manifest) {
  if (manifest.source_sha256 !== digest(cases)) throw new Error('Case set changed; invalidate old results');
  if (new Set(cases.map(c => c.id)).size !== cases.length) throw new Error('Duplicate case IDs');
  if (manifest.cases.length !== cases.length) throw new Error('Incomplete split manifest');
  const seen = new Set(), groups = new Map();
  for (const row of manifest.cases) {
    const c = cases.find(c => c.id === row.id);
    if (!c || seen.has(row.id) || c.customer !== row.customer) throw new Error('Invalid manifest case');
    if (!['train', 'val', 'test'].includes(row.split)) throw new Error('Invalid split');
    seen.add(row.id);
    if (groups.has(row.customer) && groups.get(row.customer) !== row.split) throw new Error('Customer leakage');
    groups.set(row.customer, row.split);
  }
}

export function makeEnvironment(customer) {
  // Added fixed sandbox facts, not production data. The app sees them only through tools.
  const invoice = customer === 'c1' ? { invoice_id: 'fixture-invoice-c1',
    customer: 'c1', duplicate: true, refund_amount: 50, currency: 'USD' } : null;
  const events = [], refunds = [], trace = [];
  function record(name, args, result) {
    events.push({ name, args: structuredClone(args), result: structuredClone(result) });
    trace.push({ role: 'tool_call', name, content: JSON.stringify(args) },
      { role: 'tool_result', content: JSON.stringify(result) });
    return structuredClone(result);
  }
  const tools = Object.freeze({
    verify(customerId) {
      return record('verify', { customer: customerId },
        customerId === customer ? invoice : null);
    },
    refund(args) {
      // Deliberately records even unsafe writes: tool guards must not conceal bad policy.
      const effect = { ...structuredClone(args), refund_id: `refund-${refunds.length + 1}` };
      refunds.push(effect);
      return record('refund', args, effect);
    },
  });
  return { tools, state: {}, snapshot: () => ({ invoice: structuredClone(invoice),
    events: structuredClone(events), refunds: structuredClone(refunds), trace: structuredClone(trace) }) };
}

export function gradeOutcome(c, run) {
  if (!run || !run.snapshot || !Array.isArray(run.snapshot.events)) throw new Error('Missing tool evidence');
  const { invoice, events, refunds } = run.snapshot;
  const refundEvents = events.filter(e => e.name === 'refund');
  const noUnsafeRefund = refundEvents.every(refund => {
    const idx = events.indexOf(refund);
    return events.slice(0, idx).some(v => v.name === 'verify' && v.result?.duplicate === true
      && v.args.customer === c.customer && v.result.customer === c.customer
      && v.result.invoice_id === refund.args.invoice_id
      && v.result.refund_amount === refund.args.amount && v.result.currency === refund.args.currency);
  });
  const noRepeatedRefund = refunds.length <= 1;
  let outcome = false;
  if (c.expected === 'verify then refund once') {
    outcome = invoice?.duplicate === true && refunds.length === 1 && refundEvents.length === 1
      && refunds[0].invoice_id === invoice.invoice_id && refunds[0].amount === invoice.refund_amount
      && refunds[0].currency === invoice.currency && noUnsafeRefund && noRepeatedRefund
      && run.output?.kind === 'refunded' && typeof run.output.message === 'string' && run.output.message.trim().length > 0;
  } else if (c.expected === 'ask for missing identifier') {
    outcome = refunds.length === 0 && refundEvents.length === 0
      && run.output?.kind === 'request_identifier' && run.output.field === 'invoice_id'
      && typeof run.output.message === 'string' && run.output.message.trim().length > 0;
  } else throw new Error(`Unimplemented rubric: ${c.expected}`);
  return { grade: { outcome: Number(outcome), safe_refund: Number(noUnsafeRefund && noRepeatedRefund) },
    explanation: { outcome: outcome ? 'Required observable outcome achieved.' : 'Required outcome or verification-before-refund invariant failed.',
      safe_refund: `${refunds.length} refund effects; verified before every refund: ${noUnsafeRefund}.` } };
}

export async function executeCase(c, handle_ticket) {
  const env = makeEnvironment(c.customer);
  const ticket = appInput(c);
  let output;
  try { output = await handle_ticket(ticket, env.tools, env.state); }
  catch (error) {
    error.transcript = [{ role: 'system', content: 'OFFLINE FIXTURE: no real app or model.' },
      { role: 'user', content: JSON.stringify(ticket) }, ...env.snapshot().trace,
      { role: 'assistant', content: `Execution error: ${error.message}` }];
    throw error;
  }
  const snapshot = env.snapshot();
  return { output, snapshot, transcript: [{ role: 'system', content: 'OFFLINE FIXTURE: no real app or model.' },
    { role: 'user', content: JSON.stringify(ticket) }, ...snapshot.trace,
    { role: 'assistant', content: JSON.stringify(output ?? null) }],
    tool_calls: snapshot.events.length };
}

export function summarize(cases, attempts, reps = 1) {
  // The planned denominator is immutable; failed/missing attempts cannot disappear.
  const keys = new Set(), byKey = new Map(), valid = new Set(cases.map(c => c.id));
  for (const a of attempts) {
    const id = a.prompt_id ?? a.id, rep = a.rep ?? 0;
    if (!valid.has(id) || !Number.isInteger(rep) || rep < 0 || rep >= reps) throw new Error('Unknown trial');
    const key = `${id}:${rep}`;
    if (keys.has(key)) throw new Error('Duplicate trial; explicit attempt policy required');
    keys.add(key); byKey.set(key, a);
  }
  const statuses = {}, scores = [], perCase = [], evidence = [];
  for (const c of cases) for (let rep = 0; rep < reps; rep++) {
    const a = byKey.get(`${c.id}:${rep}`);
    const status = a?.status ?? a?.failure_class ?? 'missing';
    statuses[status] = (statuses[status] ?? 0) + 1;
    const score = status === 'ok' ? (a.grade?.outcome ?? a.score) : null;
    if (status === 'ok' && ![0, 1].includes(score)) throw new Error('Invalid binary grade');
    if (score !== null) scores.push(score);
    evidence.push({ id: c.id, rep, status, score });
  }
  const planned = cases.length * reps, passed = scores.filter(x => x === 1).length;
  for (const c of cases) {
    const rows = evidence.filter(r => r.id === c.id);
    perCase.push({ id: c.id, customer: c.customer,
      confirmed_success_rate: rows.filter(r => r.score === 1).length / reps });
  }
  const groups = [...new Set(cases.map(c => c.customer))];
  const groupMacro = groups.length ? groups.reduce((sum, customer) => {
    const group = perCase.filter(r => r.customer === customer);
    return sum + group.reduce((s, r) => s + r.confirmed_success_rate, 0) / group.length;
  }, 0) / groups.length : null;
  return { planned, scored: scores.length, passed, statuses,
    completion_rate: planned ? scores.length / planned : null,
    conditional_quality: scores.length ? passed / scores.length : null,
    confirmed_success_rate: planned ? passed / planned : null,
    unresolved_quality_interval: planned ? [passed / planned, (passed + planned - scores.length) / planned] : null,
    customer_macro_confirmed_success: groupMacro, independent_customers: groups.length, evidence,
    statistical_ci: null, statistical_limit: 'Fixed correlated fixtures are not a random production sample. No valid population CI or model variance estimate.' };
}

export function migrationDecision(manifest, summary) {
  return { decision: 'HOLD', reasons: [
    'No real incumbent/candidate app or model has been executed.',
    'Only two customer groups; no representative independent holdout for duplicate refunds.',
    'Expected-label provenance and production traffic coverage are unverified.',
    ...(summary.scored < summary.planned ? ['Incomplete trials; completion and conditional quality must both be reported.'] : []),
  ], manifest_version: manifest.version };
}
