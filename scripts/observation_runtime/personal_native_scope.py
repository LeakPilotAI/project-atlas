"""Pure proposed native-test scope. Constants are boundaries,not permission."""
import ntpath

AUTHORIZATION='P-ATLAS-PERSONAL-NATIVE-COMPATIBILITY-V1'
ROOT=r'D:\Work\Project Atlas\logs\diagnostics\continuation-fixture-d8a9f847f38c4bde9376e5158581280e'
SECONDS,ENTRIES,BYTES=600,4096,128*1024*1024


def require_scope(authorization,root):
    if authorization!=AUTHORIZATION or str(root)!=ROOT:
        raise ValueError('EXACT_PERSONAL_NATIVE_APPROVAL_AND_ROOT_REQUIRED')
    return SECONDS,ENTRIES,BYTES


def assess_python_layout(value):
    """Structural test only; installed readiness also needs actual native evidence.

    No executable is opened,started,copied or authenticated by this function.
    The development venv may point to C:;that cannot attest D:operational readiness.
    """
    fields={'schema','launch_executable','native_image','python_executable','base_executable',
            'prefix','base_prefix','stdlib','architecture_bits','version'}
    if type(value) is not dict or set(value)!=fields or value['schema']!='PERSONAL_PYTHON_LAYOUT_V1':
        raise ValueError('EXACT_OBSERVED_PYTHON_LAYOUT_REQUIRED')
    reasons=[]
    for key in ('launch_executable','native_image','python_executable','base_executable','prefix','base_prefix','stdlib'):
        path=value[key]
        if (type(path) is not str or not path.startswith('D:\\') or ntpath.normpath(path)!=path
                or any(c in path[3:] for c in (':','%','\x00','/'))
                or any(p in ('','.','..') for p in path[3:].split('\\'))):
            reasons.append(key+':D_RESIDENT_EXACT_PATH_REQUIRED')
    if (type(value['architecture_bits']) is not int or value['architecture_bits']!=64
            or value['version']!='3.12'):
        reasons.append('PINNED_PYTHON312_X64_REQUIRED')
    return {'schema':'PERSONAL_PYTHON_LAYOUT_ASSESSMENT_V1',
            'state':'STRUCTURALLY_COMPATIBLE' if not reasons else 'NOT_READY',
            'reasons':reasons,'operational_acceptance':False,'startup_authorized':False}
