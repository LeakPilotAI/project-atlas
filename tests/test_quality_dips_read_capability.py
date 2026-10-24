"""Read-only contract fixtures; fake custody is explicitly NOT real authority."""
import copy
from contextlib import contextmanager
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from app.api.quality_dips_selected_paper import financial_view
from app.investment.quality_dips_read_capability import SelectedReadCapability
from app.services.paper_daily_report import build_daily_report
from app.services.paper_financial_replay import digest
from test_quality_dips_integration_v1 import system


class FixtureAuthority:
    """Fixed harness-captured pins, no issuer/custody/security acceptance."""
    def __init__(self, enrollment, pin):
        self.expected, self.pin = copy.deepcopy(enrollment), copy.deepcopy(pin)
        self.available, self.coherent = True, True

    @contextmanager
    def lease(self, enrollment, now):
        if not self.available or enrollment != self.expected:
            raise ValueError("NO_ACCEPTED_AUTHORITY")
        captured = copy.deepcopy(self.pin)
        yield SimpleNamespace(snapshot=captured, check=lambda p, t:
                              self.coherent and p == captured == self.pin)


def setup_read(tmp_path):
    s = system(tmp_path, "SPY", "ETF")
    s.service.execute(s.approve(s.entry()))
    pin, manifest, rows, state, _, _, _ = s.store._load()
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": s.service.account,
             "epoch": manifest["epoch"], "policy_digest": digest(manifest), "timezone": manifest["timezone"]}
    s.now[0] += 1
    day = datetime.fromtimestamp(s.now[0], ZoneInfo(scope["timezone"])).date().isoformat()
    report = build_daily_report(scope, manifest, pin, rows, day, s.now[0])
    enrollment = {"schema": "QD_READ_ENROLLMENT_V1", "account_id": s.service.account,
                  "epoch": manifest["epoch"], "manifest_digest": digest(manifest),
                  "policy_digest": digest(manifest["account_policy"]), "source_root": pin["root"],
                  "projection_root": s.target.expected_root, "report_root": [9, 8, 7], "inception": pin["inception"]}
    current = {"schema": "QD_READ_CURRENT_V1", "enrollment_digest": digest(enrollment),
               "observed_at": s.now[0], "expires_at": s.now[0] + 30, "generation": 1,
               "source": pin, "reports": {"root": enrollment["report_root"]},
               "high_water": len(rows), "acknowledged_revision": len(rows), "status": "ACKNOWLEDGED"}
    evidence = {"manifest": manifest, "rows": rows, "state": state, "scope": scope,
                "documents": [{"report": report}]}
    authority = FixtureAuthority(enrollment, current)
    port = SimpleNamespace(read_verified=lambda e, p: copy.deepcopy(evidence))
    cap = SelectedReadCapability(enrollment=enrollment, authority=authority, clock=lambda: s.now[0], port=port)
    return SimpleNamespace(**locals())


def test_read_only_snapshot_to_existing_router(tmp_path):
    x = setup_read(tmp_path)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    view = financial_view(reader=x.cap, verifier=x.cap, clock=lambda: x.s.now[0],
                          account_id=x.s.service.account, epoch=x.s.service.epoch)
    assert view["status"] == "ACKNOWLEDGED" and view["cash"] == "900.0"
    assert view["report_status"] == "INCOMPLETE" and view["valuation"] is None
    assert next(iter(view["positions"].values()))["remaining"] == "2.5"
    assert view["inception"]["opening_cash"] == "1000"
    assert not view["startup_authorized"]
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("field,value", [
    ("schema", "FUTURE"), ("status", "UNKNOWN"), ("observed_at", 0),
    ("observed_at", True), ("expires_at", 0), ("generation", 0),
    ("high_water", 0), ("acknowledged_revision", 0), ("enrollment_digest", "foreign"),
])
def test_pin_refusals(tmp_path, field, value):
    x = setup_read(tmp_path)
    x.authority.pin[field] = value
    with pytest.raises(ValueError):
        x.cap.read_committed(x.s.service.account, x.s.service.epoch)


@pytest.mark.parametrize("damage", ["missing", "foreign", "rollback", "changed", "unknown_writer", "future", "clock_back"])
def test_authority_and_concurrent_read_refusal(tmp_path, damage):
    x = setup_read(tmp_path)
    if damage == "missing":
        x.authority.available = False
    elif damage == "foreign":
        x.cap.enrollment["source_root"] = [1, 2, 3]
    elif damage == "rollback":
        x.authority.pin["source"]["entries"] = []
    elif damage == "unknown_writer":
        x.authority.coherent = False
    elif damage == "future":
        x.authority.pin["observed_at"] += 1
    else:
        original = x.port.read_verified
        def race(e, p):
            result = original(e, p)
            if damage == "changed":
                x.authority.pin["generation"] += 1
            else:
                x.s.now[0] -= 2
            return result
        x.port.read_verified = race
    with pytest.raises(ValueError):
        x.cap.read_committed(x.s.service.account, x.s.service.epoch)


@pytest.mark.parametrize("damage", ["state", "rows", "manifest", "legacy", "report_cash", "report_source", "report_missing", "scope"])
def test_source_and_report_refusals(tmp_path, damage):
    x = setup_read(tmp_path)
    if damage == "state":
        x.evidence["state"]["cash"] = "1000"
    elif damage == "rows":
        x.evidence["rows"] = []
    elif damage == "manifest":
        x.evidence["manifest"]["opening_cash"] = "2000"
    elif damage == "legacy":
        x.evidence["manifest"]["schema"] = "PAPER_EPOCH_V1"
    elif damage == "report_cash":
        x.evidence["documents"][0]["report"]["cash"]["closing"] = "1000"
    elif damage == "report_source":
        x.evidence["documents"][0]["report"]["source"]["revision"] = 0
    elif damage == "scope":
        x.evidence["scope"]["account_id"] = "legacy"
    else:
        x.evidence["documents"] = []
    with pytest.raises((ValueError, KeyError)):
        x.cap.read_committed(x.s.service.account, x.s.service.epoch)


def test_absent_dependencies_and_foreign_payload(tmp_path):
    with pytest.raises(ValueError):
        SelectedReadCapability(enrollment={}, authority=None, clock=None, port=None)
    x = setup_read(tmp_path)
    payload = x.cap.read_committed(x.s.service.account, x.s.service.epoch)
    payload["state"]["cash"] = "1000"
    assert x.cap.verify(payload, account_id=x.s.service.account, epoch=x.s.service.epoch,
                        now=x.s.now[0])["verified"] is False


def test_trusted_observation_time_survives_slow_read_without_freshening_it(tmp_path):
    x = setup_read(tmp_path)
    payload = x.cap.read_committed(x.s.service.account, x.s.service.epoch)
    x.s.now[0] += 2
    assert x.cap.verify(payload, account_id=x.s.service.account, epoch=x.s.service.epoch,
                        now=x.s.now[0])["verified"] is True
    assert payload["observed_at"] == x.current["observed_at"]
    x.s.now[0] += 29
    with pytest.raises(ValueError):
        x.cap.read_committed(x.s.service.account, x.s.service.epoch)
