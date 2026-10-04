from datetime import datetime, timedelta, timezone
import pytest

from app.investment.prospective_evidence import collect_board, read_records


def inputs():
    return ([{"symbol": "ABC", "quality_dips_v2": {"quality_dips_v3": {"patient_state": "WATCH"},
             "missing_v2_evidence": ["fundamentals"]}}],
            [{"symbol": "ABC", "price": 100, "timestamp": datetime.now(timezone.utc).isoformat()}])


def test_prospective_snapshot_is_immutable_deduplicated_and_unknown(tmp_path):
    board, research = inputs()
    path = tmp_path / "evidence.jsonl"
    created = collect_board(board, research, path)
    before = path.read_bytes()
    research[0]["price"] = 200
    assert collect_board(board, research, path) == []
    assert path.read_bytes() == before
    row = read_records(path)[0]
    assert row["price"] == row["source_snapshot"]["price"] == 100
    assert row["future_outcome"] == "UNKNOWN"
    assert row["evidence_class"] == "FORWARD_COLLECTION"
    assert row["observation_id"] == created[0]["observation_id"]
    assert row["missing_data"] == ["fundamentals"]
    assert not row["live_capital_allowed"]


@pytest.mark.parametrize("change", [{"timestamp": "2099-01-01T00:00:00Z"}, {"price": None},
                                    {"evidence_class": "TEST"}, {"evidence_class": "DIAGNOSTIC"}])
def test_ineligible_source_does_not_create_performance_evidence(tmp_path, change):
    board, research = inputs()
    research[0].update(change)
    assert collect_board(board, research, tmp_path / "evidence.jsonl") == []


def test_corruption_does_not_silently_discard_evidence(tmp_path):
    board, research = inputs()
    path = tmp_path / "evidence.jsonl"
    path.write_text("corrupt\n")
    with pytest.raises(ValueError):
        collect_board(board, research, path)
