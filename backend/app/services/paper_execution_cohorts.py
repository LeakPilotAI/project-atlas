"""Read-only execution-version cohorts; never relabel or rewrite journal evidence."""
from collections import defaultdict
from datetime import datetime, timezone
import math
from statistics import median


def _version(row):
    features = row.get("features")
    return row.get("paper_execution_model_version") or (features.get("paper_execution_model_version") if isinstance(features, dict) else None)


def _time(row):
    for key in ("exit_timestamp", "timestamp", "entry_timestamp", "signal_timestamp"):
        try:
            value = datetime.fromisoformat(str(row.get(key)).replace("Z", "+00:00"))
            return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            pass
    return None


def execution_model_cohorts(rows):
    trades = defaultdict(list)
    ignored = 0
    for row in rows:
        if row.get("event") not in ("open", "close"):
            continue
        if not row.get("trade_id"):
            ignored += 1
            continue
        trades[str(row["trade_id"])].append(row)
    groups = defaultdict(list)
    excluded = 0
    for events in trades.values():
        if any(str(row.get(key) or "").upper() in {"TEST", "DIAGNOSTIC"}
               for row in events for key in ("trade_type", "evidence_class")):
            excluded += 1
            continue
        versions = {str(_version(row)) for row in events if _version(row)}
        version = next(iter(versions)) if len(versions) == 1 else "CONFLICTING_METADATA" if versions else "UNKNOWN/legacy"
        closes = [row for row in events if row["event"] == "close"]
        # Duplicate identical closes count once. Conflicting closes stay unresolved.
        unique_closes = {repr(sorted(row.items())): row for row in closes}
        close = next(iter(unique_closes.values())) if len(unique_closes) == 1 else None
        interrupted = close and (close.get("session_roll") or str(close.get("result") or "").upper() in {"SESSION_ROLL", "INTERRUPTED"})
        r = None
        if close and not interrupted and len(versions) <= 1:
            raw = close.get("net_pnl_r")
            if raw is None:
                raw = close.get("R_multiple")
            try:
                r = float(raw)
                if not math.isfinite(r):
                    r = None
            except (TypeError, ValueError):
                pass
        groups[version].append({"events": events, "close": close, "has_close": bool(closes),
                                "interrupted": bool(interrupted), "r": r,
                                "conflicting_close": len(unique_closes) > 1})
    result = []
    for version, items in sorted(groups.items()):
        resolved = [item for item in items if item["r"] is not None]
        returns = [item["r"] for item in resolved]
        dates = sorted(t for item in items for row in item["events"] if (t := _time(row)))
        wins = sum(r > 0 and not (item["close"].get("scratch") or str(item["close"].get("result")).upper() in {"BE", "SCRATCH"})
                   for item in resolved for r in [item["r"]])
        scratches = sum(bool(item["close"].get("scratch")) or str(item["close"].get("result")).upper() in {"BE", "SCRATCH"} for item in resolved)
        equity = peak = drawdown = 0.0
        dated = all(_time(item["close"]) for item in resolved)
        for item in sorted(resolved, key=lambda item: _time(item["close"]) or ""):
            equity += item["r"]
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        result.append({"paper_execution_model_version": version, "trade_count": len(items),
                       "open_count": sum(not item["has_close"] for item in items),
                       "closed_count": sum(item["has_close"] for item in items),
                       "resolved_count": len(returns), "unknown_result_count": sum(item["has_close"] and item["r"] is None and not item["interrupted"] for item in items),
                       "interrupted_count": sum(item["interrupted"] for item in items),
                       "conflicting_close_count": sum(item["conflicting_close"] for item in items),
                       "wins": wins, "losses": len(returns) - wins - scratches, "scratches": scratches,
                       "win_rate": wins / len(returns) if returns else None,
                       "total_r": sum(returns) if returns else None,
                       "expectancy_r": sum(returns) / len(returns) if returns else None,
                       "median_r": median(returns) if returns else None,
                       "max_drawdown_r": drawdown if returns and dated else None,
                       "evidence_start": dates[0] if dates else None, "evidence_end": dates[-1] if dates else None})
    return {"cohorts": result, "excluded_test_diagnostic_trades": excluded,
            "ignored_events_without_trade_id": ignored,
            "note": "Distinct trade IDs; net R preferred including zero. Interrupted and unknown results excluded from R metrics, retained in counts. No pooled performance.",
            "execution": "PAPER_ONLY", "live_capital_allowed": False, "automatic_real_money_execution": False}
