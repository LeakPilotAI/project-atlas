import json

from app.services.perp_setup_paper_mirror import PerpSetupPaperMirror


def test_explicit_cancel_all_pending_is_append_only_and_clears_runtime(tmp_path):
    path = tmp_path / "pending.jsonl"
    mirror = PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    mirror._pending = {
        "BTC|a|a": {"setup_instance_id": "BTC|a|a", "setup_key": "BTC:LONG", "symbol": "BTC", "side": "LONG"},
        "ETH|b|b": {"setup_instance_id": "ETH|b|b", "setup_key": "ETH:SHORT", "symbol": "ETH", "side": "SHORT"},
    }
    assert mirror.cancel_all_pending(reason="OPERATOR_CANCEL") == 2
    assert mirror.status()["pending_count"] == 0
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    assert [x["event"] for x in rows] == ["cancelled", "cancelled"]
    assert all(x["reason"] == "OPERATOR_CANCEL" for x in rows)


def test_shutdown_preserves_pending_for_restart(tmp_path):
    path = tmp_path / "pending.jsonl"
    path.write_text(
        json.dumps({"event":"armed","setup_instance_id":"BTC|a|a","setup_key":"BTC:LONG","symbol":"BTC","side":"LONG"}) + "\n"
    )
    mirror = PerpSetupPaperMirror(pending_path=path)
    assert mirror.status()["pending_count"] == 1
    assert mirror.cancel_all_pending(reason="ATLAS_SHUTDOWN") == 0

    restarted = PerpSetupPaperMirror(pending_path=path)
    assert restarted.status()["pending_count"] == 1
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    assert [x["event"] for x in rows] == ["armed"]
