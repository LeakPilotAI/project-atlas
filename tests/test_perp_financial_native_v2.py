"""Actual existing FS2/FS3 interfaces, confined synthetic native resources."""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest
from test_perp_financial_v2 import entry, exit_command, funding, manifest
from test_quality_dips_financial_records_native import TestPins, f


@pytest.fixture(autouse=True)
def confinement(tmp_path):
    root = Path(os.environ["ATLAS_D1_RUN_ROOT"])
    assert root.parent == Path(__file__).resolve().parents[1] / "logs/diagnostics"
    assert root.name.startswith(("qd-d1-financial-records-", "qd-fs3-report-projection-"))
    assert tmp_path.is_relative_to(root)
    assert all(not p.is_symlink() and not p.is_junction() for p in [tmp_path, *tmp_path.parents])


def test_native_perp_ack_projection_and_restart(tmp_path):
    spec = importlib.util.spec_from_file_location("perp_fs3", Path(f.__file__).with_name("financial_reporting.py"))
    reports = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reports)
    source, projection = str(tmp_path / "source"), str(tmp_path / "projection")
    pins = TestPins(f.FinancialRecordStore.provision_disposable(source, manifest()))
    target = reports.ProjectionTarget(projection, reports.ProjectionTarget.provision_disposable(projection))
    pins.now = 3602
    store = f.FinancialRecordStore(source, pins, projection=target)
    try:
        receipt = store.execute(entry(), projection_required=True)
        assert store.execute(entry(), projection_required=True) == receipt
        view = store.snapshot()
        assert view["audit"]["schema"] == "PAPER_PERP_ARITHMETIC_AUDIT_V2"
        assert view["state"]["reserved_margin"] == "25.0"
        store.close()
        store = f.FinancialRecordStore(source, pins, projection=target)
        assert store.snapshot() == view
    finally:
        store.close()
        target.close()


def test_native_perp_commit_before_projection_ack_remains_unknown(tmp_path):
    source = str(tmp_path / "source")
    pins = TestPins(f.FinancialRecordStore.provision_disposable(source, manifest()))
    pins.now = 3602
    store = f.FinancialRecordStore(source, pins)
    try:
        outcome = store.execute(entry(), projection_required=True)
        assert outcome["status"] == "UNKNOWN" and not outcome["fully_acknowledged"]
        with pytest.raises(ValueError): store.execute(entry(), projection_required=True)
    finally:
        store.close()
    with pytest.raises(ValueError): f.FinancialRecordStore(source, pins)


@pytest.mark.parametrize("boundary", ["before-0001-intent.json", "after-0001-intent.json",
    "after-0001-record.json", "after-0001-commit.json", "after-0001-ack.json", "complete"])
def test_abrupt_perp_native_child_never_replays_uncertain_effect(boundary, tmp_path):
    from test_quality_dips_financial_records_native import CHILD, REPO, helper

    source = str(tmp_path / "source")
    pins = TestPins(f.FinancialRecordStore.provision_disposable(source, manifest()))
    pins.now = 3602
    owner = f.FinancialRecordStore(source, pins)
    pin_file = tmp_path / "synthetic-custody.json"
    pin_file.write_text(json.dumps(pins.pin))
    try:
        code, _, err = helper([sys.executable, "-I", "-B", "-c", CHILD, str(REPO), source,
                               str(pin_file), json.dumps(entry()), boundary], tmp_path)
        assert code == (25 if boundary == "complete" else 24), err
        pins.pin = json.loads(pin_file.read_text())
        if boundary == "complete":
            restarted = f.FinancialRecordStore(source, pins)
            try:
                receipt = restarted.execute(entry())
                assert receipt["source_revision"] == 1 and len(pins.pin["entries"]) == 1
            finally:
                restarted.close()
        else:
            for _ in range(2):
                with pytest.raises(ValueError): f.FinancialRecordStore(source, pins)
            assert len(list(Path(source).glob("*-record.json"))) <= 1
    finally:
        owner.close()


@pytest.mark.parametrize("side", ["LONG", "SHORT"])
def test_native_partial_funding_full_exit_immutable_report(side, tmp_path):
    from test_fs3_financial_reporting_native import m

    source, projection, reports = (str(tmp_path / leaf) for leaf in ("source", "projection", "reports"))
    pins = TestPins(f.FinancialRecordStore.provision_disposable(source, manifest()))
    target = m.ProjectionTarget(projection, m.ProjectionTarget.provision_disposable(projection))
    store = f.FinancialRecordStore(source, pins, projection=target)
    scope = {"schema": "FS3_REPORT_SCOPE_V1", "account_id": "synthetic", "epoch": manifest()["epoch"],
             "policy_digest": f.digest(manifest()), "timezone": "UTC"}
    report_pins = TestPins(m.ReportArchive.provision_disposable(reports, scope, manifest()))
    archive = m.ReportArchive(reports, report_pins)
    class View:
        def snapshot(self): return store.snapshot()["state"]
    view = View()
    view.manifest = manifest()
    try:
        pins.now = 3602
        store.execute(entry(side=side), projection_required=True)
        for command in (exit_command(view, "0.2"),):
            pins.now = command["timestamp"]
            store.execute(command, projection_required=True)
        command = funding(view)
        pins.now = command["timestamp"]
        store.execute(command, projection_required=True)
        command = exit_command(view, "0.3", 7202, "final", "104")
        pins.now = command["timestamp"]
        store.execute(command, projection_required=True)
        pins.now = 86400
        service = m.ReportService(store, archive)
        document = service.publish("1970-01-01", 86400)
        assert document == service.publish("1970-01-01", 86400)
        assert service.history() == [document]
        report = document["report"]
        assert report["status"] == "COMPLETE" and not report["open_positions"]
        assert report["currency"] == "USDC" and report["realized"]["funding"] != "0"
        assert report["cash"]["closing"] == store.snapshot()["state"]["cash"]
    finally:
        store.close()
        target.close()
        archive.close()
