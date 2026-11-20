"""Offline checks of the one-shot native test's confinement and resource guard."""
import pytest

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
