"""Offline checks of the one-shot native test's confinement and resource guard."""
import stat
from types import SimpleNamespace

import pytest

from scripts import native_install_adapter_acceptance as acceptance
from scripts.native_install_adapter_acceptance import contained, enforce, main


@pytest.mark.parametrize('entries,size,now',[(40000,0,1),(0,1024**3,1),(0,0,590),(39999,1024**3-1,589)])
def test_total_scope_guards_include_all_retained_children(entries,size,now):
    if entries==39999:
        enforce(0,entries,size,now=now)
    else:
        with pytest.raises(ValueError,match='LIMIT_REFUSAL'):
            enforce(0,entries,size,now=now)


def test_foreign_destination_refused_without_creation(tmp_path):
    with pytest.raises(ValueError,match='ESCAPE'):
        contained(tmp_path/'foreign',tmp_path/'owned')


def test_no_implicit_native_execution():
    with pytest.raises(SystemExit,match='GRANT_REQUIRED'):
        main([])


@pytest.mark.parametrize('allowed,listed,expected',[((),['a','b'],'LINKED_FILE'),
    (('a','b'),['a','b'],None),(('a','b'),['a'],'EXTERNAL_HARDLINK_ALIAS')])
def test_only_complete_explicit_owned_probe_alias_group_is_counted(tmp_path,monkeypatch,allowed,listed,expected):
    original=type(tmp_path).lstat
    def metadata(path,*args,**kwargs):
        if path.parent==tmp_path and path.name in ('a','b'):
            return SimpleNamespace(st_mode=stat.S_IFREG,st_nlink=2,st_dev=1,st_ino=2,st_size=10)
        return original(path,*args,**kwargs)
    monkeypatch.setattr(acceptance,'contained',lambda p:p)
    monkeypatch.setattr(acceptance.os,'walk',lambda *a,**k:[(tmp_path,[],listed)])
    monkeypatch.setattr(type(tmp_path),'lstat',metadata)
    if expected:
        with pytest.raises(ValueError,match=expected):
            acceptance.usage(tmp_path,permitted_probe_links=allowed)
    else:
        assert acceptance.usage(tmp_path,permitted_probe_links=allowed)==(3,20)
