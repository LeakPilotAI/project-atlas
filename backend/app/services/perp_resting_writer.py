"""Order-control ACK around the existing canonical native perpetual writer.

No exchange order submission, accounting replacement, trust default or recovery.
Financial publication remains exactly one call through NativeFinancialWriter.
"""
from app.services.paper_financial_replay import FinancialSourceUncertain, body, digest, strict
from app.services.perp_resting_order import validate_fill, validate_order
from app.services.unified_native_writer import NativeFinancialWriter, OperationalPerpFinancialWriter


class RestingPerpWriter:
    def __init__(self, *, financial, orders):
        if (type(financial) not in (NativeFinancialWriter, OperationalPerpFinancialWriter) or orders is None
                or orders.execution_domain != financial.execution_domain
                or body(orders.manifest) != body(financial.manifest)):
            raise ValueError('RESTING_EXACT_FINANCIAL_DOMAIN_REQUIRED')
        self.financial, self.orders = financial, orders
        self.store, self.authority, self.manifest, self.binding = financial.store, financial.authority, financial.manifest, financial.binding
        self.components = {'financial': financial, 'orders': orders}
        control = self._control()
        if any(row['state'] == 'FILL_PENDING' for row in control['state']['orders'].values()):
            raise ValueError('RESTING_UNACKNOWLEDGED_FILL_RESTART_REFUSED')

    def _control(self):
        verifier = getattr(self.authority, 'verify_order_components', None)
        if (any(getattr(self, key) is not value for key, value in self.components.items())
                or self.financial.authority is not self.authority
                or self.financial.store is not self.store or verifier is None
                or verifier(self.binding, self.components) is not True):
            raise ValueError('RESTING_COMPONENT_AUTHORITY_REQUIRED')
        return self.orders.snapshot()

    def _cut(self):
        if any(row['state'] == 'FILL_PENDING' for row in self._control()['state']['orders'].values()):
            raise FinancialSourceUncertain('RESTING_CURRENT_FINANCIAL_CUT_UNKNOWN')
        return self.financial._cut()

    def verify_resting(self, proposal, observation):
        if (type(proposal) is not dict or set(proposal) != {'operation_id', 'kind', 'order'}
                or proposal['kind'] not in ('RESTING_ORDER', 'CANCEL_RESTING_ORDER')):
            raise ValueError('RESTING_EXACT_ADMISSION_REQUIRED')
        validate_order(proposal['order'], self.manifest)
        control, cut = self._control(), self.financial._cut()
        prior = control['state']['orders'].get(proposal['order']['order_id'])
        if prior is not None and body(prior['order']) != body(proposal['order']):
            raise ValueError('RESTING_ORIGINAL_ORDER_CONFLICT')
        verifier = getattr(self.authority, 'verify_resting_order', None)
        if verifier is None or verifier(self.binding, proposal, observation, cut, control) is not True:
            raise ValueError('RESTING_STRATEGY_OR_PORTFOLIO_AUTHORITY_REQUIRED')
        return True

    def dispatch_resting(self, proposal, reservation):
        order = validate_order(proposal['order'], self.manifest)
        control = self._control()
        prior = control['state']['orders'].get(order['order_id'])
        if prior is not None and body(prior['order']) != body(order):
            raise ValueError('RESTING_ORIGINAL_ORDER_CONFLICT')
        verifier = getattr(self.authority, 'verify_order_reservation', None)
        if (type(reservation) is not dict or reservation.get('state') != 'RESERVED'
                or verifier is None or verifier(self.binding, proposal, reservation, self._control()) is not True):
            raise ValueError('RESTING_GLOBAL_RESERVATION_REQUIRED')
        cancel = proposal['kind'] == 'CANCEL_RESTING_ORDER'
        event = {'kind': 'CANCEL' if cancel else 'ARM', 'order_id': order['order_id'],
                 'at': self.orders.clock() if cancel else order['created_at'],
                 'payload': {'reason': 'NO_FINANCIAL_EFFECT'} if cancel else order}
        return self.orders.apply(event, reservation)

    def preview(self, proposal, observation):
        if any(row['state'] == 'FILL_PENDING' for row in self._control()['state']['orders'].values()):
            raise ValueError('RESTING_FINANCIAL_SOURCE_UNCERTAIN')
        value = self.financial.preview(proposal, observation)
        if proposal['command']['schema'] == 'PAPER_PERP_MAKER_FILL_V1':
            row = self._control()['state']['orders'].get(proposal['command']['origin_ref'])
            if row is None or row['state'] != 'RESERVED':
                raise ValueError('RESTING_FILL_NOT_ADMITTED_OR_UNKNOWN')
            validate_fill(row['order'], proposal['command'])
        return value

    def verify_proposal(self, proposal, observation):
        self._control()
        if proposal['command']['schema'] == 'PAPER_PERP_MAKER_FILL_V1':
            row = self._control()['state']['orders'].get(proposal['command']['origin_ref'])
            if row and row['state'] == 'ACKNOWLEDGED':
                if row['command_digest'] != digest(proposal['command']):
                    raise ValueError('RESTING_CONFLICTING_FINANCIAL_RETRY')
                return self.financial.verify_proposal(proposal, observation)
        self.preview(proposal, observation)
        return True

    def dispatch(self, proposal, reservation):
        if any(row['state'] == 'FILL_PENDING' for row in self._control()['state']['orders'].values()):
            raise ValueError('RESTING_FINANCIAL_SOURCE_UNCERTAIN')
        command = self.financial._shape(proposal)
        if command['schema'] != 'PAPER_PERP_MAKER_FILL_V1':
            return self.financial.dispatch(proposal, reservation)
        row = self._control()['state']['orders'].get(command['origin_ref'])
        if row is None or row['state'] != 'RESERVED':
            raise ValueError('RESTING_NO_REPLAY_OF_UNCERTAIN_CALLBACK')
        validate_fill(row['order'], command)
        cut = self.financial._cut()
        self.financial._margin_authority(proposal, cut)
        if (proposal['source_head'] != cut['head']
                or self.authority.verify_reservation(self.binding, proposal, reservation, cut) is not True):
            raise ValueError('RESTING_FINANCIAL_RESERVATION_REQUIRED')
        self.store.preview(command)  # Validate canonical arithmetic/evidence before recording PENDING.
        event = {'kind': 'FILL_PENDING', 'order_id': command['origin_ref'], 'at': command['timestamp'], 'payload': command}
        self.orders.apply(event, reservation)
        receipt = self.financial.dispatch(proposal, reservation)
        if self.store.operation_receipt(command['operation_id'], digest(command)) != receipt:
            raise ValueError('RESTING_NATIVE_ACK_REQUIRED')
        ack = {'kind': 'ACK', 'order_id': command['origin_ref'], 'at': self.orders.clock(), 'payload': receipt}
        self.orders.apply(ack, reservation)
        return strict(body(receipt))

    def verify_order_drain(self):
        return all(row['state'] in ('ACKNOWLEDGED', 'CANCELLED') for row in self._control()['state']['orders'].values())

    def verify_financial_receipt(self, proposal, receipt):
        if self.store.operation_receipt(proposal['operation_id'], digest(proposal['command'])) != receipt:
            return False
        if proposal['command']['schema'] == 'PAPER_PERP_MAKER_FILL_V1':
            row = self._control()['state']['orders'].get(proposal['command']['origin_ref'])
            return (row is not None and row['state'] == 'ACKNOWLEDGED'
                    and row['command_digest'] == digest(proposal['command']) and row['receipt'] == receipt)
        return True
