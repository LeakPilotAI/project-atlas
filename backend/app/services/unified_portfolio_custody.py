"""Durable unified reservation protocol; no default issuer, risk conversion or roster.

The native journal is control evidence, not a financial ledger. Actual financial
effects stay in the existing lane writers. Risk/ownership/custody authentication
must be installed independently; a local hash or test lease grants no authority.
"""
import copy
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest, number, strict, text
from app.services.paper_portfolio_risk import LANES


def portfolio_transition(scope, manifest, state, event):
    if (type(event) is not dict or set(event) != {'kind', 'order_id', 'at', 'payload'}
            or type(event['at']) is not int or event['at'] < state['last_clock']):
        raise ValueError('UNIFIED_CONTROL_EVENT_OR_CLOCK_INVALID')
    after, p = copy.deepcopy(state), event['payload']
    pending = any(row['state'] == 'RESERVED' for row in state['operations'].values())
    if event['kind'] == 'SESSION':
        if (set(p) != {'grant_digest', 'session_id'} or pending or not state['entry_closed']
                or state['session'] is not None and state['finalized'] is None
                or p['grant_digest'] in state['sessions']):
            raise ValueError('UNIFIED_NEW_VERIFIED_SESSION_REQUIRED')
        text(p['session_id'])
        after.update(session=p['grant_digest'], entry_closed=False, finalized=None)
        after['sessions'].append(p['grant_digest'])
    elif event['kind'] == 'CLOSE':
        if p != {'grant_digest': state['session']} or state['session'] is None:
            raise ValueError('UNIFIED_CLOSE_SESSION_MISMATCH')
        after['entry_closed'] = True
    elif event['kind'] == 'RESERVE':
        request = p
        ident = event['order_id']
        kind = request['proposal']['kind']
        if (pending or state['session'] != digest(request['grant']) or ident != request['proposal']['operation_id']
                or ident in state['operations'] or request['lane'] not in LANES
                or state['entry_closed'] and kind in ('ENTRY', 'RESTING_ORDER')):
            raise ValueError('UNIFIED_PENDING_OR_CONFLICTING_RESERVATION')
        after['operations'][ident] = {'state': 'RESERVED', 'binding': digest(request), 'request': strict(body(request)), 'receipt': None}
    elif event['kind'] == 'ACK':
        row = state['operations'].get(event['order_id'])
        if row is None or row['state'] != 'RESERVED' or set(p) != {'binding', 'receipt'} or p['binding'] != row['binding']:
            raise ValueError('UNIFIED_CONTROL_ACK_CONFLICT')
        after['operations'][event['order_id']].update(state='ACKNOWLEDGED', receipt=strict(body(p['receipt'])))
    elif event['kind'] == 'FINAL':
        if (pending or not state['entry_closed'] or state['finalized'] is not None
                or set(p) != {'grant_digest', 'outcomes'} or p['grant_digest'] != state['session']
                or set(p['outcomes']) != set(LANES)
                or any(row.get('state') != 'ACKNOWLEDGED_FLAT_AND_DRAINED' for row in p['outcomes'].values())):
            raise ValueError('UNIFIED_FINAL_DRAIN_OR_REPORT_UNVERIFIED')
        after['finalized'] = strict(body(p))
    else:
        raise ValueError('UNIFIED_CONTROL_KIND_INVALID')
    after['revision'] += 1
    after['last_clock'] = event['at']
    return after


class UnifiedPortfolioCustody:
    def __init__(self, *, writers, journal, policy, risk, ownership, authority, clock):
        if (type(writers) is not dict or set(writers) != set(LANES)
                or any(x is None for x in (*writers.values(), journal, risk, ownership, authority, clock))):
            raise ValueError('UNIFIED_NATIVE_CUSTODY_DEPENDENCIES_REQUIRED')
        self.writers, self.journal, self.policy = dict(writers), journal, strict(body(policy))
        self.risk, self.ownership, self.authority, self.clock = risk, ownership, authority, clock
        self.components = {'writers': self.writers, 'journal': journal, 'policy_digest': digest(policy),
                           'risk': risk, 'ownership': ownership, 'clock': clock}
        self._writer_ids = dict(writers)
        if (journal.manifest['accounts'] != {lane: digest(writer.manifest) for lane, writer in writers.items()}
                or journal.manifest['policy_digest'] != digest(policy)):
            raise ValueError('UNIFIED_CUSTODY_ACCOUNT_POLICY_SUBSTITUTION')
        self._verify()

    def _verify(self):
        if (self.authority.verify_components(self.components) is not True
                or any(self.writers.get(lane) is not writer for lane, writer in self._writer_ids.items())
                or set(self.writers) != set(LANES)
                or digest(self.policy) != self.components['policy_digest']
                or self.journal is not self.components['journal'] or self.risk is not self.components['risk']
                or self.ownership is not self.components['ownership'] or self.clock is not self.components['clock']):
            raise ValueError('UNIFIED_CUSTODY_COMPONENTS_CHANGED')

    def _event(self, kind, identity, payload):
        issuer = getattr(self.authority, 'event_authorization', None)
        if issuer is None:
            raise ValueError('UNIFIED_ACCEPTED_CONTROL_EVENT_AUTHORITY_REQUIRED')
        authorization = issuer(kind, payload, self.components, self.clock())
        return self.journal.apply({'kind': kind, 'order_id': identity, 'at': self.clock(), 'payload': payload},
                                  authorization)

    def verify_restart(self, grant):
        self._verify()
        with self.ownership.lease(grant, self.writers, self.clock()) as owner, self.journal.guard():
            state = self.journal.snapshot()['state']
            if (owner.check() is not True or self.authority.verify_session(grant, self.components, self.clock()) is not True
                    or not state['entry_closed'] or digest(grant) in state['sessions']
                    or state['session'] is not None and state['finalized'] is None
                    or any(row['state'] == 'RESERVED' for row in state['operations'].values())):
                return False
            # A new grant is not recovery authority for surviving positions or
            # outstanding resting exposure. Verify native sources before SESSION.
            for writer in self.writers.values():
                cut = writer._cut()
                if any(number(position['remaining']) > 0 for position in cut['state']['positions'].values()):
                    return False
                if hasattr(writer, 'verify_order_drain') and writer.verify_order_drain() is not True:
                    return False
            self._event('SESSION', 'session:' + digest(grant), {'grant_digest': digest(grant), 'session_id': grant['session_id']})
            return owner.check() is True

    @contextmanager
    def lease(self, request):
        self._verify()
        with self.ownership.lease(request['grant'], self.writers, self.clock()) as owner, self.journal.guard():
            if owner.check() is not True or self.authority.verify_session(request['grant'], self.components, self.clock()) is not True:
                raise ValueError('UNIFIED_ACTUAL_OWNERSHIP_OR_SESSION_UNVERIFIED')
            yield PortfolioLease(self, request, owner)

    order_lease = lease

    def close_entry_admission(self, grant):
        with self.lease({'grant': grant}) as lease:
            state = self.journal.snapshot()['state']
            if state['session'] != digest(grant): return False
            if not state['entry_closed']: self._event('CLOSE', 'close:' + digest(grant), {'grant_digest': digest(grant)})
            return lease.owner.check() is True

    def verify_drain(self, grant):
        with self.lease({'grant': grant}) as lease:
            state = self.journal.snapshot()['state']
            return (state['entry_closed'] and state['session'] == digest(grant)
                    and all(row['state'] == 'ACKNOWLEDGED' for row in state['operations'].values())
                    and self.ownership.drain(grant, self.writers, self.clock()) is True and lease.owner.check() is True)

    def read_accounts(self, grant):
        """Existing-only coherent read; no writer mutex, latch or recovery side effect."""
        self._verify()
        before = self.journal.snapshot()
        unavailable = {'schema': 'ATLAS_UNIFIED_ACCOUNT_CUTS_V1', 'state': 'UNKNOWN', 'accounts': None,
                       'total_cash': None, 'total_equity': None, 'startup_authorized': False}
        if any(row['state'] != 'ACKNOWLEDGED' for row in before['state']['operations'].values()):
            return unavailable
        with self.ownership.lease(grant, self.writers, self.clock()) as owner:
            cuts = {lane: writer._cut() for lane, writer in self.writers.items()}
            verifier = getattr(self.authority, 'verify_read_cuts', None)
            if (owner.check() is not True or verifier is None or verifier(grant, self.components, cuts, self.clock()) is not True
                    or body(before) != body(self.journal.snapshot())):
                return unavailable
            accounts = {}
            for lane, cut in cuts.items():
                state, manifest = cut['state'], cut['manifest']
                accounts[lane] = {'epoch': manifest['epoch'], 'strategy': manifest['strategy'], 'currency': manifest['currency'],
                    'source_revision': state['revision'], 'source_head': cut['head'], 'observed_at': self.clock(),
                    'opening_cash': manifest['opening_cash'], 'cash': state['cash'], 'available_cash': state.get('available_cash', state['cash']),
                    'gross': state['gross'], 'realized_costs': state['costs'], 'net': state['net'],
                    'fees': state.get('fees'), 'slippage': state.get('slippage'), 'funding': state.get('funding'),
                    'positions': {key: p for key, p in state['positions'].items() if number(p['remaining']) > 0},
                    'valuation': None, 'valuation_status': 'UNAVAILABLE'}
                if hasattr(self.writers[lane], 'orders'):
                    control = self.writers[lane].orders.snapshot()
                    accounts[lane]['resting_orders'] = {key: {'state': row['state'], **{k: row['order'][k] for k in
                        ('symbol', 'side', 'quantity', 'limit_price', 'expires_at', 'source_revision')}}
                        for key, row in control['state']['orders'].items() if row['state'] in ('RESERVED', 'FILL_PENDING')}
                    if accounts[lane]['resting_orders']:
                        # Financial cash is proven, but pending-order spendable cash
                        # requires a separate accepted risk-reservation projection.
                        accounts[lane]['available_cash'] = None
            return {**unavailable, 'state': 'ACKNOWLEDGED', 'accounts': strict(body(accounts))}

    def finalize_shutdown(self, grant, outcomes, lanes):
        """Persist only the already native-verified lane reports and final drain."""
        with self.lease({'grant': grant}) as lease:
            if (set(lanes) != set(self.writers)
                    or any(lanes[k].writer is not writer for k, writer in self.writers.items())
                    or self.verify_drain(grant) is not True):
                return False
            for key, writer in self.writers.items():
                cut = writer._cut()
                if (outcomes[key].get('state') != 'ACKNOWLEDGED_FLAT_AND_DRAINED'
                        or outcomes[key].get('source_head') != cut['head']
                        or outcomes[key].get('session_id') != grant['session_id']
                        or any(number(p['remaining']) > 0 for p in cut['state']['positions'].values())
                        or lanes[key].stop(emergency=False) != outcomes[key]):
                    return False
            payload = {'grant_digest': digest(grant), 'outcomes': strict(body(outcomes))}
            prior = self.journal.snapshot()['state']['finalized']
            if prior is not None: return prior == payload and lease.owner.check() is True
            self._event('FINAL', 'final:' + digest(grant), payload)
            return lease.owner.check() is True


class PortfolioLease:
    def __init__(self, custody, request, owner):
        self.custody, self.request, self.owner = custody, strict(body(request)), owner
        self.policy = custody.policy
        self.before = self.projected = self.preview = None

    def _state(self): return self.custody.journal.snapshot()['state']

    def verify(self, request):
        if body(request) != body(self.request) or self.owner.check() is not True:
            return False
        state = self._state()
        if state['session'] != digest(request['grant']) or any(r['state'] == 'RESERVED' for r in state['operations'].values()):
            return False
        kind = request['proposal']['kind']
        if state['entry_closed'] and kind in ('ENTRY', 'RESTING_ORDER'): return False
        old = state['operations'].get(request['proposal']['operation_id'])
        if old is not None:
            if old['binding'] != digest(request): raise ValueError('UNIFIED_CUSTODY_OPERATION_CONFLICT')
            return True
        writer = self.custody.writers[request['lane']]
        if kind not in ('RESTING_ORDER', 'CANCEL_RESTING_ORDER'):
            self.preview = writer.preview(request['proposal'], self.custody.risk.observation(request))
        self.before, self.projected = self.custody.risk.project(request, self.custody.writers, self.preview, self.custody.clock())
        if self.custody.authority.verify_risk_projection(request, self.preview, self.before, self.projected) is not True:
            raise ValueError('UNIFIED_AUTHENTICATED_RISK_PROJECTION_REQUIRED')
        return True

    def acknowledged(self, request):
        row = self._state()['operations'].get(request['proposal']['operation_id'])
        return copy.deepcopy(row) if row and row['state'] == 'ACKNOWLEDGED' else None

    def reserve(self, request):
        if body(request) != body(self.request) or self.owner.check() is not True:
            raise ValueError('UNIFIED_CUSTODY_LEASE_CHANGED')
        self.custody._event('RESERVE', request['proposal']['operation_id'], request)
        return {'state': 'RESERVED', 'binding': digest(request)}

    def verify_accounting(self, request):
        return self.preview is not None and self.preview['receipt']['payload_digest'] == digest(request['proposal']['command'])

    def verify_shutdown_exit(self, request):
        return self._state()['entry_closed'] and self.custody.authority.verify_shutdown_request(request, self.custody.components) is True

    def verify_receipt(self, request, receipt):
        if self.owner.check() is not True: return False
        writer = self.custody.writers[request['lane']]
        proposal = request['proposal']
        if proposal['kind'] in ('RESTING_ORDER', 'CANCEL_RESTING_ORDER'):
            if writer.orders.verify_ack(receipt) is not True:
                return False
        elif (writer.store.operation_receipt(proposal['operation_id'], digest(proposal['command'])) != receipt):
            return False
        checker = getattr(writer, 'verify_financial_receipt', None)
        if checker is not None and proposal['kind'] not in ('RESTING_ORDER', 'CANCEL_RESTING_ORDER') and checker(proposal, receipt) is not True:
            return False
        writer._cut()  # Reconcile actual current source and QD/native/order ACK barriers.
        return self.custody.authority.verify_receipt(request, receipt, self.custody.writers) is True

    def acknowledge(self, request, receipt):
        if not self.verify_receipt(request, receipt): return False
        self.custody._event('ACK', request['proposal']['operation_id'], {'binding': digest(request), 'receipt': receipt})
        return self.owner.check() is True

    def replay(self, request, prior):
        row = self._state()['operations'].get(request['proposal']['operation_id'])
        if row is None or row['state'] != 'ACKNOWLEDGED' or row['binding'] != digest(request):
            raise ValueError('UNIFIED_REPLAY_UNCERTAIN')
        return strict(body(row['receipt']))
