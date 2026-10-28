"""Explicit confined native measurement; all authorities/market inputs synthetic.

This measures real NTFS publication, not operational enrollment or a PAPER pilot.
It never imports or executes the V5 containment launcher.
"""
import importlib.util
import json
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest, number
from app.services.personal_current_pins import PersonalCurrentPins
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_publication_custody import PersonalPublicationCustody
from app.services.quality_dips_autonomous_integration import AutonomousNativePublication
from app.services.quality_dips_autonomous_paper import AutonomousPaper
from app.services.quality_dips_personal_dependencies import PersonalSessionReservations
from test_personal_paper_inception_memory import system
from test_quality_dips_autonomous_paper import candidate, entry, monitor, setup

from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_paper_inception import (
    NativePersonalInceptionFiles,
    NativePersonalInitialReadback,
    PersonalInceptionBootstrap,
    PersonalInceptionPublisher,
    native_primitives,
)


def test_actual_native_inception_financial_events_reports_and_restart(tmp_path):
    value = os.environ.get('ATLAS_PERSONAL_PIPELINE_TEST_ROOT')
    if value is None:
        pytest.skip('NOT EXECUTED: explicit confined native pipeline root required')
    root = Path(value)
    repo = Path(__file__).resolve().parents[1]
    assert root.parent == repo/'logs/diagnostics' and root.name.startswith('qd-personal-pipeline-')
    assert tmp_path.is_relative_to(root) and not tmp_path.is_symlink() and not tmp_path.is_junction()
    assert not any(p.is_symlink() or p.is_junction() for p in (root, *root.parents))
    start = time.monotonic()
    native = native_primitives()
    handles, timings = [], {}

    def budget(extra=0):
        count, size = 0, 0
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in dirs+files:
                path = Path(directory)/name
                if path.is_symlink() or path.is_junction(): raise ValueError('TEST_LINK_REFUSED')
                count += 1
                if name in files: size += path.stat().st_size
        if count >= 2048 or size+extra > 32*1024*1024 or time.monotonic()-start > 180:
            raise ValueError('TEST_RESOURCE_LIMIT')
        return count, size

    def timed(name, callback):
        budget()
        before = time.monotonic()
        result = callback()
        timings[name] = round(time.monotonic()-before, 6)
        budget()
        return result

    # Test-owned roots only; existing Windows owner/SYSTEM policy is reused.
    s = system('QUALITY_DIPS')
    s.ledger.db.close()
    for role, resource in s.n['resources'].items():
        with native.w.WindowsOutput.create_root(str(tmp_path/role)) as out:
            resource.update(path=str(out.root), native_id=native.native.file_identity(out.root_handle))
    s.e['native_enrollment'] = s.n
    clock = lambda: s.now[0]
    images = NativePersonalCoordinationImages(root=s.n['resources']['coordination']['path'],
             native_root=s.n['resources']['coordination']['native_id'], enrollment_digest=digest(s.n))
    handles.append(images)
    write = images.output.write_bound
    def bounded_write(name, data):
        budget(len(data))
        result = write(name, data)
        budget()
        return result
    images.output.write_bound = bounded_write

    @contextmanager
    def synthetic_initialization(request):
        yield SimpleNamespace(check=lambda value: value == request)

    try:
        timed('coordination_initialize', lambda: images.initialize(PersonalNativeCoordination.initial_image(s.m),
              authorization=SimpleNamespace(lease=synthetic_initialization)))
        ledger = PersonalNativeCoordination(manifest=s.m, images=images, path=tmp_path/'coordination/memory-only')
        custody = PersonalPublicationCustody(ledger)
        bootstrap = PersonalInceptionBootstrap(enrollment=s.e, publication=custody, issuer=s.issuer,
                    clock=clock, readback=NativePersonalInitialReadback())
        publisher = PersonalInceptionPublisher(bootstrap=bootstrap, custody=custody,
                    ownership=s.owner, observer=s.observer, files=NativePersonalInceptionFiles())
        ready = timed('once_only_inception_readback', publisher.publish)
        with pytest.raises(ValueError): publisher.publish()
        with ledger.connect() as db:
            for role in ('source', 'reports'): PersonalCurrentPins.initialize(db, role, ready['current'][role])
        pins = PersonalCurrentPins(ledger=ledger, name='source', clock=clock)
        reports = PersonalCurrentPins(ledger=ledger, name='reports', clock=clock)
        images.reserve_stop_capacity(stop_commits=32, stop_bytes=256*1024)
        request = {'grant': {'session_id': 'EXPLICIT-SYNTHETIC-ONLY'}}
        reservation = PersonalSessionReservations(ledger=ledger, authorization=SimpleNamespace(verify=lambda r: r == request))
        timed('session_reservation', lambda: reservation.reserve(request))
        spec = importlib.util.spec_from_file_location('pipeline_native', repo/'scripts/volume_inspector/operational_autonomous_store.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        spec = importlib.util.spec_from_file_location('pipeline_reports', repo/'scripts/volume_inspector/financial_reporting.py')
        reporting = importlib.util.module_from_spec(spec); spec.loader.exec_module(reporting)
        projection = reporting.ProjectionTarget(s.n['resources']['projection']['path'], s.n['resources']['projection']['native_id'])
        handles.append(projection)

        class SyntheticFinancialAuthority:
            @contextmanager
            def lease(self, req, now):
                proof = {'schema': 'QD_AUTO_OP_ADMISSION_V1', 'request_digest': digest(req),
                         'status': 'READ_ACCEPTED' if req['command'] is None else 'PENDING',
                         'reservation_id': 'SYNTHETIC-NOT-OPERATIONAL', 'expires_at': now+5, 'revoked': False}
                yield SimpleNamespace(snapshot=proof, check=lambda p,t: p == proof and now <= t <= now+5,
                    acknowledge=lambda r,receipt,pin: {'schema':'QD_AUTO_OP_RESERVATION_ACK_V1',
                         'request_digest':digest(r),'receipt_digest':digest(receipt),'status':'ACKNOWLEDGED'},
                    verify_ack=lambda ack: ack['status']=='ACKNOWLEDGED', mark_unknown=lambda req: None)

        store = module.OperationalAutonomousStore(enrollment=s.n, trust=pins, authority=SyntheticFinancialAuthority(),
                                                   clock=clock, projection=projection)
        handles.append(store)
        archive = reporting.ReportArchive(s.n['resources']['report']['path'], reports)
        handles.append(archive)
        service = reporting.ReportService(store, archive)
        n = setup(tmp_path, stamp=s.now[0])
        old = n.engine
        n.m, n.ledger, n.now = s.m, ledger, s.now
        n.grant.update(epoch=s.m['epoch'], issued_at=clock(), expires_at=clock()+60)
        n.engine = AutonomousPaper(ledger=ledger, candidates=old.candidates, session_authority=old.session_authority,
                    source_authority=old.source_authority, clock=clock,
                    publication=AutonomousNativePublication(store=store, manifest=s.m))
        timed('engine_start', lambda: n.engine.start(n.grant))
        def report(): return service.publish(datetime.fromtimestamp(clock(), UTC).date().isoformat(), clock())
        assert timed('entry', lambda: entry(n))['filled']
        timed('entry_report', report)
        assert timed('partial_exit', lambda: monitor(n, candidate(n), 'partial', '110', {'fundamentals_score':60}))['filled']
        timed('partial_report', report)
        images.begin_reserved_stop()
        assert timed('full_exit', lambda: monitor(n, candidate(n), 'final', '120', {'classification':'THESIS_BROKEN'}))['filled']
        timed('final_report', report)
        assert timed('engine_stop', n.engine.stop) == 'STOPPED'
        state = timed('native_replay_audit', lambda: store.snapshot()['state'])
        assert number(state['cash']) == number('1015.9136')
        assert all(number(p['remaining']) == 0 and number(p['remaining_entry_costs']) == 0 for p in state['positions'].values())
        with ledger.connect(readonly=True) as db:
            assert ledger._load(db)[0] == state
        with pytest.raises(ValueError): reservation.reserve(request)
        image, current = images._load()
        count, size = budget()
        print(json.dumps({'synthetic_only': True, 'timings_seconds':timings, 'coordination_revision':current['revision'],
              'image_bytes':len(image), 'filesystem_entries':count, 'bytes':size,
              'financial_revision':len(pins.current()['entries']), 'report_count':len(reports.current()['reports']),
              'elapsed_seconds':round(time.monotonic()-start,6)}))
    finally:
        for handle in reversed(handles): handle.close()
