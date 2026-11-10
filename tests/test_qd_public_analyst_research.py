"""Offline contracts for one bounded public syndicated analyst-target read."""
from datetime import UTC, datetime, timedelta

import pytest

from scripts.observation_runtime import qd_public_analyst_research as research

NOW = datetime(2026, 11, 10, 17, 30, tzinfo=UTC)


def row(analyst, firm, price, when="Nov 6, 2026"):
    return (
        '<tr><td><a href="/analysts/test">' + analyst + '</a></td>'
        '<td>' + firm + '</td><td>Buy $' + str(price) + '</td>'
        '<td>Buy</td><td>Maintains</td><td>$' + str(price) + '</td>'
        '<td>+10.0%</td><td>' + when + '</td></tr>'
    )


def fixture(*rows, title="Microsoft (MSFT) Analyst Ratings"):
    return ('<html><head><title>' + title + '</title></head>'
            '<body><table><tbody>' + ''.join(rows) + '</tbody></table></body></html>'
            ).encode("utf-8")


def three():
    return fixture(row("Mark Moerdler", "Bernstein", 722),
                   row("Thomas Blakey", "Cantor Fitzgerald", 630),
                   row("Brent Thill", "Jefferies", 650))


def test_three_named_dated_distinct_firms_are_only_secondary_research():
    raw = three()
    result = research.parse_public_targets(raw, symbol="MSFT", retrieved_at=NOW)
    assert result["symbol"] == "MSFT"
    assert result["original_html_sha256"]
    assert result["individual_firm_count"] == 3
    assert {r["firm"] for r in result["individually_attributed_targets"]} == {
        "Bernstein", "Cantor Fitzgerald", "Jefferies"}
    assert {r["target_usd"] for r in result["individually_attributed_targets"]} == {
        "722", "630", "650"}
    assert result["syndicated_secondary_evidence"] is True
    for field in ("original_firm_reports_verified", "independent_issuer_authenticated",
                  "valuation_source_operationally_accepted",
                  "native_forward_publication_created",
                  "simulated_paper_order_authorized", "live_order_authorized"):
        assert result[field] is False


@pytest.mark.parametrize("damage", [
    "foreign_symbol", "two_firms", "stale_firms", "future_firms",
    "duplicate_conflict", "bad_price", "oversized", "foreign_title",
])
def test_unsafe_or_insufficient_analyst_evidence_refuses(damage):
    raw = three()
    symbol = "MSFT"
    if damage == "foreign_symbol":
        symbol = "AVGO"
    elif damage == "two_firms":
        raw = fixture(row("Mark Moerdler", "Bernstein", 722),
                      row("Thomas Blakey", "Cantor Fitzgerald", 630))
    elif damage == "stale_firms":
        raw = fixture(*[row(*values, when="Jan 1, 2026") for values in (
            ("Mark Moerdler", "Bernstein", 722),
            ("Thomas Blakey", "Cantor Fitzgerald", 630),
            ("Brent Thill", "Jefferies", 650))])
    elif damage == "future_firms":
        raw = fixture(*[row(*values, when="Nov 12, 2026") for values in (
            ("Mark Moerdler", "Bernstein", 722),
            ("Thomas Blakey", "Cantor Fitzgerald", 630),
            ("Brent Thill", "Jefferies", 650))])
    elif damage == "duplicate_conflict":
        raw = fixture(row("Mark Moerdler", "Bernstein", 722),
                      row("Mark Moerdler", "Bernstein", 999),
                      row("Thomas Blakey", "Cantor Fitzgerald", 630),
                      row("Brent Thill", "Jefferies", 650))
    elif damage == "bad_price":
        raw = fixture(row("Mark Moerdler", "Bernstein", "NaN"),
                      row("Thomas Blakey", "Cantor Fitzgerald", 630),
                      row("Brent Thill", "Jefferies", 650))
    elif damage == "oversized":
        raw = raw + b"x" * (research.MAX_PAGE_BYTES + 1)
    elif damage == "foreign_title":
        raw = fixture(row("Mark Moerdler", "Bernstein", 722),
                      row("Thomas Blakey", "Cantor Fitzgerald", 630),
                      row("Brent Thill", "Jefferies", 650),
                      title="Foreign stock ratings")
    with pytest.raises(ValueError):
        research.parse_public_targets(raw, symbol=symbol, retrieved_at=NOW)


def test_same_firm_can_count_only_once_after_repeated_rows():
    raw = fixture(row("Mark Moerdler", "Bernstein", 722),
                  row("Mark Moerdler", "Bernstein", 722),
                  row("Thomas Blakey", "Cantor Fitzgerald", 630),
                  row("Brent Thill", "Jefferies", 650))
    result = research.parse_public_targets(raw, symbol="MSFT", retrieved_at=NOW)
    assert result["individual_firm_count"] == 3


def test_public_fetch_is_single_bounded_credential_free_exact_url():
    seen = []
    class Response:
        status = 200
        def geturl(self):
            return "https://stockanalysis.com/stocks/msft/ratings/"
        def read(self, cap):
            seen.append(("bytes", cap))
            return three()
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    def opener(request, *, timeout):
        seen.append(("url", request.full_url, timeout))
        assert request.get_header("Authorization") is None
        return Response()

    result = research.fetch_public_targets("MSFT", now=NOW, opener=opener)
    assert result["individual_firm_count"] == 3
    assert seen == [("url", "https://stockanalysis.com/stocks/msft/ratings/", 8),
                    ("bytes", research.MAX_PAGE_BYTES + 1)]


def test_wrong_response_url_and_symbol_refuse_before_any_market_access():
    class Response:
        status = 200
        def geturl(self):
            return "https://untrusted.invalid/redirect"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
    with pytest.raises(ValueError, match="EXACT_PUBLIC_PAGE"):
        research.fetch_public_targets("MSFT", now=NOW, opener=lambda *a, **k: Response())
    with pytest.raises(ValueError, match="SYMBOL_REQUIRED"):
        research.fetch_public_targets("MSFT;rm", opener=lambda *a, **k: pytest.fail("NO_IO"))


def test_bad_timestamp_refuses_even_with_valid_html():
    with pytest.raises(ValueError, match="BOUNDED_EXACT_INPUT"):
        research.parse_public_targets(three(), symbol="MSFT",
                                      retrieved_at=datetime(2026, 11, 10))
