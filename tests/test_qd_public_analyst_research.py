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


def test_existing_explicit_val_review_counts_one_syndicated_domain_not_five_firms():
    raw = fixture(
        row("Mark Moerdler", "Bernstein", 722, "Nov 6, 2026"),
        row("Thomas Blakey", "Cantor Fitzgerald", 630, "Nov 3, 2026"),
        row("Brent Thill", "Jefferies", 650, "Nov 2, 2026"),
    )
    receipt = research.parse_public_targets(raw, symbol="MSFT", retrieved_at=NOW)
    result = research.review_syndicated_receipt(receipt, now=NOW)
    assert result["named_firms_in_syndicated_listing"] == 3
    assert result["secondary_upstream_review_source_count"] == 1
    assert result["fresh_secondary_target_count_for_review"] == 1
    assert result["admissible_independent_valuation_sources"] == 0
    assert result["independently_authenticated_original_issuers"] == 0
    assert result["latest_original_firm_target_date"] == "2026-11-06"
    assert result["review"]["source_count"] == 1
    assert result["review"]["structural_window_complete"] is False
    assert result["review"]["window_complete"] is False
    assert result["review"]["issuer_independence_declared"] is False
    assert result["review"]["base"] is None
    for flag in ("operational_source_accepted", "paper_fill_authorized", "live_order_authorized"):
        assert result[flag] is False


def test_original_firm_asof_not_refreshed_by_recent_capture():
    raw = fixture(
        row("Mark Moerdler", "Bernstein", 722, "Oct 28, 2026"),
        row("Thomas Blakey", "Cantor Fitzgerald", 630, "Oct 27, 2026"),
        row("Brent Thill", "Jefferies", 650, "Oct 22, 2026"),
    )
    receipt = research.parse_public_targets(raw, symbol="MSFT", retrieved_at=NOW)
    result = research.review_syndicated_receipt(receipt, now=NOW)
    assert result["named_firms_in_syndicated_listing"] == 3
    assert result["latest_original_firm_target_date"] == "2026-10-28"
    assert result["fresh_secondary_target_count_for_review"] == 0
    assert result["review"]["source_count"] == 0
    assert result["review"]["base"] is None
    assert result["status"] == "RESEARCH_REVIEW_ONLY_ORIGINAL_TARGET_TOO_OLD"


@pytest.mark.parametrize("damage", [
    "pretend_original", "pretend_issuer", "pretend_operational",
    "foreign_source_url", "tamper_symbol", "duplicate_firm",
    "bad_target", "future_receipt", "expired_receipt", "extra_attribute",
])
def test_secondary_receipt_cannot_claim_financial_or_original_authority(damage):
    from copy import deepcopy
    receipt = deepcopy(research.parse_public_targets(three(), symbol="MSFT", retrieved_at=NOW))
    now = NOW
    if damage == "pretend_original":
        receipt["original_firm_reports_verified"] = True
    elif damage == "pretend_issuer":
        receipt["independent_issuer_authenticated"] = True
    elif damage == "pretend_operational":
        receipt["valuation_source_operationally_accepted"] = True
    elif damage == "foreign_source_url":
        receipt["secondary_source_url"] = "https://evil.invalid/msft"
    elif damage == "tamper_symbol":
        receipt["symbol"] = "AVGO"
    elif damage == "duplicate_firm":
        receipt["individually_attributed_targets"][1]["firm"] = "Bernstein"
    elif damage == "bad_target":
        receipt["individually_attributed_targets"][1]["target_usd"] = "nan"
    elif damage == "future_receipt":
        receipt["retrieved_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif damage == "expired_receipt":
        now = NOW + timedelta(days=2)
    elif damage == "extra_attribute":
        receipt["not_authorized"] = True
    with pytest.raises(ValueError):
        research.review_syndicated_receipt(receipt, now=now)



def test_avgo_current_target_after_arrow_is_not_previous_target_or_source_grant():
    """The live AVGO public listing uses revised '$old → $new' analyst targets."""
    now = datetime(2026, 11, 19, 15, 30, tzinfo=UTC)

    def revision(analyst, firm, old, new, when):
        source = row(analyst, firm, new, when)
        return source.replace(
            "<td>$" + str(new) + "</td>",
            "<td>$" + str(old) + " → $" + str(new) + "</td>",
        )

    raw = fixture(
        revision("James Schneider", "Goldman Sachs", 540, 460, "Nov 18, 2026"),
        revision("Joshua Buchalter", "TD Cowen", 475, 425, "Nov 16, 2026"),
        revision("Mike Harrison", "Rothschild & Co Redburn", 595, 398, "Nov 13, 2026"),
        row("Thomas O'Malley", "Barclays", 500, "Oct 28, 2026"),
        row("John Vinh", "KeyBanc", 575, "Oct 27, 2026"),
        title="Broadcom (AVGO) Analyst Ratings",
    )
    data = research.parse_public_targets(raw, symbol="AVGO", retrieved_at=now)
    assert data["individual_firm_count"] == 5
    by_firm = {a["firm"]: a["target_usd"] for a in data["individually_attributed_targets"]}
    assert by_firm == {
        "Goldman Sachs": "460", "TD Cowen": "425",
        "Rothschild & Co Redburn": "398",
        "Barclays": "500", "KeyBanc": "575",
    }
    verified = research.review_syndicated_receipt(data, now=now)
    assert verified["named_firms_in_syndicated_listing"] == 5
    assert verified["admissible_independent_valuation_sources"] == 0
    assert verified["independently_authenticated_original_issuers"] == 0
    assert verified["operational_source_accepted"] is False
    assert verified["paper_fill_authorized"] is False
    assert verified["live_order_authorized"] is False


@pytest.mark.parametrize("bad", [
    "$540 → n/a", "$540 → $460 → $400", "$0 → $460",
    "$540 → $0", "$540 → $460 trailing", "$-20 → $460",
    "$540 ↔ $460", "$540 → $1,000", "$540 → $460.999",
])
def test_malformed_target_revision_does_not_create_third_independent_firm(bad):
    raw = fixture(
        row("Thomas Blakey", "Cantor Fitzgerald", 630),
        row("Brent Thill", "Jefferies", 650),
        row("James Schneider", "Goldman Sachs", 540).replace(
            "<td>$540</td>", "<td>" + bad + "</td>",
        ),
    )
    with pytest.raises(ValueError, match="THREE_DATED_DISTINCT_FIRMS_REQUIRED"):
        research.parse_public_targets(raw, symbol="MSFT", retrieved_at=NOW)
