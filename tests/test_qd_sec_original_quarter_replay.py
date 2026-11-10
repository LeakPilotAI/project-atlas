"""Synthetic caches for direct SEC original-document quarter corroboration.

No network, original-filing authority, corporate-action assertion or account IO.
"""
from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json

import pytest

from scripts.observation_runtime import qd_sec_original_quarter_replay as replay
from test_sec_filing_evidence import document, submission, reference

NOW = datetime(2026, 11, 10, 17, 45, tzinfo=UTC)
CIK = "0000789019"
SUB = "https://data.sec.gov/submissions/CIK" + CIK + ".json"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK" + CIK + ".json"
ORIGINAL = reference()["url"]


def companyfacts():
    def fact(value):
        return {"start": "2026-07-01", "end": "2026-09-30",
                "filed": "2026-10-20", "form": "10-Q",
                "accn": "0000000000-26-000001", "val": value}
    return {
        "cik": 789019,
        "facts": {"us-gaap": {
            "EarningsPerShareDiluted": {"units": {"USD/shares": [fact(2.22)]}},
            "WeightedAverageNumberOfDilutedSharesOutstanding": {
                "units": {"shares": [fact(1000000000)]}},
        }},
    }


def store(root, url, value, *, provider="SEC_EDGAR"):
    raw = value if type(value) is str else json.dumps(value, sort_keys=True)
    packet = {"schema": "FREE_RESEARCH_CACHE_V1", "provider": provider,
              "url": url, "domain": "TLS_PUBLIC_PROVIDER",
              "retrieved_at": NOW.isoformat(),
              "sha256": hashlib.sha256(raw.encode()).hexdigest(),
              "raw": raw}
    path = root / (hashlib.sha256(url.encode()).hexdigest() + ".json")
    path.write_text(json.dumps(packet, sort_keys=True), encoding="utf-8")
    return path


def prepared(tmp_path):
    store(tmp_path, SUB, submission())
    store(tmp_path, FACTS, companyfacts())
    store(tmp_path, ORIGINAL, document(), provider="SEC_EDGAR_DOCUMENT")
    return tmp_path


def run(root, *, now=NOW, symbol="MSFT", cik=CIK, accession=None):
    return replay.inspect_original_quarter(
        symbol=symbol, cik=cik, cache_root=root, now=now,
        accession=accession)


def test_realistic_original_inline_and_separate_sec_companyfacts_agree(tmp_path):
    result = run(prepared(tmp_path))
    assert result["status"] == "DIRECT_SEC_ORIGINAL_AND_COMPANYFACTS_CORROBORATED"
    assert result["symbol"] == "MSFT" and result["cik"] == CIK
    assert result["diluted_eps_usd"] == "2.22"
    assert result["diluted_weighted_average_shares"] == "1000000000"
    assert result["period_start"] == "2026-07-01"
    assert result["period_end"] == "2026-09-30"
    assert result["accession"] == reference()["accession"]
    assert result["original_filing_sha256"] == hashlib.sha256(document().encode()).hexdigest()
    for key in ("share_adjustment_basis_accepted", "twelve_quarter_history_accepted",
                "operational_source_accepted", "financial_paper_authorized",
                "live_order_authorized"):
        assert result[key] is False
    assert result["external_provider_requests"] == 0


@pytest.mark.parametrize("damage", [
    "alter_original_bytes", "alter_original_hash", "wrong_provider", "wrong_cache_domain",
    "stale_acquisition", "future_acquisition", "wrong_cik", "wrong_eps",
    "missing_diluted_shares", "wrong_shares", "different_report",
    "wrong_original_document_identity", "missing_original", "invalid_decimal",
    "duplicate_quarter_period", "different_cik_parameter",
])
def test_original_quarter_refuses_tampered_or_unmatched_sources(tmp_path, damage):
    prepared(tmp_path)
    paths = {
        "sub": tmp_path / (hashlib.sha256(SUB.encode()).hexdigest() + ".json"),
        "facts": tmp_path / (hashlib.sha256(FACTS.encode()).hexdigest() + ".json"),
        "original": tmp_path / (hashlib.sha256(ORIGINAL.encode()).hexdigest() + ".json"),
    }
    if damage == "missing_original":
        paths["original"].unlink()
    elif damage == "different_cik_parameter":
        with pytest.raises(ValueError):
            run(tmp_path, cik="0001730168")
        return
    else:
        filename = "original" if damage.startswith("alter_original") or damage == "wrong_original_document_identity" else "facts"
        if damage in ("different_report",):
            filename = "sub"
        path = paths[filename]
        cached = json.loads(path.read_text())
        if damage == "alter_original_bytes":
            cached["raw"] += "<!-- tampered -->"
        elif damage == "alter_original_hash":
            cached["sha256"] = "0" * 64
        elif damage == "wrong_provider":
            cached["provider"] = "UNTRUSTED"
        elif damage == "wrong_cache_domain":
            cached["domain"] = "SYNTHETIC"
        elif damage == "stale_acquisition":
            cached["retrieved_at"] = "2026-01-01T00:00:00+00:00"
        elif damage == "future_acquisition":
            cached["retrieved_at"] = "2026-12-01T00:00:00+00:00"
        elif damage == "wrong_original_document_identity":
            cached["raw"] = cached["raw"].replace("0000789019", "0001730168")
            cached["sha256"] = hashlib.sha256(cached["raw"].encode()).hexdigest()
        else:
            data = json.loads(cached["raw"])
            if damage == "wrong_cik":
                data["cik"] = 1730168
            elif damage == "wrong_eps":
                data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][0]["val"] = 5.55
            elif damage == "missing_diluted_shares":
                data["facts"]["us-gaap"].pop("WeightedAverageNumberOfDilutedSharesOutstanding")
            elif damage == "wrong_shares":
                data["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"]["shares"][0]["val"] = 8
            elif damage == "invalid_decimal":
                data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][0]["val"] = "INVALID"
            elif damage == "duplicate_quarter_period":
                data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"].append(
                    deepcopy(data["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"][0]))
            elif damage == "different_report":
                data["filings"]["recent"]["reportDate"][0] = "2026-06-30"
            cached["raw"] = json.dumps(data, sort_keys=True)
            cached["sha256"] = hashlib.sha256(cached["raw"].encode()).hexdigest()
        path.write_text(json.dumps(cached, sort_keys=True), encoding="utf-8")
    with pytest.raises((ValueError, TypeError)):
        run(tmp_path)


def test_cache_recheck_refuses_symlinked_original_file(tmp_path):
    prepared(tmp_path)
    original = tmp_path / (hashlib.sha256(ORIGINAL.encode()).hexdigest() + ".json")
    replacement = tmp_path / "archived-copy"
    original.rename(replacement)
    try:
        original.symlink_to(replacement)
    except (OSError, NotImplementedError):
        pytest.skip("Windows local symlink privilege not available")
    with pytest.raises(ValueError, match="CACHED_EXACT_ORIGINAL_REQUIRED"):
        run(tmp_path)


@pytest.mark.parametrize("bad", ["msft", "MSFT/../", "A" * 9])
def test_security_symbol_must_be_exact_and_never_trigger_io(tmp_path, bad):
    with pytest.raises(ValueError, match="EXPLICIT_SECURITY"):
        run(tmp_path, symbol=bad)


def test_explicit_accession_replays_only_matching_original_10q(tmp_path):
    prepared(tmp_path)
    result = run(tmp_path, accession=reference()["accession"])
    assert result["accession"] == reference()["accession"]
    assert result["diluted_eps_usd"] == "2.22"
    assert result["original_filing_and_companyfacts_matched"] is True
    assert result["twelve_quarter_history_accepted"] is False
    assert result["financial_paper_authorized"] is False


@pytest.mark.parametrize("bad_accession", [
    "0000000000-26-000002", "0000000000-26-999999",
])
def test_exact_requested_quarter_never_falls_back_to_latest(tmp_path, bad_accession):
    prepared(tmp_path)
    with pytest.raises(ValueError, match="SUBMISSIONS_10Q_ACCESSION_REQUIRED"):
        run(tmp_path, accession=bad_accession)


@pytest.mark.parametrize("bad_accession", [
    "", "000000000026000001", "0000000000-26-000001/../",
    "0000000000-26-000001?fake", 123, True,
])
def test_invalid_accession_refuses_without_accessing_cached_resources(tmp_path, bad_accession):
    with pytest.raises(ValueError, match="EXACT_HISTORICAL_ACCESSION_REQUIRED"):
        run(tmp_path, accession=bad_accession)


def test_explicit_accession_cannot_admit_annual_report_as_standalone_10q(tmp_path):
    prepared(tmp_path)
    path = tmp_path / (hashlib.sha256(SUB.encode()).hexdigest() + ".json")
    cache = json.loads(path.read_text(encoding="utf-8"))
    data = json.loads(cache["raw"])
    data["filings"]["recent"]["form"][0] = "10-K"
    cache["raw"] = json.dumps(data, sort_keys=True)
    cache["sha256"] = hashlib.sha256(cache["raw"].encode()).hexdigest()
    path.write_text(json.dumps(cache, sort_keys=True), encoding="utf-8")
    with pytest.raises(ValueError, match="SUBMISSIONS_10Q_ACCESSION_REQUIRED"):
        run(tmp_path, accession=reference()["accession"])
