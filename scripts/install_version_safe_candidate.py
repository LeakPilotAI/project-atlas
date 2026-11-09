"""Version-safe immutable candidate CODE-ONLY installer, source phase (NO APPROVAL).

Historical V7/V8 installer and their immutable receipts are never modified.
No native installation is possible without a SEPARATE exact operator approval
record not present in this source milestone. Never select a release, authorize
financial PAPER, initialize accounts, connect providers, or launch a service.
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path

from scripts.build_release_candidate import source_bytes
from scripts.native_install_plan import prepare_install_inputs
from scripts.native_install_candidate import _copy_prepared_code
from scripts.install_verified_release import (
    installation_target, installed_readback, write_new_json,
)

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'docs/ATLAS_VERSION_SAFE_CODE_ONLY_INSTALL_PROPOSAL_R1_2026-11-09.json'
REVIEW_SHA = '539d8619fc52ca724762b38d4675292a38a72a29df3a0a4aa531358d8f62aa36'
SOURCE = '2d4879878bf58bea5a3ed0a986b809791f638fec'
ARCHIVE = '5b295cc8e60be9d078321b39197afa4d12ad31897bc258575889099b3f5f7dac'
INVENTORY = '22960eadfe5c6ca3e95b799788ba02cc702bd2db66ba14f61707380472ad7331'
DEPENDENCY = '93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91'
DEPENDENCY_FILE = 'b1363f4514d3cdce4a1914e79d14842ece94136ed5d035ea195b4883da99a7a0'
SELECTION_FILE = '0070390c30db6bcf027d59f32bd7ed3d5aab2996a9b886720f30154692b79f8a'
PHYSICAL_FILE = '9f2a90027b475666df0647815a48c0a9fbf363191eced3212302b5dfcd97559d'
PY_INVENTORY = '2eaa943a5fa35fe4863defd9bc843dd93503367509b56c4880a0aef3c1f9960f'
V7_HEAD = '933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997'
V7_RELEASE = 'af96bec0484a8e43f9965610e071a907a0d316bf'
NATIVE_SELECTION_ROOT = [4004218753, 65536, 1532785]
CLOCK_SOURCE = 'ATLAS_NTP_V1:time.cloudflare.com+time.google.com'
# Deliberately absent, require an independent future create-only operator decision.
APPROVAL = ROOT / 'docs/ATLAS_VERSION_SAFE_CODE_INSTALL_APPROVED_R1.json'
APPROVAL_SCHEMA = 'ATLAS_VERSION_SAFE_CODE_INSTALL_APPROVAL_V1'


def strict(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('VERSION_SAFE_INSTALL_DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('INVALID_JSON_CONSTANT')))


def checked(path, expected, *, maximum=16 * 1024**2):
    path = Path(path)
    if type(expected) is not str or not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('VERSION_SAFE_INSTALL_EXACT_SHA_REQUIRED')
    raw = source_bytes(path.parent, path.name, maximum_bytes=maximum)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('VERSION_SAFE_INSTALL_PIN_CHANGED')
    return raw


def read_exact_review():
    """No installation permission comes from an R1 DESIGN_NOT_PERMISSION file."""
    review = strict(checked(REVIEW, REVIEW_SHA))
    if (type(review) is not dict or review.get('schema')!='ATLAS_VERSION_SAFE_NONFINANCIAL_CODE_INSTALL_REVIEW_V1'
            or review.get('status')!='DESIGN_NOT_PERMISSION'
            or review.get('native_code_install_authorized') is not False
            or review.get('selection_authorized') is not False
            or review.get('approval_record_present') is not False
            or review.get('execution_attempted') is not False
            or review.get('provider_connections_authorized') is not False
            or review.get('simulated_trading_authorized') is not False
            or review.get('live_trading_authorized') is not False
            or review.get('paper_account_inception_authorized') is not False
            or review.get('release_installer_currently_allows_this_candidate') is not False):
        raise ValueError('VERSION_SAFE_INSTALL_REVIEW_NOT_AUTHORITY')
    c = review['candidate']; d = review['dependencies']; p = review['native_plan']
    if (c.get('source_commit') != SOURCE or c.get('archive_sha256') != ARCHIVE
            or c.get('inventory_sha256') != INVENTORY
            or c.get('selection_sha256') != SELECTION_FILE
            or d.get('full_source_inventory_sha256') != DEPENDENCY
            or d.get('receipt_file_sha256') != DEPENDENCY_FILE
            or d.get('native_source_physical_receipt_sha256') != PHYSICAL_FILE
            or d.get('python_inventory_sha256') != PY_INVENTORY
            or d.get('python_files') != 9566
            or p.get('files') != 10574 or p.get('directories') != 914
            or p.get('bytes') != 265175432 or p.get('previous_selected_head') != V7_HEAD
            or p.get('previous_selected_revision') != 11
            or review['clock'].get('source') != CLOCK_SOURCE
            or review['clock'].get('fresh_180_second_qualification_required') is not True
            or review['clock'].get('clock_financially_certified') is not False):
        raise ValueError('VERSION_SAFE_INSTALL_REVIEW_IDENTITY_MISMATCH')
    diagnostic = ROOT / 'logs/diagnostics'
    if (Path(c['archive_path']) != diagnostic / 'atlas-version-safe-ntp-source-candidate-20261109-r12-proposal/atlas-source.zip'
            or Path(c['selection_inventory_path']) != diagnostic / 'atlas-version-safe-ntp-source-selection-20261109-r12-proposal.json'
            or Path(d['receipt_path']) != diagnostic / 'qd-d-runtime-coordination-installation-20261028.json'
            or Path(d['native_source_physical_receipt_path']) != diagnostic / 'atlas-version-safe-source-dependency-physical-20261109.json'
            or Path(p['destination']) != Path('D:/AtlasRuntime/releases') / SOURCE
            or Path(p['receipt_path']) != diagnostic / ('qd-unselected-release-'+SOURCE+'.json')):
        raise ValueError('VERSION_SAFE_INSTALL_REVIEW_FOREIGN_PATH')
    checked(c['archive_path'], ARCHIVE, maximum=64*1024**2)
    checked(c['selection_inventory_path'], SELECTION_FILE)
    checked(d['receipt_path'], DEPENDENCY_FILE)
    physical = strict(checked(d['native_source_physical_receipt_path'], PHYSICAL_FILE))
    if (physical.get('status') != 'PHYSICAL_FILE_ID_CONTENT_NAMESPACE_VERIFIED'
            or physical.get('verified_files') != 10182
            or physical.get('verified_directories') != 903
            or physical.get('native_file_handles_after_close') != 0
            or physical.get('native_directory_handles_after_close') != 0
            or physical.get('source_image_self_execution_verified') is not False):
        raise ValueError('VERSION_SAFE_INSTALL_DEPENDENCY_PHYSICAL_PROOF_REQUIRED')
    # Historical adapter hashes are frozen by the prior design review.
    for path, pin in review['reviewed_adapter_byte_sha256'].items():
        if path not in {
            'scripts/install_verified_release.py','scripts/native_install_candidate.py',
            'scripts/native_install_plan.py','scripts/build_release_candidate.py',
            'scripts/observation_runtime/personal_version_safe_release_clock.py',
            'scripts/release_selection.py'}:
            raise ValueError('VERSION_SAFE_INSTALL_FOREIGN_ADAPTER')
        checked(ROOT / path, pin)
    if len(review['reviewed_adapter_byte_sha256']) != 6:
        raise ValueError('VERSION_SAFE_INSTALL_ADAPTER_SET_INCOMPLETE')
    return review


def require_v7_predecessor():
    """Native locked record read, no selector publication."""
    from scripts.release_selection import digest
    from scripts.release_selection_store import NativeSelectionStore
    store = NativeSelectionStore(root=r'D:\AtlasRuntime\selection', native_root=list(NATIVE_SELECTION_ROOT))
    try:
        with store.locked():
            rows = store.records()
            if (len(rows)!=11 or type(rows[-1]) is not dict
                    or rows[-1].get('revision') != 11
                    or digest(rows[-1]) != V7_HEAD
                    or type(rows[-1].get('selected')) is not dict
                    or rows[-1]['selected'].get('release') != V7_RELEASE):
                raise ValueError('VERSION_SAFE_INSTALL_NATIVE_PREDECESSOR_CHANGED')
        return True
    finally:
        store.close()


def prepare_reviewed_code():
    """Recheck the entire sealed source/dependency plan without native effects."""
    review=read_exact_review()
    require_v7_predecessor()
    from scripts.release_selection import digest
    selection = Path(r'D:\AtlasRuntime\selection')
    if os.path.lexists(selection/'r0012.json') or os.path.lexists(selection/'r0012.pending'):
        raise ValueError('VERSION_SAFE_INSTALL_NATIVE_R12_ALREADY_EXISTS')
    c, d, p = review['candidate'], review['dependencies'], review['native_plan']
    receipt = strict(checked(d['receipt_path'], DEPENDENCY_FILE))
    prepared = prepare_install_inputs(
        archive=c['archive_path'], archive_sha256=ARCHIVE, source_commit=SOURCE,
        dependency_receipt=receipt, dependency_digest=DEPENDENCY,
        inventory_digest=INVENTORY, require_tracked=True)
    if (len(prepared['runtime']) != 1008 or len(prepared['dependencies']) != 9566
            or len(prepared['names']) != 10574 or len(prepared['directories'])+1 != 914
            or prepared['total'] != 265175432):
        raise ValueError('VERSION_SAFE_INSTALL_NATIVE_PLAN_CHANGED')
    # The shared target admission is create-only and refuses partial histories.
    destination,audit=installation_target(SOURCE,p['receipt_path'])
    return {'review':review,'prepared':prepared,'dependency':receipt,
            'destination':destination,'audit':audit}


def require_separate_operator_approval():
    """R1 is deliberately not authorized; a future exact approval is mandatory."""
    if not APPROVAL.is_file():
        raise ValueError('VERSION_SAFE_INSTALL_SEPARATE_OPERATOR_APPROVAL_ABSENT')
    # A future approval schema requires a separately pinned approved receipt.
    # This source milestone intentionally cannot establish that pin, so even
    # creating an unreviewed local file at this path cannot enable installation.
    raise ValueError('VERSION_SAFE_INSTALL_APPROVAL_NOT_YET_REVIEWED')


def _qualify_native_clock_180s(clock, runtime_id):
    """Use exactly one real NTP object, 180 monotonic seconds, no OS clock."""
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock, SOURCE
    if type(clock) is not IndependentNtpClock:
        raise ValueError('VERSION_SAFE_INSTALL_REAL_TWO_PEER_CLOCK_REQUIRED')
    initial = clock.evidence
    if (initial.get('source') != SOURCE or initial.get('domain') != 'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS'
            or initial.get('financial_authority') is not False
            or type(initial.get('bound_ms')) is not int or not 0 <= initial['bound_ms'] <= 1000):
        raise ValueError('VERSION_SAFE_INSTALL_NTP_SOURCE_REFUSED')
    start=time.perf_counter()
    samples=0
    while True:
        clock.require_operational(runtime_id)
        evidence=clock.evidence
        if (evidence.get('source') != SOURCE or evidence.get('domain') != 'TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS'
                or evidence.get('financial_authority') is not False
                or type(evidence.get('bound_ms')) is not int
                or not 0 <= evidence['bound_ms'] <= 1000):
            raise ValueError('VERSION_SAFE_INSTALL_NTP_CONTINUITY_REFUSED')
        samples+=1
        elapsed=time.perf_counter()-start
        if elapsed >= 180:
            break
        wait=min(5,180-elapsed)
        if wait <= 0:
            raise ValueError('VERSION_SAFE_INSTALL_NTP_MONOTONIC_REFUSED')
        time.sleep(wait)
    if samples < 37:
        raise ValueError('VERSION_SAFE_INSTALL_NTP_37_SAMPLES_REQUIRED')
    return {'elapsed_seconds':elapsed,'samples':samples,'bound_ms':evidence['bound_ms']}


def _native_copy_only_after_approval(*, prepared_review, clock, preflight):
    """Reviewed physical copy/readback implementation, blocked pending approval.

    Even direct invocation of this private function cannot copy until a
    separately pinned approval record exists. No selector writers.
    """
    require_separate_operator_approval()
    from scripts.observation_runtime.atlas_independent_ntp_clock import IndependentNtpClock, SOURCE
    if type(clock) is not IndependentNtpClock or type(preflight) is not dict:
        raise ValueError('VERSION_SAFE_INSTALL_APPROVED_CLOCK_REQUIRED')
    if (type(preflight.get('elapsed_seconds')) not in (int,float)
            or preflight['elapsed_seconds'] < 180
            or type(preflight.get('samples')) is not int or preflight['samples'] < 37
            or type(preflight.get('bound_ms')) is not int or not 0 <= preflight['bound_ms'] <= 1000):
        raise ValueError('VERSION_SAFE_INSTALL_180S_CLOCK_PROOF_REQUIRED')
    if (type(prepared_review) is not dict
            or set(prepared_review) != {'review','prepared','dependency','destination','audit'}):
        raise ValueError('VERSION_SAFE_INSTALL_REVIEWED_PLAN_REQUIRED')
    ready=prepared_review
    destination,audit=ready['destination'],ready['audit']
    if (destination != Path('D:/AtlasRuntime/releases')/SOURCE_COMMIT
            or audit != ROOT/'logs/diagnostics'/('qd-unselected-release-'+SOURCE_COMMIT+'.json')):
        raise ValueError('VERSION_SAFE_INSTALL_DESTINATION_CHANGED')
    runtime_id='qd-unselected-code-install-'+SOURCE_COMMIT
    def admission():
        clock.require_operational(runtime_id)
        if (time.monotonic()-ready['prepared']['started'] > 600
                or os.path.lexists(Path(r'D:\AtlasRuntime\selection')/'r0012.json')
                or os.path.lexists(Path(r'D:\AtlasRuntime\selection')/'r0012.pending')):
            raise ValueError('VERSION_SAFE_INSTALL_ADMISSION_LOST')
        ev=clock.evidence
        if (ev.get('source')!=SOURCE or ev.get('domain')!='TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS'
                or ev.get('financial_authority') is not False
                or type(ev.get('bound_ms')) is not int or not 0 <= ev['bound_ms'] <= 1000):
            raise ValueError('VERSION_SAFE_INSTALL_NTP_CHANGED')
        return True
    # All read-only physical/selector checks must be repeated immediately before
    # the create-only journal; partial effects are preserved, never repaired.
    require_v7_predecessor()
    installation_target(SOURCE_COMMIT,audit)
    admission()
    journal=audit.with_suffix('.pending.jsonl')
    intent={'schema':'ATLAS_UNSELECTED_CODE_INSTALL_INTENT_V1',
            'source_commit':SOURCE_COMMIT, 'archive_sha256':ARCHIVE,
            'inventory_sha256':INVENTORY,'dependency_sha256':DEPENDENCY,
            'destination':str(destination),'selection_allowed':False,'financial_authority':False}
    write_new_json(journal,intent)
    def record(value):
        raw=b'\n'+json.dumps(value,sort_keys=True,allow_nan=False).encode()
        with journal.open('ab') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
    try:
        copied=_copy_prepared_code(destination=destination,archive_sha256=ARCHIVE,
            source_commit=SOURCE_COMMIT,prepared=ready['prepared'],observer=record,
            admission=admission)
        admission()
        receipt={'schema':'ATLAS_QD_D_RUNTIME_INSTALLATION_V1','stage':'D_RUNTIME_LAYOUT_VERIFIED',
            'release_path':str(destination),'source_commit':SOURCE_COMMIT,
            'files':copied['files'],'directories':copied['directories'],
            'archive_sha256':ARCHIVE,'inventory_sha256':INVENTORY,
            'selected':False,'financial_effects':False,'provider_connections':False,
            'operational_acceptance':False}
        pin=hashlib.sha256(json.dumps(receipt['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        result=installed_readback(destination,receipt,pin,
            timeout=min(180,max(1,600-(time.monotonic()-ready['prepared']['started'])-5)))
        admission()
        receipt.update(layout=result['layout'],artifact_digest=pin)
        write_new_json(audit,receipt)
        record({'stage':'UNSELECTED_CODE_INSTALL_VERIFIED',
                'receipt_sha256':hashlib.sha256(audit.read_bytes()).hexdigest()})
        return receipt
    except (ValueError,OSError,RuntimeError,KeyError,TypeError):
        record({'stage':'FAILED_PRESERVE_PARTIAL_NO_RETRY_OR_SELECTION'})
        raise


SOURCE_COMMIT = SOURCE


def install_unselected(*, approved_execution=False, clock=None):
    """Fail-closed until a separate installation approval is reviewed and pinned.

    This source-only milestone exposes the exact independent pre-install review.
    Native copying/readback is intentionally NOT reachable via any current
    public entrypoint; it will be enabled only by a later reviewed approval.
    """
    if approved_execution is not True:
        raise ValueError('VERSION_SAFE_INSTALL_EXPLICIT_EXECUTION_REQUIRED')
    require_separate_operator_approval()
    raise ValueError('VERSION_SAFE_INSTALL_SOURCE_ONLY_NO_NATIVE_MUTATION')


def main(argv=None):
    raise SystemExit('VERSION_SAFE_INSTALL_NO_APPROVED_EXECUTION_ENTRYPOINT: source-only installer admission; approval and fresh 180s NTP preflight still required.')


if __name__=='__main__':
    main()
