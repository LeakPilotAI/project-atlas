import sqlite3

import pytest
from app.adapters.hyperliquid_request_gate import (
    HyperliquidRequestGate,
    RequestGateRefused,
)


def gate(tmp_path, **kwargs):
    return HyperliquidRequestGate(tmp_path/"gate.sqlite", rights_approved=kwargs.get("rights",True), budget_approved=kwargs.get("budget",True), max_attempts=2)


@pytest.mark.parametrize("value", ["yes", 1, [], None])
def test_nonboolean_approval_denied(tmp_path, value):
    with pytest.raises(RequestGateRefused): gate(tmp_path,rights=value)
    with pytest.raises(RequestGateRefused): gate(tmp_path,budget=value)


@pytest.mark.parametrize("sql", ["UPDATE budget SET attempted=-1", "UPDATE budget SET attempted=99", "UPDATE budget SET max_attempts=999", "DELETE FROM budget"])
def test_corrupt_gate_never_resets_or_spends(tmp_path,sql):
    g=gate(tmp_path)
    with sqlite3.connect(g.path) as db: db.execute(sql)
    with pytest.raises(RequestGateRefused): g.remaining()
    with pytest.raises(RequestGateRefused): g.consume_before_attempt("HTTP")
    with pytest.raises(RequestGateRefused): gate(tmp_path)


def test_gate_missing_after_init_does_not_recreate(tmp_path):
    g=gate(tmp_path)
    g.path.rename(tmp_path/"preserved.sqlite")
    with pytest.raises(RequestGateRefused): g.consume_before_attempt("HTTP")
    assert not g.path.exists()
