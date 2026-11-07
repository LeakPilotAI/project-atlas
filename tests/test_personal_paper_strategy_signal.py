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
                              "evidence_class": "FORWARD_COLLECTION"}}
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
