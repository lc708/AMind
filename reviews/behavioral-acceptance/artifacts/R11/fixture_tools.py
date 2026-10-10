"""Local fixed billing service. Its audit record is evidence, never a reference answer."""
import copy


def fresh_state(customer):
    if customer not in {'c1', 'c2'}:
        raise ValueError('unknown fixed fixture customer')
    return {'customer': customer, 'invoice': ({'id': 'inv-c1', 'customer': 'c1',
            'duplicate': True, 'amount_cents': 1000} if customer == 'c1' else None),
            'verified': [], 'refunds': [], 'profile': {'unchanged': True}}


class FixtureTools:
    def __init__(self, state, broken_lookup=False):
        self.state = state
        self.events = []
        self.broken_lookup = broken_lookup

    def lookup_invoice(self, customer):
        invoice = None if self.broken_lookup else self.state['invoice']
        self.events.append({'op': 'lookup', 'customer': customer,
                            'invoice': copy.deepcopy(invoice)})
        return copy.deepcopy(invoice)

    def verify_invoice(self, invoice_id, customer):
        invoice = self.state['invoice']
        allowed = bool(invoice and invoice['id'] == invoice_id and
                       invoice['customer'] == customer and invoice['duplicate'])
        self.events.append({'op': 'verify', 'invoice_id': invoice_id,
                            'customer': customer, 'allowed': allowed})
        if allowed and invoice_id not in self.state['verified']:
            self.state['verified'].append(invoice_id)
        return allowed

    def refund_once(self, invoice_id, idempotency_key):
        invoice = self.state['invoice']
        allowed = bool(invoice and invoice['id'] == invoice_id and
                       invoice_id in self.state['verified'] and
                       idempotency_key == 'refund:' + invoice_id)
        existing = next((r for r in self.state['refunds'] if r['key'] == idempotency_key), None)
        self.events.append({'op': 'refund', 'invoice_id': invoice_id,
                            'key': idempotency_key, 'allowed': allowed,
                            'applied': bool(allowed and existing is None)})
        if not allowed:
            raise ValueError('forbidden refund attempt')
        if existing is None:
            self.state['refunds'].append({'invoice_id': invoice_id, 'key': idempotency_key,
                                         'amount_cents': invoice['amount_cents']})
        return {'refunded': True}
