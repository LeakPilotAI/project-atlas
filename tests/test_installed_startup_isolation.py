"""Launch policy qualification; no installed or financial process is started."""
import ast
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import install_verified_release as adapter, installed_nonfinancial_launcher as launcher


def readback_code():
    tree=ast.parse(Path(adapter.__file__).read_text(encoding='utf-8-sig'))
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='installed_readback')
    return next(n.value.value for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in n.targets))


def startup(code):
    begin=code.index('if not sys.flags.isolated')
    end=code.index('sys.path[:0]',begin)
    return code[begin:end]


@pytest.mark.parametrize('contract',[readback_code(),launcher.CHILD,launcher.DISPOSABLE_CHILD],ids=['readback','installed-child','disposable-child'])
@pytest.mark.parametrize('fault',['site-enabled','relative-hook','outside-root','bytecode-enabled','live-bytecode'])
def test_actual_bootstrap_guards_reject_unsafe_startup(tmp_path,contract,fault):
    flags=SimpleNamespace(isolated=1,no_site=1,dont_write_bytecode=1)
    runtime=SimpleNamespace(flags=flags,dont_write_bytecode=True,path=[str(tmp_path/'python/Lib')])
    if fault=='site-enabled':flags.no_site=0
    elif fault=='relative-hook':runtime.path.append('__editable__.project_atlas.finder.__path_hook__')
    elif fault=='outside-root':runtime.path.append(str(tmp_path.parent/'workspace'))
    elif fault=='bytecode-enabled':flags.dont_write_bytecode=0
    else:runtime.dont_write_bytecode=False
    with pytest.raises(ValueError):exec(startup(contract),{'sys':runtime,'Path':Path,'root':tmp_path,'request':{'seconds':120,'requests':96}})


@pytest.mark.parametrize('contract',[readback_code(),launcher.CHILD,launcher.DISPOSABLE_CHILD],ids=['readback','installed-child','disposable-child'])
def test_actual_guards_accept_only_absolute_release_paths(tmp_path,contract):
    runtime=SimpleNamespace(flags=SimpleNamespace(isolated=1,no_site=1,dont_write_bytecode=1),dont_write_bytecode=True,path=[str(tmp_path/'python/Lib')])
    exec(startup(contract),{'sys':runtime,'Path':Path,'root':tmp_path,'request':{'seconds':120,'requests':96}})


def test_dependency_directory_can_import_without_executing_editable_or_customization(tmp_path):
    deps=tmp_path/'python/Lib/site-packages';deps.mkdir(parents=True)
    (deps/'editable.pth').write_text('import builtins; builtins.ATLAS_UNSAFE_SITE_EXECUTED=True\n')
    (deps/'sitecustomize.py').write_text('import builtins; builtins.ATLAS_UNSAFE_SITE_EXECUTED=True\n')
    (deps/'approved_dependency.py').write_text('VALUE="verified-local"\n')
    code='import sys,json,builtins; sys.path.insert(0,sys.argv[1]); import approved_dependency; print(json.dumps({"site_disabled":sys.flags.no_site,"dependency":approved_dependency.VALUE,"site_executed":getattr(builtins,"ATLAS_UNSAFE_SITE_EXECUTED",False)}))'
    r=subprocess.run([sys.executable,'-I','-B','-S','-c',code,str(deps)],capture_output=True,timeout=8,check=True)
    assert json.loads(r.stdout)=={'site_disabled':1,'dependency':'verified-local','site_executed':False}
    assert not list(tmp_path.rglob('*.pyc'))


def test_outer_installed_entry_requires_no_site_and_absolute_paths():
    text=Path(launcher.__file__).read_text(encoding='utf-8-sig')
    fn=ast.parse(text).body
    body=next(n for n in fn if isinstance(n,ast.FunctionDef) and n.name=='support_entry')
    checks=ast.get_source_segment(text,body)
    assert 'sys.flags.no_site' in checks and 'Path(p).is_absolute()' in checks
    assert 'site.addsitedir' not in checks.replace('# Add the verified directory without site.addsitedir:','')
    module=Path('scripts/windows/Atlas-Installed-Nonfinancial.psm1').read_text(encoding='utf-8-sig')
    assert "'-I -B -S " in module
