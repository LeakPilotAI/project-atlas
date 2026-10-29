"""Equivalent full inventory limits, including refusal before link descent."""
import stat
from types import SimpleNamespace

import pytest
from personal_fixture_budget import fixture_budget


def test_complete_inventory_counts_nested_directories_and_exact_bytes(tmp_path):
    (tmp_path/'child').mkdir()
    (tmp_path/'one').write_bytes(b'abc')
    (tmp_path/'child/two').write_bytes(b'defgh')
    assert fixture_budget(tmp_path, started=0, clock=lambda:0)==(3,8)


@pytest.mark.parametrize('setting,value', [('max_entries',2),('max_bytes',7),('extra',1)])
def test_count_and_byte_limits_remain_fail_closed(tmp_path,setting,value):
    (tmp_path/'one').write_bytes(b'12345678')
    (tmp_path/'two').write_bytes(b'')
    settings={'max_entries':2048,'max_bytes':8,'extra':0,setting:value}
    with pytest.raises(ValueError,match='RESOURCE_LIMIT'):
        fixture_budget(tmp_path,started=0,clock=lambda:0,**settings)


def test_exact_byte_ceiling_is_accepted_but_entry_ceiling_refuses(tmp_path):
    (tmp_path/'one').write_bytes(b'1234')
    assert fixture_budget(tmp_path,started=0,clock=lambda:0,max_bytes=4,max_entries=2)==(1,4)
    with pytest.raises(ValueError,match='RESOURCE_LIMIT'):
        fixture_budget(tmp_path,started=0,clock=lambda:0,max_bytes=4,max_entries=1)


def test_elapsed_budget_cannot_be_reset_by_an_empty_inventory(tmp_path):
    with pytest.raises(ValueError,match='RESOURCE_LIMIT'):
        fixture_budget(tmp_path,started=0,clock=lambda:181)


def test_missing_root_is_not_initialized(tmp_path):
    with pytest.raises(FileNotFoundError):
        fixture_budget(tmp_path/'absent',started=0,clock=lambda:0)
    assert not (tmp_path/'absent').exists()


@pytest.mark.parametrize('attributes,mode', [
    (stat.FILE_ATTRIBUTE_REPARSE_POINT,stat.S_IFDIR),
    (stat.FILE_ATTRIBUTE_REPARSE_POINT,stat.S_IFREG),
    (0,stat.S_IFIFO),
])
def test_reparse_and_special_entry_refuse_without_descending(tmp_path,monkeypatch,attributes,mode):
    import personal_fixture_budget as module
    calls=[]
    class Entries:
        def __enter__(self):
            return iter([SimpleNamespace(path=str(tmp_path/'untrusted'),
                stat=lambda **kwargs:SimpleNamespace(st_mode=mode,st_size=0,st_file_attributes=attributes))])
        def __exit__(self,*args):return False
    def scan(path):
        calls.append(path)
        assert path==str(tmp_path)
        return Entries()
    monkeypatch.setattr(module.os,'scandir',scan)
    with pytest.raises(ValueError,match='LINK_REFUSED'):
        fixture_budget(tmp_path,started=0,clock=lambda:0)
    assert calls==[str(tmp_path)]
