from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from app.backtest.forecast_replay import (
    evaluate_holdout,
    freeze_selection,
    replay_baselines,
)
from test_afi_baselines import ASOF, ASSET, history


def issue(day):return datetime(2026,9,day,0,1,tzinfo=UTC)


def frozen():
    return freeze_selection(history(),asset_id=ASSET,selection_issues=[issue(20),issue(21)],
                            frozen_at=issue(24),evidence_asof=ASOF,lookback=5)


def test_actual_refit_replay_resolves_and_preserves_provenance():
    r=replay_baselines(history(),asset_id=ASSET,issued_times=[issue(20),issue(21),issue(22)],
                       evidence_asof=ASOF,lookback=5,method="ENDPOINT_DRIFT")
    assert r["score"]["scored_n"]==3 and r["requested_n"]==3 and r["refused_n"]==0
    assert all(c["training_available_through"]<=c["issued_at"] for c in r["cases"])
    assert not r["predictive_skill_established"]


def test_missing_future_label_and_insufficient_training_remain_explicit():
    last=datetime(2026,10,19,0,1,tzinfo=UTC)
    r=replay_baselines(history(),asset_id=ASSET,issued_times=[issue(10),last],evidence_asof=ASOF,lookback=5)
    assert r["requested_n"]==2 and r["refused_n"]==1
    assert r["score"]["pending_n"]==1 and r["score"]["scored_n"]==0
    assert [c["status"] for c in r["cases"]]==["REFUSED","PENDING"]


def test_frozen_selection_and_holdout_are_separate_and_reproducible():
    selection=frozen()
    a=evaluate_holdout(history(),selection,holdout_issues=[issue(25),issue(26),issue(27)],evidence_asof=ASOF)
    b=evaluate_holdout(history(),selection,holdout_issues=[issue(25),issue(26),issue(27)],evidence_asof=ASOF)
    assert a==b and a["selected_method"]==selection["selected_method"]
    assert set(a["reports"])=={"NO_CHANGE","ENDPOINT_DRIFT"}
    assert not a["retuning_allowed"] and not a["independently_unseen"]
    assert all(r["score"]["scored_n"]==3 for r in a["reports"].values())


@pytest.mark.parametrize("times",[[issue(21),issue(20)],[issue(20),issue(20)],[],[ASOF+timedelta(days=1)]])
def test_replay_timing_and_size_refuse(times):
    with pytest.raises(ForecastEvidenceRefused):
        replay_baselines(history(),asset_id=ASSET,issued_times=times,evidence_asof=ASOF,lookback=5)


@pytest.mark.parametrize("change",[{"frozen_at":issue(21)}, {"embargo":timedelta(days=4)},
                                    {"selection_issues":[issue(10)]},{"selection_issues":[issue(20)]}])
def test_peek_embargo_and_incomplete_selection_refuse(change):
    opts={"asset_id":ASSET,"selection_issues":[issue(20),issue(21)],"frozen_at":issue(24),"evidence_asof":ASOF,"lookback":5}
    with pytest.raises(ForecastEvidenceRefused):freeze_selection(history(),**{**opts,**change})


@pytest.mark.parametrize("key,value",[("selected_method","FORGED"),("freeze_sha256","a"*64),("lookback",6)])
def test_holdout_cannot_replace_frozen_selection(key,value):
    selection=deepcopy(frozen());selection[key]=value
    with pytest.raises(ForecastEvidenceRefused):evaluate_holdout(history(),selection,holdout_issues=[issue(25)],evidence_asof=ASOF)


def test_holdout_rejects_overlap_empty_or_preselection_cases():
    for times in ([],[issue(20)],[issue(23)]):
        with pytest.raises(ForecastEvidenceRefused):evaluate_holdout(history(),frozen(),holdout_issues=times,evidence_asof=ASOF)

def test_selection_uses_pre_freeze_outcome_revision_not_later_correction():
    import hashlib
    import json

    from app.backtest.forecast_dataset import review_dataset
    from test_afi_dataset_integrity import encode
    original=history();m=json.loads(original.manifest_bytes);p=json.loads(original.payload_bytes)
    row=p['records'][11]
    p['records'].append({**row,'record_id':'late-correction','revision':'v2','raw_price':9000,'value':9000,
                         'available_at':'2026-10-18T00:00:00+00:00'})
    raw=encode(p);m.update(content_sha256=hashlib.sha256(raw).hexdigest(),record_count=len(p['records']))
    revised=review_dataset(encode(m),raw,asof=ASOF)
    selected=freeze_selection(revised,asset_id=ASSET,selection_issues=[issue(20),issue(21)],frozen_at=issue(24),evidence_asof=ASOF,lookback=5)
    old=frozen()
    assert selected['candidate_mae']==old['candidate_mae'] and selected['selected_method']==old['selected_method']

def test_outcome_vintage_must_not_exceed_evidence_or_precede_issuance():
    for cutoff in (ASOF+timedelta(seconds=1),issue(19)):
        with pytest.raises(ForecastEvidenceRefused):
            replay_baselines(history(),asset_id=ASSET,issued_times=[issue(20)],evidence_asof=ASOF,
                             lookback=5,outcome_asof=cutoff)
