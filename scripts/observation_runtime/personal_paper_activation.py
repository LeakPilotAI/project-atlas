"""Existing-only local operator approval record. No writer or default enrollment."""
import importlib.util
import ntpath
from pathlib import Path

from app.services.paper_financial_replay import body, digest, strict


class NativePersonalActivationReader:
    def __init__(self,*,root=None,native_root=None,binding=None):
        if (type(root) is not str or not ntpath.normcase(root).startswith('d:\\atlascustody\\personalpaper\\')
                or any(c in root[3:] for c in (':','%','\x00','/')) or ntpath.normpath(root)!=root or any(x in ('','..','.') for x in root[3:].split('\\'))
                or type(native_root) is not list or len(native_root)!=3
                or any(type(v) is not int or v<0 for v in native_root)
                or type(binding) is not dict or set(binding)!={'id','sha256'}
                or type(binding['id']) is not list or len(binding['id'])!=3
                or any(type(v) is not int or v<0 for v in binding['id'])
                or type(binding['sha256']) is not str or len(binding['sha256'])!=64
                or any(c not in '0123456789abcdef' for c in binding['sha256'])):
            raise ValueError('PERSONAL_INSTALLED_NATIVE_APPROVAL_REQUIRED')
        self.root,self.native_root,self.binding=root,list(native_root),{'id':list(binding['id']),'sha256':binding['sha256']}
    def read(self):
        # Import opens no resource. Actual root access is existing-only and bound.
        spec=importlib.util.spec_from_file_location('personal_approval_bound',Path(__file__).parents[1]/'volume_inspector/snapshot_store.py')
        native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
        with native.w.WindowsOutput(self.root) as out:
            if native.native.file_identity(out.root_handle)!=self.native_root:raise ValueError('PERSONAL_APPROVAL_ROOT_SUBSTITUTION')
            value=strict(native.read_bound(out,'activation.json',self.binding)[0].decode())
        if value.get('schema')!='ATLAS_PERSONAL_ACTIVATION_V1' or value.get('origin')!='LOCAL_OPERATOR':raise ValueError('PERSONAL_APPROVAL_NO_FIXTURE_OR_STRICT_SUBSTITUTION')
        return value


def compose_installed_personal_qd(*, policy=None, enrollment=None, runtime_dependencies=None,
                                native_dependencies=None, store=None, native_reader=None,
                                installation=None, local_clock=None, runtime_id=None):
    """Minimum installed QD assembly; no default authority, paths or activation.

    The sole operator's native activation record, actual clock and native-backed
    mirror are mandatory. It delegates to the existing personal runtime without
    changing strict/manual contracts or creating a session, account or provider.
    Caller owns all explicitly installed dependency handles.
    """
    from app.services.personal_native_coordination import PersonalNativeCoordination
    from app.services.personal_paper_runtime import (
        PersonalOperatorInstallation,
        compose_personal_qd,
    )
    from app.services.quality_dips_autonomous_enrollment import validate_enrollment

    from scripts.observation_runtime.personal_coordination_store import (
        NativePersonalCoordinationImages,
    )
    from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority
    from scripts.observation_runtime.personal_runtime_current import PersonalRuntimeCurrent
    from scripts.observation_runtime.personal_windows_clock import LocalWindowsClock
    from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership

    if (any(v is None for v in (policy, enrollment, runtime_dependencies, native_dependencies,
                                store, native_reader, installation, local_clock, runtime_id))
            or type(installation) is not PersonalOperatorInstallation
            or type(installation.reader) is not NativePersonalActivationReader
            or type(local_clock) is not LocalWindowsClock):
        raise ValueError('PERSONAL_INSTALLED_NATIVE_DEPENDENCIES_REQUIRED')
    local_clock.require_operational(runtime_id)
    e = validate_enrollment(enrollment)
    engine = runtime_dependencies['engine']
    ledger = engine.ledger
    custody = native_dependencies['custody']
    if (type(custody) is not PersonalRuntimeCurrent or runtime_dependencies['custody'] is not custody
            or custody.source is not store.trust
            or custody.reports is not runtime_dependencies['reports'].archive.trust
            or custody.source.ledger is not ledger or custody.reports.ledger is not ledger
            or custody.reader is not runtime_dependencies['reader'] or custody.native_reader is not native_reader
            or custody.clock is not local_clock):
        raise ValueError('PERSONAL_INSTALLED_CURRENT_CUSTODY_BINDING')
    if (type(ledger) is not PersonalNativeCoordination
            or type(ledger.images) is not NativePersonalCoordinationImages
            or ledger.images.root_id != e['resources']['coordination']['native_id']
            or ledger.images.enrollment != digest(e)
            or ledger.images.root != e['resources']['coordination']['path']
            or ledger.path.parent != Path(ledger.images.root)
            or digest(ledger.manifest) != e['inception_digest']
            or engine.clock is not local_clock or native_dependencies['clock'] is not local_clock
            or body(native_reader.enrollment) != body(e)):
        raise ValueError('PERSONAL_INSTALLED_COORDINATION_OR_CLOCK_BINDING')
    from app.services.quality_dips_personal_dependencies import PersonalSessionReservations

    authority, owner, sessions = installation.identity, native_dependencies['ownership'], native_dependencies['sessions']
    if (type(authority) is not NativePersonalOperatorAuthority or authority.reader is not installation.reader
            or authority.clock is not local_clock or body(authority.enrollment) != body(e)
            or type(owner) is not NativePersonalWriterOwnership or owner.authority is not authority
            or owner.ledger is not ledger
            or body(owner.enrollment) != body(e) or runtime_dependencies['ownership'] is not owner
            or type(sessions) is not PersonalSessionReservations or sessions.ledger is not ledger
            or sessions.authorization is not authority):
        raise ValueError('PERSONAL_INSTALLED_SESSION_OR_WRITER_BINDING')
    # Existing-only read rejects missing/partial coordination, without repair.
    with ledger.connect(readonly=True) as db:
        state, head, _ = ledger._load(db)
        if db.execute('SELECT 1 FROM projections WHERE receipt IS NULL').fetchone():
            raise ValueError('PERSONAL_INSTALLED_UNACKNOWLEDGED_COORDINATION')
    native_reader.verify_resources()
    cut = native_reader.read_committed()
    if (cut.get('schema') != 'QD_AUTO_OP_READ_V1' or cut.get('state') != state
            or cut.get('head') != head or cut.get('manifest') != ledger.manifest):
        raise ValueError('PERSONAL_INSTALLED_NATIVE_MIRROR_DISAGREEMENT')
    return compose_personal_qd(policy=policy, enrollment=e, runtime_dependencies=runtime_dependencies,
                              native_dependencies=native_dependencies, store=store,
                              native_reader=native_reader, installation=installation)
