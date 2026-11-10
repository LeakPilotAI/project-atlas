"""Explicit, bounded Alpaca IEX data observation, never a PAPER order or session.

A real provider connection is possible ONLY with both --execute-data-only and
--confirm-scope ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING. Nothing reads
config or opens a socket during --inspect. A successful exit requires actual
authentication, subscription and at least one fresh provider quote, never just
a websocket handshake or a positive research catalog.
"""
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused, SYMBOL

SCOPE = "ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING"
REASON = "IEX_CONFIGURATION_OR_DATA_UNAVAILABLE"
R14_SELECTED_ENVELOPE = Path("D:/AtlasRuntime/selection/r0013.json")
R15_SELECTED_ENVELOPE = Path("D:/AtlasRuntime/selection/r0014.json")


def request_scope(*, seconds, symbols, execute, confirm_scope):
    # All input checks precede credential loading or an external network call.
    if (type(seconds) is not int or not 1 <= seconds <= 60
            or type(symbols) is not list or not 1 <= len(symbols) <= 10
            or len(set(symbols)) != len(symbols)
            or any(type(s) is not str or SYMBOL.fullmatch(s) is None for s in symbols)):
        raise IEXRefused("IEX_PROBE_BOUNDED_ARGUMENTS_REQUIRED")
    if execute is not True or confirm_scope != SCOPE:
        raise IEXRefused("IEX_PROBE_EXPLICIT_DATA_ONLY_SCOPE_REQUIRED")
    return list(symbols)


def _admit_symbol_diagnostics(data, requested, observed, callback_count):
    """Require complete per-symbol transport counts; never accept fabricated coverage.

    Older injected test transports omit this optional source-only diagnostic.
    Absence is UNKNOWN, not an all-zero report or financial acceptance.
    """
    rows = data.get('per_symbol_quote_diagnostics')
    if rows is None:
        return None
    if (type(rows) is not dict or set(rows) != set(requested)
            or any(type(row) is not dict or set(row) !=
                   {'received', 'accepted', 'rejected', 'fresh_callbacks'}
                   for row in rows.values())):
        raise IEXRefused('IEX_PROBE_INVALID_PER_SYMBOL_DIAGNOSTICS')
    for symbol, row in rows.items():
        if (any(type(value) is not int or value < 0 for value in row.values())
                or row['received'] != row['accepted'] + row['rejected']
                or row['fresh_callbacks'] > row['accepted']
                or (row['fresh_callbacks'] > 0) != (symbol in observed)):
            raise IEXRefused('IEX_PROBE_INVALID_PER_SYMBOL_DIAGNOSTICS')
    if (sum(x['accepted'] for x in rows.values()) > data['quote_count']
            or sum(x['fresh_callbacks'] for x in rows.values()) != callback_count):
        raise IEXRefused('IEX_PROBE_INVALID_PER_SYMBOL_DIAGNOSTICS')
    return {symbol: dict(rows[symbol]) for symbol in sorted(rows)}


def admit_result(data, *, observed_symbols, observed_count, requested_symbols):
    """Require fresh callback observation, not merely provider connection.

    This object is transport evidence only. Never certifies SIP/NBBO, broker
    instrument rights, quote continuity, fills or financial PAPER authority.
    """
    if (type(data) is not dict or data.get('authenticated') is not True
            or data.get('subscribed') is not True
            or type(data.get('quote_count')) is not int or data['quote_count'] <= 0
            or data.get('fresh_quote_observed_during_connection') is not True
            or type(data.get('result')) is not dict
            or data['result'].get('connection') != 'DISCONNECTED'
            or type(observed_count) is not int or observed_count <= 0
            or type(observed_symbols) is not set or not observed_symbols
            or not observed_symbols <= set(requested_symbols)):
        raise IEXRefused("IEX_PROBE_NO_AUTHENTICATED_FRESH_QUOTE")
    per_symbol = _admit_symbol_diagnostics(data, requested_symbols,
                                            observed_symbols, observed_count)
    packet={
        'schema':'ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1',
        'status':'BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY',
        'authenticated':True,
        'subscribed':True,
        'quote_count':data['quote_count'],
        'fresh_quote_observed_during_connection':True,
        'observed_symbols':sorted(observed_symbols),
        'callback_quote_count':observed_count,
        'connection_closed':True,
        'single_exchange_not_nbbo':True,
        'continuous_executable_prices_verified':False,
        'provider_rights_independently_accepted':False,
        'paper_fill_authorized':False,
        'live_order_authorized':False,
    }
    if per_symbol is not None:
        packet['per_symbol_quote_diagnostics'] = per_symbol
    # Reuse current r12 source assessment; accepting a short provider sample
    # must never silently promote any of the nine financial operating gates.
    from scripts.observation_runtime.atlas_r12_alpaca_source_admission import validate_bounded_iex_probe
    verdict=validate_bounded_iex_probe(packet)
    if (verdict.get('paper_execution_authorized') is not False
            or verdict.get('continuous_live_quote_freshness_verified') is not False
            or verdict.get('provider_data_rights_accepted') is not False):
        raise IEXRefused("IEX_PROBE_UNEXPECTED_FINANCIAL_AUTHORITY")
    return packet


async def bounded_data_only_probe(*, seconds, symbols, credentials, feed_factory=IEXFeed):
    if not isinstance(credentials, Credentials):
        raise IEXRefused('IEX_PROBE_CREDENTIAL_TYPE_REQUIRED')
    accepted=set()
    count=0
    def fresh_event(event):
        nonlocal count
        if (type(event) is not dict
                or event.get('provider')!='ALPACA_IEX'
                or event.get('symbol') not in symbols
                or type(event.get('timestamp')) is not str
                or not event['timestamp']
                or event.get('paper_fill_authorized') is not False
                or event.get('live_order_authorized') is not False):
            raise IEXRefused('IEX_PROBE_CALLBACK_SOURCE_CHANGED')
        accepted.add(event['symbol'])
        count+=1
    result=await feed_factory(symbols).run(credentials,seconds=seconds,
                                           max_reconnects=0,on_fresh_quote=fresh_event)
    return admit_result(result, observed_symbols=accepted, observed_count=count,
                        requested_symbols=symbols)


def inspect_selected_data_only():
    """Offline selected-release preview, without credentials or provider I/O.

    Historical r0013 remains present when R15 is selected. Always prefer
    the latest known revision and verify its complete native selection chain;
    never claim the obsolete R14 was selected merely because r0013 exists.
    The old R12-only verifier remains available only for pre-R14 deployments.
    """
    if R15_SELECTED_ENVELOPE.exists():
        from scripts.observation_runtime.atlas_r15_paper_offline_commissioning import (
            inspect as inspect_r15,
        )
        report = inspect_r15()
        if (report.get("schema") != "ATLAS_SELECTED_R15_OFFLINE_FINANCIAL_COMMISSIONING_V1"
                or report.get("decision") != "NO_GO"
                or report.get("selected_native_revision") != 14
                or report.get("selected_code_verified") is not True
                or report.get("installed_financial_clock_source_binding_verified") is not True
                or report.get("financial_operating_gates_independently_accepted") != 0
                or report.get("current_iex_equity_quotes_verified") is not False
                or report.get("native_qd_forward_writer_enrolled") is not False
                or report.get("paper_start_authorized") is not False
                or report.get("provider_connection_opened") is not False
                or report.get("credential_bytes_read") is not False
                or report.get("live_trading_authorized") is not False
                or not isinstance(report.get("quality_dips_research_catalog_symbols"), int)
                or report["quality_dips_research_catalog_symbols"] <= 0):
            raise IEXRefused("IEX_PROBE_SELECTED_R15_SOURCE_GATE_REFUSED")
        revision = 14
        catalog_count = report["quality_dips_research_catalog_symbols"]
        qd_published = False
    elif R14_SELECTED_ENVELOPE.exists():
        from scripts.observation_runtime.atlas_r14_two_lane_source_preflight import (
            inspect as inspect_r14,
        )
        report = inspect_r14()
        qd = report.get("quality_dips")
        hl = report.get("hyperliquid")
        if (report.get("schema") != "ATLAS_R14_TWO_LANE_FINANCIAL_SOURCE_PREFLIGHT_V1"
                or report.get("decision") != "NO_GO"
                or report.get("selected_code_revision") != 13
                or report.get("financial_operating_gates_accepted") != 0
                or report.get("paper_startup_authorized") is not False
                or report.get("provider_connections_opened") is not False
                or type(qd) is not dict or type(hl) is not dict
                or qd.get("research_inventory_verified") is not True
                or qd.get("operational_source_publication_verified") is not False
                or qd.get("robinhood_equity_etf_universe_verified") is not False
                or hl.get("native_financial_writer_verified") is not False):
            raise IEXRefused("IEX_PROBE_SELECTED_R14_SOURCE_GATE_REFUSED")
        revision = 13
        catalog_count = qd["catalog_symbols"]
        qd_published = False
    else:
        from scripts.observation_runtime.atlas_r12_alpaca_source_admission import (
            assess,
        )
        report = assess()
        if (report.get("native_revision") != 12
                or report.get("startup_authorized") is not False
                or report.get("contract_entitlement_independently_verified") is not False):
            raise IEXRefused("IEX_PROBE_SELECTED_R12_SOURCE_GATE_REFUSED")
        revision = 12
        catalog_count = report["catalog"]["research_symbol_count"]
        qd_published = report["qd_forward_publication_verified"]
    return {
        "schema":"ATLAS_IEX_BOUNDED_DATA_ONLY_PREFLIGHT_V1",
        "status":"REQUIRES_EXPLICIT_DATA_ONLY_SESSION_APPROVAL",
        "selected_revision":revision,
        "source_catalog_symbols":catalog_count,
        "forward_source_verified":qd_published,
        "provider_authentication_performed":False,
        "private_credentials_accessed":False,
        "provider_connected":False,
        "provider_rights_independently_accepted":False,
        "current_executable_quotes_verified":False,
        "robinhood_universe_verified":False,
        "trading_authorized":False,
        "sample_already_verified":False,
    }


def main(argv=None, *, credentials_loader=None, feed_factory=IEXFeed):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--inspect',action='store_true',help='Offline readiness; NEVER read keys or connect')
    group.add_argument('--execute-data-only',action='store_true',help='Explicit bounded credentialed observation')
    parser.add_argument('--confirm-scope',default=None)
    parser.add_argument('--seconds',type=int,default=20)
    parser.add_argument('--symbols',nargs='+',default=['MSFT','SPY'])
    parser.add_argument('--receipt-id',default=None,help='Exact 32-hex ID for create-only sanitized diagnostic; execute only')
    args=parser.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None or args.receipt_id is not None:
            print(json.dumps({'status':'REFUSED','reason':REASON}))
            return 1
        try:
            print(json.dumps(inspect_selected_data_only(),sort_keys=True))
            return 0
        except (IEXRefused, OSError, ValueError, KeyError, TypeError):
            # An invalid/partial native selection never falls back to R12.
            print(json.dumps({'status':'REFUSED','reason':REASON},sort_keys=True))
            return 1
    try:
        symbols=request_scope(seconds=args.seconds,symbols=args.symbols,
                              execute=args.execute_data_only,confirm_scope=args.confirm_scope)
        # Explicit data-only consent is necessary but not sufficient: verify
        # the CURRENT selected native code before any private key bytes or
        # provider transport can be opened. This never grants financial GO.
        selected=inspect_selected_data_only()
        if selected.get('selected_revision') not in (12,13,14) or selected.get('trading_authorized') is not False:
            raise IEXRefused('IEX_PROBE_SELECTED_CODE_PREAUTH_REQUIRED')
        if args.receipt_id is not None:
            from scripts.observation_runtime.atlas_r12_iex_diagnostic_receipt import ID
            if ID.fullmatch(args.receipt_id) is None:
                raise IEXRefused('IEX_DIAGNOSTIC_EXACT_OPERATION_ID_REQUIRED')
        loader=credentials_loader or Credentials.load
        credentials=loader(REPO/'config/alpaca.env')
        outcome=asyncio.run(bounded_data_only_probe(
            seconds=args.seconds,symbols=symbols,credentials=credentials,
            feed_factory=feed_factory))
        if args.receipt_id is not None:
            from scripts.observation_runtime import atlas_r12_iex_diagnostic_receipt as receipt
            # Only a fully admitted, authenticated fresh-quote result reaches
            # this create-once diagnostic path. Never a native QD publication.
            receipt.RECORDS_DIR.mkdir(parents=True,exist_ok=True)
            evidence=receipt.write_receipt(outcome,symbols,args.receipt_id)
            outcome['diagnostic_receipt']={
                'operation_id':evidence['operation_id'],
                'body_sha256':evidence['body_sha256'],
                'status':evidence['status'],
                'financial_authority':False}
        # Do not print raw quotes, transport headers, account info or keys.
        print(json.dumps(outcome,sort_keys=True))
        return 0
    except (IEXRefused,OSError,ValueError,TimeoutError):
        print(json.dumps({'status':'REFUSED','reason':REASON},sort_keys=True))
        return 1


if __name__=='__main__':
    raise SystemExit(main())
