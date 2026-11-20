"""Selected-r12 IEX/Quality Dips source readiness: READ-ONLY and data-only.

Inspect the existing durable Alpaca research catalog and QD source custody.
Do NOT load private config contents, open provider sockets, mint financial
entitlements, publish forward source, or create any account or trading order.
A research symbol (even a valid Alpaca asset) is NOT a Robinhood listing or
an executable IEX quote. Free IEX is single venue, NOT NBBO.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
CATALOG=ROOT/'logs/research/alpaca_equity_inventory.json'
ALPACA_CONFIG=ROOT/'config/alpaca.env'
MAX_CATALOG_BYTES=5*1024*1024
IEX_MAX_SYMBOLS_PER_CONNECTION=30


def inventory(path=CATALOG):
    from scripts.observation_runtime.alpaca_equity_catalog import rotating_batch
    path=Path(path)
    if (not path.is_file() or path.is_symlink() or path.stat().st_size>MAX_CATALOG_BYTES):
        raise ValueError('R12_ALPACA_RESEARCH_INVENTORY_ABSENT_OR_UNSAFE')
    data=path.read_bytes()
    try:packet=json.loads(data)
    except (ValueError,UnicodeError):
        raise ValueError('R12_ALPACA_RESEARCH_INVENTORY_MALFORMED') from None
    if (type(packet) is not dict or
        packet.get('schema')!='ATLAS_ALPACA_EQUITY_RESEARCH_INVENTORY_V1' or
        packet.get('source')!='ALPACA_US_EQUITY_ASSETS' or
        packet.get('paper_execution_authorized') is not False or
        packet.get('live_order_authorized') is not False or
        packet.get('robinhood_brokerage_verified') is not False):
        raise ValueError('R12_ALPACA_RESEARCH_ONLY_INVENTORY_REQUIRED')
    rows=packet.get('rows')
    if (type(rows) is not list or not rows or len(rows)>20000):
        raise ValueError('R12_ALPACA_RESEARCH_INVENTORY_SIZE_REFUSED')
    symbols=[r.get('symbol') if type(r) is dict else None for r in rows]
    if (any(type(s) is not str for s in symbols) or
        symbols!=sorted(set(symbols))):
        raise ValueError('R12_ALPACA_RESEARCH_SYMBOLS_UNSORTED_OR_DUPLICATE')
    if any(type(r) is not dict or r.get('asset_class')!='us_equity' or
           r.get('provider_tradable') is not True or
           type(r.get('exchange')) is not str for r in rows):
        raise ValueError('R12_ALPACA_RESEARCH_ASSET_SCOPE_CHANGED')
    try:roster=rotating_batch(packet,offset=0,limit=8)
    except (ValueError,TypeError,KeyError):
        raise ValueError('R12_ALPACA_RESEARCH_DIGEST_OR_SYMBOL_REFUSED') from None
    return {'catalog_file_sha256':hashlib.sha256(data).hexdigest(),
        'catalog_content_sha256':packet['sha256'],
        'captured_at':packet.get('captured_at'),
        'research_symbol_count':len(rows),
        'read_only_preview':roster,
        'required_nonoverlapping_30_symbol_rosters':math.ceil(len(rows)/IEX_MAX_SYMBOLS_PER_CONNECTION),
        'provider_research_inventory_verified':True,
        'robinhood_brokerage_coverage_verified':False,
        'paper_execution_eligible_from_catalog':False}


def validate_bounded_iex_probe(probe):
    """Only observation evidence; NEVER a financial entitlement or fill grant.

    A disconnected authenticated/subscribed sample with a fresh event is a
    data observation. Its quote is NOT persistent executable price coverage.
    """
    if (type(probe) is not dict or
        probe.get('schema')!='ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1' or
        probe.get('authenticated') is not True or
        probe.get('subscribed') is not True or
        probe.get('connection_closed') is not True or
        type(probe.get('quote_count')) is not int or
        probe['quote_count']<=0 or
        probe.get('fresh_quote_observed_during_connection') is not True or
        probe.get('paper_fill_authorized') is not False or
        probe.get('live_order_authorized') is not False):
        raise ValueError('R12_IEX_BOUNDED_REAL_DATA_EVIDENCE_REQUIRED')
    return {'observed_authenticated_iex_quote':True,
            'sample_connection_closed':True,
            'continuous_live_quote_freshness_verified':False,
            'provider_data_rights_accepted':False,
            'paper_execution_authorized':False}


def assess(*,catalog_path=CATALOG,config_path=ALPACA_CONFIG,source_root=None):
    from scripts.observation_runtime.quality_dips_source_inventory import inspect
    from scripts.observation_runtime.atlas_r12_financial_readiness import run
    selected=run(deep=False)
    if (selected['native_revision']!=12 or selected['decision']!='NO_GO' or
         selected['selected_code_verified'] is not True or
         selected['accepted_financial_operating_gates']!=0 or
         selected['startup_authorized'] is not False):
        raise ValueError('R12_IEX_SELECTED_FINANCIAL_GATE_STATUS_REQUIRED')
    found=inventory(catalog_path)
    native=inspect() if source_root is None else inspect(root=source_root)
    if native.get('schema')!='ATLAS_QD_NATIVE_SOURCE_INVENTORY_V1':
        raise ValueError('R12_IEX_QD_SOURCE_CUSTODY_UNRECOGNIZED')
    config=Path(config_path)
    config_exists=config.is_file() and not config.is_symlink()
    # Credential bytes, metadata, token, host info never inspected or printed.
    return {'schema':'ATLAS_R12_ALPACA_QUALITY_DIPS_SOURCE_ADMISSION_V1',
        'status':'RESEARCH_UNIVERSE_VERIFIED_FORWARD_SOURCE_BLOCKED',
        'native_revision':12,'selected_code_verified':True,
        'provider':'ALPACA','allowed_market':'US_STOCKS_ETFS',
        'perpetuals_and_kalshi_excluded':True,
        'data_feed':'IEX','feed_scope':'SINGLE_EXCHANGE_NOT_NBBO',
        'free_plan_iex_max_websocket_symbols':IEX_MAX_SYMBOLS_PER_CONNECTION,
        'catalog':found,
        'credential_configuration_file_present':config_exists,
        'credentials_opened_or_authenticated':False,
        'bounded_iex_data_session_verified':False,
        'continuous_live_quote_freshness_verified':False,
        'contract_entitlement_independently_verified':False,
        'robinhood_brokerage_coverage_verified':False,
        'qd_native_custody':native,
        'qd_forward_publication_verified':native['operational_publication_verified'] is True,
        'financial_paper_gates_accepted':0,
        'provider_connections_opened':False,'financial_accounts_created':False,
        'orders_submitted':False,'startup_authorized':False,
        'next_action':'Separately authorize bounded data-only IEX probe; verify real authenticated/subscribed fresh quote observations, current provider scope, owned QD forward publisher and exact native custody before accounts.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect',action='store_true',required=True)
    parser.parse_args(argv)
    result=assess()
    print(json.dumps(result,sort_keys=True,indent=2))
    return 2 # still NO-GO regardless of research catalog size


if __name__=='__main__':
    raise SystemExit(main())
