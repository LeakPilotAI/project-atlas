"""Synthetic memory/ASGI only; no enrolled account, native writes or listener."""

import copy
import os
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from app.services.personal_paper_runtime import PersonalEnrolledRuntime
from app.services.quality_dips_stop_bridge import PaperStopBridge
from fastapi.testclient import TestClient
from test_personal_paper_runtime import installed
from test_quality_dips_autonomous_enrollment import fixture as enrollment_fixture

from scripts.observation_runtime.personal_paper_read import PersonalReadComposition
from scripts.observation_runtime.quality_dips_read_service import build_app


def setup():
    native = copy.deepcopy(enrollment_fixture().e)
    trace = []
    reader = SimpleNamespace(enrollment={"schema": "QD_AUTO_OP_READ_ENROLLMENT_V1",
                                        "account_id": native["account_id"], "epoch": native["epoch"]})
    payload = {"status": "SYNTHETIC_TEST_READ_NOT_FINANCIAL_EVIDENCE"}

    def read(account, epoch):
        trace.append(("read", account, epoch))
        return copy.deepcopy(payload)

    reader.read_committed = read
    reader.verify = lambda value, **scope: {"verified": value == payload}
    ports = {"reader": reader}
    install = installed(accounts={"QUALITY_DIPS": digest(native)}, ports=ports)
    # READ_ONLY alone must suffice; no automatic financial session is granted.
    install.reader.value["actions"] = ["READ_ONLY"]
    runtime = PersonalEnrolledRuntime.__new__(PersonalEnrolledRuntime)
    runtime._enrollment = body({"execution_domain": "PERSONAL_PAPER"})
    runtime.installation = install.i
    runtime.runtime = SimpleNamespace(reader=reader, engine=SimpleNamespace(clock=install.clock))
    runtime._personal_acceptance = object()
    runtime.admission = SimpleNamespace(enrollment=native, acceptance=runtime._personal_acceptance)
    runtime.financial = SimpleNamespace(components=lambda: trace.append(("native_read_check",)))
    runtime.installation_components = lambda: ports
    identity = {"pid": os.getpid(), "creation_filetime": 12345, "image": "D:\\SYNTHETIC-READER.exe"}
    observer = lambda: copy.deepcopy(identity)
    composition = PersonalReadComposition(runtime=runtime, observer=observer)
    return SimpleNamespace(**locals())


def test_reads_use_actual_bound_reader_and_personal_read_lease_only():
    s = setup()
    assert s.composition.preflight() == s.payload
    assert s.composition.verify(s.payload, account_id=s.native["account_id"],
                                epoch=s.native["epoch"], now=1000) == {"verified": True}
    assert ("read", s.native["account_id"], s.native["epoch"]) in s.trace
    assert {row[0] for row in s.trace} == {"read", "native_read_check"}
    assert s.install.reader.value["actions"] == ["READ_ONLY"]


@pytest.mark.parametrize("runtime", [None, {}, SimpleNamespace()])
def test_uninstalled_strict_or_fixture_objects_do_not_enter_personal_composition(runtime):
    with pytest.raises(ValueError, match="PERSONAL_COMPOSED_RUNTIME_REQUIRED"):
        PersonalReadComposition(runtime=runtime)


@pytest.mark.parametrize("damage", ["reader", "source", "account", "acceptance", "process",
                                    "host", "reader-enrollment", "clock", "revoked", "facts",
                                    "runtime-domain", "presentation-account"])
def test_changed_runtime_scope_or_authority_refuses_before_publishing_read(damage):
    s = setup()
    if damage == "reader":
        s.runtime.runtime.reader = object()
    elif damage == "source":
        s.runtime.admission.enrollment["epoch"] = "FOREIGN_EPOCH"
    elif damage == "account":
        s.install.i.accounts["QUALITY_DIPS"] = "f" * 64
    elif damage == "acceptance":
        s.runtime.admission.acceptance = object()
    elif damage == "process":
        s.identity["creation_filetime"] += 1
    elif damage == "host":
        s.composition.host_id = "changed"
    elif damage == "reader-enrollment":
        s.reader.enrollment["schema"] = "FS2_TEST_PIN_V1"
    elif damage == "clock":
        s.runtime.runtime.engine.clock = lambda: 1000
    elif damage == "revoked":
        s.install.i.revoke()
    elif damage == "facts":
        s.install.facts["FINANCIAL_INTEGRITY"] = False
    elif damage == "runtime-domain":
        s.runtime._enrollment = body({"execution_domain": "DISPOSABLE_TEST"})
    elif damage == "presentation-account":
        s.composition.account = "FOREIGN"
    with pytest.raises(ValueError):
        s.composition.preflight()


def test_revocation_during_read_discards_the_result():
    s = setup()

    def revoke(account, epoch):
        s.install.i.revoke()
        return copy.deepcopy(s.payload)

    s.reader.read_committed = revoke
    with pytest.raises(ValueError):
        s.composition.preflight()


def test_foreign_account_refuses_without_touching_reader():
    s = setup()
    before = list(s.trace)
    with pytest.raises(ValueError, match="ACCOUNT_SCOPE"):
        s.composition.read_committed("FOREIGN", s.native["epoch"])
    assert s.trace == before


def test_existing_host_assets_health_and_default_command_refusal_asgi_only():
    s = setup()
    app = build_app(s.composition, 8765)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        assert client.get("/health").status_code == 200
        response = client.get("/quality_dips.html?mode=selected-paper")
        assert response.status_code == 200 and "Selected PAPER" in response.text
        assert client.get("/static/quality_dips_selected_paper.js").status_code == 200
        assert client.get("/api/investments/quality-dips").status_code == 404
        assert client.post("/api/investments/quality-dips/selected-paper").status_code == 403
        assert client.post("/_atlas/control/stop").status_code == 403
        assert client.get("/health", headers={"Host": "foreign.invalid"}).status_code == 403
    assert {row[0] for row in s.trace} == {"read", "native_read_check"}


def test_read_acceptance_cannot_register_a_financial_stop_bridge():
    s = setup()
    bridge = SimpleNamespace(verify_session=lambda: True)
    with pytest.raises(ValueError, match="SEPARATE_CONTROL_COMPOSITION_ACCEPTANCE_REQUIRED"):
        build_app(s.composition, 8765, control_bridge=bridge, control_token="SYNTHETIC")


def test_personal_stop_requires_retained_owned_close_just_like_strict_runtime():
    s = setup()
    s.runtime.runtime.enrollment = {"process_identity": {"pid": os.getpid(), "created": 12345,
                                                        "image": "D:\\SYNTHETIC-READER.exe"}}
    ownership = SimpleNamespace(verify_session=lambda binding, identity: True)
    with pytest.raises(ValueError, match="PAPER_STOP_RETAINED_OWNED_CLOSE_REQUIRED"):
        PaperStopBridge(runtime=s.runtime, ownership=ownership)


def test_personal_stop_uses_existing_runtime_and_preserves_incomplete_outcome():
    s = setup()
    s.install.reader.value['actions'].append('SHUTDOWN_FLATTEN')
    s.runtime.runtime.enrollment = {"process_identity": {"pid": os.getpid(), "created": 12345,
                                                        "image": "D:\\SYNTHETIC-READER.exe"}}
    calls = []
    outcome = {"status": "SHUTDOWN_INCOMPLETE", "position_state": "POSITION_OPEN"}
    s.runtime.stop = lambda **kwargs: calls.append(kwargs) or copy.deepcopy(outcome)
    closer = object()
    bridge = PaperStopBridge(runtime=s.runtime,
                             ownership=SimpleNamespace(verify_session=lambda binding, identity: True),
                             evidence=object(), owned_close=closer)
    result = bridge.request_stop("SHUTDOWN_FLATTEN")
    assert s.runtime.runtime.engine.entry_admission_closed is True
    assert calls[0]["owned_close"] is closer
    assert result["outcome"] == outcome and result["phase"] == "FINISHED"


def control_setup():
    s = setup()
    s.runtime.runtime.enrollment = {'process_identity': {
        'pid': s.identity['pid'], 'created': s.identity['creation_filetime'], 'image': s.identity['image']}}
    s.calls = []
    s.runtime.stop = lambda **kw: s.calls.append(kw) or {'status': 'SHUTDOWN_INCOMPLETE',
                                                      'position_state': 'POSITION_OPEN'}
    s.bridge = PaperStopBridge(runtime=s.runtime, evidence=object(), owned_close=object(),
                              ownership=SimpleNamespace(verify_session=lambda binding, identity: True))
    return s


def test_explicit_personal_stop_binding_registers_without_dispatching():
    s = control_setup()
    s.install.reader.value['actions'].append('SHUTDOWN_FLATTEN')
    assert s.composition.verify_control_bridge(s.bridge) is True
    app = build_app(s.composition, 8765, control_bridge=s.bridge, control_token='x' * 32)
    assert '/_atlas/control/stop' in {getattr(r, 'path', None) for r in app.routes}
    assert s.calls == []


@pytest.mark.parametrize('damage', ['read-only', 'foreign-runtime', 'process', 'revoked',
                                   'owned-close', 'ownership', 'evidence', 'components'])
def test_personal_stop_requires_current_explicit_scope_and_sealed_ports(damage):
    s = control_setup()
    s.install.reader.value['actions'].append('SHUTDOWN_FLATTEN')
    if damage == 'read-only':
        s.install.reader.value['actions'] = ['READ_ONLY']
    elif damage == 'foreign-runtime':
        s.bridge.runtime = object()
    elif damage == 'process':
        s.runtime.runtime.enrollment['process_identity']['created'] += 1
    elif damage == 'revoked':
        s.install.i.revoke()
    elif damage == 'owned-close':
        s.bridge.owned_close = object()
    elif damage == 'ownership':
        s.bridge.ownership = SimpleNamespace(verify_session=lambda *args: True)
    elif damage == 'evidence':
        s.bridge.evidence = object()
    else:
        s.runtime.installation_components = lambda: {'foreign': object()}
    with pytest.raises((ValueError, AttributeError)):
        s.bridge.request_stop('SHUTDOWN_FLATTEN')
    assert s.calls == []
    assert not getattr(s.runtime.runtime.engine, 'entry_admission_closed', False)


def test_emergency_permission_is_distinct_from_flatten_permission():
    s = control_setup()
    s.install.reader.value['actions'].append('SHUTDOWN_FLATTEN')
    with pytest.raises(ValueError):
        s.bridge.request_stop('EMERGENCY')
    assert s.calls == []
    s.install.reader.value['actions'].append('EMERGENCY_STOP')
    s.bridge.request_stop('EMERGENCY')
    assert s.calls == [{'mode': 'EMERGENCY'}]


def test_revoked_stop_permission_after_host_construction_refuses_dispatch():
    s = control_setup()
    s.install.reader.value['actions'].append('SHUTDOWN_FLATTEN')
    assert s.composition.verify_control_bridge(s.bridge)
    s.install.reader.value['actions'] = ['READ_ONLY']
    with pytest.raises(ValueError):
        s.bridge.request_stop('SHUTDOWN_FLATTEN')
    assert s.calls == []


def test_personal_control_asgi_requires_transport_and_current_action_permission():
    s = control_setup()
    s.install.reader.value['actions'].append('SHUTDOWN_FLATTEN')
    token = 'synthetic-transport-test-' + 'x' * 32
    app = build_app(s.composition, 8765, control_bridge=s.bridge, control_token=token)
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 50000)) as client:
        path = '/_atlas/control/stop'
        headers = {'Origin': 'http://127.0.0.1:8765', 'x-atlas-control': token}
        assert client.post(path, json={'mode': 'SHUTDOWN_FLATTEN'}).status_code == 403
        assert s.calls == []
        result = client.post(path, headers=headers, json={'mode': 'SHUTDOWN_FLATTEN'})
        assert result.status_code == 200
        assert result.json()['outcome']['position_state'] == 'POSITION_OPEN'
        assert len(s.calls) == 1
        s.install.reader.value['actions'] = ['READ_ONLY']
        assert client.post(path, headers=headers, json={'mode': 'SHUTDOWN_FLATTEN'}).status_code == 409
        assert len(s.calls) == 1


def test_permission_revoked_during_stop_cannot_publish_finished_outcome():
    s = control_setup()
    s.install.reader.value['actions'].append('SHUTDOWN_FLATTEN')
    def stop(**kw):
        s.calls.append(kw)
        s.install.i.revoke()
        return {'status': 'STOPPED', 'position_state': 'FLAT'}
    s.runtime.stop = stop
    with pytest.raises(ValueError):
        s.bridge.request_stop('SHUTDOWN_FLATTEN')
    assert len(s.calls) == 1
    assert s.bridge.progress == {'schema': 'QD_CONTROL_STOP_V1', 'phase': 'REFUSED', 'outcome': None}
