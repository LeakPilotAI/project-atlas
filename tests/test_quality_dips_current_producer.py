"""Disposable source-only assembly; native image I/O is an in-memory double.

No financial engine/store/account, provider, Windows process or installed runtime.
"""

import copy
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.investment.quality_dips_candidate_evidence import CandidateEvidenceAdapter
from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_current_producer import QualityDipsCurrentProducer
from app.services.quality_dips_research_only import project_explicit_research
from test_personal_research_archive import setup as archive_setup
from test_quality_dips_v2_board import _row

STAMP = 1793282400


def proof(schema, value, **extra):
    return {
        "schema": schema,
        "verified": True,
        "binding": digest(value),
        "receipt_id": "EXPLICIT_SYNTHETIC_NOT_OPERATIONAL",
        **extra,
    }


def fixture(monkeypatch, symbols=("MSFT",)):
    s = archive_setup(monkeypatch)
    s.now[0] = STAMP
    iso = datetime.fromtimestamp(STAMP, UTC).isoformat()
    rows, instruments, quotes = [], [], {}
    for symbol in symbols:
        row = _row()
        row.update(symbol=symbol, asset_type="STOCK", timestamp=iso)
        row["trend"]["as_of"] = iso
        for val in row["valuation_sources"]:
            val["as_of"] = iso
        rows.append(row)
        instrument = {
            "symbol": symbol,
            "instrument_id": "SYNTHETIC:" + symbol,
            "asset_class": "STOCK",
            "currency": "USD",
            "units": "SHARES",
            "long_supported": True,
            "fractional": True,
            "rules_revision": "SYNTHETIC-R1",
        }
        instruments.append(instrument)
        quotes[symbol] = {
            "symbol": symbol,
            "instrument_id": instrument["instrument_id"],
            "source": "SYNTHETIC_IEX_NOT_LIVE",
            "effective_timestamp": iso,
            "execution_price": "90",
        }
    cut = {
        "schema": "QD_CURRENT_RESEARCH_INPUT_V1",
        "execution_domain": "DISPOSABLE",
        "source_id": s.e["source_id"],
        "input_revision": 1,
        "observed_at": STAMP,
        "rows": rows,
        "instruments": instruments,
        "quotes": quotes,
        "observations": {},
        "publication": {
            "schema": "QD_RANKING_REVISION_V1",
            "state": "ACTIVE",
            "issuer": "SYNTHETIC_ORIGINAL_SOURCE",
            "cohort_id": "SYNTHETIC_QD_V3",
            "generation": 1,
            "source_revision": 1,
            "issued_at": STAMP,
            "expires_at": STAMP + 300,
        },
        "monitors": {},
        "provenance": {
            "fixture_only": True,
            "free_source_receipts": ["SYNTHETIC_SEC", "SYNTHETIC_IEX"],
        },
    }
    source = SimpleNamespace(read_current=lambda: copy.deepcopy(cut))
    flags = SimpleNamespace(accepted=True, receipt_domain="DISPOSABLE", mutate=False)

    def accept(context, *, now):
        expected = {"input": cut, "enrollment": s.e, "execution_domain": "DISPOSABLE"}
        if not flags.accepted or context != expected:
            return False
        value = proof(
            "QD_CURRENT_RESEARCH_VERIFIED_V1",
            context,
            execution_domain=flags.receipt_domain,
        )
        if flags.mutate:
            context["input"]["provenance"]["changed"] = True
        return value

    def ranking(bundle, *, now):
        board = project_explicit_research(
            cut["rows"], now=datetime.fromtimestamp(now, UTC)
        )
        assert (
            bundle["board"] == board
            and bundle["observation"]
            == cut["observations"][bundle["instrument"]["symbol"]]
        )
        assert bundle["publication"] == cut["publication"]
        return proof("QD_RANKING_VERIFIED_V1", bundle)

    def execution(value, *, now):
        assert value["instrument"] in cut["instruments"]
        assert value["quote"] == cut["quotes"][value["instrument"]["symbol"]]
        return proof("QD_EXECUTION_VERIFIED_V1", value)

    candidates = CandidateEvidenceAdapter(
        ranking_authority=SimpleNamespace(verify_current=ranking),
        execution_authority=SimpleNamespace(verify=execution),
    )
    expected_components = []

    def components(c):
        if not expected_components:
            assert (
                c["archive"] is s.archive
                and c["clock"] is s.clock
                and c["candidates"] is candidates
            )
            assert c["source_id"] == s.e["source_id"] and c["lane"] == "QUALITY_DIPS"
            expected_components.append(dict(c))
        return s.auth.valid and c == expected_components[0]

    s.auth.verify_components = components
    s.auth.verify_head = lambda c, h, now: components(c) and h == s.archive.current()
    s.auth.verify_current = lambda c, h, p, now: (
        components(c) and h == s.archive.current() and p == s.archive.read(h)
    )
    s.auth.verify_research = lambda rows, at, raw, now: (
        raw == make_raw()
        and rows == make_raw()["board"]
        and at == datetime.fromtimestamp(cut["observed_at"], UTC).isoformat()
        and flags.accepted
    )
    s.auth.verify_publication = lambda c, h, p, sources, now: (
        components(c)
        and sources["current_input"]["input"] == cut
        and sources["current_input"]["enrollment"] == digest(s.e)
        and sources["current_input"]["acceptance"]["binding"]
        == digest({"enrollment": s.e, "execution_domain": "DISPOSABLE", "input": cut})
    )

    def refresh_observations():
        board = project_explicit_research(
            cut["rows"], now=datetime.fromtimestamp(s.now[0], UTC)
        )
        cut["observations"] = {
            row["symbol"]: {
                "observation_id": "SYNTHETIC_ORIGINAL:" + row["symbol"],
                "symbol": row["symbol"],
                "strategy_version": "QUALITY_DIPS_V3",
                "policy_version": "quality-dips-v3-mos-15-20-25-30-v1",
                "evidence_class": "FORWARD_COLLECTION",
                "classification": row["quality_dips_v2"]["quality_dips_v3"][
                    "patient_state"
                ],
                "prediction": row["quality_dips_v2"]["quality_dips_v3"],
                "missing_data": [],
                "execution": "MANUAL_ONLY",
                "timestamp": iso,
                "source_timestamp": iso,
            }
            for row in board
        }

    def make_raw():
        return owner._project(copy.deepcopy(cut), s.now[0])

    def reopen(domain="DISPOSABLE"):
        expected_components.clear()
        return QualityDipsCurrentProducer(
            source=source,
            input_authority=SimpleNamespace(verify_current=accept),
            publication_authority=s.auth,
            archive=s.archive,
            candidates=candidates,
            clock=s.clock,
            enrollment=s.e,
            execution_domain=domain,
        )

    refresh_observations()
    owner = reopen()
    return SimpleNamespace(**locals())


def test_complete_original_projection_candidate_archive_readback_and_no_financial_resources(
    monkeypatch,
):
    f = fixture(monkeypatch, ("MSFT", "AAPL"))

    def no_files(*args, **kwargs):
        raise AssertionError("Source assembly must not open filesystem resources")

    monkeypatch.setattr(Path, "open", no_files)
    before = copy.deepcopy(f.cut)
    p = f.owner.publish_current()
    assert [b["instrument"]["symbol"] for b in p["bundles"]] == ["MSFT", "AAPL"]
    assert p["bundles"][0]["board"] == project_explicit_research(
        f.cut["rows"], now=datetime.fromtimestamp(STAMP, UTC)
    )
    assert f.owner.read_publication(0.2) == p and f.cut == before
    r = f.s.archive.read_evidence(f.s.archive.current())
    assert r["sources"]["current_input"]["input"] == before
    assert (
        r["sources"]["current_input"]["acceptance"]["execution_domain"] == "DISPOSABLE"
    )
    assert f.s.archive.current()["revision"] == 1
    assert (
        f.s.archive.current()["native_revision"] == 2
    )  # Initial image != financial inception.
    from app.services.paper_financial_replay import strict

    with f.s.s.owner.transaction(readonly=True) as tx:
        image = strict(tx.read().decode())
    assert image["schema"] == "PERSONAL_QD_SOURCE_IMAGE_V1"
    assert set(image) == {
        "schema",
        "enrollment",
        "revision",
        "previous",
        "packet",
        "sources",
    }


def test_duplicate_restart_replay_does_not_write_or_duplicate_a_publication(
    monkeypatch,
):
    f = fixture(monkeypatch)
    p = f.owner.publish_current()
    frozen = copy.deepcopy(f.s.s.files)
    assert f.owner.publish_current() == p
    other = f.reopen()
    assert other.read_publication(0.2) == p and other.publish_current() == p
    assert f.s.s.files == frozen


@pytest.mark.parametrize(
    "damage",
    [
        "source",
        "domain",
        "receipt-domain",
        "unaccepted",
        "provenance",
        "observations",
        "quote",
        "instruments",
        "duplicate-instrument",
        "duplicate-row",
        "row-time",
        "input-time",
        "future",
        "ranking-expired",
        "ranking-generation",
        "prediction",
        "classification",
        "strategy",
        "observation-time",
        "instrument-id",
        "monitor",
        "invalid-revision",
        "authority-mutation",
    ],
)
def test_bad_inputs_refuse_before_any_publication(monkeypatch, damage):
    f = fixture(monkeypatch)
    c = f.cut
    if damage == "source":
        c["source_id"] = "FOREIGN"
    elif damage == "domain":
        c["execution_domain"] = "OPERATIONAL"
    elif damage == "receipt-domain":
        f.flags.receipt_domain = "OPERATIONAL"
    elif damage == "unaccepted":
        f.flags.accepted = False
    elif damage == "provenance":
        c["provenance"] = {}
    elif damage == "observations":
        c["observations"] = {}
    elif damage == "quote":
        c["quotes"]["MSFT"]["effective_timestamp"] = STAMP - 31
    elif damage == "instruments":
        c["instruments"] = []
    elif damage == "duplicate-instrument":
        c["instruments"] *= 2
    elif damage == "duplicate-row":
        c["rows"] *= 2
    elif damage == "row-time":
        c["rows"][0]["timestamp"] = STAMP - 601
    elif damage == "input-time":
        c["observed_at"] = STAMP - 31
    elif damage == "future":
        c["observed_at"] = STAMP + 1
    elif damage == "ranking-expired":
        c["publication"]["expires_at"] = STAMP
    elif damage == "ranking-generation":
        c["publication"]["generation"] = True
    elif damage == "prediction":
        c["observations"]["MSFT"]["prediction"]["fair_value_anchor"] = 999
    elif damage == "classification":
        c["observations"]["MSFT"]["classification"] = "WATCH"
    elif damage == "strategy":
        c["observations"]["MSFT"]["strategy_version"] = "INVENTED"
    elif damage == "observation-time":
        c["observations"]["MSFT"]["timestamp"] = STAMP + 1
    elif damage == "instrument-id":
        c["instruments"][0]["instrument_id"] = "FOREIGN"
    elif damage == "monitor":
        c["monitors"] = {"bad": {}}
    elif damage == "invalid-revision":
        c["input_revision"] = True
    elif damage == "authority-mutation":
        f.flags.mutate = True
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises((ValueError, KeyError)):
        f.owner.publish_current()
    assert f.s.s.files == frozen


@pytest.mark.parametrize("advance,accepted", [(30, True), (31, False)])
def test_current_freshness_boundary_is_preserved_on_read_and_restart(
    monkeypatch, advance, accepted
):
    f = fixture(monkeypatch)
    p = f.owner.publish_current()
    frozen = copy.deepcopy(f.s.s.files)
    f.s.now[0] += advance
    if accepted:
        assert f.reopen().read_publication(0.2) == p
    else:
        with pytest.raises(ValueError):
            f.reopen().read_publication(0.2)
    assert f.s.s.files == frozen


def test_missing_valuation_stays_watch_without_fabricating_a_candidate(monkeypatch):
    f = fixture(monkeypatch)
    f.cut["rows"][0].pop("valuation_sources")
    f.refresh_observations()
    p = f.owner.publish_current()
    assert p["bundles"] == []
    evidence = f.s.archive.read_evidence(f.s.archive.current())
    assert (
        evidence["sources"]["research"]["board"][0]["quality_dips_v2"][
            "quality_dips_v3"
        ]["patient_state"]
        == "WATCH"
    )


@pytest.mark.parametrize("damage", ["conflict", "rollback"])
def test_logical_input_revision_conflict_or_rollback_survives_restart(
    monkeypatch, damage
):
    f = fixture(monkeypatch)
    f.cut["input_revision"] = 2
    f.owner.publish_current()
    frozen = copy.deepcopy(f.s.s.files)
    if damage == "conflict":
        f.cut["provenance"]["different"] = "SYNTHETIC_CONFLICT"
    else:
        f.cut["input_revision"] = 1
    with pytest.raises(ValueError, match="CONFLICT|ROLLBACK"):
        f.reopen().publish_current()
    assert f.s.s.files == frozen


def test_new_input_revision_and_native_revision_are_distinct(monkeypatch):
    f = fixture(monkeypatch)
    f.cut["input_revision"] = 11
    assert f.owner.publish_current()["revision"] == 1
    f.cut["input_revision"] = 12
    assert f.owner.publish_current()["revision"] == 2
    assert f.s.archive.current()["native_revision"] == 3


def test_interrupted_ack_latches_uncertainty_and_does_not_retry(monkeypatch):
    f = fixture(monkeypatch)
    f.s.s.owner.fail_leaf = "0002-commit.json"
    with pytest.raises(OSError):
        f.owner.publish_current()
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError):
        f.owner.publish_current()
    with pytest.raises(ValueError):
        f.reopen().read_publication(0.2)
    assert f.s.s.files == frozen and f.s.s.owner.poisoned


def test_operational_mode_cannot_adopt_disposable_input_even_with_native_image_double(
    monkeypatch,
):
    f = fixture(monkeypatch)
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError):
        f.reopen("OPERATIONAL").publish_current()
    assert f.s.s.files == frozen


def test_input_race_refuses_before_effect(monkeypatch):
    f = fixture(monkeypatch)
    calls = []

    def changing():
        calls.append(1)
        c = copy.deepcopy(f.cut)
        if len(calls) > 1:
            c["input_revision"] += 1
        return c

    f.source.read_current = changing
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError, match="CHANGED_BEFORE"):
        f.owner.publish_current()
    assert f.s.s.files == frozen


def test_existing_publication_reader_selects_original_board_rank_without_financial_runtime(
    monkeypatch,
):
    from app.services.quality_dips_publication_reader import (
        QualityDipsPublicationReader,
    )

    f = fixture(monkeypatch, ("MSFT", "AAPL"))
    f.cut["rows"][1]["opportunity_score"] = 99
    packet = f.owner.publish_current()
    assert [b["instrument"]["symbol"] for b in packet["bundles"]] == ["AAPL", "MSFT"]
    # Explicit read-only context double; no runtime is composed or connected.
    cut = {"state": {"positions": {}}}
    runtime = SimpleNamespace(
        grant={"SYNTHETIC_READ_CONTEXT": True},
        halted=False,
        stopped=SimpleNamespace(is_set=lambda: False),
        _now=f.s.clock,
        engine=SimpleNamespace(candidates=f.candidates),
    )
    writer = SimpleNamespace(
        binding={"SYNTHETIC_READ_ONLY": True},
        runtime=SimpleNamespace(runtime=runtime),
        _cut=lambda: copy.deepcopy(cut),
    )
    writer.authority = SimpleNamespace(
        verify_publication_components=lambda binding, parts: (
            parts == {"writer": writer, "source": f.owner} and binding == writer.binding
        ),
        verify_scanner_publication=lambda binding, p, c, now: (
            binding == writer.binding and p == packet and c == cut and now == f.s.now[0]
        ),
    )
    request = QualityDipsPublicationReader(writer=writer, source=f.owner).read_request(
        0.2
    )
    assert request["instrument"]["symbol"] == "AAPL"
    assert request["bundles"] == packet["bundles"]


def test_same_input_on_independent_disposable_stores_replays_identical_packet(
    monkeypatch,
):
    first = fixture(monkeypatch).owner.publish_current()
    second = fixture(monkeypatch).owner.publish_current()
    assert body(first) == body(second)


def test_known_pre_effect_refusal_does_not_clear_or_replace_existing_state(monkeypatch):
    f = fixture(monkeypatch)
    f.flags.accepted = False
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError):
        f.owner.publish_current()
    assert f.s.s.files == frozen
    f.flags.accepted = True
    assert f.owner.publish_current()["revision"] == 1


def test_concurrent_winner_makes_other_assembly_refuse_without_duplicate_native_effect(
    monkeypatch,
):
    f = fixture(monkeypatch)
    other = f.reopen()
    # Both constructions bind identical ports except their internal projections.
    # Explicitly enrolled test graph contains these two exact component sets.
    allowed = [dict(f.owner.publication.components), dict(other.publication.components)]
    f.s.auth.verify_components = lambda c: any(c == expected for expected in allowed)
    f.s.auth.verify_head = lambda c, h, now: (
        f.s.auth.verify_components(c) and h == f.s.archive.current()
    )
    f.s.auth.verify_current = lambda c, h, p, now: (
        f.s.auth.verify_components(c)
        and h == f.s.archive.current()
        and p == f.s.archive.read(h)
    )
    original = f.owner.publication.publish_scanner

    def race(*args, **kwargs):
        other.publish_current()
        return original(*args, **kwargs)

    f.owner.publication.publish_scanner = race
    with pytest.raises(ValueError, match="EXPECTED_HEAD_CHANGED"):
        f.owner.publish_current()
    assert f.s.archive.current()["revision"] == 1
    assert other.read_publication(0.2)["revision"] == 1


@pytest.mark.parametrize(
    "damage", ["source", "release", "commit", "root", "archive", "clock"]
)
def test_enrollment_and_component_substitution_refuse(monkeypatch, damage):
    f = fixture(monkeypatch)
    if damage == "source":
        f.owner.enrollment["source_id"] = "OTHER"
    elif damage == "release":
        f.owner.enrollment["release_digest"] = "0" * 64
    elif damage == "commit":
        f.owner.enrollment["source_commit"] = "0" * 40
    elif damage == "root":
        f.owner.enrollment["root_id"] = [9, 9, 9]
    elif damage == "archive":
        f.owner.publication.archive = object()
    elif damage == "clock":
        f.owner.clock = lambda: STAMP
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError):
        f.owner.publish_current()
    assert f.s.s.files == frozen


@pytest.mark.parametrize("damage", ["issuer", "cohort", "chronology"])
def test_no_entry_still_requires_complete_current_ranking_identity(monkeypatch, damage):
    f = fixture(monkeypatch)
    f.cut["rows"][0].pop("valuation_sources")
    f.refresh_observations()
    if damage == "issuer":
        f.cut["publication"].pop("issuer")
    elif damage == "cohort":
        f.cut["publication"]["cohort_id"] = ""
    else:
        f.cut["observed_at"] -= 1
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError):
        f.owner.publish_current()
    assert f.s.s.files == frozen


def test_blanket_true_is_not_an_input_acceptance_receipt(monkeypatch):
    f = fixture(monkeypatch)
    f.owner.input_authority.verify_current = lambda *args, **kwargs: True
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError, match="AUTHORITY_UNVERIFIED"):
        f.owner.publish_current()
    assert f.s.s.files == frozen


def test_completion_freshness_crossing_fails_closed_without_write(monkeypatch):
    f = fixture(monkeypatch)
    p = f.owner.publish_current()
    f.s.now[0] = STAMP + 30
    original = f.owner.publication.read_publication

    def late(timeout):
        result = original(timeout)
        f.s.now[0] += 1
        return result

    f.owner.publication.read_publication = late
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError, match="REPLAY_OR_SOURCE_CUT_CHANGED"):
        f.owner.read_publication(0.2)
    assert f.s.s.files == frozen and p["revision"] == 1


def test_reentrant_publication_cannot_share_a_mutable_projection(monkeypatch):
    f = fixture(monkeypatch)
    frozen = copy.deepcopy(f.s.s.files)
    f.owner.publication.publish_scanner = lambda *args, **kwargs: (
        f.owner.publish_current()
    )
    with pytest.raises(ValueError, match="ALREADY_ACTIVE"):
        f.owner.publish_current()
    assert f.s.s.files == frozen


@pytest.mark.parametrize(
    "damage", ["domain", "source", "enrollment", "receipt", "binding"]
)
def test_new_input_cannot_adopt_foreign_or_unverified_prior_provenance(
    monkeypatch, damage
):
    f = fixture(monkeypatch)
    f.owner.publish_current()
    original = f.s.archive.read_evidence

    def damaged(head):
        result = original(head)
        evidence = result["sources"]["current_input"]
        if damage == "domain":
            evidence["input"]["execution_domain"] = "OPERATIONAL"
        elif damage == "source":
            evidence["input"]["source_id"] = "FOREIGN"
        elif damage == "enrollment":
            evidence["enrollment"] = "0" * 64
        elif damage == "receipt":
            evidence["acceptance"] = True
        else:
            evidence["acceptance"]["binding"] = "0" * 64
        return result

    monkeypatch.setattr(f.s.archive, "read_evidence", damaged)
    f.cut["input_revision"] += 1
    frozen = copy.deepcopy(f.s.s.files)
    with pytest.raises(ValueError):
        f.owner.publish_current()
    assert f.s.s.files == frozen


def test_fresh_successor_can_follow_expired_input_without_refreshing_old_evidence(
    monkeypatch,
):
    f = fixture(monkeypatch)
    first = f.owner.publish_current()
    original_files = copy.deepcopy(f.s.s.files)
    f.s.now[0] += 31
    with pytest.raises(ValueError):
        f.owner.read_publication(0.2)
    f.cut["input_revision"] += 1
    f.cut["observed_at"] = f.s.now[0]
    f.cut["quotes"]["MSFT"]["effective_timestamp"] = datetime.fromtimestamp(
        f.s.now[0], UTC
    ).isoformat()
    second = f.owner.publish_current()
    assert second["revision"] == 2 and first["observed_at"] == STAMP
    assert second["observed_at"] == STAMP + 31
    assert all(f.s.s.files[k] == v for k, v in original_files.items())


def test_free_source_bundle_and_real_readonly_scanner_reach_archive_as_no_entry(
    monkeypatch, tmp_path
):
    import asyncio

    from app.investment.free_research_providers import (
        FreeResearchBundle,
        read_only_ingest,
    )
    from app.investment.scan import InvestmentScanner
    from app.investment.scan_settings import ScanSettings
    from app.investment.universe import InvestmentUniverse
    from test_free_research_pipeline import (
        NOW,
        AssetType,
        UniverseEntry,
        bars,
        client,
        facts,
    )

    def response(url):
        if "/assets/" in url:
            return {
                "symbol": "MSFT",
                "id": "SYNTHETIC-ASSET",
                "class": "us_equity",
                "status": "active",
                "tradable": True,
                "fractionable": True,
                "exchange": "NASDAQ",
            }
        if "/bars?" in url:
            return bars()
        if "/calendar?" in url:
            return [{"date": "2026-10-28", "open": "09:30", "close": "16:00"}]
        if "company_tickers" in url:
            return {"0": {"cik_str": 789019, "ticker": "MSFT", "title": "Synthetic"}}
        return facts()

    c, _, calls, _ = client(tmp_path, response=response)
    bundle = FreeResearchBundle(client=c, now=lambda: NOW)
    universe = InvestmentUniverse([UniverseEntry("MSFT", asset_type=AssetType.STOCK)])
    scanner = InvestmentScanner(
        settings=ScanSettings(
            enabled=False,
            persist=False,
            notify_discord=False,
            inter_symbol_delay_seconds=0,
            max_retries=0,
        ),
        universe=universe,
        ingest=read_only_ingest(
            bundle=bundle, universe=universe, history_root=tmp_path / "history"
        ),
        history_root=tmp_path / "history",
        persist=False,
        research_only=True,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Financial or legacy record access forbidden")

    monkeypatch.setattr(scanner, "_paper_book", forbidden)
    monkeypatch.setattr(scanner, "_port", forbidden)
    result = asyncio.run(scanner.run_once(now=NOW))
    assert (
        result.evaluated == 1 and result.failed == 0 and int(NOW.timestamp()) == STAMP
    )
    f = fixture(monkeypatch)
    f.cut["rows"] = [result.observations[0].research.as_dict()]
    receipts = bundle.load("MSFT")["receipts"]
    f.cut["provenance"] = {"fixture_only": True, "free_source_receipts": receipts}
    f.refresh_observations()
    before_calls = len(calls)
    packet = f.owner.publish_current()
    record = f.s.archive.read_evidence(f.s.archive.current())
    assert packet["bundles"] == []
    assert (
        record["sources"]["current_input"]["input"]["provenance"][
            "free_source_receipts"
        ]
        == receipts
    )
    assert len(calls) == before_calls == 6
    assert not (tmp_path / "history").exists()
