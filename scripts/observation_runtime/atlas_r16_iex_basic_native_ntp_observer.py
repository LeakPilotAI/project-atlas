"""R16 original installed independent UTC + thirty-symbol IEX research roster.

Run ONLY with selected immutable R16 D: python.exe, from its release CWD,
through runpy.run_path of THIS host-side wrapper. All trading-data/clock
implementations are original installed R16 bytes, SHA-pinned BEFORE keys.

Research catalog 0..N scanned in at most 30-name subscriptions; 10..35 sec,
one socket, zero retries/reconnects. Per-symbol accepted quote counts measure
the limitation honestly: a successful ACK can coexist with 24 unavailable
symbols. Never prices, account files, execution orders or financial grants.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import runpy
import secrets
from pathlib import Path

ORIGINAL = runpy.run_path(
    r"D:\Work\Project Atlas\scripts\observation_runtime\atlas_r16_joint_ntp_iex_data_only.py",
    run_name="atlas_r16_original_installed_clock_components",
)
# The joint loader ensures original installed Python/Backend win sys.path
# precedence before the first app.* import, and pins 4 immutable source SHAs.
from app.investment.alpaca_iex import IEXFeed,Credentials,IEXRefused
import scripts.observation_runtime.atlas_r12_iex_rotation_plan as rotation

SCHEMA="ATLAS_R16_NATIVE_NTP_IEX_BASIC_30_SYMBOL_RESEARCH_V1"
PLANNER_SHA="6ed58452e8dc26f2ac5fd307b8f280a74b4513859c05f034b931256862bbcc7f"
MIN_SECONDS=10
MAX_SECONDS=35
CATALOG=Path(r"D:\Work\Project Atlas\logs\research\alpaca_equity_inventory.json")
CONFIG=Path(r"D:\Work\Project Atlas\config\alpaca.env")
SCOPE=ORIGINAL["SCOPE"]


def roster(*,seconds,offset,pins,confirmed_scope):
    if (type(seconds) is not int or not MIN_SECONDS<=seconds<=MAX_SECONDS
            or type(offset) is not int or offset<0
            or type(pins) not in (tuple,list)
            or confirmed_scope!=SCOPE):
        raise ValueError("R16_NTP_IEX_RESEARCH_EXACT_DATA_ONLY_SCOPE_REQUIRED")
    if (not CATALOG.is_file() or CATALOG.is_symlink()
            or CATALOG.is_junction()
            or not 0<CATALOG.stat().st_size<=5*1024*1024):
        raise ValueError("R16_NTP_IEX_LOCAL_RESEARCH_CATALOG_REQUIRED")
    path=Path(rotation.__file__).resolve()
    expected=ORIGINAL["RELEASE"]/"scripts/observation_runtime/atlas_r12_iex_rotation_plan.py"
    if (path!=expected.resolve()
            or hashlib.sha256(path.read_bytes()).hexdigest()!=PLANNER_SHA):
        raise ValueError("R16_NTP_IEX_ORIGINAL_RESEARCH_PLANNER_REQUIRED")
    planned=rotation.plan(
        json.loads(CATALOG.read_text(encoding="utf-8")),
        offset=offset,monitored_symbols=pins)
    if (planned.get("schema")!="ATLAS_R12_IEX_RESEARCH_OBSERVATION_ROSTER_V1"
            or not 1<=planned.get("requested_symbol_count",0)<=30
            or planned.get("requested_symbol_count")!=len(planned.get("requested_symbols",[]))
            or planned.get("max_iex_websocket_symbols")!=30
            or any(planned.get(k) is not False for k in (
                "full_universe_one_connection_supported",
                "monitored_symbols_independently_verified",
                "robinhood_brokerage_coverage_verified",
                "provider_rights_accepted",
                "paper_execution_authorized","live_trading_authorized",
                "startup_authorized"))):
        raise ValueError("R16_NTP_IEX_RESEARCH_NOT_A_FINANCIAL_ROSTER")
    return planned


def safe_result(*,planned,raw,ntp,seconds,before,after,roots_before,roots_after):
    """Only aggregate/identifier fields, NO prices or provider raw frames."""
    symbols=planned["requested_symbols"]
    if (type(raw) is not dict
            or set(raw)!={"authenticated","subscribed","endpoint",
                "feed","quote_count","fresh_quote_observed_during_connection",
                "reconnects","result","per_symbol_quote_diagnostics"}
            or raw.get("authenticated") is not True
            or raw.get("subscribed") is not True
            or raw.get("endpoint")!="wss://stream.data.alpaca.markets/v2/iex"
            or raw.get("feed")!="IEX"
            or raw.get("reconnects")!=0
            or type(raw.get("result")) is not dict
            or raw["result"].get("connection")!="DISCONNECTED"
            or raw["result"].get("paper_startup_authorized") is not False
            or type(raw.get("quote_count")) is not int
            or raw["quote_count"]<0
            or type(raw.get("fresh_quote_observed_during_connection")) is not bool
            or type(ntp) is not ORIGINAL["NativeUtcUpperBound"]
            or type(ntp.samples_verified) is not int
            or ntp.samples_verified<2
            or not 0<=ntp.max_uncertainty_ms<=1000
            or before!=after or roots_before!=roots_after
            or roots_after.get("native_root_total")!=12
            or roots_after.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R16_NTP_IEX_SELECTED_CLOCK_OR_ACK_REQUIRED")
    diag=raw.get("per_symbol_quote_diagnostics")
    if (type(diag) is not dict or set(diag)!=set(symbols)
            or any(type(v) is not dict or set(v)!={
                "received","accepted","rejected","fresh_callbacks"}
                or any(type(val) is not int or val<0 for val in v.values())
                or v["received"]!=v["accepted"]+v["rejected"]
                or v["fresh_callbacks"]!=0
                for v in diag.values())):
        raise ValueError("R16_NTP_IEX_EXACT_QUOTE_QUALITY_COUNTS_REQUIRED")
    received=sum(v["received"] for v in diag.values())
    accepted=sum(v["accepted"] for v in diag.values())
    rejected=sum(v["rejected"] for v in diag.values())
    valid_symbols=sum(v["accepted"]>0 for v in diag.values())
    if (raw["quote_count"]!=accepted
            or raw["fresh_quote_observed_during_connection"] != (accepted>0)
            or received!=accepted+rejected):
        raise ValueError("R16_NTP_IEX_PROVIDER_AGGREGATE_DRIFT_REFUSED")
    return {
        "schema":SCHEMA,
        "status":("R16_NTP_IEX_FULL_ROSTER_SUBSCRIBED_PARTIAL_FRESH_QUOTES"
                  if accepted else
                  "R16_NTP_IEX_ALL_SUBSCRIBED_NO_FRESH_QUOTES"),
        "selected_native_head":ORIGINAL["R16_HEAD"],
        "selected_original_immutable_R16_modules_verified":True,
        "data_only_symbol_roster":symbols,
        "requested_symbols_count":len(symbols),
        "research_catalog_size":planned["catalog_count"],
        "research_catalog_digest":planned["catalog_sha256"],
        "research_cursor_offset":planned["offset"],
        "next_research_offset_uncommitted":planned["next_offset"],
        "minimum_30_symbol_research_batches":planned[
            "minimum_rosters_with_same_pinned_symbols"],
        "true_original_utc_source":ORIGINAL["ntp_module"].SOURCE,
        "native_ntp_samples_verified":ntp.samples_verified,
        "max_ntp_uncertainty_ms":ntp.max_uncertainty_ms,
        "native_utc_bound_used_for_all_quote_freshness":True,
        "websocket_authenticated":True,
        "roster_subscription_acknowledged":True,
        "websocket_closed":True,
        "data_connections":1,
        "provider_reconnects":0,
        "duration_seconds":seconds,
        "symbols_with_at_least_one_accepted_quote":valid_symbols,
        "symbols_without_any_accepted_quote":len(symbols)-valid_symbols,
        "quote_messages_received":received,
        "quote_messages_accepted":accepted,
        "quote_messages_rejected":rejected,
        "accepted_quote_symbol_count_is_not_global_market_coverage":True,
        "provider_license_and_rights_accepted":False,
        "provider_supervised_operational_source_accepted":False,
        "robinhood_universe_current_executable_coverage":False,
        "full_iex_catalog_realtime_coverage":False,
        "original_native_financial_account_roots_unmodified":True,
        "original_financial_writer_roles_enrolled":0,
        "native_financial_account_files_created":0,
        "hyperliquid_provider_requests":0,
        "paper_orders_created":0,
        "live_orders_created":0,
        "financial_operating_gates_accepted":0,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
        "quotes_and_credentials_exposed":False,
    }


async def observe(*,seconds,offset,pins,confirmed_scope):
    planned=roster(
        seconds=seconds,offset=offset,pins=pins,
        confirmed_scope=confirmed_scope)
    before=ORIGINAL["require_original_selected_modules"]()
    roots_before=ORIGINAL["inspect_two_lane_native_roots"]()
    if (roots_before.get("native_root_total")!=12
            or roots_before.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R16_NTP_IEX_ORIGINAL_FINANCIAL_ROOTS_NOT_EMPTY")
    rid="atlas-r16-native-30symbol-data-only-"+secrets.token_hex(12)
    clock=ORIGINAL["NativeVersionSafePaperOperatorClock"](runtime_id=rid)
    try:
        if ORIGINAL["require_version_safe_release_digest"](
                clock=clock,runtime_id=rid,
                release_digest=ORIGINAL["ARTIFACT_DIGEST"]) is not True:
            raise ValueError("R16_NTP_IEX_RESEARCH_RELEASE_DIGEST_REFUSED")
        ntp=ORIGINAL["NativeUtcUpperBound"](clock)
        ntp()
        credentials=Credentials.load(CONFIG)
        original_feed=IEXFeed(planned["requested_symbols"],
                              clock=ntp,max_age=5)
        result=await original_feed.run(
            credentials,seconds=seconds,max_reconnects=0)
        clock.require_operational(rid)
        ntp()
        after=ORIGINAL["require_original_selected_modules"]()
        roots_after=ORIGINAL["inspect_two_lane_native_roots"]()
        return safe_result(
            planned=planned,raw=result,ntp=ntp,seconds=seconds,
            before=before,after=after,
            roots_before=roots_before,roots_after=roots_after)
    finally:
        clock.revoke()


def inspect(*,offset=0,pins=()):
    plan=roster(
        seconds=MIN_SECONDS,offset=offset,pins=pins,confirmed_scope=SCOPE)
    return {
        "schema":SCHEMA,
        "status":"R16_NATIVE_INDEPENDENT_NTP_30_SYMBOL_RESEARCH_INSPECT_ONLY",
        "selected_native_head":ORIGINAL["R16_HEAD"],
        "requested_symbols_count":plan["requested_symbol_count"],
        "research_catalog_size":plan["catalog_count"],
        "minimum_30_symbol_research_batches":plan[
            "minimum_rosters_with_same_pinned_symbols"],
        "provider_connected":False,
        "native_ntp_network_requests":0,
        "credential_bytes_read":False,
        "current_qualified_financial_market_source":False,
        "financial_operating_gates_accepted":0,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect",action="store_true")
    mode.add_argument("--execute-data-only",action="store_true")
    p.add_argument("--confirm-scope")
    p.add_argument("--seconds",type=int,default=20)
    p.add_argument("--offset",type=int,default=0)
    p.add_argument("--monitor-research",action="append",default=[])
    args=p.parse_args(argv)
    if args.inspect:
        if args.confirm_scope is not None:return 2
        try:
            print(json.dumps(inspect(
                offset=args.offset,pins=args.monitor_research),sort_keys=True))
            return 0
        except (OSError,ValueError,TypeError,KeyError):
            return 2
    try:
        result=asyncio.run(observe(
            seconds=args.seconds,offset=args.offset,
            pins=args.monitor_research,confirmed_scope=args.confirm_scope))
        print(json.dumps(result,sort_keys=True))
        return 0 if result["quote_messages_accepted"]>0 else 2
    except (OSError,IEXRefused,ValueError,TypeError,KeyError,TimeoutError):
        print(json.dumps({
            "schema":SCHEMA,
            "status":"R16_NATIVE_INDEPENDENT_UTC_RESEARCH_QUOTE_ADMISSION_REFUSED",
            "financial_operating_gates_accepted":0,
            "paper_start_authorized":False,
            "live_trading_authorized":False,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
