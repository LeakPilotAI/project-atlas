from datetime import datetime, timedelta, timezone
import pytest

from app.investment.prospective_evidence import collect_board, read_records
import app.investment.quality_dips_paper as qdp


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



def test_new_forward_observation_is_mirrored_to_paper_after_freeze(tmp_path, monkeypatch):
    board, research = inputs()
    paper_path = tmp_path / "quality_dips_paper.jsonl"
    monkeypatch.setattr(qdp, "QUALITY_DIPS_PAPER_JOURNAL_PATH", paper_path)
    # mirror_forward_observation's default argument was bound at import time;
    # route the integration call to an isolated journal while preserving the
    # production mirror implementation.
    original = qdp.mirror_forward_observation
    calls = []

    def isolated(row):
        calls.append(row["observation_id"])
        return original(row, path=paper_path)

    monkeypatch.setattr(qdp, "mirror_forward_observation", isolated)
    evidence_path = tmp_path / "evidence.jsonl"
    created = collect_board(board, research, evidence_path)
    assert len(created) == 1
    assert calls == [created[0]["observation_id"]]
    events = qdp.read_events(paper_path)
    assert len(events) == 1
    assert events[0]["event"] == "decision"
    assert events[0]["decision"] == "PAPER_NO_FILL"
    assert events[0]["execution"] == "PAPER_ONLY"
    assert events[0]["live_capital_allowed"] is False
    # Daily source evidence is immutable/deduplicated, so refreshes cannot
    # duplicate PAPER decisions or positions.
    assert collect_board(board, research, evidence_path) == []
    assert len(qdp.read_events(paper_path)) == 1
