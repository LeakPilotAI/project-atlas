from datetime import datetime, timedelta, timezone
import pytest
from app.investment.evidence_lifecycle import freeze_policy, classify_observation


def test_freeze_rejects_retrospective_split_and_version_overwrite(tmp_path):
    now = datetime.now(timezone.utc)
    args = dict(version="v1", policy={"margin": 15}, rationale="prospective experiment",
                development_end=(now+timedelta(days=10)).isoformat(),
                holdout_start=(now+timedelta(days=11)).isoformat(),
                holdout_end=(now+timedelta(days=20)).isoformat(), path=tmp_path/"freezes.jsonl")
    freeze = freeze_policy(**args)
    with pytest.raises(ValueError):
        freeze_policy(**args)
    with pytest.raises(ValueError):
        freeze_policy(**{**args, "version": "bad", "development_end": (now-timedelta(days=1)).isoformat()})
    obs = {"policy_version": "v1", "evidence_class": "FORWARD_COLLECTION", "timestamp": (now+timedelta(days=12)).isoformat()}
    assert classify_observation(obs, freeze) == "HOLDOUT"
    assert classify_observation({**obs, "timestamp": (now+timedelta(days=2)).isoformat()}, freeze) == "DEVELOPMENT"
    for evidence in ("TEST", "DIAGNOSTIC", "HISTORICAL_IMMUTABLE", "DEVELOPMENT"):
        assert classify_observation({**obs, "evidence_class": evidence}, freeze) == evidence
    assert classify_observation({**obs, "policy_version": "other"}, freeze) == "FORWARD_COLLECTION"
