"""Explicit synthetic filesystem custody, NOT independent rollback authority."""
import copy
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path

from app.services.paper_financial_replay import (
    apply_event,
    body,
    digest,
    event_stream_record,
    initial_state,
)

ROOT = Path(__file__).resolve().parents[1]


class Custody:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if (self.root.parent != ROOT/'logs/diagnostics'
                or re.fullmatch(r'continuation-fixture-[0-9a-f]{32}', self.root.name) is None
                or any(p.is_symlink() or p.is_junction() for p in (self.root, *self.root.parents))):
            raise ValueError('EXACT_DISPOSABLE_CUSTODY_ROOT_REQUIRED_BEFORE_IO')
        self.valid = True
        self.path = self.root / 'synthetic-current.json'
        lock = self.root / 'synthetic-lock'
        if not lock.exists():
            with lock.open('xb') as stream:
                stream.write(b'0')
        self.lock_path = lock

    @contextmanager
    def lease(self):
        import msvcrt
        with self.lock_path.open('r+b') as stream:
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    def current(self):
        return json.loads(self.path.read_text(encoding='utf8')) if self.path.exists() else None

    def verify_current(self, pin):
        return self.valid and self.current() == pin

    def verify_scope(self, root, accounts):
        return self.valid and Path(root) == self.root/'archive' and accounts == manifests()

    def boundary(self, pin, cuts):
        return {'schema':'OFFLINE_CONTINUATION_BOUNDARY_V1','predecessor_pin_digest':digest(pin),
                'cuts_digest':digest(cuts),'state':'FINAL_FLAT_DRAINED_NO_RESTING_OR_UNKNOWN',
                'proof':'EXPLICIT_SYNTHETIC_BOUNDARY_NOT_OPERATIONAL_AUTHORITY'}

    def verify_boundary(self, value):
        return self.valid and value['proof'] == 'EXPLICIT_SYNTHETIC_BOUNDARY_NOT_OPERATIONAL_AUTHORITY'

    def compare_and_swap(self, before, after):
        if not self.valid or self.current() != before:
            return False
        path = self.path.with_suffix('.pending')
        with path.open('xb') as stream:
            stream.write(body(after).encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, self.path)
        return True


def manifests():
    from test_perp_financial_v2 import manifest
    qd = json.loads((ROOT / 'tests/fixtures/fs1/legacy-synthetic-golden.json').read_text(encoding='utf8'))['cases'][0]['manifest']
    return {'QUALITY_DIPS': qd, 'HYPERLIQUID': manifest()}


def records():
    from test_perp_financial_v2 import entry
    ms = manifests()
    rows = {lane: [] for lane in ms}
    states = {lane: initial_state(m) for lane, m in ms.items()}
    heads = {lane: digest(m) for lane, m in ms.items()}
    def put(lane, command):
        state, receipt = apply_event(ms[lane], states[lane], command)
        receipt['projection_required'] = False
        checksum = digest([heads[lane], command, receipt])
        rows[lane].append(event_stream_record(state['revision'], command['operation_id'], body(command),
                                             heads[lane], checksum, body(receipt)))
        states[lane], heads[lane] = state, checksum
    lane = 'QUALITY_DIPS'
    for i in range(66):
        stamp = ms[lane]['opened_at'] + 1 + i * 2
        command = {'schema':'PAPER_COMMAND_FIXTURE_V1','epoch':ms[lane]['epoch'],'operation_id':f'SYNTHETIC-QD-{i}-ENTRY',
                   'kind':'ENTRY','expected_source_revision':states[lane]['revision'],'timestamp':stamp,'manual':True,
                   'quote':{'symbol':'MSFT','price':'100','observed_at':stamp,'source_id':'SYNTHETIC-PRICE'},
                   'symbol':'MSFT','side':'LONG','quantity':'0.1','risk_price':None,'origin_ref':f'SYNTHETIC-ORIGIN-{i}'}
        put(lane, command)
        pid = next(k for k, p in states[lane]['positions'].items() if p['remaining'] != '0.0')
        put(lane, {'schema':'PAPER_COMMAND_FIXTURE_V1','epoch':ms[lane]['epoch'],'operation_id':f'SYNTHETIC-QD-{i}-EXIT',
                   'kind':'EXIT','expected_source_revision':states[lane]['revision'],'timestamp':stamp+1,'manual':True,
                   'quote':{'symbol':'MSFT','price':'101','observed_at':stamp+1,'source_id':'SYNTHETIC-PRICE'},
                   'position_id':pid,'quantity':'0.1','expected_position_revision':1})
    lane = 'HYPERLIQUID'
    put(lane, entry())
    pid = next(iter(states[lane]['positions']))
    def exit_row(qty, timestamp, op):
        q = copy.deepcopy(entry()['evidence'])
        q.update(bid='102',ask='103',observed_at=timestamp,sequence=op)
        return {'schema':'PAPER_PERP_COMMAND_V2','epoch':ms[lane]['epoch'],'operation_id':op,'kind':'EXIT',
                'expected_source_revision':states[lane]['revision'],'timestamp':timestamp,'position_id':pid,
                'expected_position_revision':states[lane]['positions'][pid]['revision'],
                'quantity':qty,'liquidity':'TAKER','evidence':q}
    put(lane, exit_row('0.2',3603,'SYNTHETIC-PARTIAL'))
    put(lane, {'schema':'PAPER_PERP_COMMAND_V2','epoch':ms[lane]['epoch'],'operation_id':'SYNTHETIC-FUNDING',
               'kind':'FUNDING','expected_source_revision':states[lane]['revision'],'timestamp':7201,'position_id':pid,
               'expected_position_revision':states[lane]['positions'][pid]['revision'],
               'evidence':{'source':'synthetic-funding','symbol':'BTC','settlement_at':7200,'interval_seconds':3600,
                           'rate':'0.001','oracle':'100','source_id':'hour-7200'}})
    put(lane, exit_row('0.3',7202,'SYNTHETIC-FINAL'))
    return rows
