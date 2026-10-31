"""Crash-state/restart and competing reservations; synthetic in-memory stores only."""
import copy
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, RLock

import pytest
from app.services.paper_financial_replay import body, digest
from app.services.personal_publication_custody import PersonalPublicationCustody
from test_personal_paper_inception_memory import system


@pytest.mark.parametrize('state',['PENDING','COMMITTED','ACKNOWLEDGED'])
def test_restart_never_republishes_an_existing_inception_reservation(state):
    s=system('QUALITY_DIPS')
    try:
        intent=s.b.scope();context={'schema':'SYNTHETIC-OWNED-CONTEXT'}
        with s.custody.reserve(intent,context,s.now[0]) as tx:
            if state!='PENDING':
                committed=tx.commit({'schema':'SYNTHETIC-CURRENT','state':'ACKNOWLEDGED'},s.now[0])
                if state=='ACKNOWLEDGED':tx.acknowledge(committed,s.now[0])
        reopened=PersonalPublicationCustody(s.ledger)
        assert reopened.row(intent['operation_id'])[2]==state
        with pytest.raises(ValueError),reopened.reserve(intent,context,s.now[0]):pytest.fail('blind restart')
        if state!='ACKNOWLEDGED':
            with pytest.raises(ValueError):reopened.acknowledged(intent['operation_id'])
        assert not s.files.values
    finally:s.ledger.db.close()


def test_caller_mutation_cannot_change_reserved_intent_receipt():
    s=system('QUALITY_DIPS')
    try:
        intent=s.b.scope();original=copy.deepcopy(intent);context={'schema':'SYNTHETIC-CONTEXT'}
        with s.custody.reserve(intent,context,s.now[0]) as tx:
            intent['epoch']='caller-changed';context['schema']='caller-changed'
            commit=tx.commit({'schema':'SYNTHETIC-CURRENT'},s.now[0])
            tx.acknowledge(commit,s.now[0])
        _,ack=s.custody.acknowledged(original['operation_id'])
        assert commit['intent_digest']==digest(original) and ack['commit_digest']==digest(commit)
    finally:s.ledger.db.close()


def test_competing_publishers_have_only_one_durable_inception():
    s=system('HYPERLIQUID');s.ledger.db.close()
    s.ledger.db=sqlite3.connect(':memory:',check_same_thread=False);lock=RLock()
    @contextmanager
    def connect(readonly=False):
        with lock,s.ledger.db:yield s.ledger.db
    s.ledger.connect=connect
    PersonalPublicationCustody.install_schema(s.ledger.db);s.ledger.db.commit()
    barrier=Barrier(2)
    def publish():
        barrier.wait(timeout=5)
        try:return s.pub.publish()
        except ValueError:return 'REFUSED'
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:publish(),range(2)))
        assert sum(type(v) is dict for v in results)==1 and results.count('REFUSED')==1
        assert s.custody.row(s.b.scope()['operation_id'])[2]=='ACKNOWLEDGED'
        assert len(s.files.values)==3 and not any(role=='projection' for role,_ in s.files.values)
        assert s.ledger.db.execute('SELECT COUNT(*) FROM personal_publications').fetchone()[0]==1
        assert body(s.b.verify_publication()['current'])==body(next(v for v in results if type(v) is dict)['current'])
    finally:s.ledger.db.close()
