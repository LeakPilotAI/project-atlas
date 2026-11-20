"""One actual Alpaca Basic IEX 30-symbol research batch; no financial authority.

Only observes a SINGLE bounded websocket session (max 30 symbols), deriving
its symbols from a SHA-pinned local research catalog. This does not impersonate
an accepted financial position owner, publish execution prices, persist quote
frames, create broker orders or grant source rights.

Operator accepts exact data-only observation scope separately from a future
native QD source publisher and its actual owned position-symbol reader.
"""
import argparse
import asyncio
import json
from pathlib import Path

from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused

from scripts.observation_runtime.alpaca_iex_probe import (
    SCOPE,
    inspect_selected_data_only,
)
from scripts.observation_runtime.atlas_r12_iex_rotation_plan import (
    CATALOG,
    MAX_SYMBOLS,
)
from scripts.observation_runtime.atlas_r12_iex_rotation_plan import (
    plan as plan_roster,
)

SCHEMA="ATLAS_ALPACA_IEX_BASIC_SINGLE_RESEARCH_BATCH_V1"
MIN_SECONDS=5
MAX_SECONDS=20


def catalog_snapshot():
    if (not CATALOG.is_file() or CATALOG.is_symlink()
            or CATALOG.is_junction() or CATALOG.stat().st_size>5*1024*1024):
        raise ValueError("IEX_BASIC_BOUND_LOCAL_RESEARCH_CATALOG_REQUIRED")
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def prepare(*,scope,offset,pinned_research_symbols=(),snapshot=None):
    if scope!=SCOPE:
        raise ValueError("IEX_BASIC_EXPLICIT_DATA_ONLY_SCOPE_REQUIRED")
    src=inspect_selected_data_only()
    revision=src.get("selected_revision")
    if (type(revision) is not int or revision not in (14,22)
            or src.get("trading_authorized") is not False
            or src.get("provider_rights_independently_accepted") is not False):
        raise ValueError("IEX_BASIC_EXACT_SELECTED_NO_FINANCIAL_AUTHORITY")
    if type(pinned_research_symbols) not in (list,tuple):
        raise ValueError("IEX_BASIC_RESEARCH_PINS_REQUIRED")
    roster=plan_roster(catalog_snapshot() if snapshot is None else snapshot,
                       offset=offset,
                       monitored_symbols=list(pinned_research_symbols))
    if (roster["requested_symbol_count"]<1
            or roster["requested_symbol_count"]>MAX_SYMBOLS
            or len(set(roster["requested_symbols"]))!=roster["requested_symbol_count"]
            or roster["full_universe_one_connection_supported"] is not False
            or roster["provider_rights_accepted"] is not False
            or roster["paper_execution_authorized"] is not False):
        raise ValueError("IEX_BASIC_RESEARCH_SCOPE_AND_CAPACITY_REFUSED")
    # Bind this RESEARCH ONLY batch to the current selected release.
    # Historical R15 and current R22 must never share receipt identity.
    return {**roster,"selected_native_release":{14:"R15",22:"R22"}[revision]}


def sanitize(roster, result, *, seconds):
    if (type(roster) is not dict
            or roster.get("selected_native_release") not in ("R15","R22")
            or type(result) is not dict
            or type(result.get("authenticated")) is not bool
            or type(result.get("subscribed")) is not bool
            or type(result.get("fresh_quote_observed_during_connection")) is not bool
            or result.get("endpoint")!="wss://stream.data.alpaca.markets/v2/iex"
            or result.get("feed")!="IEX"
            or result.get("reconnects")!=0
            or type(result.get("per_symbol_quote_diagnostics")) is not dict
            or set(result["per_symbol_quote_diagnostics"])!=set(roster["requested_symbols"])
            or type(result.get("result")) is not dict
            or result["result"].get("connection")!="DISCONNECTED"
            or result["result"].get("paper_startup_authorized") is not False):
        raise ValueError("IEX_BASIC_ONE_EXACT_DISCONNECTED_SESSION_REQUIRED")
    diagnostics=result["per_symbol_quote_diagnostics"]
    for row in diagnostics.values():
        if (type(row) is not dict
                or set(row)!={"received","accepted","rejected","fresh_callbacks"}
                or any(type(row[k]) is not int or row[k]<0 for k in row)
                or row["received"]!=row["accepted"]+row["rejected"]
                or row["fresh_callbacks"]!=0):
            raise ValueError("IEX_BASIC_AGGREGATE_DIAGNOSTICS_ONLY_REQUIRED")
    observed=sum(row["received"] for row in diagnostics.values())
    accepted=sum(row["accepted"] for row in diagnostics.values())
    if (type(result.get("quote_count")) is not int
            or result["quote_count"]!=accepted
            or result["subscribed"] and not result["authenticated"]
            or result["fresh_quote_observed_during_connection"] and not accepted):
        raise ValueError("IEX_BASIC_QUOTE_COUNTER_CONFLICT")
    return {
        "schema":SCHEMA,
        "status":("AUTHENTICATED_30_SYMBOL_DATA_ONLY_OBSERVATION"
                  if result["authenticated"] and result["subscribed"]
                  else "DATA_ONLY_AUTH_OR_SUBSCRIPTION_UNAVAILABLE"),
        "selected_native_release":roster["selected_native_release"],
        "catalog_digest":roster["catalog_sha256"],
        "catalog_count":roster["catalog_count"],
        "research_offset":roster["offset"],
        "next_research_offset_uncommitted":roster["next_offset"],
        "requested_symbols_count":roster["requested_symbol_count"],
        "pinned_research_symbols_count":len(roster["pinned_research_symbols"]),
        "one_websocket_connection_seconds":seconds,
        "authenticated":result["authenticated"],
        "all_requested_symbols_subscription_acknowledged":result["subscribed"],
        "websocket_closed_after_batch":True,
        "quote_messages_received":observed,
        "quote_messages_accepted":accepted,
        "quote_messages_rejected":sum(row["rejected"] for row in diagnostics.values()),
        "symbols_with_accepted_quote":sum(1 for row in diagnostics.values() if row["accepted"]),
        "fresh_quotes_seen_during_connection":result["fresh_quote_observed_during_connection"],
        "raw_quotes_or_prices_published":False,
        "cursor_durably_committed":False,
        "current_qualified_market_source":False,
        "independent_provider_contract_rights_accepted":False,
        "financial_position_owner_verified":False,
        "trading_suppressed":True,
        "paper_start_authorized":False,
        "live_money_authorized":False,
        "orders_created":0,
    }


async def observe_one(*,scope,offset,pinned_research_symbols=(),seconds=12,
                      snapshot=None,credential_loader=None,runner=None):
    if type(seconds) is not int or not MIN_SECONDS<=seconds<=MAX_SECONDS:
        raise ValueError("IEX_BASIC_BOUNDED_SESSION_SECONDS_REQUIRED")
    roster=prepare(scope=scope,offset=offset,
                   pinned_research_symbols=pinned_research_symbols,snapshot=snapshot)
    # This is an intentionally separate RESEARCH-ONLY feed. Do not supply a
    # synthetic position owner to the financial roster/rotation bridge.
    feed=IEXFeed(roster["requested_symbols"])
    credentials=(Credentials.load(Path("config/alpaca.env"))
                 if credential_loader is None else credential_loader())
    if type(credentials) is not Credentials:
        raise IEXRefused("IEX_BASIC_VALIDATED_DATA_ONLY_CREDENTIALS_REQUIRED")
    if runner is None:
        result=await feed.run(credentials,seconds=seconds,max_reconnects=0)
    else:
        result=await runner(feed,credentials,seconds)
    return sanitize(roster,result,seconds=seconds)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect",action="store_true")
    mode.add_argument("--execute-data-only",action="store_true")
    parser.add_argument("--confirm-scope")
    parser.add_argument("--offset",type=int,default=0)
    parser.add_argument("--monitor-research",action="append",default=[])
    parser.add_argument("--seconds",type=int,default=12)
    args=parser.parse_args(argv)
    try:
        roster=prepare(scope=SCOPE,offset=args.offset,
                       pinned_research_symbols=args.monitor_research)
        if args.inspect:
            if args.confirm_scope is not None:
                raise ValueError("IEX_BASIC_INSPECT_HAS_NO_ACTIVE_SCOPE")
            print(json.dumps({
                "schema":SCHEMA,"status":"OFFLINE_ROSTER_NOT_CONNECTED",
                "catalog_count":roster["catalog_count"],
                "requested_symbols_count":roster["requested_symbol_count"],
                "next_research_offset_uncommitted":roster["next_offset"],
                "data_provider_called":False,
                "paper_start_authorized":False,
                "live_money_authorized":False},sort_keys=True))
            return 0
        result=asyncio.run(observe_one(
            scope=args.confirm_scope,offset=args.offset,
            pinned_research_symbols=args.monitor_research,seconds=args.seconds))
        print(json.dumps(result,sort_keys=True))
        return 0 if result["authenticated"] and result[
            "all_requested_symbols_subscription_acknowledged"] else 2
    except (IEXRefused,ValueError,TypeError,KeyError,OSError,TimeoutError):
        print(json.dumps({"schema":SCHEMA,"status":"DATA_ONLY_SCOPE_REFUSED",
                          "prices_exposed":False,"orders_created":0,
                          "paper_start_authorized":False},sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
