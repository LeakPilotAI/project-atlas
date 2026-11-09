"""Version-safe independent UTC source-only; no operational network or orders."""
import pytest
from scripts.observation_runtime import personal_version_safe_release_clock as v


class FakeNtp:
    def __init__(self, *, runtime_id):
        self.runtime_id = runtime_id
        self.closed = False
        self.evidence = {"source": v.SOURCE,
                         "domain": "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS",
                         "financial_authority": False, "bound_ms": 139}

    def require_operational(self, runtime_id):
        if self.closed or runtime_id != self.runtime_id:
            raise ValueError("FAKE_NTP_REVOKED_OR_WRONG_RUNTIME")

    def sample(self):
        self.require_operational(self.runtime_id)
        return {"utc": 1800000000, "source": v.SOURCE}

    def verify(self, sample):
        return not self.closed and type(sample) is dict and sample.get("source") == v.SOURCE

    def runtime_sample(self):
        return {"utc": 1800000000, "source_id": v.SOURCE}

    def verify_runtime_sample(self, sample):
        return not self.closed and type(sample) is dict and sample.get("source_id") == v.SOURCE

    def revoke(self):
        self.closed = True


def make_clock(monkeypatch):
    calls = []
    monkeypatch.setattr(v, "require_native_version_safe_clock_source",
                        lambda *, deep: calls.append(deep) or "native-future-r12-head")
    monkeypatch.setattr(v, "IndependentNtpClock", FakeNtp)
    c = v.NativeVersionSafePaperOperatorClock(runtime_id="SOURCE_ONLY_TEST")
    return c, calls


def test_actual_unselected_workspace_refuses_before_ntp(monkeypatch):
    monkeypatch.setattr(v, "IndependentNtpClock",
                        lambda **kwargs: pytest.fail("NTP request must not precede installed selection"))
    with pytest.raises(ValueError, match="VERSION_SAFE_CLOCK_INSTALLED_SOURCE_REQUIRED"):
        v.NativeVersionSafePaperOperatorClock(runtime_id="SOURCE_ONLY_TEST")


def test_matched_selection_and_clock_functions(monkeypatch):
    c, calls = make_clock(monkeypatch)
    assert calls == [True, False]
    assert c.require_operational("SOURCE_ONLY_TEST") is c
    assert c() == 1800000000
    sample = c.sample()
    assert c.verify(sample)
    assert not c.verify({"source": "unrelated"})
    rt = c.runtime_clock()
    assert rt.verify(rt.sample())
    assert rt() == 1800000000
    assert calls[0] is True and all(x is False for x in calls[1:])
    assert c._revoked is False


def test_selected_release_change_permanently_revokes(monkeypatch):
    c, _ = make_clock(monkeypatch)
    bound = c._bound_clock
    monkeypatch.setattr(v, "require_native_version_safe_clock_source",
                        lambda *, deep: "new-selected-head")
    with pytest.raises(ValueError, match="VERSION_SAFE_CLOCK_NATIVE_OR_NTP_REVOKED"):
        c.sample()
    assert c._revoked and bound.closed
    assert not c.verify({"source": v.SOURCE})
    assert not c.verify_runtime_sample({"source_id": v.SOURCE})


@pytest.mark.parametrize("field,bad", [
    ("source", "WINDOWS_TIME"),
    ("domain", "SINGLE_PEER"),
    ("financial_authority", True),
    ("financial_authority", 0),
    ("bound_ms", 1001),
    ("bound_ms", True),
])
def test_bad_ntp_evidence_permanently_revokes(monkeypatch, field, bad):
    c, _ = make_clock(monkeypatch)
    bound = c._bound_clock
    bound.evidence[field] = bad
    with pytest.raises(ValueError, match="VERSION_SAFE_CLOCK_NATIVE_OR_NTP_REVOKED"):
        c.runtime_sample()
    assert bound.closed and c._revoked


@pytest.mark.parametrize("failure", ["wrong_id", "pid", "ntp_swap", "wrong_type"])
def test_owner_or_object_substitution_revokes(monkeypatch, failure):
    c, _ = make_clock(monkeypatch)
    bound = c._bound_clock
    if failure == "pid": c._pid = -1
    elif failure == "ntp_swap": c._clock = object()
    elif failure == "wrong_type": c._runtime_id = object()
    with pytest.raises(ValueError, match="VERSION_SAFE_CLOCK_OWNER_OR_IDENTITY_CHANGED"):
        c.require_operational("WRONG" if failure == "wrong_id" else "SOURCE_ONLY_TEST")
    assert c._revoked and bound.closed


def test_bad_runtime_id_refuses_without_selector_or_ntp(monkeypatch):
    monkeypatch.setattr(v, "require_native_version_safe_clock_source",
                        lambda **kw: pytest.fail("invalid runtime must refuse before selection"))
    for value in ("", None, 123, "x" * 257):
        with pytest.raises(ValueError, match="VERSION_SAFE_CLOCK_RUNTIME_ID_REQUIRED"):
            v.NativeVersionSafePaperOperatorClock(runtime_id=value)


def test_selector_refusal_never_initializes_ntp(monkeypatch):
    def refuse(*, deep):
        assert deep
        raise ValueError("NATIVE_UNSELECTED")
    monkeypatch.setattr(v, "require_native_version_safe_clock_source", refuse)
    monkeypatch.setattr(v, "IndependentNtpClock",
                        lambda **kw: pytest.fail("NTP should never be initialized"))
    with pytest.raises(ValueError, match="NATIVE_UNSELECTED"):
        v.NativeVersionSafePaperOperatorClock(runtime_id="SOURCE_ONLY_TEST")
