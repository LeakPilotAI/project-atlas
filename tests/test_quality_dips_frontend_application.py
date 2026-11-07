"""Disposable FS2/FS3-to-router-to-shipped-page tests; no native security/server."""
import copy
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from app.api.quality_dips_selected_paper import financial_view
from app.services.paper_daily_report import build_daily_report
from app.services.paper_financial_replay import digest, strict
from test_quality_dips_integration_v1 import system


def enriched_system(tmp_path):
    s = system(tmp_path, "SPY", "ETF")
    original = s.reader.read_committed
    report = [None]
    selection = [None]
    change = [None]

    def read(account, epoch):
        payload = original(account, epoch)
        if payload.get("status") != "ACKNOWLEDGED":
            return payload
        payload["projection_revision"] = payload["source_revision"]
        payload["inception"] = {"schema": "QD_SELECTED_INCEPTION_VIEW_V1", "account_id": account, "epoch": epoch,
            "policy_digest": digest(s.manifest["account_policy"]), "policy_schema": s.manifest["account_policy"]["schema"],
            "currency": "USD", "opening_cash": s.manifest["opening_cash"]}
        payload.update(report=copy.deepcopy(report[0]), report_status=report[0]["status"] if report[0] else "UNAVAILABLE")
        payload["selection"] = copy.deepcopy(selection[0])
        if change[0]:
            change[0](payload)
        return payload

    s.reader.read_committed = read

    def publish_fixture_report():
        # Reporting is explicit admitted test setup, NEVER called by GET.
        with s.store.guard():
            pin, manifest, rows, _, _, _, _ = s.store._load()
        scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": s.service.account, "epoch": s.service.epoch,
                 "policy_digest": digest(manifest), "timezone": "America/New_York"}
        day = datetime.fromtimestamp(s.now[0], ZoneInfo(scope["timezone"])).date().isoformat()
        report[0] = build_daily_report(scope, manifest, pin, rows, day, s.now[0] + 1)
        entry = next(strict(row["command"]) for row in rows if strict(row["command"])["kind"] == "ENTRY")
        candidate = strict(entry["authority_evidence"]["candidate"])
        selection[0] = {"schema": "QD_SELECTION_PRESENTATION_V1", "basis": "Acknowledged entry decision; not current eligibility",
                        "cohort_id": candidate["cohort_id"], "generation": candidate["generation"],
                        "candidates": [{"symbol": candidate["ranking"]["symbol"],
                            "asset_class": candidate["execution"]["instrument"]["asset_class"],
                            "rank": candidate["ranking"]["rank"], "status": "SELECTED", "reasons": candidate["reasons"]}]}

    return s, publish_fixture_report, change


def test_actual_disposable_ledger_projection_api_and_page(tmp_path):
    s, report, _ = enriched_system(tmp_path)
    frames = []

    def capture(cash, remaining):
        report()
        before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        view = s.read()
        assert view["status"] == "ACKNOWLEDGED" and view["cash"] == cash
        assert view["inception"]["opening_cash"] == "1000"
        assert view["projection_revision"] == view["source_revision"]
        assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        frames.append({"payload": view, "now": s.now[0], "expectedCash": cash, "remaining": remaining})

    s.service.execute(s.approve(s.entry()))
    capture("900.0", "2.5")
    s.now[0] += 86400
    s.service.execute(s.approve(s.exit_request("1")))
    capture("943.968", "1.5")
    s.service.execute(s.approve(s.exit_request("1.5", "final")))
    capture("1009.920", None)
    assert frames[1]["payload"]["report"]["realized"]["fees"] == "0.016"

    class Unavailable:
        def read_committed(self, account, epoch):
            raise OSError("fixture unavailable")
    missing = financial_view(reader=Unavailable(), verifier=s.ReadVerifier(), clock=lambda: s.now[0],
                             account_id=s.service.account, epoch=s.service.epoch)
    frames.append({"payload": missing, "now": s.now[0], "expectedCash": None, "remaining": None})
    source = tmp_path / "synthetic-router-frames.json"
    source.write_text(json.dumps(frames), encoding="utf-8")
    root = Path(__file__).parents[1]
    result = subprocess.run(["node", str(root / "tests/quality_dips_selected_application.cjs"), str(source)],
                            cwd=root, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 disposable application frames passed" in result.stdout


@pytest.mark.parametrize("damage", ["inception-epoch", "inception-cash", "projection-revision"])
def test_verified_payload_still_requires_exact_read_metadata_scope(tmp_path, damage):
    s, _, change = enriched_system(tmp_path)
    s.service.execute(s.approve(s.entry()))
    def mutate(payload):
        if damage == "inception-epoch": payload["inception"]["epoch"] = "legacy-epoch"
        if damage == "inception-cash": payload["inception"]["opening_cash"] = None
        if damage == "projection-revision": payload["projection_revision"] += 1
    change[0] = mutate
    view = s.read()
    assert view["status"] == "UNKNOWN" and view["cash"] is None


def test_optional_inception_is_unavailable_not_synthesized(tmp_path):
    s = system(tmp_path)
    s.service.execute(s.approve(s.entry()))
    view = s.read()
    assert view["status"] == "ACKNOWLEDGED" and view["inception"] is None
    assert view["projection_revision"] is None
