import app.investment.quality_dips_paper_terminal as terminal


def _lot():
    return {"event": "open_lot", "lot_id": "lot-1", "symbol": "MSFT"}


def _board(state="THESIS_BROKEN", blockers=None):
    return [{
        "symbol": "MSFT",
        "quality_dips_v2": {
            "quality_dips_v3": {
                "patient_state": state,
                "blockers": blockers or [],
            }
        },
    }]


def test_terminal_thesis_closes_at_fresh_observed_quote(monkeypatch):
    captured = []
    monkeypatch.setattr(terminal, "open_lots", lambda rows: [_lot()])
    monkeypatch.setattr(
        terminal,
        "close_lot",
        lambda lot_id, **kw: captured.append((lot_id, kw)) or {"event": "close_lot", "lot_id": lot_id},
    )
    quotes = {"MSFT": {"quality": "LIVE", "price": 410.0, "effective_timestamp": "2026-10-05T16:00:00+00:00"}}
    result = terminal.close_terminal_quality_dips_paper(_board(), quotes, events=[_lot()])
    assert result["closed_lots"] == 1
    assert result["skipped_lots"] == 0
    assert captured[0][1]["exit_price"] == 410.0
    assert captured[0][1]["closed_at"] == "2026-10-05T16:00:00+00:00"
    assert captured[0][1]["reason"] == "THESIS_BROKEN"
    assert result["live_capital_allowed"] is False


def test_terminal_thesis_without_fresh_quote_stays_open(monkeypatch):
    monkeypatch.setattr(terminal, "open_lots", lambda rows: [_lot()])
    monkeypatch.setattr(terminal, "close_lot", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not close")))
    quotes = {"MSFT": {"quality": "REFERENCE", "price": 410.0, "effective_timestamp": "2026-10-04T16:00:00+00:00"}}
    result = terminal.close_terminal_quality_dips_paper(_board(), quotes, events=[_lot()])
    assert result["closed_lots"] == 0
    assert result["skipped_lots"] == 1
    assert result["skips"][0]["reason"] == "NO_FRESH_EXECUTABLE_MARK"


def test_price_decline_without_terminal_thesis_never_closes(monkeypatch):
    monkeypatch.setattr(terminal, "open_lots", lambda rows: [_lot()])
    monkeypatch.setattr(terminal, "close_lot", lambda *a, **k: (_ for _ in ()).throw(AssertionError("price-only close forbidden")))
    quotes = {"MSFT": {"quality": "LIVE", "price": 1.0, "effective_timestamp": "2026-10-05T16:00:00+00:00"}}
    result = terminal.close_terminal_quality_dips_paper(_board("WATCH"), quotes, events=[_lot()])
    assert result["terminal_candidates"] == 0
    assert result["closed_lots"] == 0


def test_thesis_integrity_blocker_is_terminal(monkeypatch):
    captured = []
    monkeypatch.setattr(terminal, "open_lots", lambda rows: [_lot()])
    monkeypatch.setattr(terminal, "close_lot", lambda lot_id, **kw: captured.append(kw) or {"lot_id": lot_id})
    quotes = {"MSFT": {"quality": "FRESH", "price": 420.0, "effective_timestamp": "2026-10-05T16:05:00+00:00"}}
    result = terminal.close_terminal_quality_dips_paper(
        _board("WATCH", ["thesis integrity failed"]),
        quotes,
        events=[_lot()],
    )
    assert result["closed_lots"] == 1
    assert captured[0]["reason"] == "THESIS_INTEGRITY_TERMINAL"
