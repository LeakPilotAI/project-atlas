import json

from app.services.perp_setup_paper_mirror import PerpSetupPaperMirror


def test_terminal_instance_does_not_rearm_after_restart(tmp_path):
    path = tmp_path / "pending.jsonl"
    instance = "BTC:LONG|first|epoch"
    path.write_text(
        json.dumps({"event":"armed","setup_instance_id":instance,"setup_key":"BTC:LONG","symbol":"BTC","side":"LONG"})+"\n"+
        json.dumps({"event":"cancelled","setup_instance_id":instance,"setup_key":"BTC:LONG","symbol":"BTC","side":"LONG","reason":"ATLAS_SHUTDOWN"})+"\n",
        encoding="utf-8",
    )
    mirror = PerpSetupPaperMirror(pending_path=path)
    mirror._seeded = True
    setup = {
        "setup_key":"BTC:LONG",
        "first_seen_at":"first",
        "paper_mirror_epoch_at":"epoch",
        "symbol":"BTC",
        "side":"LONG",
        "tier":"QUALIFIED",
        "state":"PREPARE",
        "score":80,
        "levels":{"l1":99.0,"l2":98.0,"l3":97.0,"stop":95.0,"tp1":105.0,"tp2":110.0},
    }
    instruction={"action":"PLACE_RESTING_L1","limit_price":99.0}
    assert mirror._arm(setup, mark=100.0, instruction=instruction) is False
    assert mirror.status()["pending_count"] == 0
