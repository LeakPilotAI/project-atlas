"""Both actual strategy planners/native writers; all external trust and prices synthetic.

USD/USDC conversion at1 is explicitly test policy, not operational parity evidence.
No third strategy, financial ledger, provider request or protected resource access.
"""
import copy
import importlib.util
import json
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.services.paper_financial_replay import digest, number
from app.services.quality_dips_publication_reader import QualityDipsPublicationReader
from app.services.quality_dips_unified_planner import QualityDipsUnifiedPlanner
from app.services.quality_dips_unified_writer import QualityDipsUnifiedShutdown
from app.services.unified_native_writer import (
    CanonicalWriterLane,
    PerpShutdownCoordinator,
)
from app.services.unified_paper_runtime import UnifiedPaperRuntime
from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
from perp_order_native_fixture import DurableTestPins
from perp_order_native_fixture import build as build_perp
from qd_autonomous_binding_fixture import build as build_qd
from test_alpaca_iex import message
from test_qd_unified_source_planner import components
from test_unified_native_writer import FixtureCustody
from test_unified_paper_runtime import Installation

REPO = Path(__file__).resolve().parents[1]


class ActualSourceRisk:
    def __init__(self, qd, perp, clock): self.qd, self.perp, self.clock = qd, perp, clock
    def observation(self, request): return self.runtime.observations[request['lane']]
    def cuts(self, states, heads, controls):
        # Reuse the existing fixture's native perpetual margin/funding projection.
        helper = FixtureCustody.__new__(FixtureCustody)
        helper.clock = self.clock
        rows = helper.cut(states['HYPERLIQUID'], heads['HYPERLIQUID'])
        for row in rows: row['allocated_usd'] = '1000'
        q = rows[0]
        q.update(epoch=self.qd.writer.manifest['epoch'], revision=states['QUALITY_DIPS']['revision'],
                 head=heads['QUALITY_DIPS'], positions=[], committed_usd='0')
        for ident, p in states['QUALITY_DIPS']['positions'].items():
            qty = number(p['remaining'])
            if qty <= 0: continue
            quote = self.qd.f.snapshot()['quotes'][0]
            if quote['state'] != 'FRESH': raise ValueError('SYNTHETIC_TEST_RISK_QUOTE_UNAVAILABLE')
            exposure = qty * max(number(p['entry']), number(quote['ask']))
            cost = qty * number(p['entry'])
            q['positions'].append({'id': ident, 'instrument_id': p['instrument']['instrument_id'], 'side': p['side'],
                'quantity': str(qty), 'gross_usd': str(exposure), 'loss_usd': str(cost), 'reserved_usd': str(cost), 'derivatives': None})
        q['committed_usd'] = str(sum(number(p['reserved_usd']) for p in q['positions']))
        target = rows[1]
        target['revision'] += controls['state']['revision']
        target['head'] = digest([target['head'], controls['head']])
        for key, row in controls['state']['orders'].items():
            if row['state'] not in ('RESERVED', 'FILL_PENDING'): continue
            order = row['order']; qty = number(order['quantity'])
            mark = number(str(order['plan']['reference_price']))
            margin = qty * max(mark, number(order['limit_price'])) / number(order['leverage'])
            notional, loss = qty * mark, qty * number(order['risk_price'])
            d = {'schema': 'ATLAS_PERP_RISK_EVIDENCE_V2', 'margin_mode': 'INITIAL_RESERVE_CASH_SETTLED_FUNDING_V2',
                'leverage': order['leverage'], 'max_leverage': '2', 'notional': str(notional), 'collateral': str(margin),
                'maintenance_margin': str(notional * number('.05')), 'unrealized_pnl': '0', 'funding_cash': '0',
                'fees_cash': '0', 'slippage_cash': '0', 'equity': str(margin), 'stress_loss_cash': str(loss),
                'funding_complete': True, 'fee_schedule_id': 'synthetic-fees', 'funding_cut': 'NO_POSITION_YET',
                'mark_id': order['source_digest'], 'book_id': order['source_digest']}
            target['positions'].append({'id': self.perp.m['epoch'] + ':pending:' + key, 'instrument_id': 'HL:' + order['symbol'],
                'side': order['side'], 'quantity': order['quantity'], 'gross_usd': str(notional), 'loss_usd': str(loss),
                'reserved_usd': str(margin), 'derivatives': d})
        target['committed_usd'] = str(sum(number(p['reserved_usd']) for p in target['positions']))
        return rows
    def project(self, request, writers, preview, now):
        raw = {lane: writer._cut() for lane, writer in writers.items()}
        states, heads = {k: v['state'] for k, v in raw.items()}, {k: v['head'] for k, v in raw.items()}
        control = self.perp.orders.snapshot()
        before = self.cuts(states, heads, control)
        states, heads, projected = copy.deepcopy(states), dict(heads), copy.deepcopy(control)
        p, lane = request['proposal'], request['lane']
        if p['kind'] in ('RESTING_ORDER', 'CANCEL_RESTING_ORDER'):
            order = p['order']
            if p['kind'] == 'RESTING_ORDER':
                projected['state']['orders'][order['order_id']] = {'order': order, 'state': 'RESERVED'}
            else: projected['state']['orders'][order['order_id']]['state'] = 'CANCELLED'
            projected['state']['revision'] += 1
            projected['head'] = digest([control['head'], p])
        else:
            states[lane] = preview['after']
            heads[lane] = digest([raw[lane]['head'], p['command'], preview['receipt']])
            if p['command']['schema'] == 'PAPER_PERP_MAKER_FILL_V1':
                projected['state']['orders'][p['command']['origin_ref']]['state'] = 'ACKNOWLEDGED'
                projected['state']['revision'] += 2
                projected['head'] = digest([control['head'], p])
        self.last = (request, preview, before, self.cuts(states, heads, projected))
        return self.last[2:]


def build(root, confinement, qd_confinement):
    root = Path(root)
    qd_root = Path(qd_confinement) / ('account-' + uuid.uuid4().hex)
    qd_root.mkdir()
    s = build_qd(qd_root, qd_confinement, stamp=1793026790, session_reports=True)
    q = components(s)
    perproot = root / 'perp'; perproot.mkdir()
    p = build_perp(perproot, confinement, stamp=s.x.n.now[0] - 1, shared_now=s.x.n.now)
    clock = s.x.x.clock
    q_packet = {'schema': 'QD_SCANNER_PUBLICATION_V1', 'source_id': 'SYNTHETIC_ORIGINAL_SCANNER', 'revision': 1,
        'observed_at': clock(), 'bundles': [q.b], 'monitors': {}}
    q_source = SimpleNamespace(read_publication=lambda timeout: copy.deepcopy(q_packet))
    q.a.verify_publication_components = lambda binding, actual: actual['writer'] is q.writer and actual['source'] is q_source
    q.a.verify_scanner_publication = lambda binding, packet, cut, now: packet == q_packet and q.a.valid
    reader = QualityDipsPublicationReader(writer=q.writer, source=q_source)
    q.a.verify_planner_components = lambda binding, actual: actual == {'writer': q.writer, 'observer': q.observer, 'quotes': q.quotes, 'reader': reader}
    q.a.verify_decision_source = lambda binding, request, observation, cut: q.a.valid and q.observer.verify_observation(observation)
    qp = QualityDipsUnifiedPlanner(writer=q.writer, observer=q.observer, quotes=q.quotes, reader=reader)
    writers = {'QUALITY_DIPS': q.writer, 'HYPERLIQUID': p.writer}
    risk = ActualSourceRisk(q, p, clock)
    policy = {'schema': 'ATLAS_PAPER_PORTFOLIO_RISK_V2', 'policy_id': 'EXPLICIT_SYNTHETIC_USD_USDC_CONVERSION_AT_ONE',
        'capital_usd': '2000', 'max_gross_usd': '300', 'max_loss_usd': '200', 'max_positions': 4,
        'allocations': {'QUALITY_DIPS': '1000', 'HYPERLIQUID': '1000'}, 'max_age': 5, 'max_perp_leverage': '2',
        'perp_collateral_model': 'INITIAL_RESERVE_CASH_SETTLED_FUNDING_V2'}

    class Ownership:
        valid = True
        @contextmanager
        def lease(self, grant, actual, now):
            yield SimpleNamespace(check=lambda: self.valid and all(actual[k] is writers[k] for k in writers))
        def drain(self, grant, actual, now):
            return self.valid and p.writer.verify_order_drain() and s.runtime.runtime.engine.status() == 'STOPPED'
    ownership = Ownership()

    class Authority:
        valid, fail_ack = True, False
        def verify_components(self, actual): return self.valid and actual['writers'] == writers and actual['risk'] is risk
        def verify_session(self, grant, actual, now): return self.valid and grant == {'session_id': 'synthetic-unified-session'}
        def verify_risk_projection(self, request, preview, before, after): return self.valid and risk.last == (request, preview, before, after)
        def verify_shutdown_request(self, request, actual): return self.valid and r.state == 'STOPPING' and r.entry_closed.is_set()
        def verify_receipt(self, *args): return self.valid
        def verify_read_cuts(self, grant, actual, cuts, now):
            return (self.verify_session(grant, actual, now) and actual['writers'] == writers
                    and all(cuts[k] == writers[k]._cut() for k in writers))
        def event_authorization(self, kind, payload, actual, at):
            if self.fail_ack and kind == 'ACK': raise OSError('SYNTHETIC_GLOBAL_ACK_FAILURE')
            self.active = {'kind': kind, 'payload_digest': digest(payload), 'at': at}
            return copy.deepcopy(self.active)
        def verify_scope(self, scope, pin, at): return self.valid and scope['manifest_digest'] == digest(binding)
        def verify_event(self, scope, event, state, token):
            return self.valid and token == self.active and token == {'kind': event['kind'], 'payload_digest': digest(event['payload']), 'at': event['at']}
    a = Authority()
    binding = {'schema': 'UNIFIED_CONTROL_BINDING_V1', 'epoch': 'synthetic-unified-control', 'opened_at': clock(),
        'accounts': {k: digest(w.manifest) for k, w in writers.items()}, 'policy_digest': digest(policy),
        'roster_digest': digest(['QD_V5_DECISION', 'QD_SOURCE', 'QD_PROJECTION', 'QD_REPORT', 'PERP_SOURCE', 'PERP_PROJECTION',
                                'PERP_REPORT', 'PERP_ORDERS', 'GLOBAL_CUSTODY'])}
    spec = importlib.util.spec_from_file_location('two_lane_control', REPO / 'scripts/volume_inspector/unified_portfolio_store.py')
    control_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(control_module)
    scope = {'schema': 'UNIFIED_PORTFOLIO_SCOPE_V1', 'execution_domain': 'DISPOSABLE_TEST', 'epoch': binding['epoch'],
        'manifest_digest': digest(binding), 'writer_id': 'EXPLICIT_SYNTHETIC_GLOBAL_WRITER'}
    pin = control_module.PortfolioControlStore.provision_disposable(root / 'global', scope, confinement=confinement)
    pins = DurableTestPins(root / 'global-pin.json', clock, pin)
    journal = control_module.PortfolioControlStore(root / 'global', trust=pins, authority=a, clock=clock,
                                                   manifest=binding, execution_domain='DISPOSABLE_TEST')
    custody = UnifiedPortfolioCustody(writers=writers, journal=journal, policy=policy, risk=risk, ownership=ownership, authority=a, clock=clock)
    qstop = QualityDipsUnifiedShutdown(writer=q.writer, quotes=q.quotes, reports=s.runtime.runtime.reports, session_id='synthetic-unified-session')
    books = SimpleNamespace(shutdown_evidence=lambda position, cut, at: p.planner._book(p.packet, position['symbol']))
    pstop = PerpShutdownCoordinator(writer=p.writer, books=books, reports=p.service, clock=clock,
                                    session_id='synthetic-unified-session', started_at=clock())
    p_observer = SimpleNamespace(last=None)
    async def p_observe():
        p_observer.last = {'lane': 'HYPERLIQUID', 'at': clock(), 'connection': 'CONNECTED', 'session': 'OPEN',
                           'signal': None, 'source': {'id': p.packet['source_id'], 'revision': p.packet['revision']}}
        return copy.deepcopy(p_observer.last)
    p_observer.observe = p_observe
    p_observer.verify_observation = lambda value: value == p_observer.last
    q.a.verify_lane = lambda b, c: c['writer'] is q.writer and c['planner'] is qp and c['shutdown'] is qstop
    p.a.verify_lane = lambda b, c: c['writer'] is p.writer and c['planner'] is p.planner and c['shutdown'] is pstop
    qlane = CanonicalWriterLane(writer=q.writer, observer=q.observer, planner=qp, shutdown=qstop, reports=qstop.reports)
    plane = CanonicalWriterLane(writer=p.writer, observer=p_observer, planner=p.planner, shutdown=pstop, reports=p.service)
    r = UnifiedPaperRuntime(lanes={'QUALITY_DIPS': qlane, 'HYPERLIQUID': plane}, installation=Installation(), portfolio=custody, clock=clock)
    risk.runtime = r
    q.a.verify_shutdown_components = lambda b, c: c['runtime'] is r and c['writer'] is q.writer and c['quotes'] is q.quotes
    q.a.verify_shutdown_request = lambda *args: r.state == 'STOPPING' and r.entry_closed.is_set()
    q.a.verify_drain = lambda b, cut, result: all(number(x['remaining']) == 0 for x in cut['state']['positions'].values())
    p.a.verify_shutdown_components = lambda b, c: c['runtime'] is r and c['writer'] is p.writer and c['reports'] is p.service
    p.a.verify_drain = lambda b, cut, result: p.writer.verify_order_drain() and all(number(x['remaining']) == 0 for x in cut['state']['positions'].values())
    old_verify = p.a.verify_proposal
    p.a.verify_proposal = lambda b, proposal, observation, cut: old_verify(b, proposal, observation, cut) or (
        proposal['strategy_ref'] == 'SHUTDOWN_FLATTEN:synthetic-unified-session' and r.state == 'STOPPING' and r.entry_closed.is_set())
    qstop.bind(r); pstop.bind(r)
    p.a.verify_order_reservation = lambda b, proposal, reservation, control: reservation == pending_token()
    p.a.verify_reservation = lambda b, proposal, reservation, cut: reservation == pending_token()
    def pending_token():
        pending = [x for x in journal.snapshot()['state']['operations'].values() if x['state'] == 'RESERVED']
        return {'state': 'RESERVED', 'binding': pending[0]['binding']} if len(pending) == 1 else None
    q.a.verify_reservation = lambda b, proposal, reservation, cut: reservation == pending_token()
    old_event = p.a.verify_event
    def order_event(scope, event, state, token):
        if event['kind'] in ('ARM', 'CANCEL', 'FILL_PENDING'): return token == pending_token()
        if event['kind'] == 'ACK':
            receipt = event['payload']
            return token == pending_token() and p.store.operation_receipt(receipt['operation_id'], receipt['payload_digest']) == receipt
        return old_event(scope, event, state, token)
    p.a.verify_event = order_event
    def tick(at, *, stock_bid='99.9', stock_ask='100', monitor=None, **perp_book):
        p.advance(at, **perp_book)
        iso = datetime.fromtimestamp(at, UTC).isoformat().replace('+00:00', 'Z')
        q.f.receive(json.dumps([message(bp=float(stock_bid), ap=float(stock_ask), t=iso)]))
        q_packet.update(revision=q_packet['revision'] + 1, observed_at=at)
        live = [x for x in q.writer._cut()['state']['positions'].values() if number(x['remaining']) > 0]
        if live:
            q_packet['bundles'] = []
            q_packet['monitors'] = {live[0]['instrument']['instrument_id']: {'symbol': live[0]['symbol'], 'instrument': live[0]['instrument'],
                'observed_at': at, 'current': {} if monitor is None else monitor}}
    def close():
        journal.close(); p.close()
        if s.runtime.grant is not None: s.runtime.stop()
        s.x.x.close()
    return SimpleNamespace(**locals())
