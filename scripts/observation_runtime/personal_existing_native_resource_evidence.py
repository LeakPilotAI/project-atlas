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


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True))
