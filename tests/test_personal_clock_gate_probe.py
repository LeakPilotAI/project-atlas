from scripts.observation_runtime.personal_clock_gate_probe import inspect_personal_clock_gate


def test_probe_never_grants_activation(monkeypatch):
    import scripts.observation_runtime.personal_windows_clock as mod

    class FakeClock:
        revoked = False
        def __init__(self, **kwargs):
            assert kwargs["expected_source"] == "time.windows.com,0x9"
            self.evidence = {"bound_ms": 349, "domain": "LOCAL_WINDOWS"}
        def revoke(self):
            FakeClock.revoked = True

    monkeypatch.setattr(mod, "LocalWindowsClock", FakeClock)
    result = inspect_personal_clock_gate()
    assert result["trusted_clock_verified_for_probe"] is True
    assert result["uncertainty_ms"] == 349
    assert result["forward_financial_write_authorized"] is False
    assert result["native_activation_verified"] is False
    assert FakeClock.revoked


def test_probe_reports_clock_blocker_without_authority(monkeypatch):
    import scripts.observation_runtime.personal_windows_clock as mod

    class BlockedClock:
        def __init__(self, **kwargs):
            raise ValueError("CLOCK_UNCERTAINTY_EXCEEDED:1180ms")

    monkeypatch.setattr(mod, "LocalWindowsClock", BlockedClock)
    result = inspect_personal_clock_gate()
    assert result["trusted_clock_verified_for_probe"] is False
    assert result["blocker"] == "CLOCK_UNCERTAINTY_EXCEEDED"
    assert result["operator_lease_verified"] is False
