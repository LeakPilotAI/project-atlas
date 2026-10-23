"""Isolated transactional PAPER ledger; no production imports or activation."""
import hashlib
import json
import sqlite3
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from app.services.daily_paper_shutdown_plan import plan_shutdown
from app.services.paper_partial_accounting import replay_partial_fills


def create_fixture_ledger(path, positions):
    with Path(path).open("xb"):
        pass
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE positions(id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        db.execute("CREATE TABLE exits(id TEXT PRIMARY KEY, body TEXT NOT NULL)")
        db.execute("CREATE TABLE partial_fills(id TEXT PRIMARY KEY, trade TEXT NOT NULL, body TEXT NOT NULL)")
        db.execute("CREATE TABLE reports(session TEXT PRIMARY KEY, body TEXT NOT NULL)")
        db.execute("CREATE TABLE report_history(session TEXT, revision INTEGER, body TEXT, previous TEXT, digest TEXT, PRIMARY KEY(session,revision))")
        db.execute("CREATE TABLE control(stopped INTEGER NOT NULL)")
        db.execute("INSERT INTO control VALUES(0)")
        db.executemany("INSERT INTO positions VALUES(?,?)", [(p["trade_id"], json.dumps(p, sort_keys=True)) for p in positions])


def _number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite position accounting")
    return result


def _partial_position(p):
    return {**p, "schema": "PAPER_PARTIAL_POSITION_V1", "entry": p["actual_entry_price"]}


def _fixture_admission_state(db):
    rows = db.execute("SELECT stopped FROM control").fetchall()
    if rows not in ([(0,)], [(1,)]):
        raise ValueError("Corrupt or ambiguous fixture writer admission")
    return rows[0][0]


def append_partial_fixture(path, trade_id, fill, *, fault=lambda phase: None):
    """Persist an explicit fixture fill once; no execution/provider authority."""
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True, timeout=1) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        body = json.dumps(fill, sort_keys=True)
        prior = db.execute("SELECT body FROM partial_fills WHERE id=?", (fill["fill_id"],)).fetchone()
        if prior:
            if prior[0] != body:
                raise ValueError("Conflicting durable fill identity")
            return
        if _fixture_admission_state(db) != 0:
            raise ValueError("Fill admission quiesced")
        record = db.execute("SELECT body FROM positions WHERE id=?", (trade_id,)).fetchone()
        if not record or fill["trade_id"] != trade_id:
            raise ValueError("Unknown fill position")
        p = json.loads(record[0])
        fills = [json.loads(row[0]) for row in db.execute("SELECT body FROM partial_fills WHERE trade=? ORDER BY rowid", (trade_id,))]
        state = replay_partial_fills(_partial_position(p), [*fills, fill])
        if state["complete"] and (type(fill.get("session_id")) is not str or not fill["session_id"]):
            raise ValueError("Final fill requires explicit session identity")
        fault("before_partial")
        db.execute("INSERT INTO partial_fills VALUES(?,?,?)", (fill["fill_id"], trade_id, body))
        fault("after_partial")
        if state["complete"]:
            final = {"trade_id": trade_id, "session_id": fill["session_id"],
                     "exit_timestamp": fill["timestamp"], "reason": "RECORDED_PARTIAL_FILLS_COMPLETE",
                     "status": "SIMULATED_EXIT", "net_pnl_r": state["net_r_original_risk"],
                     "currency_accounting": {"currency": state["currency"], "net": state["net_currency"]},
                     "partial_accounting": state}
            db.execute("INSERT INTO exits VALUES(?,?)", (trade_id, json.dumps(final, sort_keys=True)))
            fault("after_finalization")
        fault("before_commit")
        db.commit()
        fault("after_commit")


def _report_digest(body, previous):
    return hashlib.sha256((previous + "\n" + body).encode()).hexdigest()


def verify_report_history(db, session):
    previous = ""
    latest = None
    revision = 0
    for number, body, parent, digest in db.execute(
        "SELECT revision,body,previous,digest FROM report_history WHERE session=? ORDER BY revision", (session,)
    ):
        revision += 1
        if number != revision or parent != previous or _report_digest(body, parent) != digest:
            raise ValueError("Corrupt report lineage")
        previous, latest = digest, body
    cached = db.execute("SELECT body FROM reports WHERE session=?", (session,)).fetchone()
    if (cached[0] if cached else None) != latest:
        raise ValueError("Report history/cache mismatch")
    return revision, previous


def liquidate(path, session, quotes, *, now, max_age, fault=lambda phase: None):
    """Exclusive transaction: exit and report commit together, retry after ambiguity.

    Isolated store only. Entry admission is fenced durably before pricing; no
    external order or writer is controlled by this prototype.
    """
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=rw", uri=True, timeout=1) as db:
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        _fixture_admission_state(db)
        db.execute("UPDATE control SET stopped=1")
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        revision, previous = verify_report_history(db, session)
        prior = db.execute("SELECT body FROM reports WHERE session=?", (session,)).fetchone()
        if prior and json.loads(prior[0])["complete"]:
            return json.loads(prior[0])
        positions = [json.loads(row[0]) for row in db.execute(
            "SELECT body FROM positions WHERE id NOT IN (SELECT id FROM exits) ORDER BY id")]
        plan = plan_shutdown(session, positions, quotes, now=now, max_age=max_age)
        by_id = {p["trade_id"]: p for p in positions}
        for intent in plan["intents"]:
            p = by_id[intent["trade_id"]]
            entry, risk = _number(p["actual_entry_price"]), _number(p["risk_price"])
            if entry <= 0 or risk <= 0 or p["side"] not in ("LONG", "SHORT"):
                raise ValueError("Invalid position risk/side")
            fee, slip = _number(p["fees_bps"]), _number(p["slippage_bps"])
            if min(fee, slip) < 0:
                raise ValueError("Negative simulation costs")
            price = _number(intent["reference_price"])
            gross = (price - entry) / risk * (1 if p["side"] == "LONG" else -1)
            # Same round-trip entry-notional convention as PaperJournal.close_trade.
            cost = (fee + slip) / Decimal(10000) * 2 * entry / risk
            exit_row = {**intent, "session_id": session, "exit_timestamp": now,
                        "status": "SIMULATED_EXIT", "gross_pnl_r": str(gross),
                        "cost_r": str(cost), "net_pnl_r": str(gross - cost),
                        "fees_bps": str(fee), "slippage_bps": str(slip)}
            if "quantity" in p or "currency" in p:
                quantity = _number(p["quantity"])
                original_quantity = quantity
                fills = [json.loads(row[0]) for row in db.execute(
                    "SELECT body FROM partial_fills WHERE trade=? ORDER BY rowid", (intent["trade_id"],))]
                partial = replay_partial_fills(_partial_position(p), fills) if fills else None
                if partial:
                    quantity = _number(partial["remaining_quantity"])
                currency = p["currency"]
                if quantity <= 0 or type(currency) is not str or not currency:
                    raise ValueError("Explicit positive quantity and currency required")
                risk_currency = risk * quantity
                exit_row["currency_accounting"] = {
                    "currency": currency, "quantity": str(quantity),
                    "risk_currency": str(risk_currency),
                    "gross": str(gross * risk_currency),
                    "entry_fee": str(entry * quantity * fee / Decimal(10000)),
                    "exit_fee": str(entry * quantity * fee / Decimal(10000)),
                    "entry_slippage": str(entry * quantity * slip / Decimal(10000)),
                    "exit_slippage": str(entry * quantity * slip / Decimal(10000)),
                    "net": str((gross - cost) * risk_currency),
                    "cost_policy": "LEGACY_ROUND_TRIP_ENTRY_NOTIONAL",
                    "funding": "NOT_MODELED",
                }
                if partial:
                    money = exit_row["currency_accounting"]
                    money["shutdown_quantity"] = str(quantity)
                    money["quantity"] = str(original_quantity)
                    money["net"] = str(_number(money["net"]) + _number(partial["net_currency"]))
                    money["gross"] = str(_number(money["gross"]) + _number(partial["gross_currency"]))
                    money["prior_partial_accounting"] = partial
                    original_risk = risk * original_quantity
                    money["risk_currency"] = str(original_risk)
                    exit_row["net_pnl_r"] = str(_number(money["net"]) / original_risk)
                    exit_row["gross_pnl_r"] = str(_number(money["gross"]) / original_risk)
            fault("before_exit")
            db.execute("INSERT INTO exits VALUES(?,?)", (intent["trade_id"], json.dumps(exit_row, sort_keys=True)))
            fault("after_exit")
        rows = [json.loads(row[0]) for row in db.execute("SELECT body FROM exits ORDER BY id")]
        session_rows = [row for row in rows if row["session_id"] == session]
        report = {"session_id": session, "clock": now, "complete": not plan["unresolved"],
                  "unresolved": plan["unresolved"], "closed_n": len(session_rows),
                  "realized_pnl_r": str(sum((_number(row["net_pnl_r"]) for row in session_rows), Decimal(0))),
                  "unit": "SUM_OF_TRADE_R_NOT_CURRENCY", "production_authorized": False}
        totals = {}
        for row in session_rows:
            money = row.get("currency_accounting")
            if money:
                currency = money["currency"]
                totals[currency] = totals.get(currency, Decimal(0)) + _number(money["net"])
        report["currency_totals_exact"] = {key: str(value) for key, value in sorted(totals.items())}
        report["currency_display_2dp_half_even"] = {
            key: str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)) for key, value in sorted(totals.items())}
        report["currency_unavailable_n"] = sum("currency_accounting" not in row for row in session_rows)
        body = json.dumps(report, sort_keys=True)
        db.execute("INSERT INTO report_history VALUES(?,?,?,?,?)",
                   (session, revision + 1, body, previous, _report_digest(body, previous)))
        db.execute("INSERT OR REPLACE INTO reports VALUES(?,?)", (session, body))
        fault("before_commit")
        db.commit()
        fault("after_commit")
        return report
