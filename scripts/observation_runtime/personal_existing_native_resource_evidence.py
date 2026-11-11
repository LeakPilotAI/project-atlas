"""Read-only native Windows resource evidence for existing personal PAPER epochs.

This is not enrollment, writer ownership, inception or activation authority.
"""
import json
from pathlib import Path

QD_EPOCH = 'qd-paper-20261024-b2cbd50cfe59475fa3726549365cc253'
QD_BASE = Path(r'D:\AtlasPaper\QualityDips') / QD_EPOCH
QD_CUSTODY = Path(r'D:\AtlasCustody\QualityDips') / QD_EPOCH
ROLES = ('source', 'projection', 'report', 'control', 'coordination', 'custody')


def inspect(*, base=QD_BASE, custody=QD_CUSTODY):
    from scripts.observation_runtime.personal_paper_inception import native_primitives
    native = native_primitives()
    result = {}
    for role in ROLES:
        path = custody if role == 'custody' else base / role
        try:
            with native.w.WindowsOutput(str(path)) as output:
                identity = native.native.file_identity(output.root_handle)
            result[role] = {'path': str(path), 'native_id': identity, 'verified': True}
        except (OSError, ValueError) as exc:
            result[role] = {'path': str(path), 'verified': False,
                            'reason': type(exc).__name__}
    verified = all(item['verified'] for item in result.values())
    ids = [tuple(item['native_id']) for item in result.values() if item['verified']]
    unique = len(ids) == len(set(ids))
    return {'schema': 'ATLAS_QD_EXISTING_NATIVE_RESOURCE_EVIDENCE_V1',
            'epoch': base.name, 'resources': result,
            'all_six_verified': verified and unique,
            'native_identities_distinct': unique,
            'enrollment_accepted': False, 'writer_ownership_verified': False,
            'financial_inception_authorized': False, 'paper_start_authorized': False}



HL_EPOCH = 'hl-paper-20261108-de437abe-v1'
HL_BASE = Path(r'D:\AtlasPaper\Hyperliquid') / HL_EPOCH
HL_CUSTODY = Path(r'D:\AtlasCustody\Hyperliquid') / HL_EPOCH


def inspect_two_lane_native_roots(*, qd_base=QD_BASE, qd_custody=QD_CUSTODY,
                                  hl_base=HL_BASE, hl_custody=HL_CUSTODY):
    """Windows handle-bound, existing-only QD+perp root evidence.

    Identity and an empty namespace are technical PRECONDITIONS for a future
    independent enrollment. Neither this scan nor an inferred writer roster
    constitutes an accepted enrollment, financial inception or session grant.
    Never creates a directory, file, account, process or network request.
    """
    from scripts.observation_runtime.personal_paper_inception import native_primitives

    lanes = {
        'QUALITY_DIPS': (Path(qd_base), Path(qd_custody)),
        'HYPERLIQUID': (Path(hl_base), Path(hl_custody)),
    }
    native = native_primitives()
    records = {}
    all_ids = []
    all_paths = []
    for lane, (base, custody) in lanes.items():
        roots = {}
        for role in ROLES:
            path = custody if role == 'custody' else base / role
            entry = {'path': str(path), 'native_identity_verified': False,
                     'existing_empty_namespace_verified': False}
            try:
                # Reject aliases/reparse points before opening a Windows
                # handle: a plausible path string is not custody identity.
                for candidate in (path, base, custody):
                    if (not candidate.is_dir() or candidate.is_symlink()
                            or candidate.is_junction()):
                        raise ValueError('NONORDINARY_NATIVE_RESOURCE_DIRECTORY')
                if path.is_symlink() or path.is_junction():
                    raise ValueError('REPARSE_NATIVE_RESOURCE_REFUSED')
                # Handle readback, independent from stat or JSON enrollment.
                with native.w.WindowsOutput(str(path)) as output:
                    native_id = native.native.file_identity(output.root_handle)
                if (type(native_id) is not list or len(native_id) != 3
                        or any(type(v) is not int or v < 0 for v in native_id)):
                    raise ValueError('NATIVE_RESOURCE_FILE_ID_REFUSED')
                entry['native_id'] = native_id
                entry['native_identity_verified'] = True
                # Only enumerate names; never open, alter or adopt a file.
                entry['existing_empty_namespace_verified'] = not any(path.iterdir())
                all_ids.append(tuple(native_id))
                all_paths.append(str(path).casefold())
            except (OSError, ValueError) as exc:
                entry['reason'] = type(exc).__name__
            roots[role] = entry
        records[lane] = {'epoch': base.name, 'roots': roots}
    total = sum(len(item['roots']) for item in records.values())
    verified = sum(
        int(entry['native_identity_verified'])
        for lane in records.values() for entry in lane['roots'].values()
    )
    empty = sum(
        int(entry['existing_empty_namespace_verified'])
        for lane in records.values() for entry in lane['roots'].values()
    )
    distinct = (verified == len(all_ids) == total
                and len(set(all_ids)) == total
                and len(set(all_paths)) == total)
    preconditions = total == 12 and verified == 12 and empty == 12 and distinct
    return {
        'schema': 'ATLAS_TWO_LANE_EXISTING_NATIVE_ROOT_PRE_ENROLLMENT_V1',
        'lanes': records,
        'native_root_total': total,
        'native_root_ids_verified': verified,
        'existing_empty_root_namespaces': empty,
        'all_twelve_distinct_and_empty': preconditions,
        'next_unmet_stage': (
            'INDEPENDENT_ACCOUNT_ENROLLMENTS_WITH_ACCEPTED_WRITER_OWNERSHIP'
            if preconditions else
            'REPAIR_OR_REVIEW_EXISTING_NATIVE_RESOURCE_IDENTITY_WITHOUT_ADOPTION'
        ),
        'activation_publication_can_precede_account_enrollment': False,
        'source_archive_genesis_requires_existing_native_activation': True,
        'operator_account_enrollment_verified': False,
        'writer_ownership_verified': False,
        'native_activation_record_verified': False,
        'financial_inception_verified': False,
        'current_scanner_source_issuer_accepted': False,
        'paper_start_authorized': False,
        'live_trading_authorized': False,
        'filesystem_writes': 0,
        'network_requests': 0,
    }

if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True))
