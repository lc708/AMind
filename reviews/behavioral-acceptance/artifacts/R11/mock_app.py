"""Deterministic contract fixture, NOT the production application or model."""


def handle_ticket(ticket, tools, state):
    invoice = tools.lookup_invoice(ticket['customer'])
    if invoice is None:
        return {'resolution': 'need_identifier', 'requested_fields': ['invoice_id'],
                'message': 'Please provide the invoice identifier so I can locate it.'}
    if not tools.verify_invoice(invoice['id'], ticket['customer']):
        return {'resolution': 'escalate', 'message': 'Invoice verification failed.'}
    tools.refund_once(invoice['id'], 'refund:' + invoice['id'])
    return {'resolution': 'refunded', 'invoice_id': invoice['id'],
            'message': 'I verified the duplicate and refunded it once.'}
