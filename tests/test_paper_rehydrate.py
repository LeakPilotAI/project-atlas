"""Coach must resume journal opens after process restart."""

from app.services.perp_micro_coach import PerpMicroCoach


def test_row_from_journal_maps_hemi_fields():
    row = {
        "trade_id": "abc123",
        "symbol": "hemi",
        "side": "short",
        "actual_entry_price": 0.013639,
        "stop_price": 0.0139,
        "tp1_price": 0.01317,
        "mark": 0.013639,
        "tier": "junk",
        "counts_for_live": False,
        "signal_score": 84,
        "mfe_r": 0.0,
        "mae_r": 0.0,
        "entry_timestamp": "2026-08-29T03:00:00+00:00",
    }
    p = PerpMicroCoach._row_from_journal(row)
    assert p["symbol"] == "HEMI"
    assert p["side"] == "SHORT"
    assert p["entry"] == 0.013639
    assert p["stop"] == 0.0139
    assert p["tp1"] == 0.01317
    assert p["trade_id"] == "abc123"
    assert p["counts_for_live"] is False


def test_rehydrate_inserts_missing_open(monkeypatch):
    coach = PerpMicroCoach()
    row = {
        "trade_id": "stuck1",
        "symbol": "HEMI",
        "side": "SHORT",
        "actual_entry_price": 0.0136,
        "stop_price": 0.0139,
        "tp1_price": 0.0131,
        "mark": 0.0136,
    }

    class _J:
        def list_open(self):
            return [row]

    import app.services.paper_journal as pj

    monkeypatch.setattr(pj, "paper_journal", _J())
    added = coach._rehydrate_open()
    assert added == 1
    assert "stuck1" in coach._open
    assert coach._open["stuck1"]["entry"] == 0.0136
