"""Disposable-only tests of native-bound original SEC WATCH source issuer.

These tests intentionally construct uninitialized exact native class instances
with monkeypatched original authority/clock/SEC readback. They do NOT claim
real Windows operator activation or an accepted operational SEC source.
"""
from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
from app.investment.quality_dips_candidate_evidence import verified
from app.services.paper_financial_replay import digest
from test_quality_dips_current_producer import STAMP, fixture

from scripts.observation_runtime import personal_selected_qd_sec_watch_issuer as issuer
from scripts.observation_runtime.personal_local_authority import (
    NativePersonalOperatorAuthority,
)
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock,
)

SEC = {
    "status": "DIRECT_SEC_ORIGINAL_AND_COMPANYFACTS_CORROBORATED",
    "original_filing_and_companyfacts_matched": True,
    "operational_source_accepted": False,
    "financial_paper_authorized": False,
    "live_order_authorized": False,
    "accession": "SYNTHETIC-NOT-SEC",
}


def setup(monkeypatch, symbols=("MSFT",)):
    f = fixture(monkeypatch, symbols)
    for row in f.cut["rows"]:
        row["valuation_sources"] = []
    f.refresh_observations()
    f.cut["execution_domain"] = "OPERATIONAL"
    f.cut["publication"]["issuer"] = issuer.WATCH
    f.cut["instruments"] = []
    f.cut["quotes"] = {}
    f.cut["monitors"] = {}
    f.cut["provenance"] = {
        "schema": issuer.WATCH,
        "sec_quarters": {symbol: copy.deepcopy(SEC) for symbol in symbols},
    }
    release = f.s.e["release_digest"]
    owner = RetainedSelectedNativeOwnerPreflight.__new__(
        RetainedSelectedNativeOwnerPreflight
    )
    owner._phase = "INITIAL_READBACK_ONLY"
    owner.release_digest = release
    seen = []
    owner.verify_still_running = lambda: seen.append("original_job") or True
    owner.require_exact_roster = lambda **kw: seen.append(("roster", kw)) or True

    clock = NativeVersionSafePaperOperatorClock.__new__(
        NativeVersionSafePaperOperatorClock
    )
    monkeypatch.setattr(NativeVersionSafePaperOperatorClock, "__call__",
                        lambda self: STAMP)
    clock.require_operational = lambda runtime: seen.append(("clock", runtime))

    qd = {
        "account_id": f.s.e["account_id"],
        "release_digest": release,
    }
    perp = {
        "account_id": "SYNTHETIC_PERP_OTHER",
        "release_digest": release,
    }
    operator = NativePersonalOperatorAuthority.__new__(
        NativePersonalOperatorAuthority
    )
    operator.clock = clock
    operator.enrollment = qd
    operator.accounts = {
        "QUALITY_DIPS": digest(qd),
        "HYPERLIQUID": digest(perp),
    }
    operator.runtime_id = "SYNTHETIC_NOT_REAL_OWNER"
    activation = {"activation_id": "SYNTHETIC_READONLY_ONLY"}
    operator.activation = lambda action: (
        seen.append(("activation", action)) or copy.deepcopy(activation)
    )
    # Bind the actual original in-memory immutable native image protocol to
    # the synthetic typed selected clock. This is still not a real operator
    # or an original financial root; native CAS/readback runs unchanged.
    archive = f.s.archive
    f.s.clock = clock
    archive.clock = clock
    archive._ports = (archive.images, archive.authority, clock)
    current = archive.current
    archive.current = lambda: seen.append("archive_readback") or current()
    release_check = SimpleNamespace(accepted=True)
    monkeypatch.setattr(
        issuer, "require_version_safe_release_digest",
        lambda **_: release_check.accepted,
    )
    receipt = SimpleNamespace(value=copy.deepcopy(SEC), calls=[])
    def original(*, symbol, cik, now):
        receipt.calls.append((symbol, cik, now))
        return copy.deepcopy(receipt.value)
    monkeypatch.setattr(issuer, "inspect_original_quarter", original)
    context = {
        "enrollment": archive.enrollment,
        "execution_domain": "OPERATIONAL",
        "input": f.cut,
    }
    instance = issuer.NativeSelectedQualityDipsSecWatchIssuer(
        owner=owner, operator=operator, clock=clock,
        archive=archive, qd=qd, perp=perp,
    )
    return SimpleNamespace(
        model=instance, context=context, seen=seen, receipt=receipt,
        owner=owner, operator=operator, clock=clock, archive=archive,
        qd=qd, perp=perp, release=release_check, activation=activation,
        fixture=f,
    )


def test_exact_native_source_issuer_proves_only_sec_corroborated_nontrade(monkeypatch):
    s = setup(monkeypatch)
    before = copy.deepcopy(s.context)
    proof = s.model.verify_current(s.context, now=STAMP)
    assert proof == verified(proof, digest(s.context), issuer.SCHEMA)
    assert s.context == before
    assert proof["execution_domain"] == "OPERATIONAL"
    assert proof["no_entry_only"] is True
    assert proof["independent_equity_valuation_accepted"] is False
    assert proof["executable_market_quote_accepted"] is False
    assert proof["financial_paper_startup_authorized"] is False
    assert proof["live_trading_authorized"] is False
    assert s.receipt.calls[0][:2] == ("MSFT", "0000789019")
    assert ("activation", "CONNECT_APPROVED_DATA") in s.seen
    assert any(isinstance(x, tuple) and x[0] == "roster" for x in s.seen)
    assert "archive_readback" in s.seen
    # Exact duplicate is allowed without changing the original proof.
    assert s.model.verify_current(s.context, now=STAMP) == proof


@pytest.mark.parametrize("damage", [
    "instrument", "quote", "monitor", "faker", "wrong_issuer",
    "wrong_domain", "wrong_id", "wrong_revision", "untrusted_valuation",
    "untrusted_normalization", "missing_sec", "wrong_sec", "foreign_sec",
    "missing_observation", "prediction", "expired", "future",
    "unexpected_field", "ranking_expired", "ranking_future", "ranking_state",
])
def test_sec_watch_nontrade_issuer_refuses_any_untrusted_source_or_eligibility(
    monkeypatch, damage,
):
    s = setup(monkeypatch)
    c = s.context["input"]
    if damage == "instrument":
        c["instruments"] = [{"symbol": "MSFT", "instrument_id": "SYNTHETIC"}]
    elif damage == "quote":
        c["quotes"]["MSFT"] = {"execution_price": "999"}
    elif damage == "monitor":
        c["monitors"]["x"] = {}
    elif damage == "faker":
        c["provenance"]["sec_quarters"]["MSFT"]["operational_source_accepted"] = True
    elif damage == "wrong_issuer":
        c["publication"]["issuer"] = "ANALYST_FAKE"
    elif damage == "wrong_domain":
        s.context["execution_domain"] = "DISPOSABLE"
    elif damage == "wrong_id":
        c["source_id"] = "WRONG_SOURCE"
    elif damage == "wrong_revision":
        c["input_revision"] = True
    elif damage == "untrusted_valuation":
        c["rows"][0]["valuation_sources"] = [{
            "value": 999999, "provenance": "ANALYST_CONSENSUS",
            "as_of": "2026-11-13",
        }]
    elif damage == "untrusted_normalization":
        c["rows"][0]["normalization_sources"] = [{
            "value": 999999, "provenance": "DCF",
            "as_of": "2026-11-13",
        }]
    elif damage == "missing_sec":
        c["provenance"]["sec_quarters"] = {}
    elif damage == "wrong_sec":
        c["provenance"]["sec_quarters"]["MSFT"]["accession"] = "FAKE"
    elif damage == "foreign_sec":
        c["rows"][0]["symbol"] = "GOOG"
    elif damage == "missing_observation":
        c["observations"] = {}
    elif damage == "prediction":
        c["observations"]["MSFT"]["classification"] = "DEEP_VALUE"
    elif damage == "expired":
        c["observed_at"] = STAMP - 31
    elif damage == "unexpected_field":
        c["test_only"] = True
    elif damage == "ranking_expired":
        c["publication"]["expires_at"] = STAMP
    elif damage == "ranking_future":
        c["publication"]["issued_at"] = STAMP + 1
    elif damage == "ranking_state":
        c["publication"]["state"] = "REVOKED"
    else:
        c["observed_at"] = STAMP + 1
    with pytest.raises((ValueError, KeyError, TypeError)):
        s.model.verify_current(s.context, now=STAMP)


@pytest.mark.parametrize("block", [
    "phase", "revoked_job", "release", "activation", "archive",
    "account", "operator_clock",
])
def test_source_issuer_cannot_infer_native_financial_rights_from_local_json(
    monkeypatch, block,
):
    s = setup(monkeypatch)
    if block == "phase":
        s.owner._phase = "PREINCEPTION"
    elif block == "revoked_job":
        s.owner.verify_still_running = lambda: False
    elif block == "release":
        s.release.accepted = False
    elif block == "activation":
        s.operator.activation = lambda _: (_ for _ in ()).throw(
            ValueError("SYNTHETIC_NATIVE_ACTIVATION_REVOKED")
        )
    elif block == "archive":
        s.archive.current = lambda: (_ for _ in ()).throw(
            ValueError("SYNTHETIC_NATIVE_ARCHIVE_REVOKED")
        )
    elif block == "account":
        s.operator.accounts = {"QUALITY_DIPS": digest(s.qd)}
    else:
        s.clock.require_operational = lambda _: (_ for _ in ()).throw(
            ValueError("SYNTHETIC_TRUSTED_UTC_REVOKED")
        )
    with pytest.raises(ValueError):
        s.model.verify_current(s.context, now=STAMP)


def test_issuer_does_not_backfill_wrong_future_revision_or_new_activation(monkeypatch):
    s = setup(monkeypatch)
    original = s.model.verify_current(s.context, now=STAMP)
    s.context["input"]["input_revision"] = 3
    assert s.model.verify_current(s.context, now=STAMP) != original
    s.context["input"]["input_revision"] = 2
    with pytest.raises(ValueError, match="CONTEXT_CHANGED_OR_REPLAY"):
        s.model.verify_current(s.context, now=STAMP)
    s.context["input"]["input_revision"] = 4
    s.activation["activation_id"] = "SYNTHETIC_NEW_OPERATOR"
    s.operator.activation = lambda _: copy.deepcopy(s.activation)
    with pytest.raises(ValueError, match="ACTIVATION_CHANGED"):
        s.model.verify_current(s.context, now=STAMP)


def test_uninitialized_or_derived_native_issuer_ports_not_accepted(monkeypatch):
    s = setup(monkeypatch)
    with pytest.raises(ValueError, match="ORIGINAL_TWO_ACCOUNTS_OWNER_REQUIRED"):
        issuer.NativeSelectedQualityDipsSecWatchIssuer(
            owner=SimpleNamespace(**s.owner.__dict__), operator=s.operator,
            clock=s.clock, archive=s.archive, qd=s.qd, perp=s.perp,
        )
    with pytest.raises(ValueError, match="ORIGINAL_TWO_ACCOUNTS_OWNER_REQUIRED"):
        issuer.NativeSelectedQualityDipsSecWatchIssuer(
            owner=s.owner, operator=s.operator, clock=s.clock,
            archive=s.archive, qd=s.qd, perp={
                "account_id": "SYNTHETIC",
                "release_digest": "a" * 64,
            },
        )



def test_sec_watch_issuer_integrates_with_original_source_publisher_without_entries(
    monkeypatch,
):
    from app.services.quality_dips_current_producer import (
        QualityDipsCurrentProducer,
    )
    s = setup(monkeypatch)
    f = s.fixture
    f.expected_components.clear()
    original_binding = digest(s.context)

    def authenticate_original_source(components, old, packet, sources, now):
        attested = sources.get("current_input", {})
        receipt = attested.get("acceptance", {})
        return (
            f.s.auth.verify_components(components)
            and packet["bundles"] == []
            and packet["monitors"] == {}
            and attested.get("input") == f.cut
            and receipt.get("schema") == issuer.SCHEMA
            and receipt.get("binding") == original_binding
            and receipt.get("no_entry_only") is True
            and receipt.get("executable_market_quote_accepted") is False
            and receipt.get("financial_paper_startup_authorized") is False
        )

    f.s.auth.verify_publication = authenticate_original_source
    publisher = QualityDipsCurrentProducer(
        source=f.source,
        input_authority=s.model,
        publication_authority=f.s.auth,
        archive=s.archive,
        candidates=f.candidates,
        clock=s.clock,
        enrollment=f.s.e,
        execution_domain="OPERATIONAL",
    )
    before = copy.deepcopy(f.s.s.files)
    packet = publisher.publish_current()
    assert packet["schema"] == "QD_SCANNER_PUBLICATION_V1"
    assert packet["bundles"] == []
    assert packet["monitors"] == {}
    assert packet["revision"] == 1
    assert len(f.s.s.files) > len(before)
    evidence = f.s.archive.read_evidence(f.s.archive.current())
    receipt = evidence["sources"]["current_input"]["acceptance"]
    assert receipt["no_entry_only"] is True
    assert receipt["financial_paper_startup_authorized"] is False
    assert receipt["independent_equity_valuation_accepted"] is False
    assert publisher.read_publication(.2) == packet
    # Source renewal from the same accepted input revision never repeats
    # the original immutable native image write.
    frozen = copy.deepcopy(f.s.s.files)
    assert publisher.publish_current() == packet
    assert f.s.s.files == frozen
    assert f.s.archive.current()["native_revision"] == 2



def test_sec_receipt_reparse_may_cross_second_but_not_source_ttl(monkeypatch):
    s = setup(monkeypatch)
    monkeypatch.setattr(NativeVersionSafePaperOperatorClock, "__call__",
                        lambda self: STAMP + 29)
    proof = s.model.verify_current(s.context, now=STAMP)
    assert proof["no_entry_only"] is True
    assert proof["financial_paper_startup_authorized"] is False


def test_sec_watch_trusted_clock_cannot_exceed_source_ttl(monkeypatch):
    s = setup(monkeypatch)
    monkeypatch.setattr(NativeVersionSafePaperOperatorClock, "__call__",
                        lambda self: STAMP + 31)
    with pytest.raises(ValueError, match="TRUSTED_UTC_REQUIRED"):
        s.model.verify_current(s.context, now=STAMP)



def test_two_original_sec_stock_symbols_are_separately_reread_and_watch_only(
    monkeypatch,
):
    s = setup(monkeypatch, ("MSFT", "AVGO"))
    proof = s.model.verify_current(s.context, now=STAMP)
    assert proof["verified"] is True
    assert proof["no_entry_only"] is True
    assert proof["executable_market_quote_accepted"] is False
    assert {symbol for symbol, _, _ in s.receipt.calls} == {"MSFT", "AVGO"}
    assert {cik for _, cik, _ in s.receipt.calls} == {
        "0000789019", "0001730168",
    }
    assert set(s.context["input"]["provenance"]["sec_quarters"]) == {"MSFT", "AVGO"}
    assert s.context["input"]["quotes"] == {}
    assert s.context["input"]["instruments"] == []
    assert proof["financial_paper_startup_authorized"] is False


def test_two_stock_sec_watch_cannot_trust_a_one_company_source(monkeypatch):
    s = setup(monkeypatch, ("MSFT", "AVGO"))
    s.context["input"]["provenance"]["sec_quarters"].pop("AVGO")
    with pytest.raises(ValueError, match="MISSING_INDEPENDENT_VALUATION_NO_ENTRY"):
        s.model.verify_current(s.context, now=STAMP)



def test_one_syndicated_low_mean_high_cannot_be_three_original_issuer_reports(
    monkeypatch,
):
    s = setup(monkeypatch)
    # Three statistics from one consensus publisher are not three
    # originating analyst firms. This is research metadata ONLY.
    s.context["input"]["rows"][0]["input_snapshot"] = {
        "valuation": {
            key: {
                "value": value,
                "source": "SYNTHETIC_SINGLE_AGGREGATOR",
                "availability": True,
                "quality": "FRESH",
                "effective_timestamp": str(STAMP),
            }
            for key, value in (
                ("target_low_price", 110),
                ("target_mean_price", 135),
                ("target_high_price", 200),
            )
        }
    }
    result = s.model.verify_current(s.context, now=STAMP)
    assert result["no_entry_only"] is True
    assert result["independent_equity_valuation_accepted"] is False
    assert result["executable_market_quote_accepted"] is False
    assert result["financial_paper_startup_authorized"] is False
    assert s.context["input"]["quotes"] == {}
    assert s.context["input"]["instruments"] == []
