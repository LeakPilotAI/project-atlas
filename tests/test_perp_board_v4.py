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


def test_long_limits_below_mark_are_resting():
    row = build_perp_board([_setup("BTC", tier="PRIME", state="PREPARE", score=90)])[0]
    assert row["limit_sanity"]["l1"]["behavior"] == "RESTING"
    assert row["limit_sanity"]["l1"]["marketable"] is False
    assert "Leverage affects exposure" in row["leverage_note"]


def test_short_limit_below_mark_is_flagged_marketable():
    setup = _setup("XRP", tier="QUALIFIED", state="PREPARE", score=80)
    setup["side"] = "SHORT"
    setup["levels"]["l1"] = 99.5
    row = build_perp_board([setup])[0]
    assert row["limit_sanity"]["l1"]["behavior"] == "MARKETABLE"
    assert row["limit_sanity"]["l1"]["marketable"] is True


def test_resting_actionable_l1_gets_exact_manual_instruction():
    row = build_perp_board([_setup("BTC", tier="PRIME", state="PREPARE", score=90)])[0]
    instruction = row["manual_instruction"]
    assert instruction["action"] == "PLACE_RESTING_L1"
    assert instruction["can_mark_entered"] is True
    assert instruction["limit_price"] == 99.5
    assert instruction["order_type"] == "LIMIT"


def test_stale_setup_blocks_new_manual_order_even_with_resting_l1():
    setup = _setup("BTC", tier="PRIME", state="WAIT", score=90)
    setup["discovery_stale"] = True
    row = build_perp_board([setup])[0]
    assert row["manual_instruction"]["action"] == "NO_NEW_ORDER"
    assert row["manual_instruction"]["can_mark_entered"] is False
    assert "STALE SETUP" in row["manual_instruction"]["headline"]


def test_marketable_l1_blocks_new_manual_order():
    setup = _setup("XRP", tier="QUALIFIED", state="PREPARE", score=80)
    setup["side"] = "SHORT"
    setup["levels"]["l1"] = 99.5
    row = build_perp_board([setup])[0]
    assert row["manual_instruction"]["action"] == "NO_NEW_ORDER"
    assert row["manual_instruction"]["can_mark_entered"] is False
    assert "FILL NOW" in row["manual_instruction"]["headline"]


def test_wait_state_blocks_manual_entry():
    row = build_perp_board([_setup("SOL", tier="PRIME", state="WAIT", score=90)])[0]
    assert row["manual_instruction"]["action"] == "WAIT"
    assert row["manual_instruction"]["can_mark_entered"] is False


def test_board_limit_is_enforced():
    rows = [_setup(f"X{i}", tier="WATCH", state="WAIT", score=50 + i) for i in range(10)]
    assert len(build_perp_board(rows, limit=3)) == 3


def test_board_rejects_malformed_side_rows():
    bad = _setup("AAPL", tier="PRIME", state="PREPARE", score=99)
    bad["side"] = "BUY"
    assert build_perp_board([bad]) == []
