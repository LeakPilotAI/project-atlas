import hashlib
import json
from pathlib import Path

import pytest
from app.backtest.forecast_artifacts import read_forecast
from app.backtest.forecast_dataset import review_dataset
from app.backtest.forecast_evaluation import ForecastEvidenceRefused
from test_afi_baselines import ASOF

FIXTURE=Path(__file__).parent/"fixtures/afi-legacy-v1"
ARTIFACT="fd49e1070d6ed3fcbe7fc521e72fbecabf6c53b9d6ea5ab840166cd66329acba.json"


def test_actual_prior_session_v1_bytes_are_still_readable_without_rewriting():
    provenance=json.loads((FIXTURE/"provenance.json").read_bytes())
    for name,digest in provenance["hashes"].items():assert hashlib.sha256((FIXTURE/name).read_bytes()).hexdigest()==digest
    review=review_dataset((FIXTURE/"manifest.json").read_bytes(),(FIXTURE/"records.json").read_bytes(),asof=ASOF)
    data=read_forecast(FIXTURE/ARTIFACT,review,evidence_asof=ASOF)
    assert data["schema"]=="AFI_SYNTHETIC_FORECAST_ARTIFACT_V1" and "release_source_sha256" not in data
    assert data["forecast"]["point"]==121.5 and not data["trading_authority"]


def test_prior_v1_modified_forecast_refuses_instead_of_silent_migration(tmp_path):
    data=json.loads((FIXTURE/ARTIFACT).read_bytes());data["forecast"]["point"]=999
    path=tmp_path/ARTIFACT;path.write_text(json.dumps(data),encoding="utf-8")
    review=review_dataset((FIXTURE/"manifest.json").read_bytes(),(FIXTURE/"records.json").read_bytes(),asof=ASOF)
    with pytest.raises(ForecastEvidenceRefused):read_forecast(path,review,evidence_asof=ASOF)
