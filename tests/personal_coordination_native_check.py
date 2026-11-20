"""Explicit bounded nonfinancial Windows check; never an operational installer.

All writes are confined to ONE new test root. No financial source/projection/
report store, account, provider, service, launcher or child process is activated.
Synthetic authorization is used only for this test-owned coordination surface.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from app.services.paper_financial_replay import digest
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.quality_dips_personal_dependencies import PersonalSessionReservations
from test_personal_paper_inception_memory import system

from scripts.observation_runtime.personal_coordination_store import (
    NativePersonalCoordinationImages,
)
from scripts.observation_runtime.personal_paper_inception import native_primitives


def run(root):
    repo = Path(__file__).resolve().parents[1]
    root = Path(root).absolute()
    if (root.parent != repo/'logs/diagnostics' or not root.name.startswith('qd-coordination-native-')
            or root.exists() or root.drive.upper() != 'D:'
            or any(p.is_symlink() or p.is_junction() for p in (root.parent, *root.parent.parents))):
        raise ValueError('EXACT_NEW_TEST_ROOT_REQUIRED')
    started = time.monotonic()
    native = native_primitives()
    results, objects, owned = {}, [], []

    def budget():
        if time.monotonic() - started > 90:
            raise ValueError('TEST_TIME_LIMIT')
        entries, size = 0, 0
        for directory in [root, *owned]:
            if directory.exists():
                if directory.is_symlink() or directory.is_junction():
                    raise ValueError('TEST_NAMESPACE_CHANGED')
                for p in directory.iterdir():
                    if p.is_symlink() or p.is_junction():
                        raise ValueError('TEST_LINK_REFUSED')
                    entries += 1
                    if p.is_file():
                        size += p.stat().st_size
        if entries > 1024 or size > 8 * 1024 * 1024:
            raise ValueError('TEST_RESOURCE_LIMIT')
        return entries, size

    @contextmanager
    def synthetic_authority(request):
        yield SimpleNamespace(check=lambda observed: observed == request and time.monotonic() - started <= 90)

    def store(name):
        budget()
        path = root/name
        with native.w.WindowsOutput.create_root(str(path)) as out:
            identity = native.native.file_identity(out.root_handle)
        owned.append(path)
        images = NativePersonalCoordinationImages(root=str(path), native_root=identity,
                                                  enrollment_digest=digest(['SYNTHETIC_COORDINATION_ONLY', name]))
        objects.append(images)
        write = images.output.write_bound
        def bounded_write(leaf, data):
            budget()
            value = write(leaf, data)
            budget()
            return value
        images.output.write_bound = bounded_write
        return images, path, identity

    def hashes(path):
        budget()
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir() if p.is_file()}

    # Creates only the one bounded test root and its explicitly owned children.
    with native.w.WindowsOutput.create_root(str(root)):
        pass
    failure = None
    try:
        manifest = system('QUALITY_DIPS').m  # Explicit synthetic unit-test data.
        image = PersonalNativeCoordination.initial_image(manifest)
        images, path, identity = store('normal')
        images.initialize(image, authorization=SimpleNamespace(lease=synthetic_authority))
        ledger = PersonalNativeCoordination(manifest=manifest, images=images, path=path/'memory-only')
        request = {'grant': {'session_id': 'SYNTHETIC_NATIVE_ONCE'}}
        reservation = PersonalSessionReservations(ledger=ledger,
                           authorization=SimpleNamespace(verify=lambda candidate: candidate == request))
        receipt = reservation.reserve(request)
        assert reservation.verify(request, receipt)
        results['native_pending_ack_readback'] = True
        before = hashes(path)
        with ledger.connect(readonly=True) as db:
            assert ledger._load(db)[0]['cash'] == '1000'
        assert hashes(path) == before
        results['read_only_hash_parity'] = True

        def writer(n):
            budget()
            with ledger.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO personal_sessions VALUES(?,?,?)',
                           (f'SYNTHETIC_CONCURRENT_{n}', '{}', 'ACKNOWLEDGED'))
        with ThreadPoolExecutor(max_workers=2) as workers:
            list(workers.map(writer, range(6)))
        with ledger.connect(readonly=True) as db:
            assert db.execute('SELECT COUNT(*) FROM personal_sessions').fetchone() == (7,)
        results['concurrent_native_publication'] = True
        images.close()
        reopened = NativePersonalCoordinationImages(root=str(path), native_root=identity,
                              enrollment_digest=digest(['SYNTHETIC_COORDINATION_ONLY', 'normal']))
        objects.append(reopened)
        ledger = PersonalNativeCoordination(manifest=manifest, images=reopened, path=path/'memory-only')
        assert PersonalSessionReservations(ledger=ledger,
            authorization=SimpleNamespace(verify=lambda candidate: candidate == request)).verify(request, receipt)
        try:
            PersonalSessionReservations(ledger=ledger,
                authorization=SimpleNamespace(verify=lambda candidate: candidate == request)).reserve(request)
            raise AssertionError('DUPLICATE_SESSION_WAS_ACCEPTED')
        except ValueError as error:
            assert 'REPLAY' in str(error)
        results['restart_and_duplicate_refusal'] = True

        broken, broken_path, broken_identity = store('interrupted')
        publish = broken.output.write_bound
        def interrupt(leaf, data):
            value = publish(leaf, data)
            if leaf == '0001-commit.json':
                raise OSError('SYNTHETIC_NATIVE_COMMIT_BEFORE_ACK')
            return value
        broken.output.write_bound = interrupt
        try:
            broken.initialize(image, authorization=SimpleNamespace(lease=synthetic_authority))
            raise AssertionError('INTERRUPTION_NOT_EXERCISED')
        except OSError:
            pass
        broken.close()
        refused = NativePersonalCoordinationImages(root=str(broken_path), native_root=broken_identity,
                              enrollment_digest=digest(['SYNTHETIC_COORDINATION_ONLY', 'interrupted']))
        objects.append(refused)
        try:
            with refused.transaction(readonly=True):
                raise AssertionError('UNKNOWN_RESTART_ACCEPTED')
        except ValueError:
            pass
        results['interrupted_native_restart_refused'] = True
    except (ValueError, OSError, AssertionError, sqlite3.Error, KeyError) as error:
        failure = {'type': type(error).__name__, 'error': str(error)}
    finally:
        for value in objects:
            value.close()
        entries, size = budget()
        evidence = {'schema': 'SYNTHETIC_PERSONAL_COORDINATION_NATIVE_CHECK_V1', 'results': results,
                    'failure': failure, 'seconds': round(time.monotonic()-started, 3),
                    'entries': entries, 'bytes': size, 'handles_closed': True,
                    'financial_accounts_created': 0, 'providers': 0, 'children_started': 0,
                    'evidence_retained': True, 'operational_authority': False}
        (root/'evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf8')
        budget()
        print(json.dumps(evidence))
    return 0 if failure is None else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    sys.exit(run(args.root))
