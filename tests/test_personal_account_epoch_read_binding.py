"""Operational account identity stays distinct from its immutable epoch identity."""
import copy
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.quality_dips_operational_presentation import OperationalAutonomousSelectedRead
from test_personal_paper_inception_memory import system


def test_distinct_native_account_and_epoch_are_bound_without_relabeling():
    s=system('QUALITY_DIPS')
    try:
        assert s.n['account_id'] != s.m['epoch']
        enrollment={'account_id':s.n['account_id'],'epoch':s.m['epoch'],
                    'manifest_digest':digest(s.m),'policy_digest':s.n['policy_digest']}
        reader=object.__new__(OperationalAutonomousSelectedRead)
        reader.port=SimpleNamespace(enrollment=s.n)
        original=copy.deepcopy(s.n)
        assert reader._manifest_scope(s.m,enrollment,s.n['account_id'])
        for field in ('account_id','epoch','manifest_digest','policy_digest'):
            foreign={**enrollment,field:'FOREIGN'}
            assert not reader._manifest_scope(s.m,foreign,s.n['account_id'])
        assert s.n==original
    finally:s.ledger.db.close()


def test_fixture_or_manual_native_schema_is_not_operational_account_evidence():
    s=system('QUALITY_DIPS')
    try:
        reader=object.__new__(OperationalAutonomousSelectedRead)
        reader.port=SimpleNamespace(enrollment={**s.n,'schema':'FS2_TEST_PIN_V1'})
        with pytest.raises(ValueError):reader._manifest_scope(s.m,{},s.n['account_id'])
    finally:s.ledger.db.close()
