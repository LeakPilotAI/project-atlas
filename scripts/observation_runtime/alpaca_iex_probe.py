"""Explicit, bounded Alpaca IEX data observation, never a PAPER order or session.

A real provider connection is possible ONLY with both --execute-data-only and
--confirm-scope ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING. Nothing reads
config or opens a socket during --inspect. A successful exit requires actual
authentication, subscription and at least one fresh provider quote, never just
a websocket handshake or a positive research catalog.
"""
import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

from app.investment.alpaca_iex import SYMBOL, Credentials, IEXFeed, IEXRefused

SCOPE = "ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING"
REASON = "IEX_CONFIGURATION_OR_DATA_UNAVAILABLE"
R14_SELECTED_ENVELOPE = Path("D:/AtlasRuntime/selection/r0013.json")
R15_SELECTED_ENVELOPE = Path("D:/AtlasRuntime/selection/r0014.json")
R22_SELECTED_ENVELOPE = Path("D:/AtlasRuntime/selection/r0022.json")
R23_SELECTED_ENVELOPE = Path("D:/AtlasRuntime/selection/r0023.json")
R22_SOURCE_COMMIT = "2f0fcfd9741b8fd524f2e5921a79998373a689c9"
R22_ARTIFACT_DIGEST = "5b23187f39316cd4e4d81659fec70758d9db661051604f4d91379938c5e92a51"
R22_HEAD = "86649902c02cfe99be2e5714091d8d4e6ff9b483df6cfa645566e44d40e7f92b"
R23_SOURCE_COMMIT = "8463f1da3786647677629ae10da5e95c8940e688"
R23_ARTIFACT_DIGEST = "b7b21a66cd6487f7f2e5de05b3135c47338186d3ae621e0ef2afc50a0c3d5766"
R23_HEAD = "90ccd9a9b700c553deaf2c16ce2c3469fd986512c19abbb5815ce47c10dde39e"
R26_ORIGINAL_FINANCIAL_RECEIPT = Path(
    "D:/Work/Project Atlas/logs/diagnostics/"
    "atlas-r26-first-financial-attempt-native-reconciliation-20261119-r01.json"
)
R26_ORIGINAL_FINANCIAL_RECEIPT_SHA256 = (
    "8938224d670bfc852469c93d0538233f49be0e5d322d8225c8a6aff436a09e06"
)
NATIVE_SELECTED_RELEASES = {
    22: (R22_SOURCE_COMMIT, R22_ARTIFACT_DIGEST, R22_HEAD, 10773),
    23: (R23_SOURCE_COMMIT, R23_ARTIFACT_DIGEST, R23_HEAD, 10802),
}


def admit_original_roots_for_data_only(roots, *, selected_revision):
    """Recognize a preserved R26 postjournal state, not an empty fake epoch.

    A bounded Alpaca IEX quote *observation* can take place after original
    financial journals exist. Historical native roots are never adopted for
    trading, finance or the current R30 account; no PAPER permission follows.
    """
    if (type(roots) is not dict
            or type(selected_revision) is not int
            or roots.get("native_root_total") != 12
            or roots.get("native_root_ids_verified") != 12):
        raise IEXRefused("IEX_ORIGINAL_NATIVE_ROOTS_NOT_IDENTITY_VERIFIED")
    if roots.get("all_twelve_distinct_and_empty") is True:
        return True
    if (selected_revision < 26
            or roots.get("existing_empty_root_namespaces") != 10):
        raise IEXRefused("IEX_POSTJOURNAL_ORIGINAL_ROOT_PHASE_REFUSED")
    lanes = roots.get("lanes")
    if type(lanes) is not dict or set(lanes) != {"QUALITY_DIPS", "HYPERLIQUID"}:
        raise IEXRefused("IEX_POSTJOURNAL_ORIGINAL_NATIVE_LANES_REFUSED")
    ids = set()
    for lane in ("QUALITY_DIPS", "HYPERLIQUID"):
        record = lanes[lane]
        if type(record) is not dict or type(record.get("roots")) is not dict:
            raise IEXRefused("IEX_POSTJOURNAL_ORIGINAL_NATIVE_ROLES_REFUSED")
        roles = record["roots"]
        if set(roles) != {"source", "projection", "report",
                          "control", "coordination", "custody"}:
            raise IEXRefused("IEX_POSTJOURNAL_ORIGINAL_NATIVE_ROLES_REFUSED")
        for role, item in roles.items():
            if (type(item) is not dict
                    or item.get("native_identity_verified") is not True
                    or item.get("existing_empty_namespace_verified")
                       is not (role != "coordination")
                    or type(item.get("native_id")) is not list
                    or len(item["native_id"]) != 3
                    or any(type(v) is not int or v < 0
                           for v in item["native_id"])):
                raise IEXRefused("IEX_POSTJOURNAL_ORIGINAL_ROOT_PHASE_REFUSED")
            identity = tuple(item["native_id"])
            if identity in ids:
                raise IEXRefused("IEX_POSTJOURNAL_ORIGINAL_NATIVE_ALIAS_REFUSED")
            ids.add(identity)
    path = R26_ORIGINAL_FINANCIAL_RECEIPT
    try:
        data = path.read_bytes()
        if (path.is_symlink() or
                hashlib.sha256(data).hexdigest() !=
                    R26_ORIGINAL_FINANCIAL_RECEIPT_SHA256):
            raise IEXRefused("IEX_R26_ORIGINAL_TERMINAL_RECEIPT_CHANGED")
        historical = json.loads(data)
    except (OSError, ValueError) as exc:
        raise IEXRefused("IEX_R26_ORIGINAL_TERMINAL_RECEIPT_UNAVAILABLE") from exc
    if (historical.get("schema") !=
             "ATLAS_R26_INDEPENDENT_FIRST_ATTEMPT_NATIVE_FINANCIAL_READBACK_V1"
            or historical.get("status") !=
             "TWO_ORIGINAL_JOURNALS_VERIFIED_ACTIVATION_PRESENT_ZERO_ACCOUNT_PUBLICATIONS"
            or historical.get("selected_revision") != 26
            or historical.get("total_original_financial_roots") != 12
            or historical.get("empty_original_financial_roots") != 10
            or historical.get("original_journals_verified") != 2
            or historical.get("original_account_publications_observed") != 0
            or historical.get("original_initialization_attempt_durable_and_non_replayable")
               is not True
            or historical.get("native_custody_accounts_empty") is not True
            or historical.get("source_providers_connected") is not False
            or historical.get("paper_start_authorized") is not False
            or historical.get("live_money_trading_authorized") is not False):
        raise IEXRefused("IEX_R26_ORIGINAL_TERMINAL_RECEIPT_NOT_ACCEPTED")
    return True


def _inspect_current_native_source():
    """Read the *current* selected R22/R23 image, not a historic selector file.

    The native store validates the full original record chain. Both supported
    release heads and exact retained installed-image identities are anchored
    here. No credentials, provider sockets or financial authority are used.
    """
    from scripts import release_selection as releases
    from scripts.observation_runtime.atlas_r12_iex_rotation_plan import (
        inspect as inspect_research_roster,
    )
    from scripts.observation_runtime.atlas_r17_cpu_budget import NativeR17CpuBudget
    from scripts.observation_runtime.personal_existing_native_resource_evidence import (
        inspect_two_lane_native_roots,
    )
    from scripts.observation_runtime.personal_version_safe_release_clock import (
        SELECTOR_NATIVE,
    )
    from scripts.release_selection_store import NativeSelectionStore

    with NativeR17CpuBudget() as cpu:
        store = NativeSelectionStore(
            root=r"D:\AtlasRuntime\selection", native_root=list(SELECTOR_NATIVE)
        )
        try:
            with store.locked():
                records = store.records()
                revision = len(records)
                if (not 22 <= revision <= 64
                        or records[-1].get("revision") != revision
                        or releases.digest(records[21]) != R22_HEAD):
                    raise IEXRefused("IEX_SELECTED_NATIVE_FORWARD_CHAIN_REQUIRED")
                selected = releases.validate_spec(
                    records[-1]["selected"], "WINDOWS_LOCAL",
                )
                if revision in NATIVE_SELECTED_RELEASES:
                    expected_release, expected_artifact, expected_head, expected_files = (
                        NATIVE_SELECTED_RELEASES[revision]
                    )
                else:
                    # A successor's receipt digest does not exist at source
                    # freeze time. Bind the ACTUAL installed source/interpreter
                    # to the original verified forward SELECT chain instead.
                    from scripts.observation_runtime.personal_version_safe_release_clock import (
                        CLOCK_RELATIVE, RELEASE_PARENT, admit_version_safe_clock_source,
                    )
                    release = Path(__file__).absolute().parents[2]
                    if (releases.digest(records[22]) != R23_HEAD
                            or release.parent != RELEASE_PARENT
                            or Path(__file__).absolute() != release /
                               "scripts/observation_runtime/alpaca_iex_probe.py"
                            or Path(sys.executable).absolute() != release / "python/python.exe"):
                        raise IEXRefused("IEX_FUTURE_EXACT_INSTALLED_NATIVE_CODE_REQUIRED")
                    expected_head, verified_spec = admit_version_safe_clock_source(
                        source_file=release / CLOCK_RELATIVE, records=records,
                    )
                    if verified_spec != selected:
                        raise IEXRefused("IEX_FUTURE_VERIFIED_SELECTION_MISMATCH")
                    expected_release, expected_artifact, expected_files = (
                        release.name, selected["artifact_digest"], None,
                    )
                if (selected["release"] != expected_release
                        or selected["artifact_digest"] != expected_artifact
                        or records[-1]["action"] != "SELECT"
                        or releases.digest(records[-1]) != expected_head):
                    raise IEXRefused("IEX_SELECTED_NATIVE_SOURCE_ARTIFACT_REQUIRED")
                selected_head = expected_head
        finally:
            store.close()
        cpu.pulse()
        with releases.NativeInstalledReleaseVerifier().open(selected) as receipt:
            if (receipt["artifact_digest"] != expected_artifact
                    or receipt["source_commit"] != expected_release
                    or (len(receipt["files"]) != expected_files
                        if expected_files is not None
                        else not 10802 <= len(receipt["files"]) <= 40000)
                    or (len(receipt["directories"]) != 915
                        if expected_files is not None
                        else not 915 <= len(receipt["directories"]) <= 40000)
                    or receipt.get("financial_effects") is not False
                    or receipt.get("operational_acceptance") is not False):
                raise IEXRefused("IEX_SELECTED_NATIVE_INSTALLED_IMAGE_REQUIRED")
        cpu.pulse()
        roots = inspect_two_lane_native_roots()
        admit_original_roots_for_data_only(roots, selected_revision=revision)
        research = inspect_research_roster()
        if (research["catalog_count"] <= 0
                or research["paper_execution_authorized"] is not False
                or research["provider_rights_accepted"] is not False
                or research["authenticated_iex_connection"] is not False):
            raise IEXRefused("IEX_SELECTED_NATIVE_NONFINANCIAL_CATALOG_REQUIRED")
        # NativeSelectionStore is one-shot: never reuse revoked handles.
        final_store = NativeSelectionStore(
            root=r"D:\AtlasRuntime\selection", native_root=list(SELECTOR_NATIVE)
        )
        try:
            with final_store.locked():
                again = final_store.records()
                if (len(again) != revision
                        or releases.digest(again[-1]) != selected_head):
                    raise IEXRefused("IEX_SELECTED_NATIVE_CHANGED_DURING_INSPECT")
        finally:
            final_store.close()
        cpu.pulse()
        if revision >= 24:
            return revision, research["catalog_count"], True
        return revision, research["catalog_count"]


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
    from scripts.observation_runtime.atlas_r12_alpaca_source_admission import (
        validate_bounded_iex_probe,
    )
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
    future_selected_native_source_verified = False
    if R23_SELECTED_ENVELOPE.exists() or R22_SELECTED_ENVELOPE.exists():
        # Historical selectors persist. Only the exact native readback can
        # identify a future selected release, never a fabricated revision.
        observed = _inspect_current_native_source()
        if (type(observed) is not tuple or len(observed) not in (2, 3)
                or type(observed[0]) is not int or type(observed[1]) is not int):
            raise IEXRefused("IEX_CURRENT_NATIVE_INSPECT_RESULT_REFUSED")
        revision, catalog_count = observed[:2]
        future_selected_native_source_verified = (
            len(observed) == 3 and observed[2] is True and revision >= 24
        )
        if (revision not in (22, 23) and
                not future_selected_native_source_verified):
            raise IEXRefused("IEX_FUTURE_NATIVE_SOURCE_NOT_VERIFIED")
        qd_published = False
    elif R15_SELECTED_ENVELOPE.exists():
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
        "future_selected_native_source_verified":future_selected_native_source_verified,
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
        current_revision = selected.get('selected_revision')
        if (type(current_revision) is not int
                or (current_revision not in (12, 13, 14, 22, 23)
                    and not (24 <= current_revision <= 64
                             and selected.get('future_selected_native_source_verified') is True))
                or selected.get('trading_authorized') is not False
                or selected.get('provider_rights_independently_accepted') is not False):
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
            from scripts.observation_runtime import (
                atlas_r12_iex_diagnostic_receipt as receipt,
            )
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
