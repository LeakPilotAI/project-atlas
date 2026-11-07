from datetime import UTC, datetime, timedelta

import pytest

from app.services.personal_paper_strategy_signal import evaluate_iex_quality_dips_signal

NOW = datetime(2026, 11, 6, 20, tzinfo=UTC)


def quote(price="80"):
    return {"symbol": "MSFT", "state": "FRESH", "bid": price, "ask": price,
            "bid_lots": 2, "ask_lots": 2, "timestamp": NOW.isoformat(),
            "timestamp_basis": "PROVIDER_EVENT_TIMESTAMP"}


def research():
    return {"symbol": "MSFT", "source_verified": True, "timestamp": NOW.isoformat(),
            "normalization_value": {"conservative": 95, "base": 100, "optimistic": 105},
            "quality_score": 80, "fundamentals_score": 80,
            "valuation_score": 70, "drawdown_percentile": 80,
            "evidence_quality": "HIGH", "thesis": "INTACT", "value_trap": False}


def test_recomputed_signal_uses_provider_ask_not_caller_eligibility():
    result = evaluate_iex_quality_dips_signal(quote=quote(), symbol="MSFT", now=NOW,
                                               research={**research(), "paper_execution_eligible": True,
                                                         "classification": "GENERATIONAL"})
    assert result["candidate"] is True
    assert result["plan"]["patient_state"] == "ACCUMULATION"
    assert result["paper_fill_authorized"] is False
    assert result["research_provenance_attested"] is False
    assert "L1" in result["reached_levels"]


def test_recomputed_signal_refuses_unverified_or_stale_research():
    with pytest.raises(ValueError, match="PROVENANCE_UNVERIFIED"):
        evaluate_iex_quality_dips_signal(quote=quote(), symbol="MSFT", now=NOW,
                                          research={**research(), "source_verified": False})
    with pytest.raises(ValueError, match="STALE_OR_FUTURE"):
        evaluate_iex_quality_dips_signal(quote=quote(), symbol="MSFT", now=NOW,
                                          research={**research(), "timestamp":
                                                    (NOW - timedelta(days=2)).isoformat()})


def test_recomputed_signal_not_candidate_when_ask_above_ladder():
    result = evaluate_iex_quality_dips_signal(quote=quote("101"), symbol="MSFT", now=NOW,
                                               research=research())
    assert result["candidate"] is False
    assert result["paper_fill_authorized"] is False


def test_leased_v3_refuses_fake_provider_and_missing_operator():
    from app.investment.alpaca_iex import IEXFeed
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import inspect_leased_iex_v3_candidate
    feed = IEXFeed(["MSFT"], clock=lambda: NOW.timestamp())
    with pytest.raises(ValueError, match="LEASED_IEX_V3_DEPENDENCIES_REQUIRED"):
        inspect_leased_iex_v3_candidate(
            installation=object(), request={"action": "AUTO_PAPER"}, components=(),
            provider=object(), symbol="MSFT", now=NOW, research=research())
    with pytest.raises(ValueError, match="LEASED_IEX_V3_DEPENDENCIES_REQUIRED"):
        inspect_leased_iex_v3_candidate(
            installation=None, request={"action": "AUTO_PAPER"}, components=(),
            provider=PersonalPaperIEXProvider(feed), symbol="MSFT", now=NOW,
            research=research())
    with pytest.raises(ValueError, match="LEASED_IEX_V3_DEPENDENCIES_REQUIRED"):
        inspect_leased_iex_v3_candidate(
            installation=object(), request={"action": "READ_ONLY"}, components=(),
            provider=PersonalPaperIEXProvider(feed), symbol="MSFT", now=NOW,
            research=research())


def test_published_research_rejects_untrusted_caller_source():
    from app.services.personal_paper_strategy_signal import inspect_published_quality_dips_research
    class FakePublication:
        def read_current(self):
            return {"schema": "QD_SCANNER_PUBLICATION_V1", "source_id": "forged",
                    "revision": 1, "bundles": [{"instrument": {"symbol": "MSFT"},
                                              "board": [research()]}]}
    with pytest.raises(ValueError, match="QD_PUBLISHED_RESEARCH_DEPENDENCIES_REQUIRED"):
        inspect_published_quality_dips_research(publication=FakePublication(),
                                                symbol="MSFT", research=research())
    with pytest.raises(ValueError, match="QD_PUBLISHED_RESEARCH_DEPENDENCIES_REQUIRED"):
        inspect_published_quality_dips_research(publication=None,
                                                symbol="MSFT", research=research())


def test_published_research_matching_duplicate_board_copies_and_conflicts(monkeypatch):
    """Synthetic packet shape only; patched reader is not source authentication."""
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from app.services.personal_paper_strategy_signal import inspect_published_quality_dips_research
    publication = object.__new__(QualityDipsSourcePublication)
    row = research()
    observation = {"symbol": "MSFT", "strategy_version": "QUALITY_DIPS_V3",
                   "evidence_class": "FORWARD_COLLECTION"}
    bundle = {"instrument": {"symbol": "MSFT"}, "observation": observation,
              "board": [row]}
    packet = {"schema": "QD_SCANNER_PUBLICATION_V1", "source_id": "synthetic",
              "revision": 3, "bundles": [bundle, bundle]}
    monkeypatch.setattr(QualityDipsSourcePublication, "read_current", lambda self: packet)
    matched = inspect_published_quality_dips_research(publication=publication,
                                                       symbol="MSFT", research=row)
    assert matched["publication_read_verified"] is True
    assert matched["paper_fill_authorized"] is False
    packet["bundles"] = [bundle, {**bundle, "board": [{**row, "quality_score": 1}]}]
    with pytest.raises(ValueError, match="CONTENT_NOT_BOUND"):
        inspect_published_quality_dips_research(publication=publication,
                                                symbol="MSFT", research=row)
    packet["bundles"] = [{**bundle, "observation": {**observation, "symbol": "AVGO"}}]
    with pytest.raises(ValueError, match="OBSERVATION_MISMATCH"):
        inspect_published_quality_dips_research(publication=publication,
                                                symbol="MSFT", research=row)


def test_published_iex_candidate_refuses_forged_publication_and_provider():
    from app.investment.alpaca_iex import IEXFeed
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import evaluate_published_iex_v3_candidate
    feed = IEXFeed(["MSFT"], clock=lambda: NOW.timestamp())
    provider = PersonalPaperIEXProvider(feed)
    with pytest.raises(ValueError, match="QD_PUBLISHED_IEX_BOUND_PORTS_REQUIRED"):
        evaluate_published_iex_v3_candidate(publication=object(), provider=provider,
                                            symbol="MSFT", now=NOW)
    with pytest.raises(ValueError, match="QD_PUBLISHED_IEX_BOUND_PORTS_REQUIRED"):
        evaluate_published_iex_v3_candidate(publication=None, provider=object(),
                                            symbol="MSFT", now=NOW)


def test_published_iex_candidate_recomputes_board_inputs_without_fill_authority(monkeypatch):
    """Synthetic adapter ports: this does not certify actual source or feed."""
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import evaluate_published_iex_v3_candidate
    pub = object.__new__(QualityDipsSourcePublication)
    provider = object.__new__(PersonalPaperIEXProvider)
    row = {"symbol": "MSFT", "timestamp": NOW.isoformat(), "blockers": [],
           "missing_critical": [], "quality_dips_v2": {
               "missing_v2_evidence": [], "decision_inputs": {
                   "symbol": "MSFT", "normalization_value": research()["normalization_value"],
                   "quality_score": 80, "fundamentals_score": 80,
                   "valuation_score": 70, "drawdown_percentile": 80,
                   "evidence_quality": "HIGH", "thesis_intact": True,
                   "value_trap": False}}}
    bundle = {"instrument": {"symbol": "MSFT"}, "board": [row],
              "observation": {"symbol": "MSFT", "strategy_version": "QUALITY_DIPS_V3",
                              "evidence_class": "FORWARD_COLLECTION", "timestamp": NOW.isoformat()}}
    packet = {"schema": "QD_SCANNER_PUBLICATION_V1", "source_id": "fixture",
              "revision": 2, "bundles": [bundle, bundle]}
    monkeypatch.setattr(QualityDipsSourcePublication, "read_current", lambda self: packet)
    monkeypatch.setattr(PersonalPaperIEXProvider, "read_iex_quote", lambda self, symbol: quote())
    candidate = evaluate_published_iex_v3_candidate(publication=pub, provider=provider,
                                                    symbol="MSFT", now=NOW)
    assert candidate["candidate"] is True
    assert candidate["paper_fill_authorized"] is False
    assert candidate["research_provenance_attested"] is False
    packet["bundles"] = [bundle, {**bundle, "board": [{**row, "timestamp":
                                                          (NOW - timedelta(days=2)).isoformat()}]}]
    with pytest.raises(ValueError, match="MISSING_OR_CONFLICTING"):
        evaluate_published_iex_v3_candidate(publication=pub, provider=provider,
                                            symbol="MSFT", now=NOW)


def test_leased_published_iex_candidate_checks_lease_and_refuses_changed_components(monkeypatch):
    """Synthetic operator lease and source are not real activation evidence."""
    from contextlib import contextmanager
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services import personal_paper_strategy_signal as signals
    publication = object.__new__(QualityDipsSourcePublication)
    provider = object.__new__(PersonalPaperIEXProvider)
    class Lease:
        def __init__(self):
            self.valid = True
        def check_components(self, components):
            return self.valid
        def check(self, proof):
            return self.valid
    class Installation:
        def __init__(self):
            self.lease_obj = Lease()
        @contextmanager
        def lease(self, request):
            yield self.lease_obj
    installation = Installation()
    monkeypatch.setattr("app.services.personal_paper_runtime.checked_personal_installation",
                        lambda lease, request: {"fixture": True})
    monkeypatch.setattr(signals, "evaluate_published_iex_v3_candidate",
                        lambda **kwargs: {"candidate": True, "paper_fill_authorized": False})
    result = signals.inspect_leased_published_iex_v3_candidate(
        installation=installation, request={"action": "AUTO_PAPER"}, components=(),
        publication=publication, provider=provider, symbol="MSFT", now=NOW)
    assert result["operator_lease_checked"] is True
    assert result["paper_fill_authorized"] is False
    installation.lease_obj.valid = False
    with pytest.raises(ValueError, match="COMPONENTS_CHANGED"):
        signals.inspect_leased_published_iex_v3_candidate(
            installation=installation, request={"action": "AUTO_PAPER"}, components=(),
            publication=publication, provider=provider, symbol="MSFT", now=NOW)
    with pytest.raises(ValueError, match="DEPENDENCIES_REQUIRED"):
        signals.inspect_leased_published_iex_v3_candidate(
            installation=installation, request={"action": "READ_ONLY"}, components=(),
            publication=publication, provider=provider, symbol="MSFT", now=NOW)


def test_leased_published_journal_candidate_refuses_uninitialized_or_fake_ports(tmp_path):
    from app.investment.alpaca_iex import IEXFeed
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from app.services.personal_paper_strategy_signal import inspect_leased_published_iex_journal_candidate
    provider = PersonalPaperIEXProvider(IEXFeed(["MSFT"], clock=lambda: NOW.timestamp()))
    publication = object.__new__(QualityDipsSourcePublication)
    kwargs = dict(installation=object(), request={"action": "AUTO_PAPER"},
                  components=(), publication=publication, provider=provider,
                  symbol="MSFT", now=NOW, account_id="fixture",
                  journal_path=tmp_path / "missing.jsonl")
    with pytest.raises(ValueError, match="NOT_INITIALIZED"):
        inspect_leased_published_iex_journal_candidate(**kwargs)
    with pytest.raises(ValueError, match="DEPENDENCIES_REQUIRED"):
        inspect_leased_published_iex_journal_candidate(**{**kwargs, "publication": object()})
    with pytest.raises(ValueError, match="DEPENDENCIES_REQUIRED"):
        inspect_leased_published_iex_journal_candidate(**{**kwargs, "request": {"action": "READ_ONLY"}})


def test_leased_published_journal_candidate_positive_replay_and_revocation(tmp_path, monkeypatch):
    """Disposable positive composition, not operational source acceptance."""
    from contextlib import contextmanager
    from app.investment.quality_dips_paper import initialize_paper_account, read_events
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services import personal_paper_strategy_signal as signals
    path = tmp_path / "isolated-forward.jsonl"
    initialize_paper_account(account_id="fixture-forward", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="FORWARD_COLLECTION", path=path)
    original = path.read_bytes()
    publication = object.__new__(QualityDipsSourcePublication)
    provider = object.__new__(PersonalPaperIEXProvider)
    class Lease:
        valid = True
        def check_components(self, components):
            return self.valid
        def check(self, proof):
            return self.valid
    class Installation:
        def __init__(self):
            self.active = Lease()
        @contextmanager
        def lease(self, request):
            yield self.active
    installation = Installation()
    monkeypatch.setattr("app.services.personal_paper_runtime.checked_personal_installation",
                        lambda lease, request: {"synthetic": True})
    monkeypatch.setattr(signals, "evaluate_published_iex_v3_candidate",
                        lambda **kwargs: {"candidate": True, "paper_fill_authorized": False})
    kwargs = dict(installation=installation, request={"action": "AUTO_PAPER"},
                  components=(), publication=publication, provider=provider,
                  symbol="MSFT", now=NOW, journal_path=path,
                  account_id="fixture-forward")
    result = signals.inspect_leased_published_iex_journal_candidate(**kwargs)
    assert result["journal_cash_reconciled"] is True
    assert result["journal_open_positions"] == 0
    assert result["journal_available_cash"] == 1000
    assert result["journal_writer_lock_checked"] is True
    assert result["paper_fill_authorized"] is False
    assert path.read_bytes() == original
    assert len(read_events(path)) == 1
    installation.active.valid = False
    with pytest.raises(ValueError, match="COMPONENTS_CHANGED"):
        signals.inspect_leased_published_iex_journal_candidate(**kwargs)
    assert path.read_bytes() == original


def test_published_iex_v3_with_original_scanner_publication_and_revocation(tmp_path, monkeypatch):
    """Exercise actual publication implementation with explicitly synthetic custody."""
    import copy
    from types import SimpleNamespace
    from test_paper_source_publication import Archive, auth
    from test_quality_dips_autonomous_paper import candidate, setup
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import evaluate_published_iex_v3_candidate
    n = setup(tmp_path)
    b = candidate(n)
    authority = auth()
    raw = {"board": b["board"],
           "observations": {b["instrument"]["symbol"]: b["observation"]},
           "instruments": [b["instrument"]],
           "quotes": {b["instrument"]["symbol"]: b["quote"]},
           "publication": b["publication"], "monitors": {}}
    publication = QualityDipsSourcePublication(
        research=SimpleNamespace(read_current=lambda: copy.deepcopy(raw)),
        candidates=n.engine.candidates, source_id="SYNTHETIC_QD_ORIGINAL",
        authority=authority, archive=Archive(), clock=lambda: n.now[0])
    publication.publish_scanner(b["board"], datetime.fromtimestamp(n.now[0], UTC).isoformat())
    provider = object.__new__(PersonalPaperIEXProvider)
    symbol = b["instrument"]["symbol"]
    monkeypatch.setattr(PersonalPaperIEXProvider, "read_iex_quote",
                        lambda self, requested: {**quote(), "symbol": requested,
                                                  "timestamp": datetime.fromtimestamp(n.now[0], UTC).isoformat()})
    now = datetime.fromtimestamp(n.now[0], UTC)
    # Original scanner fixture has only a frozen V3 plan, not the full
    # decision_inputs needed to recompute against the current IEX ask.
    # Refuse rather than reuse an old classification as fill authority.
    with pytest.raises(ValueError, match="V3_EVIDENCE_INCOMPLETE"):
        evaluate_published_iex_v3_candidate(
            publication=publication, provider=provider, symbol=symbol, now=now)
    authority.valid = False
    with pytest.raises(ValueError):
        evaluate_published_iex_v3_candidate(
            publication=publication, provider=provider, symbol=symbol, now=now)


def test_real_explicit_projection_maps_to_iex_v3_using_observation_timestamp(monkeypatch):
    """Real pure projection, synthetic publication reader and IEX quote."""
    from app.services.quality_dips_research_only import project_explicit_research
    from test_quality_dips_v2_board import _row
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import evaluate_published_iex_v3_candidate
    source = _row()
    source.update(symbol="MSFT", asset_type="STOCK", timestamp=NOW.isoformat())
    source["trend"]["as_of"] = NOW.isoformat()
    for valuation in source["valuation_sources"]:
        valuation["as_of"] = NOW.isoformat()
    board = project_explicit_research([source], now=NOW)
    assert board[0]["timestamp"] == NOW.isoformat()
    assert board[0]["quality_dips_v2"]["decision_inputs"]["symbol"] == "MSFT"
    packet = {"schema": "QD_SCANNER_PUBLICATION_V1", "source_id": "fixture",
              "revision": 1, "bundles": [{"instrument": {"symbol": "MSFT"},
              "board": board, "observation": {"symbol": "MSFT",
              "strategy_version": "QUALITY_DIPS_V3", "evidence_class": "FORWARD_COLLECTION",
              "timestamp": NOW.isoformat()}}]}
    publication = object.__new__(QualityDipsSourcePublication)
    provider = object.__new__(PersonalPaperIEXProvider)
    monkeypatch.setattr(QualityDipsSourcePublication, "read_current", lambda self: packet)
    monkeypatch.setattr(PersonalPaperIEXProvider, "read_iex_quote", lambda self, symbol: quote())
    result = evaluate_published_iex_v3_candidate(publication=publication,
                                                 provider=provider, symbol="MSFT", now=NOW)
    assert result["publication_read_verified"] is True
    assert result["paper_fill_authorized"] is False
    packet["bundles"][0]["observation"]["timestamp"] = (NOW - timedelta(hours=1)).isoformat()
    with pytest.raises(ValueError, match="BOARD_OBSERVATION_TIME_MISMATCH"):
        evaluate_published_iex_v3_candidate(publication=publication,
                                            provider=provider, symbol="MSFT", now=NOW)


def test_original_current_producer_publication_to_iex_v3_and_authority_refusal(monkeypatch):
    """Real source producer, native disposable archive and publication reader.

    The IEX quote is a synthetic port; this is not live provider acceptance.
    """
    from test_quality_dips_current_producer import fixture, STAMP
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import evaluate_published_iex_v3_candidate
    f = fixture(monkeypatch)
    f.owner.publish_current()
    publication = f.owner.publication
    provider = object.__new__(PersonalPaperIEXProvider)
    now = datetime.fromtimestamp(STAMP, UTC)
    monkeypatch.setattr(PersonalPaperIEXProvider, "read_iex_quote",
                        lambda self, symbol: {**quote(), "symbol": symbol,
                                              "timestamp": now.isoformat()})
    result = evaluate_published_iex_v3_candidate(
        publication=publication, provider=provider, symbol="MSFT", now=now)
    assert result["publication_read_verified"] is True
    assert result["published_revision"] == 1
    assert result["paper_fill_authorized"] is False
    assert result["research_provenance_attested"] is False
    f.s.auth.valid = False
    with pytest.raises(ValueError):
        evaluate_published_iex_v3_candidate(
            publication=publication, provider=provider, symbol="MSFT", now=now)


def test_original_producer_with_real_iex_feed_adapter_and_disposable_journal(tmp_path, monkeypatch):
    """Original producer + feed snapshot adapter + journal, synthetic auth only."""
    from contextlib import contextmanager
    from test_quality_dips_current_producer import fixture, STAMP
    from app.investment.alpaca_iex import IEXFeed
    from app.investment.quality_dips_paper import initialize_paper_account
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import inspect_leased_published_iex_journal_candidate
    f = fixture(monkeypatch)
    f.owner.publish_current()
    now = datetime.fromtimestamp(STAMP, UTC)
    feed = IEXFeed(["MSFT"], clock=lambda: now.timestamp())
    feed.authenticated = feed.subscribed = True  # Explicit synthetic fixture state
    feed.connection = "CONNECTED"
    feed.quotes["MSFT"] = {"symbol": "MSFT", "bid": "79.99", "ask": "80",
                           "bid_lots": 2, "ask_lots": 2, "timestamp": now.isoformat(),
                           "source_timestamp": now.timestamp(), "generation": feed.generation}
    provider = PersonalPaperIEXProvider(feed)
    path = tmp_path / "forward.jsonl"
    initialize_paper_account(account_id="fixture-forward", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="FORWARD_COLLECTION", path=path)
    original = path.read_bytes()
    class Lease:
        valid = True
        def check(self, proof):
            return self.valid
        def check_components(self, components):
            return self.valid
    class Installation:
        @contextmanager
        def lease(self, request):
            yield lease
    lease = Lease()
    monkeypatch.setattr("app.services.personal_paper_runtime.checked_personal_installation",
                        lambda active, request: {"synthetic": True})
    kwargs = dict(installation=Installation(), request={"action": "AUTO_PAPER"},
                  components=(), publication=f.owner.publication, provider=provider,
                  symbol="MSFT", now=now, journal_path=path,
                  account_id="fixture-forward")
    result = inspect_leased_published_iex_journal_candidate(**kwargs)
    assert result["publication_read_verified"] is True
    assert result["journal_cash_reconciled"] is True
    assert result["journal_available_cash"] == 1000
    assert result["paper_fill_authorized"] is False
    assert path.read_bytes() == original
    feed.connection = "DISCONNECTED"
    with pytest.raises(ValueError, match="AUTHENTICATED_IEX_FEED_UNAVAILABLE"):
        inspect_leased_published_iex_journal_candidate(**kwargs)
    assert path.read_bytes() == original


def test_published_iex_v3_refuses_mutated_same_reference_and_missing_evidence(monkeypatch):
    """A mutable reused publication object cannot conceal mid-quote changes."""
    from app.services.quality_dips_research_only import project_explicit_research
    from test_quality_dips_v2_board import _row
    from app.services.paper_source_publication import QualityDipsSourcePublication
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import evaluate_published_iex_v3_candidate
    row = _row()
    row.update(symbol="MSFT", asset_type="STOCK", timestamp=NOW.isoformat())
    row["trend"]["as_of"] = NOW.isoformat()
    for valuation in row["valuation_sources"]:
        valuation["as_of"] = NOW.isoformat()
    board = project_explicit_research([row], now=NOW)
    packet = {"schema": "QD_SCANNER_PUBLICATION_V1", "source_id": "fixture",
              "revision": 1, "bundles": [{"instrument": {"symbol": "MSFT"},
              "board": board, "observation": {"symbol": "MSFT",
              "strategy_version": "QUALITY_DIPS_V3", "evidence_class": "FORWARD_COLLECTION",
              "timestamp": NOW.isoformat()}}]}
    publication = object.__new__(QualityDipsSourcePublication)
    provider = object.__new__(PersonalPaperIEXProvider)
    monkeypatch.setattr(QualityDipsSourcePublication, "read_current", lambda self: packet)
    def mutate_on_quote(self, symbol):
        packet["revision"] += 1
        return quote()
    monkeypatch.setattr(PersonalPaperIEXProvider, "read_iex_quote", mutate_on_quote)
    with pytest.raises(ValueError, match="SOURCE_CHANGED"):
        evaluate_published_iex_v3_candidate(publication=publication,
                                            provider=provider, symbol="MSFT", now=NOW)
    packet["revision"] = 1
    packet["bundles"][0]["board"][0]["quality_dips_v2"].pop("missing_v2_evidence", None)
    with pytest.raises(ValueError, match="V3_EVIDENCE_INCOMPLETE"):
        evaluate_published_iex_v3_candidate(publication=publication,
                                            provider=provider, symbol="MSFT", now=NOW)


def test_original_producer_real_operator_installation_iex_adapter_and_journal(tmp_path, monkeypatch):
    """Use the real lease validator, not a duck-typed synthetic lease."""
    from test_quality_dips_current_producer import fixture, STAMP
    from test_personal_paper_runtime import installed
    from app.investment.alpaca_iex import IEXFeed
    from app.investment.quality_dips_paper import initialize_paper_account
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import inspect_leased_published_iex_journal_candidate
    f = fixture(monkeypatch)
    f.owner.publish_current()
    now = datetime.fromtimestamp(STAMP, UTC)
    feed = IEXFeed(["MSFT"], clock=lambda: now.timestamp())
    feed.authenticated = feed.subscribed = True  # Simulated socket status, not live auth
    feed.connection = "CONNECTED"
    feed.quotes["MSFT"] = {"symbol": "MSFT", "bid": "79.99", "ask": "80",
                           "bid_lots": 2, "ask_lots": 2, "timestamp": now.isoformat(),
                           "source_timestamp": now.timestamp(), "generation": feed.generation}
    provider = PersonalPaperIEXProvider(feed)
    path = tmp_path / "forward.jsonl"
    initialize_paper_account(account_id="fixture-forward", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="FORWARD_COLLECTION", path=path)
    before = path.read_bytes()
    s = installed()
    request = {"action": "AUTO_PAPER"}
    kwargs = dict(installation=s.i, request=request, components={"port": s.reader},
                  publication=f.owner.publication, provider=provider, symbol="MSFT",
                  now=now, journal_path=path, account_id="fixture-forward")
    result = inspect_leased_published_iex_journal_candidate(**kwargs)
    assert result["operator_lease_checked"] is True
    assert result["journal_cash_reconciled"] is True
    assert result["paper_fill_authorized"] is False
    assert path.read_bytes() == before
    s.i.revoke()
    with pytest.raises(ValueError, match="ACTIVATION_REVOKED"):
        inspect_leased_published_iex_journal_candidate(**kwargs)
    assert path.read_bytes() == before


def test_leased_published_tick_planner_no_fill_and_existing_position(tmp_path, monkeypatch):
    """The new tick planner consumes the real integrated read-only lease path."""
    from test_quality_dips_current_producer import fixture, STAMP
    from test_personal_paper_runtime import installed
    from app.investment.alpaca_iex import IEXFeed
    from app.investment.quality_dips_paper import initialize_paper_account, open_lot, close_lot
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import plan_leased_published_iex_paper_tick
    f = fixture(monkeypatch)
    f.owner.publish_current()
    now = datetime.fromtimestamp(STAMP, UTC)
    feed = IEXFeed(["MSFT"], clock=lambda: now.timestamp())
    feed.authenticated = feed.subscribed = True
    feed.connection = "CONNECTED"
    feed.quotes["MSFT"] = {"symbol": "MSFT", "bid": "79.99", "ask": "80",
                           "bid_lots": 5, "ask_lots": 5, "timestamp": now.isoformat(),
                           "source_timestamp": now.timestamp(), "generation": feed.generation}
    path = tmp_path / "forward.jsonl"
    initialize_paper_account(account_id="fixture-forward", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="FORWARD_COLLECTION", path=path)
    operator = installed()
    kwargs = dict(installation=operator.i, request={"action": "AUTO_PAPER"},
                  components={"port": operator.reader}, publication=f.owner.publication,
                  provider=PersonalPaperIEXProvider(feed), symbol="MSFT", now=now,
                  journal_path=path, account_id="fixture-forward")
    before = path.read_bytes()
    result = plan_leased_published_iex_paper_tick(**kwargs)
    assert result["state"] in {"WAIT_NO_SIGNAL", "CANDIDATE_UNAUTHORIZED"}
    assert result["paper_fill_authorized"] is False
    assert result["estimated_liquidation_equity"] == 1000
    assert result["estimated_total_return"] == 0
    assert len(result["decision_evidence_digest"]) == 64
    assert result["provider_timestamp"] == now.isoformat()
    assert plan_leased_published_iex_paper_tick(**kwargs)["decision_evidence_digest"] == result["decision_evidence_digest"]
    assert path.read_bytes() == before
    plan_before_digest = result["decision_evidence_digest"]
    open_lot(f.cut["observations"]["MSFT"], level="L1", paper_notional_dollars=50,
             fill_price=80, account_id="fixture-forward", fee_bps_per_side=2, path=path)
    before = path.read_bytes()
    result = plan_leased_published_iex_paper_tick(**kwargs)
    assert result["state"] == "WAIT_EXISTING_POSITION"
    assert result["decision_evidence_digest"] != plan_before_digest
    assert result["open_positions"] == 1
    assert len(result["position_marks"]) == 1
    assert result["position_marks"][0]["bid"] == "79.99"
    assert result["position_marks"][0]["unrealized_net_pnl_estimate"] < 0
    assert result["estimated_liquidation_equity"] < 1000
    assert result["estimated_total_return"] < 0
    assert abs(result["estimated_total_return"] - result["position_marks"][0]["unrealized_net_pnl_estimate"]) < 0.000001
    assert path.read_bytes() == before
    from app.investment.quality_dips_paper import open_lots, read_events
    lot_id = open_lots(read_events(path))[0]["lot_id"]
    close_lot(lot_id, exit_price=82, reason="SYNTHETIC_TEST_ONLY", path=path)
    before = path.read_bytes()
    closed = plan_leased_published_iex_paper_tick(**kwargs)
    assert closed["open_positions"] == 0
    assert closed["decision_evidence_digest"] != result["decision_evidence_digest"]
    assert closed["estimated_liquidation_equity"] > 1000
    assert closed["estimated_total_return"] > 0
    assert path.read_bytes() == before
    operator.i.revoke()
    with pytest.raises(ValueError, match="ACTIVATION_REVOKED"):
        plan_leased_published_iex_paper_tick(**kwargs)


def test_bounded_readonly_session_refuses_invalid_clock_and_stops_on_failure(monkeypatch):
    from datetime import timedelta
    import app.services.personal_paper_strategy_signal as signals
    from app.services.personal_paper_strategy_signal import run_bounded_readonly_paper_session
    now = datetime(2026, 11, 6, tzinfo=UTC)
    calls = []
    def tick(*, now, **kwargs):
        calls.append(now)
        if len(calls) == 3:
            raise ValueError("AUTHENTICATED_IEX_FEED_UNAVAILABLE")
        return {"paper_fill_authorized": False, "live_order_authorized": False,
                "provider_timestamp": now.isoformat(),
                "decision_evidence_digest": str(len(calls))}
    monkeypatch.setattr(signals, "plan_leased_published_iex_paper_tick", tick)
    monkeypatch.setattr(signals, "propose_forward_paper_action",
                        lambda *, plan: {"paper_fill_authorized": False, "action": "WAIT"})
    stamps = iter([now, now + timedelta(seconds=1), now + timedelta(seconds=2)])
    with pytest.raises(ValueError, match="AUTHENTICATED_IEX_FEED_UNAVAILABLE"):
        run_bounded_readonly_paper_session(ticks=3, clock=lambda: next(stamps))
    assert len(calls) == 3
    calls.clear()
    stamps = iter([now, now + timedelta(seconds=1)])
    result = run_bounded_readonly_paper_session(ticks=2, clock=lambda: next(stamps))
    assert result["completed"] == 2
    assert result["paper_fill_authorized"] is False
    assert result["ticks"][0]["plan"]["decision_evidence_digest"] == "1"
    calls.clear()
    with pytest.raises(ValueError, match="PAPER_SESSION_NONMONOTONIC_CLOCK"):
        run_bounded_readonly_paper_session(ticks=2, clock=lambda: now)
    with pytest.raises(ValueError, match="PAPER_SESSION_BOUNDED_EXPLICIT_CLOCK_REQUIRED"):
        run_bounded_readonly_paper_session(ticks=31, clock=lambda: now)


def test_bounded_session_refuses_replayed_quote_event(monkeypatch):
    from datetime import timedelta
    import app.services.personal_paper_strategy_signal as signals
    from app.services.personal_paper_strategy_signal import run_bounded_readonly_paper_session
    start = datetime(2026, 11, 6, tzinfo=UTC)
    def frozen(*, now, **kwargs):
        return {"paper_fill_authorized": False, "live_order_authorized": False,
                "provider_timestamp": start.isoformat()}
    monkeypatch.setattr(signals, "plan_leased_published_iex_paper_tick", frozen)
    monkeypatch.setattr(signals, "propose_forward_paper_action",
                        lambda *, plan: {"paper_fill_authorized": False, "action": "WAIT"})
    stamps = iter([start, start + timedelta(seconds=1)])
    with pytest.raises(ValueError, match="PAPER_SESSION_PROVIDER_EVENT_NOT_ADVANCING"):
        run_bounded_readonly_paper_session(ticks=2, clock=lambda: next(stamps))
    with pytest.raises(ValueError, match="PAPER_SESSION_PROVIDER_EVENT_NOT_FRESH"):
        run_bounded_readonly_paper_session(ticks=1, clock=lambda: start + timedelta(seconds=16))


def test_bounded_session_original_source_real_lease_feed_and_journal(tmp_path, monkeypatch):
    """Multi-tick composition uses real installed ports, not a patched tick."""
    from datetime import timedelta
    from test_quality_dips_current_producer import fixture, STAMP
    from test_personal_paper_runtime import installed
    from app.investment.alpaca_iex import IEXFeed
    from app.investment.quality_dips_paper import initialize_paper_account
    from app.services.personal_paper_iex_provider import PersonalPaperIEXProvider
    from app.services.personal_paper_strategy_signal import run_bounded_readonly_paper_session
    f = fixture(monkeypatch)
    f.owner.publish_current()
    start = datetime.fromtimestamp(STAMP, UTC)
    feed = IEXFeed(["MSFT"], clock=lambda: now[0].timestamp())
    feed.authenticated = feed.subscribed = True  # Synthetic test state only.
    feed.connection = "CONNECTED"
    now = [start]
    path = tmp_path / "session.jsonl"
    initialize_paper_account(account_id="session-test", opening_cash=1000,
                             fee_bps_per_side=2, max_open_positions=1,
                             data_provenance="FORWARD_COLLECTION", path=path)
    operator = installed()
    def clock():
        stamp = start + timedelta(seconds=clock.count)
        clock.count += 1
        now[0] = stamp
        feed.quotes["MSFT"] = {"symbol": "MSFT", "bid": "79.99", "ask": "80",
                               "bid_lots": 5, "ask_lots": 5,
                               "timestamp": stamp.isoformat(),
                               "source_timestamp": stamp.timestamp(),
                               "generation": feed.generation}
        return stamp
    clock.count = 0
    kwargs = dict(installation=operator.i, request={"action": "AUTO_PAPER"},
                  components={"port": operator.reader}, publication=f.owner.publication,
                  provider=PersonalPaperIEXProvider(feed), symbol="MSFT",
                  journal_path=path, account_id="session-test")
    before = path.read_bytes()
    result = run_bounded_readonly_paper_session(ticks=2, clock=clock, **kwargs)
    assert result["completed"] == 2
    assert result["ticks"][0]["proposal"]["paper_fill_authorized"] is False
    assert result["ticks"][0]["proposal"]["action"] in ("WAIT", "PROPOSE_ENTRY")
    assert result["ticks"][0]["plan"]["provider_timestamp"] != result["ticks"][1]["plan"]["provider_timestamp"]
    assert result["ticks"][0]["plan"]["estimated_liquidation_equity"] == 1000
    assert path.read_bytes() == before
    def revoke_during_session():
        stamp = clock()
        if clock.count == 4:
            operator.i.revoke()
        return stamp
    with pytest.raises(ValueError, match="ACTIVATION_REVOKED"):
        run_bounded_readonly_paper_session(ticks=3, clock=revoke_during_session, **kwargs)
    assert clock.count == 4  # Two accepted ticks, then refusal at tick two of next run.
    assert path.read_bytes() == before


def test_forward_action_proposal_is_capacity_bounded_and_never_authorizes_fills():
    from app.services.personal_paper_strategy_signal import propose_forward_paper_action
    base = {"schema": "ATLAS_PERSONAL_PAPER_TICK_PLAN_V1", "symbol": "MSFT",
            "account_id": "paper", "decision_evidence_digest": "a" * 64,
            "paper_fill_authorized": False, "live_order_authorized": False,
            "state": "CANDIDATE_UNAUTHORIZED", "candidate": True,
            "open_positions": 0, "available_cash": 1000}
    proposal = propose_forward_paper_action(plan=base)
    assert proposal["action"] == "PROPOSE_ENTRY"
    assert proposal["max_simulated_notional"] == 100
    assert proposal["paper_fill_authorized"] is False
    assert propose_forward_paper_action(plan={**base, "available_cash": 25})["max_simulated_notional"] < 25
    assert propose_forward_paper_action(plan={**base, "available_cash": 0})["action"] == "WAIT"
    assert propose_forward_paper_action(plan={**base, "state": "WAIT_NO_SIGNAL", "candidate": False})["action"] == "WAIT"
    assert propose_forward_paper_action(plan={**base, "state": "WAIT_EXISTING_POSITION", "open_positions": 1})["action"] == "WAIT"
    for invalid in ({"paper_fill_authorized": True}, {"live_order_authorized": True},
                    {"decision_evidence_digest": "spoof"}, {"available_cash": -1},
                    {"state": "CANDIDATE_UNAUTHORIZED", "candidate": False},
                    {"state": "WAIT_EXISTING_POSITION", "open_positions": 0}):
        with pytest.raises(ValueError):
            propose_forward_paper_action(plan={**base, **invalid})
    with pytest.raises(ValueError, match="CAPACITY_INVALID"):
        propose_forward_paper_action(plan=base, max_notional=101)


def test_forward_activation_preflight_never_promotes_structural_evidence(tmp_path):
    from app.services.personal_paper_strategy_signal import assess_forward_paper_activation_readiness
    from app.investment.quality_dips_paper import initialize_paper_account
    path = tmp_path / "forward.jsonl"
    args = dict(installation=None, publication=None, provider=None,
                journal_path=path, account_id="forward")
    missing = assess_forward_paper_activation_readiness(**args)
    assert "PAPER_JOURNAL_NOT_INITIALIZED" in missing["blockers"]
    assert missing["ready"] is False
    initialize_paper_account(account_id="forward", opening_cash=1000,
                             fee_bps_per_side=2, data_provenance="FORWARD_COLLECTION", path=path)
    before = path.read_bytes()
    accepted = assess_forward_paper_activation_readiness(**args)
    assert "PAPER_JOURNAL_NOT_INITIALIZED" not in accepted["blockers"]
    assert "AUTHENTICATED_IEX_SESSION_NOT_PROVEN" in accepted["blockers"]
    assert "FORWARD_FINANCIAL_WRITE_AUTHORITY_NOT_GRANTED" in accepted["blockers"]
    assert accepted["paper_fill_authorized"] is False
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match="INPUT_INVALID"):
        assess_forward_paper_activation_readiness(**{**args, "account_id": ""})


def test_local_iex_config_preflight_never_authenticates_or_exposes_secrets(tmp_path):
    from pathlib import Path
    from app.services.personal_paper_strategy_signal import check_local_iex_config_readiness
    p = tmp_path / "iex.env"
    p.write_text("ALPACA_TRADING_ENABLED=false\nALPACA_DATA_FEED=iex\nALPACA_API_KEY=secretkey123\nALPACA_API_SECRET=secretvalue123\n", encoding="utf-8")
    good = check_local_iex_config_readiness(config_path=p)
    assert good["status"] == "VALID_FORMAT_ONLY"
    assert good["provider_authenticated"] is False
    assert good["paper_fill_authorized"] is False
    assert "secret" not in repr(good).lower()
    p.write_text(p.read_text(encoding="utf-8").replace("ALPACA_TRADING_ENABLED=false", "ALPACA_TRADING_ENABLED=true"), encoding="utf-8")
    assert check_local_iex_config_readiness(config_path=p)["status"] == "CONFIG_REJECTED"
    assert check_local_iex_config_readiness(config_path=tmp_path / "missing.env")["status"] == "CONFIG_REJECTED"
    with pytest.raises(ValueError, match="EXPLICIT_PATH_REQUIRED"):
        check_local_iex_config_readiness(config_path="iex.env")


def test_bounded_readonly_session_rejects_provider_replay_across_restarts(monkeypatch):
    from datetime import UTC, datetime, timedelta
    from app.services import personal_paper_strategy_signal as signals
    stamp = datetime(2026, 11, 7, tzinfo=UTC)
    seen = []
    def plan(*, now, **_):
        seen.append(now)
        return {"provider_timestamp": stamp.isoformat(),
                "paper_fill_authorized": False, "live_order_authorized": False}
    monkeypatch.setattr(signals, "plan_leased_published_iex_paper_tick", plan)
    monkeypatch.setattr(signals, "propose_forward_paper_action",
                        lambda *, plan: {"paper_fill_authorized": False})
    args = dict(ticks=1, clock=lambda: stamp + timedelta(seconds=1))
    first = signals.run_bounded_readonly_paper_session(**args)
    assert first["last_provider_timestamp"] == stamp.isoformat()
    assert first["paper_fill_authorized"] is False
    with pytest.raises(ValueError, match="PROVIDER_EVENT_NOT_ADVANCING"):
        signals.run_bounded_readonly_paper_session(
            **args, previous_provider_timestamp=first["last_provider_timestamp"])
    assert len(seen) == 2
    with pytest.raises(ValueError):
        signals.run_bounded_readonly_paper_session(
            **args, previous_provider_timestamp="not-a-timestamp")
