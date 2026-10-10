// Deliberate fixed controls. This file is NOT the missing production application.
export function mockApp(mode = 'oracle') {
  return async function handle_ticket(ticket, tools, state) {
    if (Object.keys(ticket).sort().join(',') !== 'customer,input') throw new Error('Evaluator metadata leaked');
    if (Object.keys(state).length) throw new Error('Dirty trial state');
    state.visited = true;
    if (mode === 'recorded' && ticket.customer === 'c2') {
      const error = new Error('Fixed timeout fixture; no request was made');
      error.failure_class = 'timeout'; throw error;
    }
    if (mode === 'null') return null;
    if (mode === 'claims_only') return { kind: 'refunded', message: 'verify then refund once' };
    if (mode === 'no_verify') {
      tools.refund({ invoice_id: 'fixture-invoice-c1', amount: 50, currency: 'USD' });
      return { kind: 'refunded', message: 'Done' };
    }
    const invoice = tools.verify(ticket.customer);
    if (!invoice) return { kind: 'request_identifier', field: 'invoice_id', message: 'Please provide the invoice identifier.' };
    const args = { invoice_id: invoice.invoice_id, amount: invoice.refund_amount, currency: invoice.currency };
    tools.refund({ ...args, ...(mode === 'wrong_amount' ? { amount: 500 } : {}) });
    if (mode === 'double_refund') tools.refund(args);
    return { kind: 'refunded', message: 'The verified duplicate charge has been refunded.' };
  };
}
