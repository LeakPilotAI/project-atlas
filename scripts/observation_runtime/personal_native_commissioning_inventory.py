"""Read-only native PAPER commissioning inventory. Never grants authority."""
import json
from pathlib import Path


def inspect(*, personal_parent=Path(r'D:\AtlasCustody\PersonalPaper'),
            qd_parent=Path(r'D:\AtlasCustody\QualityDips')):
    def children(parent):
        if not parent.is_dir():
            return None
        return sorted(p.name for p in parent.iterdir() if p.is_dir() and not p.is_symlink())
    personal, qd = children(personal_parent), children(qd_parent)
    activation_candidates = []
    for name in personal or []:
        candidate = personal_parent / name / 'activation.json'
        if candidate.is_file() and not candidate.is_symlink():
            activation_candidates.append(name)
    return {'schema': 'ATLAS_PERSONAL_NATIVE_COMMISSIONING_INVENTORY_V1',
            'personal_parent_present': personal is not None,
            'personal_child_count': len(personal or []),
            'ordinary_activation_file_candidates': activation_candidates,
            'quality_dips_parent_present': qd is not None,
            'quality_dips_child_count': len(qd or []),
            'native_activation_verified': False,
            'account_enrollment_verified': False,
            'financial_inception_authorized': False,
            'paper_start_authorized': False,
            'reason': 'NATIVE_HANDLE_BOUND_ACTIVATION_AND_ACCOUNT_ENROLLMENTS_REQUIRED'}


if __name__ == '__main__':
    print(json.dumps(inspect(), sort_keys=True))
