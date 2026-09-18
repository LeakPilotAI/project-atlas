from datetime import datetime, timedelta, timezone

from app.services.perp_setup_paper_mirror import PerpSetupPaperMirror


def test_stale_mark_timestamp_blocks_new_arm(tmp_path):
    mirror = PerpSetupPaperMirror(pending_path=tmp_path / "pending.jsonl")
    mirror._seeded = True
    setup = {
        "setup_key":"BTC:LONG","first_seen_at":"first","paper_mirror_epoch_at":"epoch",
        "symbol":"BTC","side":"LONG","tier":"QUALIFIED","state":"PREPARE","score":80,
        "mark_timestamp": (datetime.now(timezone.utc)-timedelta(seconds=60)).isoformat(),
        "levels":{"l1":99.0,"l2":98.0,"l3":97.0,"stop":95.0,"tp1":105.0,"tp2":110.0},
    }
    assert mirror._fresh_mark_timestamp(setup) is False


def test_fresh_mark_timestamp_allows_new_arm():
    setup = {"mark_timestamp": datetime.now(timezone.utc).isoformat()}
    assert PerpSetupPaperMirror._fresh_mark_timestamp(setup) is True
