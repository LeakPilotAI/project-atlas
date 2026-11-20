"""Exact Hyperliquid PAPER initialization native coordination memory image.

All SQLite bytes stay in-memory; no real account or first-publication records.
"""
from __future__ import annotations

import copy
import sqlite3

import pytest
from app.services.personal_native_coordination import (
    PersonalNativeCoordination,
    _validate_initial_native_paper_manifest,
)
from test_personal_paper_inception_memory import system


@pytest.mark.parametrize("lane", ["QUALITY_DIPS", "HYPERLIQUID"])
def test_native_initialization_image_supports_both_actual_simulated_manifest_schemas(lane):
    s=system(lane)
    try:
        m=copy.deepcopy(s.m)
        assert _validate_initial_native_paper_manifest(m)==m
        blob=PersonalNativeCoordination.initial_image(m)
        assert type(blob) is bytes and 10000 < len(blob) <= 1024*1024
        db=sqlite3.connect(":memory:")
        try:
            db.deserialize(blob)
            assert db.execute("SELECT body FROM inception").fetchall()==[
                ( __import__("app.services.paper_financial_replay",fromlist=["body"]).body(m), )
            ]
            assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0]==0
            assert db.execute("SELECT COUNT(*) FROM personal_sessions").fetchone()[0]==0
            assert db.execute("SELECT COUNT(*) FROM personal_publications").fetchone()[0]==0
        finally:
            db.close()
        observed=copy.deepcopy(s.m)
        dummy=object()
        ledger=PersonalNativeCoordination(
            manifest=observed, images=dummy,
            path="D:/NONEXISTENT_ONLY_NO_FILES/coordination.image",
        )
        assert ledger.images is dummy
        assert ledger.manifest == m
        assert s.m == m
    finally:
        s.ledger.db.close()


@pytest.mark.parametrize("damage", [
    "fixture_schema", "foreign_schema", "wrong_cash", "wrong_currency",
    "no_release", "invalid_leverage", "invalid_max_positions",
    "invalid_bps", "wrong_fee_schedule",
])
def test_native_perp_coordination_refuses_unapproved_or_invalid_manifest(damage):
    s=system("HYPERLIQUID")
    try:
        m=copy.deepcopy(s.m)
        if damage=="fixture_schema":
            m["schema"]="PAPER_EPOCH_PERP_FIXTURE_V2"
        elif damage=="foreign_schema":
            m["schema"]="PAPER_EPOCH_FIXTURE_V1"
        elif damage=="wrong_cash":
            m["opening_cash"]="2000"
        elif damage=="wrong_currency":
            m["currency"]="USD"
        elif damage=="no_release":
            m["release"]=""
        elif damage=="invalid_leverage":
            m["perp_policy"]["max_leverage"]="0"
        elif damage=="invalid_max_positions":
            m["perp_policy"]["max_positions"]=999
        elif damage=="invalid_bps":
            m["perp_policy"]["maker_bps"]="-5"
        elif damage=="wrong_fee_schedule":
            m["perp_policy"]["fee_schedule_id"]=""
        with pytest.raises((ValueError,TypeError,KeyError)):
            PersonalNativeCoordination.initial_image(m)
    finally:
        s.ledger.db.close()


def test_native_initialization_does_not_grant_trading_or_external_broker_access():
    assert not hasattr(PersonalNativeCoordination,"place_order")
    assert not hasattr(PersonalNativeCoordination,"submit_order")
    assert not hasattr(PersonalNativeCoordination,"create_external_account")
