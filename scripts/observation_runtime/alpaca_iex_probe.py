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
        from scripts.observation_runtime.atlas_r12_alpaca_source_admission import assess
        report=assess()
        print(json.dumps({
            'schema':'ATLAS_IEX_BOUNDED_DATA_ONLY_PREFLIGHT_V1',
            'status':'REQUIRES_EXPLICIT_DATA_ONLY_SESSION_APPROVAL',
            'selected_revision':report['native_revision'],
            'source_catalog_symbols':report['catalog']['research_symbol_count'],
            'forward_source_verified':report['qd_forward_publication_verified'],
            'provider_authentication_performed':False,
            'private_credentials_accessed':False,
            'trading_authorized':False,
            'sample_already_verified':False,
        },sort_keys=True))
        return 0
    try:
        symbols=request_scope(seconds=args.seconds,symbols=args.symbols,
                              execute=args.execute_data_only,confirm_scope=args.confirm_scope)
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
