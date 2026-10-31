import json

from app.services.perp_setup_paper_mirror import PerpSetupPaperMirror


def _armed(instance: str) -> dict:
    return {
        "event": "armed", "setup_instance_id": instance, "setup_key": "BTC:LONG",
        "symbol": "BTC", "side": "LONG", "limit_price": 99.0,
        "stop": 95.0, "tp1": 105.0, "tp2": 110.0,
    }


def test_normal_shutdown_preserves_pending_limit_for_restart(tmp_path):
    path = tmp_path / "pending.jsonl"
    instance = "BTC:LONG|first|epoch"
    path.write_text(json.dumps(_armed(instance)) + "\n", encoding="utf-8")
    mirror = PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    mirror._pending = {instance: _armed(instance)}
    assert mirror.cancel_all_pending(reason="ATLAS_SHUTDOWN") == 0
    assert instance in mirror._pending
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert [r["event"] for r in rows] == ["armed"]


def test_explicit_cancellation_remains_terminal(tmp_path):
    path = tmp_path / "pending.jsonl"
    instance = "BTC:LONG|first|epoch"
    path.write_text(json.dumps(_armed(instance)) + "\n", encoding="utf-8")
    mirror = PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    mirror._pending = {instance: _armed(instance)}
    assert mirror.cancel_all_pending(reason="OPERATOR_CANCEL") == 1
    assert instance not in mirror._pending
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["event"] == "cancelled"
    assert rows[-1]["reason"] == "OPERATOR_CANCEL"
