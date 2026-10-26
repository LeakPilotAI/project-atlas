"""Confined self-exiting subprocess for native control crash/race tests only."""
import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'backend'), str(REPO / 'tests')]
from perp_order_native_fixture import DurableTestPins, native


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--phase', choices=['none', 'before_publication', 'after_record_before_pin', 'after_pin', 'financial-after-ack'], default='none')
    args = parser.parse_args()
    path = Path(args.config).absolute()
    config = json.loads(path.read_text())
    confinement = Path(config['confinement']).absolute()
    if (confinement.parent != REPO / 'logs/diagnostics' or not confinement.name.startswith('perp-order-custody-')
            or not path.is_relative_to(confinement) or any(p.is_symlink() or p.is_junction() for p in (confinement, *confinement.parents))):
        raise ValueError('CONFINED_CHILD_ONLY')
    for key in ('root', 'pin'):
        if not Path(config[key]).absolute().is_relative_to(confinement): raise ValueError('FOREIGN_CHILD_RESOURCE')
    clock = lambda: config['now']
    authority = SimpleNamespace(verify_scope=lambda *a: True, verify_event=lambda *a: True)
    pins = DurableTestPins(config['pin'], clock)
    if config.get('portfolio'):
        spec = importlib.util.spec_from_file_location('child_portfolio_control', REPO / 'scripts/volume_inspector/unified_portfolio_store.py')
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        cls = mod.PortfolioControlStore
    else: cls = native.RestingOrderStore
    store = cls(config['root'], trust=pins, authority=authority, clock=clock, manifest=config['manifest'], execution_domain='DISPOSABLE_TEST')
    try:
        if config.get('barrier'):
            Path(config['ready']).write_text('READY')
            deadline = time.monotonic() + 5
            while not Path(config['barrier']).exists():
                if time.monotonic() > deadline: return 72
                time.sleep(.01)
        def fault(phase):
            if phase == args.phase: os._exit(71)
        if args.phase != 'financial-after-ack':
            print(json.dumps(store.apply(config['event'], config['reservation'], fault=fault)), flush=True)
        else:
            # The global reservation stays durable before actual native financial
            # publication. The child exits itself after native ACK, before global ACK.
            with store.guard():
                store.apply(config['event'], config['reservation'])
                m = config['financial']
                if any(not Path(m[k]).absolute().is_relative_to(confinement) for k in ('root', 'projection', 'pin')):
                    raise ValueError('FOREIGN_FINANCIAL_CHILD_RESOURCE')
                spec = importlib.util.spec_from_file_location('child_reports', REPO / 'scripts/volume_inspector/financial_reporting.py')
                mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
                target = mod.ProjectionTarget(m['projection'], m['projection_id'])
                financial = native.f.FinancialRecordStore(m['root'], DurableTestPins(m['pin'], clock), projection=target)
                try:
                    order = config['orders']
                    if any(not Path(order[k]).absolute().is_relative_to(confinement) for k in ('root', 'pin')):
                        raise ValueError('FOREIGN_ORDER_CHILD_RESOURCE')
                    orders = native.RestingOrderStore(order['root'], trust=DurableTestPins(order['pin'], clock),
                        authority=authority, clock=clock, manifest=order['manifest'], execution_domain='DISPOSABLE_TEST')
                    orders.apply({'kind': 'FILL_PENDING', 'order_id': m['command']['origin_ref'],
                                  'at': m['command']['timestamp'], 'payload': m['command']}, config['reservation'])
                    financial.execute(m['command'], projection_required=True)
                    os._exit(71)
                finally:
                    financial.close(); target.close()
    finally: store.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
