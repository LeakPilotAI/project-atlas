"""Execution-scope and runtime-layout checks without native operations or files."""
import pytest

from scripts.observation_runtime.native_fixture_budget import (
    BYTES as OLD_BYTES,
)
from scripts.observation_runtime.native_fixture_budget import (
    FILES as OLD_FILES,
)
from scripts.observation_runtime.native_fixture_budget import (
    BudgetRefused,
    reserve_budget,
    session_limits,
)
from scripts.observation_runtime.personal_native_scope import (
    AUTHORIZATION,
    BYTES,
    ENTRIES,
    ROOT,
    SECONDS,
    assess_python_layout,
    require_scope,
)


def test_personal_scope_is_exact_and_narrower_than_original_v1_v2():
    assert require_scope(AUTHORIZATION,ROOT)==session_limits(AUTHORIZATION,ROOT)==(600,4096,134217728)
    assert SECONDS==600 and ENTRIES<OLD_FILES and BYTES<OLD_BYTES
    assert session_limits('P-ATLAS-NATIVE-CONTINUATION-DISPOSABLE-V1',ROOT)==(1800,8192,268435456)


@pytest.mark.parametrize('authority,root',[(None,ROOT),('APPROVED',ROOT),(AUTHORIZATION,ROOT+'-other'),(AUTHORIZATION,ROOT+'\\..'),('P-ATLAS-NATIVE-CONTINUATION-DISPOSABLE-V2',ROOT)])
def test_missing_or_reused_grant_and_scope_substitution_refuse(authority,root):
    with pytest.raises(ValueError):require_scope(authority,root)


@pytest.mark.parametrize('kind',['entries','bytes','boolean-limit','increase-limit'])
def test_personal_reservations_cannot_spend_original_larger_budget(kind):
    usage={'entries':4,'charged_bytes':49152};limits={'max_entries':ENTRIES,'max_bytes':BYTES}
    if kind=='entries':usage['entries']=ENTRIES
    elif kind=='bytes':usage['charged_bytes']=BYTES-4096
    elif kind=='boolean-limit':limits['max_entries']=True
    else:limits['max_bytes']=OLD_BYTES+1
    with pytest.raises(BudgetRefused):reserve_budget(usage,entries=1,size=4096,unit=4096,**limits)


def layout():
    base='D:\\AtlasRuntime\\releases\\'+'a'*40+'\\python'
    return {'schema':'PERSONAL_PYTHON_LAYOUT_V1','launch_executable':base+'\\python.exe',
            'native_image':base+'\\python.exe','python_executable':base+'\\python.exe',
            'base_executable':base+'\\python.exe','prefix':base,'base_prefix':base,'stdlib':base+'\\Lib',
            'version':'3.12','architecture_bits':64}


def test_structural_runtime_check_is_never_startup_or_enrollment_authority():
    result=assess_python_layout(layout())
    assert result['state']=='STRUCTURALLY_COMPATIBLE'
    assert not result['startup_authorized'] and not result['operational_acceptance']


@pytest.mark.parametrize('field',['launch_executable','native_image','base_executable','base_prefix','stdlib','version','architecture_bits'])
def test_d_venv_does_not_hide_c_base_or_actual_image(field):
    value=layout();value[field]=32 if field=='architecture_bits' else '3.13' if field=='version' else 'C:\\installed-python\\python.exe'
    assert assess_python_layout(value)['state']=='NOT_READY'


@pytest.mark.parametrize('path',['D:\\tools\\..\\python.exe','D:\\tools\\python.exe:stream','D:\\%APP%\\python.exe','D:/python.exe'])
def test_unresolved_runtime_paths_refuse(path):
    value=layout();value['base_executable']=path
    assert assess_python_layout(value)['state']=='NOT_READY'
