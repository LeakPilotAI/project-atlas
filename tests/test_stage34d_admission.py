from copy import deepcopy
from uuid import uuid4

import pytest
from app.core.offline_startup_admission import (
    AdmissionRefused,
    consume_offline_admission,
    initialize_fixture_store,
)


@pytest.mark.parametrize("damage", [None, "missing", "malformed", "expired", "identity", "run", "corrupt", "absent"])
def test_admission_refusal_and_durable_single_use(tmp_path, damage):
    path = tmp_path / "consumed.sqlite"
    initialize_fixture_store(path)
    identity = {"pid": 123, "created_at": "fixture-time", "executable": "fixture.exe", "command": "fixture"}
    evidence = {"token": str(uuid4()), "run_id": str(uuid4()), "profile": "DAILY_PAPER_OFFLINE",
                "issued_at": 100, "expires_at": 130, "process": identity}
    issued = deepcopy(evidence)
    current = deepcopy(identity)
    now = 110
    if damage == "missing":
        evidence = None
    elif damage == "malformed":
        evidence.pop("token")
    elif damage == "expired":
        now = 130
    elif damage == "identity":
        current["created_at"] = "reused-pid"
    elif damage == "run":
        evidence["run_id"] = str(uuid4())
    elif damage == "corrupt":
        path.write_bytes(b"corrupt")
    elif damage == "absent":
        path = tmp_path / "absent.sqlite"
    def consume():
        return consume_offline_admission(path, evidence, issued=issued, run_id=issued["run_id"],
                                         now=now, read_identity=lambda: current)
    if damage:
        with pytest.raises(AdmissionRefused):
            consume()
    else:
        assert consume()["production_authorized"] is False
        with pytest.raises(AdmissionRefused):
            consume()
