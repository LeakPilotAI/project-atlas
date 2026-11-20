"""Disjoint disposable accounts, not a new operational admission path."""
import hashlib
import sqlite3
from decimal import Decimal

import pytest
from test_hyperliquid_native_fixture import request, restart, setup
from test_hyperliquid_paper_handoff import STAMP


def digest_tree(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def test_disjoint_accounts_preserve_unresolved_history_and_independent_cash(tmp_path):
    historical = tmp_path / "retained"
    historical.mkdir()
    h, _, old = setup(historical)
    before = digest_tree(historical)
    fresh = tmp_path / "new"
    fresh.mkdir()
    f, pin, new = setup(fresh)
    old_ids = set(old.snapshot()["position_revisions"])
    new_ids = set(new.snapshot()["position_revisions"])
    assert not old_ids.intersection(new_ids)
    r = request(new, quantity="0.5", price="104")
    receipt = new.record_exit(r, now=STAMP + 2)
    assert restart(f, pin).record_exit(r, now=STAMP + 2) == receipt
    report = new.daily_report(day="2026-10-23", timezone="UTC", currency="USD")
    assert Decimal(report["report"]["closing_cash"]) == Decimal("1001.96")
    assert not report["shutdown_authorized"]
    assert not receipt["production_authorized"]
    assert digest_tree(historical) == before
    assert len(h[3].PaperJournal().list_open()) == 1
    assert not old.snapshot()["view"]["native_positions_flat"]


@pytest.mark.parametrize("foreign", ["request", "baseline", "association"])
def test_cross_account_identity_is_not_accepted(tmp_path, foreign):
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
    a, ap, first = setup(tmp_path / "a")
    b, _, second = setup(tmp_path / "b")
    before = digest_tree(tmp_path)
    with pytest.raises(ValueError):
        if foreign == "request":
            second.record_exit(request(first), now=STAMP + 2)
        else:
            from app.services.hyperliquid_native_fixture import NativeFixtureFacade
            NativeFixtureFacade(b[0], b[1], baseline=a[2] if foreign == "baseline" else b[2],
                                association=ap, journal=b[3].PaperJournal(),
                                journal_path=b[3].JOURNAL_PATH, manual_store=b[4]).snapshot()
    assert digest_tree(tmp_path) == before


@pytest.mark.parametrize("missing", ["opening_cash", "price"])
def test_missing_evidence_never_authorizes_completion(tmp_path, missing):
    f, _, facade = setup(tmp_path)
    if missing == "price":
        r = request(facade)
        del r["quote"]["price"]
        with pytest.raises((ValueError, KeyError)):
            facade.record_exit(r, now=STAMP + 2)
        # The facade conservatively retains an unacknowledged intent. Do not
        # erase it or assume malformed downstream input made replay safe.
        with pytest.raises(ValueError, match="Unacknowledged"):
            facade.snapshot()
        with sqlite3.connect(f[1]) as db:
            assert db.execute("SELECT COUNT(*) FROM partial_fills").fetchone()[0] == 0
    else:
        # Corrupt only the disposable account; no balance fallback is acceptable.
        with sqlite3.connect(f[1]) as db:
            db.execute("DELETE FROM cash_evidence")
    with pytest.raises(ValueError):
        facade.daily_report(day="2026-10-23", timezone="UTC", currency="USD")
