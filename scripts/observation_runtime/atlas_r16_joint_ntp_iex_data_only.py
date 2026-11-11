"""One selected R16 native two-peer clock + live IEX WebSocket *same-process* test.

Launch using selected D:/AtlasRuntime/.../python/python.exe, CWD selected
immutable R16 release, and runpy.run_path of this HOST-SIDE script. Only the
pre-existing immutably installed native clock, IEX feed and probe are imported.
Exact installed origin and source SHA pins are required before credentials.

10-60 seconds, at most 2 explicit IEX symbols, one data-only WebSocket,
zero reconnects. IEX freshness compares quotes with the *same process's*
current independently cross-checked UTC upper bound, not Windows wall time.
No financial clock lease, provider-source acceptance, order, account write
or trading authority. Closing the socket and revoking the native clock does
NOT authorize PAPER startup.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import sys
import time
from pathlib import Path

# The selected Python distribution has a host-workspace site-path by default.
# Pin import precedence to the original IMMUTABLE selected R16 backend before
# the FIRST import of app.*; subsequently verify exact source SHA identities.
_ORIGINAL_R16 = Path(
    "D:/AtlasRuntime/releases/cadb3b5a163b31f9ee7bda32453a5983e809ccc0")
if (os.name == "nt"
        and Path(sys.executable).resolve() ==
            (_ORIGINAL_R16/"python/python.exe").resolve()):
    sys.path.insert(0,str(_ORIGINAL_R16/"backend"))
    sys.path.insert(0,str(_ORIGINAL_R16))

from app.investment.alpaca_iex import Credentials, IEXFeed, IEXRefused, SYMBOL
import app.investment.alpaca_iex as feed_module
import scripts.observation_runtime.personal_version_safe_release_clock as clock_module
import scripts.observation_runtime.alpaca_iex_probe as probe_module
import scripts.observation_runtime.atlas_independent_ntp_clock as ntp_module
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock, require_version_safe_release_digest,
    require_native_version_safe_clock_source,
)
from scripts.observation_runtime.alpaca_iex_probe import (
    admit_result, SCOPE,
)
from scripts.observation_runtime.personal_existing_native_resource_evidence import (
    inspect_two_lane_native_roots,
)
# The original immutable installed R16 package predates the host-side
# atlas_r16_selected_code_readback.py. Do NOT import host workspace packages
# into this selected-runtime observer. The original version-safe native
# selector verifier checks the full installed release/receipt/selection here.
SOURCE = "cadb3b5a163b31f9ee7bda32453a5983e809ccc0"
R16_HEAD = "1244c614ccc9e89e436d90df77cebb6e44a57edcb44972660940ed29ebfcd593"
ARTIFACT_DIGEST = "48c8192aa378526a319c3d2808f35f7e4662e47e69cde4daafbd4ba4115a8bd9"

SCHEMA = "ATLAS_R16_ORIGINAL_NATIVE_NTP_IEX_ONE_PROCESS_DATA_ONLY_V1"
RELEASE = Path("D:/AtlasRuntime/releases") / SOURCE
CONFIG = Path("D:/Work/Project Atlas/config/alpaca.env")
PINNED_MODULES = (
    (clock_module,"scripts/observation_runtime/personal_version_safe_release_clock.py",
     "7357b0d537a2e4b7728b896337bfee48f8856ced5b6e2410c56c623191ea17c5"),
    (ntp_module,"scripts/observation_runtime/atlas_independent_ntp_clock.py",
     "230a35d8b293be0d38ded533bb964d36bc5bf3c80d432a85656bc4c22650979c"),
    (probe_module,"scripts/observation_runtime/alpaca_iex_probe.py",
     "11a3cf3d9147437f2789e7f8123083596a9b48c30e933ea4ec6931ef38dfe801"),
    (feed_module,"backend/app/investment/alpaca_iex.py",
     "5d691df6f74ebc2200515cfda8aa7da895e02217d018022bb1b1269a92091d23"),
)


def scope(*, seconds, symbols, confirmed_scope):
    if (confirmed_scope != SCOPE
            or type(seconds) is not int or not 10 <= seconds <= 60
            or type(symbols) is not list or not 1 <= len(symbols) <= 2
            or len(set(symbols)) != len(symbols)
            or any(type(s) is not str or SYMBOL.fullmatch(s) is None
                   for s in symbols)):
        raise ValueError("R16_NTP_IEX_EXACT_BOUNDED_DATA_ONLY_SCOPE_REQUIRED")
    return tuple(symbols)


def require_original_selected_modules():
    if (os.name != "nt"
            or Path(sys.executable).resolve() != (RELEASE/"python/python.exe").resolve()
            or require_native_version_safe_clock_source(deep=True) != R16_HEAD):
        raise ValueError("R16_NTP_IEX_ORIGINAL_SELECTED_READONLY_PYTHON_REQUIRED")
    for module,relative,sha in PINNED_MODULES:
        expected=(RELEASE/relative).resolve()
        path=Path(module.__file__).resolve()
        if (path != expected or path.is_symlink() or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != sha):
            raise ValueError("R16_NTP_IEX_ORIGINAL_INSTALLED_BINARY_SHA_REFUSED")
    if not CONFIG.is_file() or CONFIG.is_symlink() or CONFIG.is_junction():
        raise ValueError("R16_NTP_IEX_EXACT_DATA_ONLY_CONFIG_REQUIRED")
    return {"selected_native_head":R16_HEAD,
            "installed_artifact_digest":ARTIFACT_DIGEST,
            "financial_clock_operational_accepted":False,
            "provider_source_operational_accepted":False,
            "paper_start_authorized":False,
            "live_trading_authorized":False}


class NativeUtcUpperBound:
    """Conservative UTC upper bound from genuine in-process issued NTP samples.

    The NTP runtime sample rounds down to integer UTC; +1 second and
    uncertainty ensure that provider quotes with fractions are not
    mistakenly labeled as being in the future. This rejects some otherwise
    fresh quotes; it can never create an executable trading price.
    """

    def __init__(self, owner):
        self.owner=owner
        self.last_sample=None
        self.last_utc_upper=None
        self.samples_verified=0
        self.max_uncertainty_ms=0

    def __call__(self):
        now=time.perf_counter_ns()
        if (self.last_sample is None
                or now-self.last_sample["monotonic_ns"] > 250_000_000):
            sample=self.owner.runtime_sample()
            if (type(sample) is not dict
                    or sample.get("schema") != "QD_AUTO_CLOCK_V3"
                    or sample.get("source_id") != ntp_module.SOURCE
                    or type(sample.get("utc")) is not int
                    or type(sample.get("uncertainty_ms")) is not int
                    or not 0 <= sample["uncertainty_ms"] <= 1000
                    or self.owner.verify_runtime_sample(sample) is not True):
                raise ValueError("R16_NTP_IEX_GENUINE_NATIVE_CLOCK_SAMPLE_REFUSED")
            self.last_sample=sample
            self.samples_verified+=1
            self.max_uncertainty_ms=max(
                self.max_uncertainty_ms,sample["uncertainty_ms"])
            now=time.perf_counter_ns()
        delta_ns=now-self.last_sample["monotonic_ns"]
        if not 0 <= delta_ns <= 1_000_000_000:
            raise ValueError("R16_NTP_IEX_MONOTONIC_CACHE_INVALID")
        upper=(self.last_sample["utc"]+1.0
               +self.last_sample["uncertainty_ms"]/1000.0
               +delta_ns/1_000_000_000)
        if (self.last_utc_upper is not None
                and upper+1.25 < self.last_utc_upper):
            raise ValueError("R16_NTP_IEX_CLOCK_ROLLBACK")
        self.last_utc_upper=max(upper,self.last_utc_upper or upper)
        return self.last_utc_upper


def admit(*, data, symbols, observed, callbacks, native_utc,
          elapsed_seconds, selected_before, selected_after, roots_before,
          roots_after):
    """Pure nonfinancial quote-count + native clock binding assessment."""
    if (type(data) is not dict
            or type(native_utc) is not NativeUtcUpperBound
            or type(native_utc.samples_verified) is not int
            or native_utc.samples_verified < 2
            or not 0 <= native_utc.max_uncertainty_ms <= 1000
            or selected_before != selected_after
            or roots_before != roots_after
            or not roots_after["all_twelve_distinct_and_empty"]
            or type(elapsed_seconds) is not float
            or not 10 <= elapsed_seconds <= 90
            or data.get("paper_fill_authorized",False) is not False
            or data.get("live_order_authorized",False) is not False):
        raise ValueError("R16_NTP_IEX_SAME_PROCESS_CLOCK_OR_ORIGINAL_ROOTS_REFUSED")
    accepted=admit_result(
        data,observed_symbols=observed,
        observed_count=callbacks,requested_symbols=list(symbols))
    diag=accepted.get("per_symbol_quote_diagnostics")
    if (type(diag) is not dict or set(diag) != set(symbols)
            or sum(v["fresh_callbacks"] for v in diag.values()) != callbacks
            or not observed):
        raise ValueError("R16_NTP_IEX_EXACT_AUTHENTICATED_DIAGNOSTICS_REQUIRED")
    return {
        "schema":SCHEMA,
        "status":"R16_SAME_PROCESS_NATIVE_NTP_AND_IEX_FRESH_QUOTE_OBSERVED",
        "selected_native_revision":15,
        "selected_native_head":R16_HEAD,
        "same_process_independent_utc_quote_freshness_verified":True,
        "native_two_peer_clock_source":ntp_module.SOURCE,
        "independent_utc_upper_bound_samples_verified":native_utc.samples_verified,
        "independent_utc_uncertainty_bound_max_ms":native_utc.max_uncertainty_ms,
        "session_duration_approx_seconds":round(elapsed_seconds,1),
        "authenticated":True,
        "subscribed":True,
        "websocket_closed":True,
        "data_feed":"ALPACA_IEX_SINGLE_EXCHANGE_NOT_NBBO",
        "requested_symbols":list(symbols),
        "fresh_callback_symbols":sorted(observed),
        "fresh_quote_callbacks":callbacks,
        "per_symbol_quote_diagnostics":diag,
        "original_twelve_native_financial_roots_unmodified":True,
        "independent_financial_clock_lease_accepted":False,
        "provider_rights_independently_accepted":False,
        "continuous_financial_source_published":False,
        "financial_writer_roles_enrolled":0,
        "financial_operating_gates_accepted":0,
        "native_financial_account_files_created":0,
        "provider_reconnects":0,
        "paper_orders_created":0,
        "live_orders_created":0,
        "paper_start_authorized":False,
        "live_trading_authorized":False,
    }


async def observe(*, seconds, symbols, confirmed_scope):
    symbols=scope(seconds=seconds,symbols=symbols,
                  confirmed_scope=confirmed_scope)
    selected_before=require_original_selected_modules()
    roots_before=inspect_two_lane_native_roots()
    if (roots_before.get("native_root_total")!=12
            or roots_before.get("all_twelve_distinct_and_empty") is not True):
        raise ValueError("R16_NTP_IEX_EXISTING_NATIVE_ROOTS_NOT_EMPTY")
    rid="atlas-r16-data-only-ntp-iex-"+secrets.token_hex(12)
    clock=NativeVersionSafePaperOperatorClock(runtime_id=rid)
    try:
        if require_version_safe_release_digest(
                clock=clock,runtime_id=rid,release_digest=ARTIFACT_DIGEST) is not True:
            raise ValueError("R16_NTP_IEX_REAL_SELECTED_CLOCK_ARTIFACT_REFUSED")
        # The real clock/selected native image MUST precede credentials.
        observer=NativeUtcUpperBound(clock)
        observer()
        credentials=Credentials.load(CONFIG)
        feed=IEXFeed(list(symbols),clock=observer,max_age=5)
        count=0
        seen=set()
        def on_quote(event):
            nonlocal count
            if (type(event) is not dict
                    or event.get("symbol") not in symbols
                    or event.get("provider")!="ALPACA_IEX"
                    or type(event.get("timestamp")) is not str
                    or event.get("paper_fill_authorized") is not False
                    or event.get("live_order_authorized") is not False):
                raise ValueError("R16_NTP_IEX_UNTRUSTED_PROVIDER_CALLBACK_REFUSED")
            observer()
            count+=1
            seen.add(event["symbol"])
        start=time.perf_counter()
        raw=await feed.run(
            credentials,seconds=seconds,max_reconnects=0,
            on_fresh_quote=on_quote)
        elapsed=float(time.perf_counter()-start)
        clock.require_operational(rid)
        observer()
        selected_after=require_original_selected_modules()
        roots_after=inspect_two_lane_native_roots()
        return admit(
            data=raw,symbols=symbols,observed=seen,callbacks=count,
            native_utc=observer,elapsed_seconds=elapsed,
            selected_before=selected_before,selected_after=selected_after,
            roots_before=roots_before,roots_after=roots_after)
    finally:
        clock.revoke()


def inspect():
    return {
        "schema":SCHEMA,
        "status":"R16_ORIGINAL_NATIVE_NTP_IEX_DATA_ONLY_SCOPE_PRECHECK",
        "network_requests":0,
        "credential_bytes_read":False,
        "native_financial_account_files_created":0,
        "independent_financial_clock_lease_accepted":False,
        "provider_rights_independently_accepted":False,
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
    p.add_argument("--seconds",type=int,default=50)
    p.add_argument("--symbols",nargs="+",default=["MSFT"])
    a=p.parse_args(argv)
    if a.inspect:
        if a.confirm_scope is not None:
            return 2
        print(json.dumps(inspect(),sort_keys=True))
        return 0
    try:
        v=asyncio.run(observe(
            seconds=a.seconds,symbols=a.symbols,
            confirmed_scope=a.confirm_scope))
        print(json.dumps(v,sort_keys=True))
        return 0
    except (ValueError,IEXRefused,OSError,TypeError,KeyError,TimeoutError):
        print(json.dumps({
            "schema":SCHEMA,"status":"R16_NATIVE_NTP_IEX_NONFINANCIAL_OBSERVATION_REFUSED",
            "financial_operating_gates_accepted":0,"paper_start_authorized":False,
            "live_trading_authorized":False,
        },sort_keys=True))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
