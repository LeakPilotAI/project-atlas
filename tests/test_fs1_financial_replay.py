import ast
import copy
import json
from decimal import localcontext
from pathlib import Path

import pytest
from app.services import paper_financial_replay as replay
from app.services.paper_epoch_fixture import create_epoch_fixture
from app.services.paper_financial_audit import audit_financial_events

GOLDEN = json.loads((Path(__file__).parent / "fixtures/fs1/legacy-synthetic-golden.json").read_text(encoding="utf-8"))["cases"]


def records(case):
    return [replay.event_stream_record(*row) for row in case["sql_rows"]]


@pytest.mark.parametrize("case", GOLDEN, ids=["quality", "perps"])
def test_retained_event_receipt_head_snapshot_and_report_bytes(case, tmp_path):
    original = copy.deepcopy(case)
    state, head, ops = replay.replay_verified_events(case["manifest"], records(case))
    assert head == case["head"]
    assert all(case["snapshot"][k] == v for k, v in state.items())
    assert [replay.body(r) for _, r in ops.values()] == [row[5] for row in case["sql_rows"]]
    audit = audit_financial_events(case["manifest"], records(case), case["snapshot"])
    assert audit["source_revision"] == 3 and not audit["startup_authorized"]
    store = create_epoch_fixture(tmp_path / "compat.sqlite", case["manifest"])
    for row in case["sql_rows"]:
        assert replay.body(store.execute(replay.strict(row[2]))) == row[5]
    assert store.snapshot() == case["snapshot"]
    assert replay.body(store.daily_report("2026-10-23")) == case["report_bytes"]
    assert case == original


@pytest.mark.parametrize("precision", [6, 28, 50])
def test_computation_and_audit_do_not_depend_on_ambient_decimal_context(precision):
    case = GOLDEN[1]
    with localcontext() as context:
        context.prec = precision
        state, head, _ = replay.replay_verified_events(case["manifest"], records(case))
        assert state["net_r"] == case["snapshot"]["net_r"] and head == case["head"]
        assert audit_financial_events(case["manifest"], records(case), case["snapshot"])["position_count"] == 1
        assert context.prec == precision


def test_failed_transition_does_not_mutate_previous_state_or_command():
    case = GOLDEN[0]
    state = replay.initial_state(case["manifest"])
    command = replay.strict(case["sql_rows"][0][2])
    before = copy.deepcopy((state, command))
    command["quantity"] = "1000000"
    original_command = copy.deepcopy(command)
    with pytest.raises(ValueError): replay.apply_event(case["manifest"], state, command)
    assert state == before[0] and command == original_command
    command = before[1]
    next_state, _ = replay.apply_event(case["manifest"], state, command)
    next_state["positions"].clear()
    assert state == before[0]


@pytest.mark.parametrize("damage", ["schema", "revision-bool", "receipt", "hash", "parent", "missing",
    "duplicate", "projection-flag", "receipt-schema", "receipt-source-bool", "epoch", "duplicate-json"])
def test_malformed_or_conflicting_stream_never_replays(damage):
    case = GOLDEN[0]
    rows = records(case)
    if damage == "schema": rows[0]["schema"] = "FUTURE"
    if damage == "revision-bool": rows[0]["revision"] = True
    if damage == "receipt": rows[0]["receipt"] = "{"
    if damage == "hash": rows[0]["digest"] = "f" * 64
    if damage == "parent": rows[1]["parent"] = "f" * 64
    if damage == "missing": rows.pop(1)
    if damage == "duplicate": rows.append(copy.deepcopy(rows[0]))
    if damage in ("projection-flag", "receipt-schema", "receipt-source-bool"):
        r = replay.strict(rows[0]["receipt"])
        if damage == "projection-flag": r["projection_required"] = "false"
        elif damage == "receipt-schema": r["schema"] = "FUTURE"
        else: r["source_revision"] = True
        rows[0]["receipt"] = replay.body(r)
    if damage == "epoch":
        c = replay.strict(rows[0]["command"]); c["epoch"] = "foreign"; rows[0]["command"] = replay.body(c)
    if damage == "duplicate-json": rows[0]["receipt"] = '{"schema":"a","schema":"b"}'
    with pytest.raises((ValueError, TypeError, KeyError)):
        replay.replay_verified_events(case["manifest"], rows)


@pytest.mark.parametrize("field", ["cash", "gross", "costs", "net", "net_r", "revision", "quantity",
    "remaining", "entry", "side", "symbol", "position-revision", "missing-position", "bool-revision", "bool-position-revision"])
def test_independent_arithmetic_refuses_contradictory_totals_and_inventory(field):
    case = GOLDEN[1]
    snapshot = copy.deepcopy(case["snapshot"])
    rows = records(case)
    if field in ("bool-revision", "bool-position-revision"):
        rows = rows[:1]
        snapshot = replay.replay_verified_events(case["manifest"], rows)[0]
    position = next(iter(snapshot["positions"].values()))
    if field in ("cash", "gross", "costs", "net", "net_r"): snapshot[field] = "9999"
    elif field == "revision": snapshot[field] += 1
    elif field in ("quantity", "remaining", "entry"): position[field] = "9999"
    elif field in ("side", "symbol"): position[field] = "WRONG"
    elif field == "position-revision": position["revision"] += 1
    elif field == "bool-revision": snapshot["revision"] = True
    elif field == "bool-position-revision": position["revision"] = True
    else: snapshot["positions"].clear()
    before = copy.deepcopy(snapshot)
    with pytest.raises(ValueError): audit_financial_events(case["manifest"], rows, snapshot)
    assert snapshot == before


@pytest.mark.parametrize("field", ["record-revision", "receipt-revision"])
def test_independent_audit_rejects_boolean_stream_revisions(field):
    case = GOLDEN[0]
    rows = records(case)
    if field == "record-revision": rows[0]["revision"] = True
    else:
        r = replay.strict(rows[0]["receipt"]); r["source_revision"] = True; rows[0]["receipt"] = replay.body(r)
    with pytest.raises(ValueError): audit_financial_events(case["manifest"], rows, case["snapshot"])


def test_arithmetic_audit_does_not_call_transition_or_replay_engine(monkeypatch):
    def forbidden(*args):
        pytest.fail("Independent audit must not use financial transition/replay")
    monkeypatch.setattr(replay, "_transition_in_place", forbidden)
    monkeypatch.setattr(replay, "replay_verified_events", forbidden)
    for case in GOLDEN:
        assert audit_financial_events(case["manifest"], records(case), case["snapshot"])["production_authorized"] is False


def test_no_storage_service_provider_or_startup_imports():
    root = Path(__file__).resolve().parents[1] / "backend/app/services"
    for name in ("paper_financial_replay.py", "paper_financial_audit.py"):
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        modules += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any(any(word in (m or "") for word in ("sqlite", "pathlib", "os", "paper_epoch_fixture", "main", "provider")) for m in modules)
