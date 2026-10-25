"""Operational-schema native records with explicitly synthetic confined trust."""
import copy
import importlib.util
import os
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from app.services.perp_operational_contract import validate_enrollment
from app.services.unified_native_writer import OperationalPerpFinancialWriter
from test_perp_financial_v2 import entry, exit_command, funding, manifest
from test_quality_dips_autonomous_enrollment import fixture


@pytest.fixture
def system(tmp_path):
    root = Path(os.environ["ATLAS_PERP_OP_TEST_ROOT"])
    repo = Path(__file__).resolve().parents[1]
    assert root.parent == repo / 'logs/diagnostics' and root.name.startswith('perp-op-codec-')
    assert tmp_path.is_relative_to(root)
    spec = importlib.util.spec_from_file_location('perp_op_test', repo / 'scripts/volume_inspector/operational_perp_store.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    e = fixture().e
    e['schema'] = 'PERP_AUTO_NATIVE_ENROLLMENT_V1'
    e['writers'].update(funding=copy.deepcopy(e['writers']['source']), mark=copy.deepcopy(e['writers']['source']))
    params = manifest()
    params.update(schema='PAPER_EPOCH_PERP_OPERATIONAL_V1', release=e['release_digest'], provenance='ACCEPTED_PERP_PAPER_PARAMETERS_V1')
    e.update(epoch=params['epoch'], account_id='synthetic-perp-account', inception_digest=digest(params), policy_digest=digest(params['perp_policy']))
    fs2 = module.base.fs2
    for role, resource in e['resources'].items():
        with fs2.w.WindowsOutput.create_root(str(tmp_path / role)) as out:
            resource.update(schema='PERP_AUTO_NATIVE_ROOT_V1', path=str(out.root), native_id=fs2.native.file_identity(out.root_handle))
    document = {"schema": 'PERP_AUTO_OP_INCEPTION_V1', "enrollment_digest": digest(e), "parameters": params, "execution": 'SIMULATED'}
    with fs2.w.WindowsOutput(str(tmp_path / 'source')) as out:
        inception = out.write_bound('inception.json', body(document).encode())
    pin = {"schema": 'PERP_AUTO_OP_PIN_V1', "root": e['resources']['source']['native_id'], "inception": inception, "epoch": e['epoch'], "entries": []}
    now, flags = [3602], {"accepted": True, "ack": True, "unknown": False, "manual_witness": False}
    class Custody:
        def current(self): return copy.deepcopy(pin)
        def check_clock(self, stamp):
            if stamp != now[0]: raise ValueError('SYNTHETIC_CLOCK_REFUSAL')
        def advance(self, old, new):
            if old != pin: raise ValueError('SYNTHETIC_STALE_CUSTODY')
            pin.clear()
            pin.update(copy.deepcopy(new))
    class Authority:
        @contextmanager
        def lease(self, request, at):
            assert request['schema'] == 'PERP_AUTO_OP_ADMISSION_REQUEST_V1'
            witness = {"schema": 'QD_AUTO_OP_ADMISSION_V1' if flags['manual_witness'] else 'PERP_AUTO_OP_ADMISSION_V1',
                           "request_digest": digest(request), "status": 'READ_ACCEPTED' if request['command'] is None else 'PENDING',
                           "reservation_id": 'SYNTHETIC_NOT_INSTALLED', "expires_at": at + 5, "revoked": False}
            yield SimpleNamespace(snapshot=witness, check=lambda p, t: flags['accepted'] and not flags['unknown'],
                acknowledge=lambda req, receipt, p: {"schema": 'PERP_AUTO_OP_RESERVATION_ACK_V1', "request_digest": digest(req), "receipt_digest": digest(receipt), "status": 'ACKNOWLEDGED' if flags['ack'] else 'UNKNOWN'},
                verify_ack=lambda ack: flags['ack'], mark_unknown=lambda req: flags.update(unknown=True))
    spec = importlib.util.spec_from_file_location('perp_op_projection', repo / 'scripts/volume_inspector/financial_reporting.py')
    reports = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reports)
    projection = reports.ProjectionTarget(str(tmp_path / 'projection'), e['resources']['projection']['native_id'])
    deps = {"enrollment": e, "trust": Custody(), "authority": Authority(), "clock": lambda: now[0], "projection": projection}
    store = module.OperationalPerpStore(**deps)
    try: yield SimpleNamespace(**locals())
    finally: store.close(); projection.close()


def test_native_operational_long_partial_funding_final_and_restart(system):
    s = system
    s.store.execute(entry())
    class View:
        manifest = s.params
        def snapshot(self): return s.store.verified_cut()['state']
    view = View()
    s.now[0] = 3603
    s.store.execute(exit_command(view, '0.2'))
    s.now[0] = 7201
    s.store.execute(funding(view))
    s.now[0] = 7202
    s.store.execute(exit_command(view, '0.3', 7202, 'final', '104'))
    cut = s.store.verified_cut()
    assert cut['state']['cash'] == '1001.52936' and cut['state']['reserved_margin'] == '0'
    assert cut['pin_schema'] == 'PERP_AUTO_OP_PIN_V1'
    assert b'PERP_AUTO_OP_RECORD_V1' in (s.tmp_path / 'source/0001-record.json').read_bytes()
    s.store.close()
    restarted = s.module.OperationalPerpStore(**s.deps)
    try: assert restarted.verified_cut()['state'] == cut['state']
    finally: restarted.close()


@pytest.mark.parametrize('schema', ['FS2_TEST_PIN_V1', 'QD_AUTO_OP_PIN_V1', 'QD_OP_CURRENT_V1'])
def test_no_test_or_other_account_pin_adoption(schema, system):
    system.pin['schema'] = schema
    with pytest.raises(ValueError): system.module.OperationalPerpStore(**system.deps)


def test_default_refusal_and_no_provisioning(system):
    with pytest.raises(ValueError): system.module.OperationalPerpStore()
    with pytest.raises(ValueError): system.module.OperationalPerpStore.provision_disposable('unused', {})
    with pytest.raises(ValueError): OperationalPerpFinancialWriter()


@pytest.mark.parametrize('target', ['sqlite', 'native', 'writer'])
def test_fixture_paths_cannot_publish_or_adopt_operational_parameters(target, system):
    from app.services.paper_epoch_fixture import create_epoch_fixture
    from app.services.unified_native_writer import NativeFinancialWriter
    s = system
    path = s.tmp_path / 'forbidden-fixture'
    with pytest.raises(ValueError):
        if target == 'sqlite': create_epoch_fixture(path, s.params)
        elif target == 'native': s.module.base.fs2.FinancialRecordStore.provision_disposable(str(path), s.params)
        else: NativeFinancialWriter(store=s.store, authority=object(), manifest=s.params, execution_domain='DISPOSABLE_TEST')
    assert not path.exists()


@pytest.mark.parametrize('failure', ['refused', 'manual-witness', 'foreign-root', 'wrong-policy', 'missing-writer'])
def test_bad_enrollment_or_authority_has_zero_effects(failure, system):
    s = system
    before = {p.name: p.read_bytes() for p in (s.tmp_path / 'source').iterdir()}
    deps = copy.copy(s.deps)
    deps['enrollment'] = copy.deepcopy(s.e)
    if failure == 'refused': s.flags['accepted'] = False
    elif failure == 'manual-witness': s.flags['manual_witness'] = True
    elif failure == 'foreign-root': deps['enrollment']['resources']['source']['native_id'][1] += 1
    elif failure == 'wrong-policy': deps['enrollment']['policy_digest'] = 'f' * 64
    else: del deps['enrollment']['writers']['funding']
    with pytest.raises(ValueError): s.module.OperationalPerpStore(**deps)
    assert {p.name: p.read_bytes() for p in (s.tmp_path / 'source').iterdir()} == before


def test_ack_unknown_cannot_replay_or_report(system):
    s = system
    s.flags['ack'] = False
    with pytest.raises(ValueError, match='ACK_UNKNOWN'): s.store.execute(entry())
    assert s.flags['unknown'] and len(s.pin['entries']) == 1
    with pytest.raises(ValueError): s.store.execute(entry())
    with pytest.raises(ValueError): s.store.verified_cut()
    with pytest.raises(ValueError): s.module.OperationalPerpStore(**s.deps)
    assert len(s.pin['entries']) == 1


def test_reader_does_not_touch_mutex_or_publish(system, monkeypatch):
    s = system
    before = {p.name: p.read_bytes() for p in (s.tmp_path / 'source').iterdir()}
    def forbidden(*args): raise AssertionError('Read acquired writer mutex or wrote latch')
    monkeypatch.setattr(s.store.coordinator, 'wait', forbidden)
    monkeypatch.setattr(s.store, '_latch', forbidden)
    s.store.preview(entry())
    s.store.verified_cut()
    with pytest.raises(ValueError): s.store.operation_receipt('missing', 'digest')
    assert {p.name: p.read_bytes() for p in (s.tmp_path / 'source').iterdir()} == before


def test_operational_writer_binds_distinct_native_cut(system):
    s = system
    class Authority:
        def verify_components(self, binding): return binding['store'] is s.store
        def verify_cut(self, binding, cut): return cut['root'] == s.pin['root']
        def verify_proposal(self, *args): return True
        def verify_reservation(self, *args): return True
    writer = OperationalPerpFinancialWriter(store=s.store, authority=Authority(), manifest=s.params, execution_domain='LOCAL_ENROLLED')
    c = entry()
    proposal = {"operation_id": c['operation_id'], "kind": c['kind'], "command": c, "source_head": s.store.verified_cut()['head'], "strategy_ref": 'SYNTHETIC_EXISTING_PLANNER'}
    writer.preview(proposal, None)
    receipt = writer.dispatch(proposal, {'SYNTHETIC': 'RESERVED'})
    assert s.store.operation_receipt(c['operation_id'], digest(c)) == receipt
    assert s.store.execute(c) == receipt


@pytest.mark.parametrize('damage', ['schema', 'path', 'alias', 'writer', 'profile'])
def test_enrollment_exact_separation(damage, system):
    e = copy.deepcopy(system.e)
    if damage == 'schema': e['schema'] = 'QD_AUTO_NATIVE_ENROLLMENT_V4'
    elif damage == 'path': e['resources']['source']['path'] = 'C:\\not-accepted'
    elif damage == 'alias': e['resources']['source'] = e['resources']['projection']
    elif damage == 'writer': del e['writers']['mark']
    else: e['profile'] = 'DISPOSABLE_ONLY'
    with pytest.raises(ValueError): validate_enrollment(e)


@pytest.fixture
def reporting(system):
    s = system
    scope = {"schema": 'FS3_PERP_REPORT_SCOPE_V3', "account_id": s.e['account_id'], "epoch": s.e['epoch'],
                 "policy_digest": digest(s.params), "timezone": 'UTC', "funding_reporting_policy": 'POSTED_CASH_AND_SETTLEMENT_ACCRUAL_V1',
                 "session_reporting_policy": 'ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1'}
    fs2 = s.module.base.fs2
    with fs2.w.WindowsOutput(str(s.tmp_path / 'report')) as out:
        bound = out.write_bound('scope.json', body(scope).encode())
    pin = {"schema": 'PERP_AUTO_OP_REPORT_PIN_V1', "root": s.e['resources']['report']['native_id'], "scope": bound, "reports": []}
    flags = {"accepted": True, "ack": True, "unknown": False}
    class Custody:
        def current(self): return copy.deepcopy(pin)
        def advance(self, old, new):
            if old != pin: raise ValueError('SYNTHETIC_REPORT_CUSTODY_CHANGED')
            pin.clear()
            pin.update(copy.deepcopy(new))
    class Authority:
        @contextmanager
        def lease(self, request, at):
            assert request['schema'] == 'PERP_AUTO_OP_REPORT_REQUEST_V1'
            def acknowledge(req, doc, pin):
                if flags.get('revoke_source_after_ack'):
                    s.flags['accepted'] = False
                return {"schema": 'PERP_AUTO_OP_REPORT_RESERVATION_ACK_V1', "request_digest": digest(req), "receipt_digest": digest(doc), "status": 'ACKNOWLEDGED' if flags['ack'] else 'UNKNOWN'}
            yield SimpleNamespace(snapshot={"schema": 'PERP_AUTO_OP_REPORT_ADMISSION_V1', "request_digest": digest(request),
                "status": 'PENDING' if request['action'] == 'PUBLISH' else 'READ_ACCEPTED', "reservation_id": 'SYNTHETIC_REPORT_RESERVATION', "expires_at": at + 5, "revoked": False},
                check=lambda p, t: flags['accepted'] and not flags['unknown'],
                acknowledge=acknowledge,
                verify_ack=lambda ack: flags['ack'], mark_unknown=lambda req: flags.update(unknown=True))
    deps = {"enrollment": s.e, "trust": Custody(), "authority": Authority(), "clock": lambda: s.now[0]}
    archive = s.module.OperationalPerpReportArchive(**deps)
    service = s.module.OperationalPerpReportService(s.store, archive)
    try: yield SimpleNamespace(**locals())
    finally: archive.close()


def test_operational_report_bound_to_replayed_financial_cut(system, reporting):
    s, r = system, reporting
    s.store.execute(entry())
    class View:
        manifest = s.params
        def snapshot(self): return s.store.verified_cut()['state']
    s.now[0] = 3603
    s.store.execute(exit_command(View()))
    s.now[0] = 86400
    document = r.service.publish('1970-01-01', 86400)
    assert document['schema'] == 'PERP_AUTO_OP_REPORT_DOCUMENT_V1'
    assert document['report']['cash']['closing'] == s.store.verified_cut()['state']['cash']
    assert document['report']['status'] == 'COMPLETE' and document['report']['lifecycle_status'] == 'NOT_EVALUATED'
    assert r.service.history() == [document]
    assert r.service.publish('1970-01-01', 86400) == document and len(r.pin['reports']) == 1


def test_reporting_cannot_bypass_native_admission(system, reporting):
    s, r = system, reporting
    s.now[0] = 86400
    with pytest.raises(ValueError, match='ADMISSION_REQUIRED'):
        s.module.reports.ReportService(s.store, r.archive).publish('1970-01-01', 86400)
    assert not r.pin['reports']
    r.flags['accepted'] = False
    with pytest.raises(ValueError): r.service.publish('1970-01-01', 86400)
    assert not r.pin['reports']


def test_report_lost_ack_remains_unknown_after_publication(system, reporting):
    system.now[0] = 86400
    reporting.flags['ack'] = False
    with pytest.raises(ValueError, match='ACK_UNKNOWN'): reporting.service.publish('1970-01-01', 86400)
    assert len(reporting.pin['reports']) == 1 and reporting.flags['unknown']
    with pytest.raises(ValueError): reporting.service.history()
    with pytest.raises(ValueError): system.module.OperationalPerpReportArchive(**reporting.deps)


def test_source_authority_loss_after_report_ack_retains_cross_store_unknown(system, reporting):
    system.now[0] = 86400
    reporting.flags['revoke_source_after_ack'] = True
    with pytest.raises(ValueError): reporting.service.publish('1970-01-01', 86400)
    assert len(reporting.pin['reports']) == 1 and reporting.flags['unknown']
    system.flags['accepted'] = True
    with pytest.raises(ValueError): reporting.service.history()
    with pytest.raises(ValueError): system.module.OperationalPerpReportArchive(**reporting.deps)


def test_operational_intraday_session_and_immutable_report_lineage(system, reporting):
    s, r = system, reporting
    s.store.execute(entry())
    document = r.service.publish_session(session_id='synthetic', started_at=3601, cutoff_at=3602, observed_at=3602)
    assert document['report']['status'] == 'COMPLETE' and len(document['report']['open_positions']) == 1
    raw = (s.tmp_path / 'report/0001-report.json').read_bytes()
    class View:
        manifest = s.params
        def snapshot(self): return s.store.verified_cut()['state']
    s.now[0] = 3603
    s.store.execute(exit_command(View()))
    final = r.service.publish_session(session_id='synthetic', started_at=3601, cutoff_at=3603, observed_at=3603)
    assert not final['report']['open_positions'] and final['report']['cash']['closing'] == s.store.verified_cut()['state']['cash']
    assert len(r.service.history()) == 2 and (s.tmp_path / 'report/0001-report.json').read_bytes() == raw


def test_operational_report_reads_never_observe_writer_mutex(system, reporting, monkeypatch):
    def forbidden(*args): raise AssertionError('Read touched writer coordination or latch')
    for target in (system.store, reporting.archive):
        monkeypatch.setattr(target.coordinator, 'wait', forbidden)
        monkeypatch.setattr(target, '_latch', forbidden)
    assert reporting.service.history() == []


@pytest.mark.parametrize('failure', ['clock', 'partial-commit', 'rollback'])
def test_native_restart_refuses_uncertain_evidence(failure, system, monkeypatch):
    s = system
    if failure == 'clock':
        s.now[0] += 1
        with pytest.raises(ValueError, match='CLOCK'): s.store.execute(entry())
        assert not s.pin['entries']
        return
    old = copy.deepcopy(s.pin)
    if failure == 'partial-commit':
        original = s.store.output.write_bound
        def interrupted(leaf, payload):
            if leaf.endswith('-ack.json'): raise OSError('SYNTHETIC_INTERRUPTION_AFTER_COMMIT')
            return original(leaf, payload)
        monkeypatch.setattr(s.store.output, 'write_bound', interrupted)
        with pytest.raises(OSError): s.store.execute(entry())
    else:
        s.store.execute(entry())
        s.pin.clear()
        s.pin.update(old)
    with pytest.raises(ValueError): s.module.OperationalPerpStore(**s.deps)
