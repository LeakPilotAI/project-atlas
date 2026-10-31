"""Confined real native stores with explicit synthetic, locally durable test pins."""
import copy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

from app.adapters.hyperliquid import _paper_execution_observation
from app.services.paper_financial_replay import body, digest, number
from app.services.perp_resting_writer import RestingPerpWriter
from app.services.perp_source_planner import PerpSourcePlanner
from app.services.unified_native_writer import NativeFinancialWriter
from test_perp_financial_v2 import manifest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('order_test_native', REPO / 'scripts/volume_inspector/resting_order_store.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
spec = importlib.util.spec_from_file_location('order_test_reports', REPO / 'scripts/volume_inspector/financial_reporting.py')
reports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reports)


class DurableTestPins:
    """Test-owned JSON custody; NOT independent rollback protection or production storage."""
    def __init__(self, path, clock, pin=None):
        self.path, self.clock = Path(path), clock
        if pin is not None:
            with self.path.open('xb') as stream:
                stream.write(body(pin).encode())
                stream.flush()
                os.fsync(stream.fileno())
    def current(self): return json.loads(self.path.read_text())
    def check_clock(self, at):
        if type(at) is not int or not 0 <= self.clock() - at <= 30: raise ValueError('SYNTHETIC_CLOCK_REFUSED')
    def advance(self, before, after):
        if self.current() != before: raise ValueError('SYNTHETIC_CAS_CONFLICT')
        temporary = self.path.with_suffix('.pending')
        with temporary.open('xb') as stream:
            stream.write(body(after).encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)


def book(now, *, bid='99.9', ask='100.1', mark='100'):
    return _paper_execution_observation('BTC', [{'universe': [{'name': 'BTC', 'szDecimals': 3, 'maxLeverage': 2}]},
        [{'markPx': mark, 'oraclePx': mark, 'funding': '-0.001'}]],
        {'coin': 'BTC', 'time': now * 1000, 'levels': [[{'px': bid, 'sz': '50', 'n': 3}], [{'px': ask, 'sz': '50', 'n': 3}]]},
        now * 1000, now * 1000)


class FixtureAuthority:
    """Explicit synthetic actor; verifies actual store receipts, not caller success flags."""
    def __init__(self): self.valid, self.reserved, self.control_reservation = True, None, None
    def verify_components(self, binding): return self.valid and binding['store'] is self.financial.store
    def verify_cut(self, binding, cut): return self.valid and cut['root'] == self.financial.store.trust.current()['root']
    def verify_proposal(self, binding, proposal, observation, cut): return self.valid and proposal['strategy_ref'].startswith('SOURCE:')
    def verify_reservation(self, binding, proposal, reservation, cut): return self.valid and reservation == self.reserved
    def verify_maker_execution(self, *args): return self.valid
    def verify_scope(self, scope, pin, now): return self.valid and scope['writer_id'] == 'EXPLICIT_SYNTHETIC_ORDER_WRITER'
    def verify_event(self, scope, event, state, reservation):
        if not self.valid: return False
        if event['kind'] in ('ARM', 'CANCEL'): return reservation == self.control_reservation
        if reservation != self.reserved: return False
        if event['kind'] == 'ACK':
            r = event['payload']
            return self.financial.store.operation_receipt(r['operation_id'], r['payload_digest']) == r
        return event['kind'] == 'FILL_PENDING'
    def verify_order_components(self, binding, actual): return self.valid and actual == {'financial': self.financial, 'orders': self.orders}
    def verify_resting_order(self, binding, proposal, observation, cut, control): return self.valid
    def verify_order_reservation(self, binding, proposal, reservation, control): return self.valid and reservation == self.control_reservation
    def verify_planner_components(self, binding, actual): return self.valid and actual['writer'] is self.writer
    def verify_strategy_source(self, *args): return self.valid
    def verify_execution_source(self, *args): return self.valid
    def verify_settlement_source(self, binding, history, oracle, now): return self.valid and oracle['source_id'] == 'SYNTHETIC_HISTORICAL_ORACLE'


def build(root, confinement, *, stamp=3601, shared_now=None):
    root, confinement = Path(root), Path(confinement)
    assert confinement.parent == REPO / 'logs/diagnostics' and confinement.name.startswith('perp-order-custody-')
    assert root.is_relative_to(confinement)
    now, m = [stamp + 1] if shared_now is None else shared_now, manifest()
    m['opened_at'] = stamp
    clock = lambda: now[0]
    a = FixtureAuthority()
    projection_id = reports.ProjectionTarget.provision_disposable(str(root / 'projection'))
    projection = reports.ProjectionTarget(str(root / 'projection'), projection_id)
    pin = native.f.FinancialRecordStore.provision_disposable(str(root / 'source'), m)
    financial_pins = DurableTestPins(root / 'financial-pin.json', clock, pin)
    store = native.f.FinancialRecordStore(str(root / 'source'), financial_pins, projection=projection)
    # verify_components is first called by construction; bind the actual store first.
    a.financial = SimpleNamespace(store=store)
    financial = NativeFinancialWriter(store=store, authority=a, manifest=m, execution_domain='DISPOSABLE_TEST')
    a.financial = financial
    scope = {'schema': 'PERP_RESTING_SCOPE_V1', 'execution_domain': 'DISPOSABLE_TEST', 'epoch': m['epoch'],
             'manifest_digest': digest(m), 'writer_id': 'EXPLICIT_SYNTHETIC_ORDER_WRITER'}
    pin = native.RestingOrderStore.provision_disposable(root / 'orders', scope, confinement=confinement)
    order_pins = DurableTestPins(root / 'order-pin.json', clock, pin)
    orders = native.RestingOrderStore(root / 'orders', trust=order_pins, authority=a, clock=clock,
                                     manifest=m, execution_domain='DISPOSABLE_TEST')
    a.orders = orders
    writer = RestingPerpWriter(financial=financial, orders=orders)
    a.writer = writer
    packet = {'schema': 'PERP_STRATEGY_SOURCE_V1', 'source_id': 'SYNTHETIC_DISCOVERY_CUT', 'revision': 1,
        'observed_at': now[0], 'markets': [{'symbol': 'BTC', 'price': '100', 'volume_24h': '20000000',
                                         'open_interest': '8000000', 'funding_rate': '-0.001'}],
        'candles': {'BTC': [{'close': 100 + .3 * i} for i in range(48)]}, 'books': {'BTC': book(now[0])},
        'funding': {}, 'oracles': {}, 'maker_fills': {}, 'setups': []}
    source = SimpleNamespace(read_cut=lambda: copy.deepcopy(packet))
    planner = PerpSourcePlanner(writer=writer, source=source, clock=clock, session_id='synthetic-session')
    report_scope = {'schema': 'FS3_PERP_REPORT_SCOPE_V3', 'account_id': 'synthetic-perp', 'epoch': m['epoch'],
        'policy_digest': digest(m), 'timezone': m['timezone'], 'funding_reporting_policy': 'POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1',
        'session_reporting_policy': 'ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1'}
    report_pin = reports.ReportArchive.provision_disposable(str(root / 'reports'), report_scope, m)
    report_pins = DurableTestPins(root / 'report-pin.json', clock, report_pin)
    archive = reports.ReportArchive(str(root / 'reports'), report_pins)
    service = reports.ReportService(store, archive)
    def advance(at, **book_changes):
        now[0] = at
        packet.update(revision=packet['revision'] + 1, observed_at=at)
        packet['books']['BTC'] = book(at, **book_changes)
    def arm(proposal):
        a.control_reservation = {'state': 'RESERVED', 'binding': digest(proposal)}
        return writer.dispatch_resting(proposal, a.control_reservation)
    def fill_proof(order, *, quantity=None):
        qty = order['quantity'] if quantity is None else quantity
        return {'schema': 'SIMULATED_MAKER_QUEUE_FILL_V1', 'order_id': order['order_id'], 'limit_price': order['limit_price'],
                'rested_at': order['created_at'], 'queue_ahead': '1', 'traded_quantity': '50',
                'trade_price': order['limit_price'], 'trade_side': 'SELL' if order['side'] == 'LONG' else 'BUY',
                'trade_at': now[0], 'source_ref': 'SYNTHETIC_AUTHENTICATED_TRADE_RECEIPT',
                'requested_quantity': order['quantity'], 'filled_quantity': qty,
                'cancelled_quantity': str(number(order['quantity']) - number(qty))}
    def dispatch(proposal):
        a.reserved = {'state': 'RESERVED', 'binding': digest(proposal)}
        return writer.dispatch(proposal, a.reserved)
    def close(): orders.close(); store.close(); projection.close(); archive.close()
    return SimpleNamespace(**locals())
