"""V7 installed Quality Dips composition: explicit clock profile, no financial effects.

Synthetic offline objects stop at strict dependency boundaries. They never
create a native account, read a private provider, or publish a session.
"""
from types import SimpleNamespace

import pytest

from scripts.observation_runtime.personal_paper_activation import (
    NativePersonalActivationReader, compose_installed_personal_qd,
)
from scripts.observation_runtime.personal_v7_operator_clock import (
    NativeV7PaperOperatorClock, PROFILE as V7_PROFILE,
)
from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
from test_personal_paper_runtime import installed
from test_personal_runtime_current_memory import system


def synthetic_call(monkeypatch, clock, profile, **changes):
    i = installed()
    mem = system()
    i.i.reader = object.__new__(NativePersonalActivationReader)
    params = {
        "policy": i.p,
        "enrollment": mem.n,
        "runtime_dependencies": {
            "engine": SimpleNamespace(ledger=object()),
            "custody": object(),
        },
        "native_dependencies": {"custody": object()},
        "store": object(),
        "native_reader": object(),
        "installation": i.i,
        "local_clock": clock,
        "runtime_id": "SYNTHETIC_V7_COMPOSITION",
        "clock_profile": profile,
    }
    params.update(changes)
    try:
        return compose_installed_personal_qd(**params)
    finally:
        mem.ledger.db.close()


def test_v7_explicit_profile_reaches_custody_binding_without_native_effects(monkeypatch):
    ticks = []
    monkeypatch.setattr(NativeV7PaperOperatorClock, "require_operational",
                        lambda self, runtime: ticks.append(runtime))
    clock = object.__new__(NativeV7PaperOperatorClock)
    with pytest.raises(ValueError, match="CURRENT_CUSTODY_BINDING"):
        synthetic_call(monkeypatch, clock, V7_PROFILE)
    assert ticks == ["SYNTHETIC_V7_COMPOSITION"]


@pytest.mark.parametrize("profile", [
    None, "", "INDEPENDENT_TWO_PEER_NTP", "FINANCIAL_OVERRIDE",
    "WINDOWS_TIME_OPERATOR_CLOCK_V4", True,
])
def test_v7_clock_cannot_be_silently_admitted_under_other_profiles(monkeypatch, profile):
    monkeypatch.setattr(NativeV7PaperOperatorClock, "require_operational",
                        lambda self, runtime: pytest.fail("unreviewed NTP activated"))
    clock = object.__new__(NativeV7PaperOperatorClock)
    with pytest.raises(ValueError, match="INSTALLED_NATIVE_DEPENDENCIES_REQUIRED"):
        synthetic_call(monkeypatch, clock, profile)


@pytest.mark.parametrize("wrong", [object(), None, "not-a-clock"])
def test_v7_profile_rejects_foreign_clock_types_before_custody(monkeypatch, wrong):
    with pytest.raises(ValueError, match="INSTALLED_NATIVE_DEPENDENCIES_REQUIRED"):
        synthetic_call(monkeypatch, wrong, V7_PROFILE)


def test_legacy_clock_profile_remains_default_and_reaches_same_custody_guard(monkeypatch):
    clocks = []
    monkeypatch.setattr(LocalWindowsClock, "require_operational",
                        lambda self, runtime: clocks.append(runtime))
    clock = object.__new__(LocalWindowsClock)
    with pytest.raises(ValueError, match="CURRENT_CUSTODY_BINDING"):
        synthetic_call(monkeypatch, clock, "WINDOWS_TIME_OPERATOR_CLOCK_V4")
    assert clocks == ["SYNTHETIC_V7_COMPOSITION"]
    with pytest.raises(ValueError, match="INSTALLED_NATIVE_DEPENDENCIES_REQUIRED"):
        synthetic_call(monkeypatch, clock, V7_PROFILE)


def test_missing_inputs_never_query_clock_or_native_store(monkeypatch):
    monkeypatch.setattr(NativeV7PaperOperatorClock, "require_operational",
                        lambda self, runtime: pytest.fail("missing inputs acquired clock"))
    clock = object.__new__(NativeV7PaperOperatorClock)
    with pytest.raises(ValueError, match="INSTALLED_NATIVE_DEPENDENCIES_REQUIRED"):
        compose_installed_personal_qd(local_clock=clock, clock_profile=V7_PROFILE)
    with pytest.raises(ValueError, match="INSTALLED_NATIVE_DEPENDENCIES_REQUIRED"):
        compose_installed_personal_qd()


def test_explicit_profile_links_operator_runtime_and_technical_exactly():
    from pathlib import Path
    source = Path(__import__(
        "scripts.observation_runtime.personal_paper_activation", fromlist=["x"]
    ).__file__).read_text(encoding="utf-8-sig")
    assert "type(local_clock) is NativeV7PaperOperatorClock" in source
    assert "type(local_clock) is LocalWindowsClock" in source
    assert "authority.clock is not local_clock or authority.clock_profile != clock_profile" in source
    assert "authority.runtime_id != runtime_id" in source
    assert "technical.clock_profile != clock_profile" in source
    assert "technical.current is not custody or technical.engine is not engine" in source
    assert "financial_authority.engine is not engine" in source
    assert "native_reader.verify_resources()" in source
    assert "ledger.connect(readonly=True)" in source
    assert "return compose_personal_qd(" in source


@pytest.mark.parametrize("damage,expected", [
    ("operator_profile", "PERSONAL_INSTALLED_SESSION_OR_WRITER_BINDING"),
    ("operator_runtime", "PERSONAL_INSTALLED_SESSION_OR_WRITER_BINDING"),
    ("technical_profile", "PERSONAL_INSTALLED_FACTUAL_TECHNICAL_CHECKS_REQUIRED"),
])
def test_v7_deep_assembly_refuses_mixed_profile_before_financial_read(
    monkeypatch, damage, expected
):
    """Synthetic classes enable deeper same-object admission without real native I/O."""
    from app.services.paper_financial_replay import digest
    from app.services import quality_dips_autonomous_enrollment as enrollment_mod
    from app.services import personal_native_coordination as ledger_mod
    from app.services import quality_dips_personal_dependencies as session_mod
    from scripts.observation_runtime import personal_runtime_current as custody_mod
    from scripts.observation_runtime import personal_coordination_store as image_mod
    from scripts.observation_runtime import personal_local_authority as operator_mod
    from scripts.observation_runtime import personal_writer_ownership as ownership_mod
    from scripts.observation_runtime import personal_installation_technical as technical_mod
    from pathlib import Path

    class FakeCustody: pass
    class FakeNativeLedger: pass
    class FakeNativeImages: pass
    class FakeOperator: pass
    class FakeOwner: pass
    class FakeSessions: pass
    class FakeTechnical: pass

    for module, attr, fake in (
        (custody_mod, "PersonalRuntimeCurrent", FakeCustody),
        (ledger_mod, "PersonalNativeCoordination", FakeNativeLedger),
        (image_mod, "NativePersonalCoordinationImages", FakeNativeImages),
        (operator_mod, "NativePersonalOperatorAuthority", FakeOperator),
        (ownership_mod, "NativePersonalWriterOwnership", FakeOwner),
        (session_mod, "PersonalSessionReservations", FakeSessions),
        (technical_mod, "NativePersonalTechnicalChecks", FakeTechnical),
    ):
        monkeypatch.setattr(module, attr, fake)

    e = {
        "resources": {"coordination": {
            "native_id": [1, 2, 3],
            "path": "D:\\\\AtlasPaper\\\\Coordination",
        }},
        "inception_digest": digest({}),
    }
    monkeypatch.setattr(enrollment_mod, "validate_enrollment", lambda _: e)
    native_reader = SimpleNamespace(enrollment=e)
    installation = installed().i
    installation.reader = object.__new__(NativePersonalActivationReader)
    clock = object.__new__(NativeV7PaperOperatorClock)
    clock_checks = []
    monkeypatch.setattr(NativeV7PaperOperatorClock, "require_operational",
                        lambda self, runtime: clock_checks.append(runtime))

    ledger = FakeNativeLedger()
    ledger.manifest = {}
    ledger.images = FakeNativeImages()
    ledger.images.root_id = [1, 2, 3]
    ledger.images.enrollment = digest(e)
    ledger.images.root = e["resources"]["coordination"]["path"]
    ledger.path = Path(ledger.images.root) / "personal-coordination.sqlite"

    engine = SimpleNamespace(ledger=ledger, clock=clock)
    native_source = SimpleNamespace(ledger=ledger)
    native_reports = SimpleNamespace(ledger=ledger)
    store = SimpleNamespace(trust=native_source)
    reports = SimpleNamespace(archive=SimpleNamespace(trust=native_reports))
    reader = object()
    custody = FakeCustody()
    custody.source, custody.reports = native_source, native_reports
    custody.reader, custody.native_reader, custody.clock = reader, native_reader, clock
    custody.bootstrap = object()

    operator = FakeOperator()
    operator.reader = installation.reader
    operator.clock = clock
    operator.enrollment = e
    operator.runtime_id = (
        "FOREIGN_RUNTIME" if damage == "operator_runtime" else "SYNTHETIC_V7_COMPOSITION")
    operator.clock_profile = (
        "WINDOWS_TIME_OPERATOR_CLOCK_V4" if damage == "operator_profile" else V7_PROFILE)
    owner = FakeOwner()
    owner.authority, owner.ledger, owner.enrollment = operator, ledger, e
    owner.read_only = False
    sessions = FakeSessions()
    sessions.ledger, sessions.authorization = ledger, operator
    technical = FakeTechnical()
    technical.bootstrap, technical.ownership = custody.bootstrap, owner
    technical.ledger, technical.clock = ledger, clock
    technical.runtime_id = "SYNTHETIC_V7_COMPOSITION"
    technical.clock_profile = (
        "WINDOWS_TIME_OPERATOR_CLOCK_V4" if damage == "technical_profile" else V7_PROFILE)
    technical.current, technical.engine = custody, engine
    installation.identity, installation.technical = operator, technical

    runtime = {"engine": engine, "custody": custody,
               "reports": reports, "reader": reader, "ownership": owner}
    native = {"custody": custody, "clock": clock,
              "ownership": owner, "sessions": sessions}
    with pytest.raises(ValueError, match=expected):
        compose_installed_personal_qd(
            policy=installation.policy, enrollment=e, runtime_dependencies=runtime,
            native_dependencies=native, store=store, native_reader=native_reader,
            installation=installation, local_clock=clock,
            runtime_id="SYNTHETIC_V7_COMPOSITION", clock_profile=V7_PROFILE)
    assert clock_checks == ["SYNTHETIC_V7_COMPOSITION"]
    assert not hasattr(ledger, "connect")
    assert not hasattr(native_source, "publish")
