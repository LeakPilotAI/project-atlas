import hashlib
import json

import pytest
from app.investment.quality_dips_fixture_handoff import audit_quality_fixture
from app.investment.quality_dips_paper import close_lot, mark_lot, open_lot, read_events


def source(tmp_path):
    path = tmp_path / "quality.jsonl"
    observation = {"observation_id": "fixture-obs", "symbol": "MSFT", "price": 100,
                   "source_timestamp": "2026-10-23T12:00:00+00:00"}
    lot = open_lot(observation, level="L1", paper_notional_dollars=100, path=path)
    return path, lot


def audit(raw):
    return audit_quality_fixture(raw, expected_sha256=hashlib.sha256(raw).hexdigest())


def test_actual_disposable_lot_restart_and_close_remain_gross_only(tmp_path):
    path, lot = source(tmp_path)
    assert audit(path.read_bytes())["remaining_lot_ids"] == [lot["lot_id"]]
    mark_lot(lot["lot_id"], market_price=105, path=path)
    close = close_lot(lot["lot_id"], exit_price=110, reason="fixture-thesis-terminal", path=path)
    original = path.read_bytes()
    assert close_lot(lot["lot_id"], exit_price=110, reason="fixture-thesis-terminal", path=path) == close
    result = audit(original)
    assert result["realized_gross_currency"] == "10.0"
    assert result["original_lot_count"] == result["closed_lot_count"] == 1
    assert result["remaining_lot_ids"] == [] and path.read_bytes() == original
    assert result["realized_net_currency"] is result["closing_cash"] is result["equity"] is None
    assert result["report_state"] == "INCOMPLETE" and not result["shutdown_authorized"]


@pytest.mark.parametrize("damage", ["orphan", "duplicate", "quantity", "pnl", "symbol", "partial", "nan", "clock", "schema"])
def test_ambiguous_native_history_refused_before_financial_summary(tmp_path, damage):
    path, lot = source(tmp_path)
    close_lot(lot["lot_id"], exit_price=110, reason="fixture", path=path)
    rows = read_events(path)
    if damage == "orphan": rows.pop(0)
    if damage == "duplicate": rows.append(dict(rows[-1]))
    if damage == "quantity": rows[-1]["quantity_shares"] = 0.5
    if damage == "pnl": rows[-1]["realized_pnl"] = 11
    if damage == "symbol": rows[-1]["symbol"] = "ETH"
    if damage == "partial": rows[-1]["event"] = "partial_exit"
    if damage == "nan": rows[-1]["realized_pnl"] = "NaN"
    if damage == "clock": rows[-1]["timestamp"] = "2000-01-01T00:00:00+00:00"
    if damage == "schema": rows[-1]["schema_version"] = True
    raw = "\n".join(json.dumps(r) for r in rows).encode()
    with pytest.raises(ValueError): audit(raw)


def test_source_pin_and_strict_fields_refuse_substitution(tmp_path):
    path, _ = source(tmp_path)
    raw = path.read_bytes()
    with pytest.raises(ValueError): audit_quality_fixture(raw, expected_sha256="foreign")
    with pytest.raises(ValueError, match="Duplicate source field"):
        audit(raw.replace(b'"event":', b'"event":"forged","event":', 1))


def test_two_disposable_strategy_sources_are_never_consolidated(tmp_path):
    path, _ = source(tmp_path)
    original = path.read_bytes()
    with pytest.raises(ValueError):
        audit(original + b'\n{"schema_version":2,"event":"open","strategy":"hyperliquid"}')
    assert path.read_bytes() == original


def test_interrupted_append_and_nonfinite_metadata_are_not_ignored(tmp_path):
    path, _ = source(tmp_path)
    raw = path.read_bytes()
    with pytest.raises(ValueError): audit(raw + b'\n{"event":')
    with pytest.raises(ValueError, match="Nonfinite"):
        audit(raw.replace(b'"event":', b'"extra":NaN,"event":', 1))


def test_native_flush_failure_does_not_return_success(tmp_path, monkeypatch):
    from app.investment import quality_dips_paper

    path, lot = source(tmp_path)
    def fail(_fd):
        raise OSError("fixture fsync failed")
    monkeypatch.setattr(quality_dips_paper.os, "fsync", fail)
    with pytest.raises(OSError, match="fixture fsync failed"):
        close_lot(lot["lot_id"], exit_price=110, reason="fixture", path=path)
    # Written bytes may exist despite missing acknowledgement. Their arithmetic
    # validity does not prove a durable commit or permission to replay.
    assert not audit(path.read_bytes())["shutdown_authorized"]
