import json

import app.services.perp_setup_paper_mirror as mirror_mod


def test_terminal_cache_hydrates_once_when_no_terminal_rows(tmp_path, monkeypatch):
    path = tmp_path / "pending.jsonl"
    path.write_text(
        json.dumps({"event": "armed", "setup_instance_id": "BTC|a|a", "symbol": "BTC", "side": "LONG"}) + "\n",
        encoding="utf-8",
    )
    mirror = mirror_mod.PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    calls = 0
    original = mirror_mod.iter_jsonl

    def counted(candidate):
        nonlocal calls
        if candidate == path:
            calls += 1
        return original(candidate)

    monkeypatch.setattr(mirror_mod, "iter_jsonl", counted)
    assert mirror._has_terminal_pending_event("ETH|b|b") is False
    assert mirror._has_terminal_pending_event("SOL|c|c") is False
    assert calls == 1


def test_status_uses_seeded_runtime_index_without_rescanning(tmp_path, monkeypatch):
    path = tmp_path / "pending.jsonl"
    mirror = mirror_mod.PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    mirror._terminal_cache_hydrated = True
    mirror._pending = {"BTC|a|a": {"setup_instance_id": "BTC|a|a"}}
    mirror._source_open_ids = {"trade-1"}
    mirror._opened_total = 3
    mirror._closed_total = 2

    def forbidden(_path):
        raise AssertionError("status must not rescan append-only journals")

    monkeypatch.setattr(mirror_mod, "iter_jsonl", forbidden)
    assert mirror.status() == {
        "pending_count": 1,
        "open_count": 1,
        "opened_total": 3,
        "closed_total": 2,
    }
