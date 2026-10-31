"""Explicit nonfinancial cache budgets and no-network offline replay."""
from datetime import timedelta

import pytest
from app.investment.free_research_transport import FreeResearchClient, ResearchRefused
from test_free_research_pipeline import CONTACT, NOW, SEC, client


@pytest.mark.parametrize('damage',['missing','stale'])
def test_cache_only_never_connects_or_changes_existing_evidence(tmp_path,damage):
    c,clock,calls,_=client(tmp_path)
    if damage=='stale':c.get(SEC,ttl=60);clock[0]+=timedelta(seconds=61)
    before={p.name:p.read_bytes() for p in c.root.iterdir()} if c.root.exists() else {}
    offline=FreeResearchClient(cache_root=c.root,now=lambda:clock[0],sec_user_agent=CONTACT,
        fetch=c.fetch,monotonic=c.mono,sleep=c.sleep,cache_only=True)
    count=len(calls)
    with pytest.raises(ResearchRefused,match='CACHE_ONLY'):offline.get(SEC,ttl=60)
    after={p.name:p.read_bytes() for p in c.root.iterdir()} if c.root.exists() else {}
    assert before==after and len(calls)==count and offline.attempted==0


def test_explicit_archive_budget_preserves_default_and_cannot_change_midrun(tmp_path):
    c,_,_,_=client(tmp_path)
    assert c.cache_maximum_bytes==64*1024*1024
    c.cache_maximum_bytes=128*1024*1024
    with pytest.raises(ResearchRefused,match='COMPONENT_CHANGED'):c.get(SEC,ttl=60)
    bounded=FreeResearchClient(cache_root=tmp_path/'small',now=lambda:NOW,sec_user_agent=CONTACT,
        fetch=lambda *args:b'{"data":1}',cache_maximum_bytes=1)
    with pytest.raises(ResearchRefused,match='CAPACITY'):bounded.get(SEC,ttl=60)
    assert not bounded.root.exists() and bounded.attempted==1


@pytest.mark.parametrize('limit',[0,-1,True,128*1024*1024+1,None])
def test_unbounded_or_invalid_cache_budget_refuses(tmp_path,limit):
    with pytest.raises(ResearchRefused,match='ARCHIVE_CACHE_BUDGET'):
        FreeResearchClient(cache_root=tmp_path,now=lambda:NOW,fetch=lambda *args:b'{}',cache_maximum_bytes=limit)
