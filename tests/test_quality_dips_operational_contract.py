"""In-memory schema fixtures are not enrollment, custody or native acceptance."""
import copy
import importlib.util
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.investment import quality_dips_operational_contract as c


def fixture():
    p = {"schema": "QD_OP_ACCOUNT_POLICY_V1", "scope": "OPERATIONAL_ACCEPTANCE_REQUIRED",
             "universe": "ELIGIBLE_QD_RANKED_STOCKS_ETFS", "max_entry_usd": "100", "max_positions": 1,
             "manual_only": True, "long_only": True, "scale_in": False, "overnight": True,
             "cost_assumptions": "SYNTHETIC_2BPS_FEE_2BPS_SLIPPAGE_PER_SIDE"}
    a = {"schema": "QD_OP_ACCOUNT_V1", "account_id": "synthetic-account", "epoch": "synthetic-epoch",
             "currency": "USD", "hypothetical_opening_cash": "1000", "policy_digest": c.digest(p)}
    resources = {role: {"schema": "QD_OP_RESOURCE_ID_V1", "resource_id": role, "role": role,
                           "root_path": "D:\\synthetic\\" + role, "native_root": [1, 2, i]}
                 for i, role in enumerate(c.ROLES, 3)}
    e = {"schema": c.ENROLLMENT, "enrollment_id": "not-real-enrollment", "workstation_id": "synthetic",
             "account": a, "policy": p, "resources": resources}
    proc = {"schema": "QD_OP_PROCESS_ID_V1", "pid": os.getpid(), "creation_filetime": 100, "image": "synthetic.exe"}
    def bound(schema, value, i):
        return {"schema": "QD_OP_FILE_BINDING_V1", "native_id": [1, 3, i], "sha256": c.digest(value), "record_schema": schema}
    source = {"schema": "QD_OP_SOURCE_PIN_V1", "resource_id": "source", "native_root": resources["source"]["native_root"],
                  "revision": 0, "inception": bound(a["schema"], a, 1), "records": [], "head_digest": c.digest(a)}
    docs = {"schema": "QD_OP_DOCUMENTS_V1", "projection": {"schema": "QD_OP_PROJECTION_DOCUMENT_V1",
                "enrollment_digest": c.digest(e), "source_pin_digest": c.digest(source), "revision": 0,
                "state": {"revision": 0, "cash": "1000", "gross": "0", "costs": "0", "net": "0", "positions": {}}},
                "report": {"schema": "QD_OP_REPORT_DOCUMENT_V1", "enrollment_digest": c.digest(e),
                            "source_pin_digest": c.digest(source), "revision": 0, "status": "COMPLETE"}}
    current = {"schema": "QD_OP_CURRENT_V1", "enrollment_digest": c.digest(e), "generation": 1, "revision": 0,
                   "acknowledged_revision": 0, "status": "ACKNOWLEDGED", "source": source}
    for i, role in enumerate(("projection", "report"), 2):
        current[role] = {"schema": "QD_OP_" + role.upper() + "_PIN_V1", "resource_id": role,
            "native_root": resources[role]["native_root"], "revision": 0, "source_pin_digest": c.digest(source),
            "record": bound(docs[role]["schema"], docs[role], i)}
    clock = {"schema": "QD_OP_CLOCK_V1", "clock_id": "synthetic", "sequence": 1, "issued_at": 100, "expires_at": 130}
    session = {"schema": "QD_OP_READ_SESSION_V1", "enrollment_digest": c.digest(e), "host_id": "a" * 32,
                   "acceptance_id": "not-real-acceptance", "acceptance": "ACCEPTED_READ_ONLY",
                   "process": proc, "capabilities": ["READ_ONLY"], "issued_at": 100, "expires_at": 130}
    bundle = {"schema": "QD_OP_READ_BUNDLE_V1", "current": current, "clock": clock, "session": session,
                  "authority": {"schema": "QD_OP_AUTHORITY_V1", "issuer_id": "not-an-issuer", "custody_id": "test-only",
                                 "enrollment_digest": c.digest(e), "current_digest": c.digest(current),
                                 "clock_digest": c.digest(clock), "session_digest": c.digest(session),
                                 "capabilities": ["READ_ONLY"], "issued_at": 100, "expires_at": 130}}
    x = SimpleNamespace(e=e, b=bundle, docs=docs, process=proc, now=100, calls=0, trusted=True, native=True)
    @contextmanager
    def lease(enrollment, now):
        assert enrollment == e
        captured = copy.deepcopy(x.b)
        yield SimpleNamespace(snapshot=captured, check=lambda value, t: x.trusted and value == captured)
    def read(enrollment, pin):
        x.calls += 1
        return copy.deepcopy(x.docs)
    x.authority = SimpleNamespace(lease=lease)
    x.port = SimpleNamespace(read_operational=read, verify_operational=lambda *args: x.native)
    x.cap = c.OperationalReadCapability(enrollment=e, authority=x.authority, clock=lambda: x.now,
        port=x.port, process_identity=proc, host_id="a" * 32)
    return x


def read(x):
    return x.cap.read_committed("synthetic-account", "synthetic-epoch")


def test_structural_and_authenticated_fixture_read():
    from app.api.quality_dips_selected_paper import financial_view

    x = fixture()
    c.validate_bundle(x.e, x.b, 100, x.process, "a" * 32)
    result = read(x)
    assert result["state"]["cash"] == "1000" and result["inception"]["policy_schema"] == "QD_OP_ACCOUNT_POLICY_V1"
    assert x.calls == 1 and result["report_status"] == "COMPLETE"
    view = financial_view(reader=x.cap, verifier=x.cap, clock=lambda: x.now,
                          account_id="synthetic-account", epoch="synthetic-epoch")
    assert view["status"] == "ACKNOWLEDGED" and view["cash"] == "1000"
    assert view["startup_authorized"] is False and view["valuation"] is None


@pytest.mark.parametrize("path,value", [
    (("schema",), "QD_READ_CURRENT_V1"),
    (("current", "schema"), "FS2_TEST_PIN_V1"),
    (("current", "source", "schema"), "FS2_TEST_PIN_V1"),
    (("current", "projection", "schema"), "FS3_REPORT_PIN_V1"),
    (("current", "status"), "UNKNOWN"),
    (("current", "revision"), True),
    (("current", "acknowledged_revision"), 1),
    (("current", "source", "native_root"), [True, 2, 3]),
    (("current", "source", "head_digest"), "f" * 64),
    (("current", "source", "inception", "record_schema"), "PAPER_EPOCH_SELECTED_QD_V3"),
    (("current", "projection", "resource_id"), "foreign"),
    (("current", "projection", "revision"), 1),
    (("session", "process", "pid"), 42),
    (("session", "process", "creation_filetime"), True),
    (("session", "host_id"), "b" * 32),
    (("session", "capabilities"), ["WRITE"]),
    (("session", "acceptance"), "INCOMPLETE"),
    (("session", "acceptance_id"), ""),
    (("session", "expires_at"), 99),
    (("authority", "expires_at"), 99),
    (("authority", "issued_at"), 101),
    (("authority", "current_digest"), "f" * 64),
    (("authority", "capabilities"), ["READ_ONLY", "WRITE"]),
    (("clock", "schema"), "QD_OP_CLOCK_V2"),
    (("clock", "sequence"), False),
    (("clock", "expires_at"), 99),
    (("clock", "expires_at"), 131),
])
def test_bad_bundle_refuses_before_resource_consumption(path, value):
    x = fixture()
    node = x.b
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValueError):
        read(x)
    assert x.calls == 0


@pytest.mark.parametrize("damage", ["test", "extra", "missing", "policy", "capital", "alias", "overlap", "unc", "relative"])
def test_bad_enrollment(damage):
    x = fixture()
    e = copy.deepcopy(x.e)
    if damage == "test": e["schema"] = "QD_READ_ENROLLMENT_V1"
    if damage == "extra": e["approved"] = True
    if damage == "missing": del e["workstation_id"]
    if damage == "policy": e["policy"]["scope"] = "DISPOSABLE_ONLY"
    if damage == "capital": e["account"]["hypothetical_opening_cash"] = "2000"
    if damage == "alias": e["resources"]["report"]["native_root"] = e["resources"]["source"]["native_root"]
    if damage == "overlap": e["resources"]["report"]["root_path"] = e["resources"]["source"]["root_path"] + "\\reports"
    if damage == "unc": e["resources"]["report"]["root_path"] = "\\\\server\\share"
    if damage == "relative": e["resources"]["report"]["root_path"] = "D:\\a\\..\\b"
    with pytest.raises(ValueError): c.validate_enrollment(e)


def test_structural_validity_is_not_authentication():
    x = fixture()
    x.trusted = False
    with pytest.raises(ValueError, match="AUTHENTICATION_REQUIRED"): read(x)
    assert x.calls == 0


def test_old_test_reader_is_never_adapted():
    x = fixture()
    x.cap.port = SimpleNamespace(read_verified=lambda *args: pytest.fail("test reader consumed"))
    with pytest.raises(TypeError, match="NATIVE_READ_ADAPTER_REQUIRED"): read(x)
    assert x.calls == 0


@pytest.mark.parametrize("damage", ["tamper", "native", "unknown", "wrong_schema", "expired", "rollback"])
def test_post_read_refusals(damage):
    x = fixture()
    if damage == "tamper": x.docs["projection"]["state"]["cash"] = "5000"
    if damage == "unknown": x.docs["report"]["status"] = "UNKNOWN"
    if damage == "wrong_schema": x.docs["projection"]["schema"] = "FS3_REPORT_V1"
    if damage == "native": x.native = False
    if damage in ("expired", "rollback"):
        original = x.port.read_operational
        def change(*args):
            result = original(*args)
            x.now = 131 if damage == "expired" else 99
            return result
        x.port.read_operational = change
    with pytest.raises(ValueError): read(x)
    assert x.calls == 1


def test_composition_operational_context_and_no_default_authority():
    path = Path(__file__).resolve().parents[1] / "scripts/observation_runtime/quality_dips_read_service.py"
    spec = importlib.util.spec_from_file_location("op_contract_composition", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    x = fixture()
    seen = []
    @contextmanager
    def accepted(context, now):
        seen.append(context)
        yield SimpleNamespace(check=lambda value, t: value == context)
    kwargs = {"account_id": "synthetic-account", "epoch": "synthetic-epoch", "enrollment": x.e,
                  "custody": x.authority, "clock": lambda: x.now, "resources": x.port,
                  "acceptance": SimpleNamespace(lease=accepted), "observer": lambda: {k: v for k, v in x.process.items() if k != "schema"}}
    composition = module.ReadComposition(**kwargs)
    x.b["session"]["host_id"] = composition.host_id
    x.b["authority"]["session_digest"] = c.digest(x.b["session"])
    assert composition.preflight()["state"]["cash"] == "1000"
    assert seen[0]["schema"] == "QD_OP_READ_SERVICE_CONTEXT_V1"
    assert seen[0]["process"] == x.process
    with pytest.raises(ValueError): module.ReadComposition(**{**kwargs, "custody": None})
    mixed = {**x.e, "schema": "QD_OP_ENROLLMENT_V99"}
    with pytest.raises(ValueError): module.ReadComposition(**{**kwargs, "enrollment": mixed})


@pytest.mark.parametrize("dependency", ["authority", "clock", "port"])
def test_missing_independent_dependencies(dependency):
    x = fixture()
    args = {"enrollment": x.e, "authority": x.authority, "clock": lambda: 100,
            "port": x.port, "process_identity": x.process, "host_id": "a" * 32}
    args[dependency] = None
    with pytest.raises(ValueError, match="AUTHORITY_REQUIRED"):
        c.OperationalReadCapability(**args)


def test_custody_revocation_during_read_refuses_return():
    x = fixture()
    original = x.port.read_operational
    def revoke(*args):
        value = original(*args)
        x.trusted = False
        return value
    x.port.read_operational = revoke
    with pytest.raises(ValueError, match="CONTINUITY_LOST"): read(x)
    assert x.calls == 1


def test_immutable_captured_account_and_process():
    x = fixture()
    x.e["account"]["account_id"] = "caller-substituted"
    x.process["pid"] = 12
    assert x.cap.account["account_id"] == "synthetic-account"
    assert x.cap.process["pid"] == os.getpid()


def test_incomplete_report_remains_explicit_not_complete():
    x = fixture()
    x.docs["report"]["status"] = "INCOMPLETE"
    x.b["current"]["report"]["record"]["sha256"] = c.digest(x.docs["report"])
    x.b["authority"]["current_digest"] = c.digest(x.b["current"])
    assert read(x)["report_status"] == "INCOMPLETE"


def test_fixed_independent_custody_rejects_coherent_local_rollback():
    x = fixture()
    expected = c.digest(x.b["current"])
    @contextmanager
    def pinned(enrollment, now):
        yield SimpleNamespace(snapshot=x.b, check=lambda b, t: c.digest(b["current"]) == expected)
    x.cap.authority = SimpleNamespace(lease=pinned)
    x.b["current"]["generation"] = 2
    x.b["authority"]["current_digest"] = c.digest(x.b["current"])
    with pytest.raises(ValueError, match="AUTHENTICATION_REQUIRED"): read(x)
    assert x.calls == 0


def test_no_operational_writer_or_test_pin_conversion_surface():
    x = fixture()
    assert not any(hasattr(x.cap, method) for method in ("write", "commit", "initialize", "repair", "recover", "command"))
    original = c.body(x.b)
    read(x)
    assert c.body(x.b) == original
