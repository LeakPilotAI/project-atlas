"""Research history reads must never bootstrap legacy storage."""
import pytest
from app.investment import history


@pytest.mark.parametrize('reader',[history.load_dates,history.load_bars])
def test_missing_research_history_read_never_creates_paths(reader,tmp_path,monkeypatch):
 calls=[];monkeypatch.setattr(history,'ensure_dirs',lambda:calls.append('WRITE'))
 root=tmp_path/'missing-research'
 assert not reader('SYNTHETIC',root=root)
 assert not root.exists() and calls==[]
