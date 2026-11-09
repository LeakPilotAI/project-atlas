"""Selected V7 read-only commissioning clock: strictly no financial authority."""
import json
from pathlib import Path

import pytest

from scripts.observation_runtime import atlas_v7_commissioning_ntp_probe as probe
from scripts.observation_runtime import personal_commissioning_preflight as personal
from scripts.observation_runtime import unified_paper_commissioning_preflight as unified


class FakeClock:
    created = []
    fail = False

    def __init__(self, *, runtime_id, lifetime):
        assert runtime_id == probe.RUNTIME_ID
        assert lifetime == 30
        self.revoked = False
        self.evidence = {
            "domain": "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS",
            "source": probe.SOURCE_ID,
            "bound_ms": 141,
            "peer_difference_ms": 2,
            "financial_authority": False,
            "os_windows_time_service_required": False,
        }
        self.created.append(self)

    def require_operational(self, runtime):
        assert runtime == probe.RUNTIME_ID
        if self.fail:
            raise ValueError("NO_VALID_PEERS")
        return self

    def sample(self):
        return {"utc": 1794000000}

    def verify(self, sample):
        return sample["utc"] == 1794000000

    def revoke(self):
        self.revoked = True


def test_v7_dual_ntp_clock_proof_does_not_admit_financial_activity(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    FakeClock.created = []
    monkeypatch.setattr(probe, "verify_selected_v7", lambda: True)
    monkeypatch.setattr(ntp, "IndependentNtpClock", FakeClock)
    result = probe.inspect_v7_independent_ntp_clock()
    assert result["trusted_clock_verified_for_probe"] is True
    assert result["uncertainty_ms"] == 141
    assert result["peer_difference_ms"] == 2
    assert result["selected_revision"] == 11
    assert result["public_ntp_authenticated"] is False
    assert result["windows_time_service_required"] is False
    assert result["continuous_financial_clock_lease_verified"] is False
    assert result["financial_clock_authorized"] is False
    assert result["native_activation_verified"] is False
    assert result["forward_financial_write_authorized"] is False
    assert result["live_order_authorized"] is False
    assert len(FakeClock.created) == 1 and FakeClock.created[0].revoked


def test_missing_or_mismatched_native_v7_prevents_ntp_query(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    monkeypatch.setattr(probe, "verify_selected_v7", lambda: (_ for _ in ()).throw(
        ValueError("V7_COMMISSIONING_SELECTOR_RECORD_CHANGED")))
    monkeypatch.setattr(ntp, "IndependentNtpClock",
                        lambda **kwargs: pytest.fail("network without native source"))
    result = probe.inspect_v7_independent_ntp_clock()
    assert not result["trusted_clock_verified_for_probe"]
    assert result["blocker"] == "V7_COMMISSIONING_SELECTOR_RECORD_CHANGED"
    assert not result["financial_clock_authorized"]


def test_ntp_peer_refusal_revokes_and_blocks(monkeypatch):
    from scripts.observation_runtime import atlas_independent_ntp_clock as ntp
    FakeClock.created = []
    monkeypatch.setattr(probe, "verify_selected_v7", lambda: True)
    monkeypatch.setattr(ntp, "IndependentNtpClock", FakeClock)
    FakeClock.fail = True
    try:
        r = probe.inspect_v7_independent_ntp_clock()
        assert r["trusted_clock_verified_for_probe"] is False
        assert r["blocker"] == "NO_VALID_PEERS"
        assert r["financial_clock_authorized"] is False
        assert len(FakeClock.created) == 1 and FakeClock.created[0].revoked
    finally:
        FakeClock.fail = False


def test_coordinated_preflight_uses_new_readonly_clock_no_native_w32tm(monkeypatch, capsys):
    from scripts.observation_runtime import atlas_v7_commissioning_ntp_probe as ntp_probe
    from scripts.observation_runtime import personal_clock_gate_probe as old_clock
    monkeypatch.setattr("sys.argv", [
        "personal", "--json", "--check-independent-ntp-clock"])
    monkeypatch.setattr(personal.subprocess, "check_output", lambda *args, **kwargs: "")
    monkeypatch.setattr(ntp_probe, "inspect_v7_independent_ntp_clock", lambda: {
        "trusted_clock_verified_for_probe": True,
        "financial_clock_authorized": False,
        "uncertainty_ms": 145})
    monkeypatch.setattr(old_clock, "inspect_personal_clock_gate",
                        lambda: pytest.fail("Windows time queried"))
    assert personal.main() == 2
    data = json.loads(capsys.readouterr().out)
    checks = {x["check"]: x["status"] for x in data["checks"]}
    assert checks["INDEPENDENT_NTP_CLOCK_PROBE"] == "PASS"
    assert "NATIVE_CLOCK_PROBE" not in checks
    assert data["native_clock_probe"] is None
    assert data["independent_ntp_clock_probe"]["financial_clock_authorized"] is False
    assert data["financial_mutations"] is data["pilot_started"] is False
    assert data["status"] == "BLOCKED"


def test_personal_refuses_both_clock_options(monkeypatch):
    monkeypatch.setattr("sys.argv", [
        "personal", "--check-native-clock", "--check-independent-ntp-clock"])
    with pytest.raises(SystemExit) as exc:
        personal.main()
    assert exc.value.code == 2


def test_unified_does_not_promote_reported_readonly_clock_to_go():
    observed = {
        "trusted_clock_verified_for_probe": True,
        "selected_release": probe.V7_RELEASE,
        "financial_clock_authorized": False,
        "public_ntp_authenticated": False,
        "continuous_financial_clock_lease_verified": False}
    result = unified.inspect(qd_report={"checks": [], "independent_ntp_clock_probe": observed})
    assert result["independent_ntp_clock_readonly_diagnostic"] == (
        "V7_DUAL_NTP_READONLY_OBSERVED_NOT_FINANCIAL_AUTHORITY")
    assert result["decision"] == "NO_GO"
    assert result["startup_authorized"] is result["live_trading_authorized"] is False
    assert result["prerequisites"]["QD_SOURCE_PUBLICATION"] == "BLOCKED"
    assert result["prerequisites"]["CURRENT_EXECUTABLE_MARKET_PRICES"] == "NOT_INDEPENDENTLY_VERIFIED"
    assert result["prerequisites"]["QD_FINANCIAL_INCEPTION"] == "BLOCKED"


@pytest.mark.parametrize("tamper", [
    {"trusted_clock_verified_for_probe": False},
    {"financial_clock_authorized": True},
    {"public_ntp_authenticated": True},
    {"continuous_financial_clock_lease_verified": True},
    {"selected_release": "foreign-release"},
    {"selected_release": None},
])
def test_unified_refuses_fabricated_ntp_evidence(tamper):
    row = {"trusted_clock_verified_for_probe": True,
           "selected_release": probe.V7_RELEASE,
           "financial_clock_authorized": False,
           "public_ntp_authenticated": False,
           "continuous_financial_clock_lease_verified": False}
    row.update(tamper)
    report = unified.inspect(qd_report={"checks": [], "independent_ntp_clock_probe": row})
    assert report["independent_ntp_clock_readonly_diagnostic"] == "NOT_VERIFIED"
    assert report["decision"] == "NO_GO" and not report["startup_authorized"]


def test_unified_cli_invokes_independent_probe_not_windows_time(monkeypatch, capsys):
    from types import SimpleNamespace
    monkeypatch.setattr("sys.argv", ["unified"])
    monkeypatch.setattr(unified.subprocess, "check_output",
                        lambda args, **kw: "a"*40)
    def fake_run(args, **kw):
        assert "--check-independent-ntp-clock" in args
        assert "--check-native-clock" not in args
        assert "--expected-source" in args and "a"*40 in args
        return SimpleNamespace(returncode=2, stdout=json.dumps(
            {"checks": [], "independent_ntp_clock_probe": None}))
    monkeypatch.setattr(unified.subprocess, "run", fake_run)
    assert unified.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["independent_ntp_clock_readonly_diagnostic"] == "NOT_VERIFIED"
    assert report["decision"] == "NO_GO"
    assert report["startup_authorized"] is False


def test_clock_source_has_no_financial_or_system_mutation():
    s = Path(probe.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "Set-Date", "/resync", "subprocess", "order_submit", "place_order",
        "create_account", "financial_authority=True", "financial_clock_authorized=True",
        "os.system", "write_bytes", "write_text",
    ):
        assert forbidden not in s
