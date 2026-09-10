from app.trading_core.perp_board import build_perp_board


def _setup(symbol, *, tier, state, score, alert=False):
    return {
        "symbol": symbol,
        "side": "LONG",
        "tier": tier,
        "state": state,
        "score": score,
        "price": 100.0,
        "alert_eligible": alert,
        "next_action": "Place L1 limit only if the setup remains valid.",
        "levels": {"l1": 99.5, "l2": 99.0, "l3": 98.5, "stop": 97.5, "tp1": 103.0, "tp2": 106.0},
    }


def test_board_orders_prime_before_qualified_and_watch():
    board = build_perp_board([
        _setup("SOL", tier="WATCH", state="WAIT", score=68),
        _setup("ETH", tier="QUALIFIED", state="PREPARE", score=75),
        _setup("BTC", tier="PRIME", state="L1_ACTIVE", score=88, alert=True),
    ])
    assert [r["symbol"] for r in board] == ["BTC", "ETH", "SOL"]
    assert board[0]["alert_eligible"] is True


def test_board_exposes_manual_levels():
    row = build_perp_board([_setup("BTC", tier="PRIME", state="PREPARE", score=90)])[0]
    assert row["l1"] == 99.5
    assert row["l2"] == 99.0
    assert row["l3"] == 98.5
    assert row["stop"] == 97.5
    assert row["tp1"] == 103.0
    assert row["tp2"] == 106.0


def test_board_limit_is_enforced():
    rows = [_setup(f"X{i}", tier="WATCH", state="WAIT", score=50 + i) for i in range(10)]
    assert len(build_perp_board(rows, limit=3)) == 3


def test_board_rejects_malformed_side_rows():
    bad = _setup("AAPL", tier="PRIME", state="PREPARE", score=99)
    bad["side"] = "BUY"
    assert build_perp_board([bad]) == []
