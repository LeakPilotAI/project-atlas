"""Instrumented _try_symbol. Observability + 1.8R geometry. No threshold changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.core.config import get_settings
from app.services.perp_micro_coach import (
    _atr_proxy,
    _min_score_for_tier,
    _rsi,
    _sma,
    _tier,
)


async def instrumented_try_symbol(self, symbol: str, price: float) -> bool:
    from app.alerts.discord import is_discord_ready, send_discord_alert
    from app.services.paper_journal import paper_journal
    from app.services.paper_pipeline import paper_pipeline
    from app.services.shadow_research import shadow_research

    settings = get_settings()
    if price <= 0:
        paper_pipeline.inc_reject("NO_PRICE")
        return False
    closes = await self._fetch_closes(symbol, 48)
    if len(closes) < 25:
        paper_pipeline.inc("candle_fail")
        return False
    closes[-1] = price
    paper_pipeline.inc("candle_success")
    paper_pipeline.last_candle_ok_at = datetime.now(timezone.utc).isoformat()

    rsi = _rsi(closes, 14)
    sma20 = _sma(closes, 20)
    if rsi is None or sma20 is None or sma20 <= 0:
        paper_pipeline.inc("candle_fail")
        return False

    ext_pct = abs(price - sma20) / sma20 * 100.0
    atr = _atr_proxy(closes, 14)
    majors = set(settings.perp_micro_majors_list)
    tier = _tier(symbol, majors)
    min_score = _min_score_for_tier(tier)
    min_rr = float(settings.perp_micro_min_rr)
    vol = float(self._vol_map.get(symbol) or 0.0)
    oi = float(self._oi_map.get(symbol) or 0.0)

    side_hyp = "NONE"
    if rsi <= float(settings.perp_micro_rsi_long):
        side_hyp = "LONG"
    elif rsi >= float(settings.perp_micro_rsi_short):
        side_hyp = "SHORT"
    elif rsi < 50:
        side_hyp = "LONG"
    else:
        side_hyp = "SHORT"

    q_research, qscore_research, q_reason_research = 0.0, 0.0, ""
    try:
        _ok_r, qscore_research, q_reason_research = self._setup_quality(
            symbol, side_hyp, price, closes, rsi, sma20, ext_pct, hard_gates=False
        )
        q_research = qscore_research
    except TypeError:
        _ok_r, qscore_research, q_reason_research = self._setup_quality(
            symbol, side_hyp, price, closes, rsi, sma20, ext_pct
        )
        q_research = qscore_research
    except Exception:
        qscore_research, q_research = 0.0, 0.0

    if side_hyp == "LONG":
        stop_r = price - 1.5 * atr
        risk_r = abs(price - stop_r) or 1e-12
        tp1_r = price + min_rr * risk_r
        rr_research = abs(tp1_r - price) / risk_r
    else:
        stop_r = price + 1.5 * atr
        risk_r = abs(price - stop_r) or 1e-12
        tp1_r = price - min_rr * risk_r
        rr_research = abs(price - tp1_r) / risk_r

    regime_norm = "UNKNOWN"
    try:
        from app.analytics.regime import detect_regime, normalize_regime

        regime_norm = normalize_regime(detect_regime(closes))
    except Exception:
        regime_norm = "UNKNOWN"

    try:
        from app.services.funnel_research import funnel_research

        sequential_guess = "evaluated"
        if ext_pct < float(settings.perp_micro_min_extension_pct):
            sequential_guess = "extension"
        elif side_hyp == "NONE" or (
            rsi > float(settings.perp_micro_rsi_long)
            and rsi < float(settings.perp_micro_rsi_short)
        ):
            sequential_guess = "rsi"
        funnel_research.observe(
            symbol=symbol,
            price=price,
            ext_pct=ext_pct,
            rsi=rsi,
            quality_score=float(q_research or 0),
            quality_min=float(min_score),
            rr=float(rr_research),
            atr=float(atr),
            volume=vol,
            open_interest=oi,
            regime=regime_norm,
            side_hyp=side_hyp,
            sequential_stage=sequential_guess,
            features={
                "sma20": sma20,
                "tier": tier,
                "quality_reason": q_reason_research,
            },
        )
    except Exception as e:
        log_msg = str(e)
        try:
            from app.services.paper_pipeline import paper_pipeline as _pp

            _pp.mark_error(f"funnel observe: {log_msg[:160]}")
        except Exception:
            pass

    if ext_pct < float(settings.perp_micro_min_extension_pct):
        paper_pipeline.inc_reject("EXTENSION_TOO_SMALL")
        shadow_research.record_evaluation(
            symbol=symbol,
            side=None,
            mark_price=price,
            score=0.0,
            required_score=62.0,
            qualified=False,
            failed_gates=["extension_too_small"],
            features={
                "ext_pct": ext_pct,
                "sma20": sma20,
                "rsi": rsi,
                "atr": atr,
                "vol": vol,
                "oi": oi,
                "rr": rr_research,
                "regime_normalized": regime_norm,
            },
            regime=regime_norm,
            rejection_stage="extension",
            regime_normalized=regime_norm,
            notes="pre-side filter",
        )
        return False
    paper_pipeline.inc("extension_pass")

    side: Optional[str] = None
    if rsi <= float(settings.perp_micro_rsi_long):
        side = "LONG"
    elif rsi >= float(settings.perp_micro_rsi_short):
        side = "SHORT"
    if side is None:
        paper_pipeline.inc_reject("RSI_NOT_EXTREME")
        shadow_research.record_evaluation(
            symbol=symbol,
            side=None,
            mark_price=price,
            score=float(rsi),
            required_score=float(settings.perp_micro_rsi_long),
            qualified=False,
            failed_gates=["rsi_not_extreme"],
            features={
                "rsi": rsi,
                "ext_pct": ext_pct,
                "sma20": sma20,
                "atr": atr,
                "vol": vol,
                "oi": oi,
                "rr": rr_research,
                "regime_normalized": regime_norm,
            },
            regime=regime_norm,
            rejection_stage="rsi",
            regime_normalized=regime_norm,
        )
        return False
    paper_pipeline.inc("rsi_extreme")
    paper_pipeline.inc("long_candidates" if side == "LONG" else "short_candidates")

    ok, qscore, reason = self._setup_quality(
        symbol, side, price, closes, rsi, sma20, ext_pct
    )
    majors = set(settings.perp_micro_majors_list)
    tier = _tier(symbol, majors)
    min_score = _min_score_for_tier(tier)
    atr = _atr_proxy(closes, 14)
    paper_pipeline.inc("quality_evaluated")

    if not ok:
        failed = []
        if qscore < min_score:
            failed.append("score_threshold")
            paper_pipeline.inc("rejected_score")
        if "RSI" in reason:
            failed.append("rsi_gate")
        if "extension" in reason.lower() or "ext" in reason.lower():
            failed.append("extension")
        if any(x in reason.lower() for x in ("liquidity", "thin", "junk")):
            failed.append("liquidity")
            paper_pipeline.inc("rejected_liquidity")
        if "ATR" in reason or "atr" in reason:
            failed.append("risk_atr")
            paper_pipeline.inc("rejected_atr")
        if "structure" in reason.lower():
            failed.append("structure")
        if not failed:
            failed.append("quality")
        paper_pipeline.inc_reject(failed[0].upper() if failed else "QUALITY")
        await paper_journal.log_candidate(
            symbol=symbol,
            side=side,
            taken=False,
            signal_price=price,
            score=qscore,
            regime=f"rsi={rsi:.1f}",
            features={"rsi": rsi, "ext_pct": ext_pct, "sma20": sma20},
            reject_reason=reason,
            strategy="rsi_extension_v1",
        )
        shadow_research.record_evaluation(
            symbol=symbol,
            side=side,
            mark_price=price,
            score=qscore,
            required_score=min_score,
            qualified=False,
            failed_gates=failed,
            features={
                "rsi": rsi,
                "ext_pct": ext_pct,
                "sma20": sma20,
                "atr": atr,
                "vol": self._vol_map.get(symbol),
                "oi": self._oi_map.get(symbol),
                "tier": tier,
                "reason": reason,
            },
            regime=regime_norm,
            rejection_stage="quality",
            regime_normalized=regime_norm,
            stop=(price - 1.5 * atr) if side == "LONG" else (price + 1.5 * atr),
            tp1=(price + 1.8 * 1.5 * atr) if side == "LONG" else (price - 1.8 * 1.5 * atr),
            tp2=(price + 3.0 * 1.5 * atr) if side == "LONG" else (price - 3.0 * 1.5 * atr),
            notes=reason,
        )
        return False
    paper_pipeline.inc("quality_pass")

    min_rr = float(settings.perp_micro_min_rr)
    if side == "LONG":
        stop = price - 1.5 * atr
        risk = abs(price - stop)
        tp1 = price + min_rr * risk
        tp2 = price + (min_rr + 1.2) * risk
    else:
        stop = price + 1.5 * atr
        risk = abs(price - stop)
        tp1 = price - min_rr * risk
        tp2 = price - (min_rr + 1.2) * risk

    if risk <= 0:
        paper_pipeline.inc_reject("ZERO_RISK")
        return False
    rr = abs(tp1 - price) / risk
    if rr < min_rr:
        paper_pipeline.inc("rejected_rr")
        paper_pipeline.inc_reject("RISK_REWARD")
        await paper_journal.log_candidate(
            symbol=symbol,
            side=side,
            taken=False,
            signal_price=price,
            score=qscore,
            regime=f"rsi={rsi:.1f}",
            features={"rsi": rsi, "ext_pct": ext_pct, "rr": rr},
            reject_reason=f"R:R {rr:.2f} < min",
            strategy="rsi_extension_v1",
        )
        shadow_research.record_evaluation(
            symbol=symbol,
            side=side,
            mark_price=price,
            score=qscore,
            required_score=min_score,
            qualified=False,
            failed_gates=["risk_reward"],
            features={"rsi": rsi, "ext_pct": ext_pct, "rr": rr, "atr": atr, "tier": tier, "regime_normalized": regime_norm},
            regime=regime_norm,
            rejection_stage="rr",
            regime_normalized=regime_norm,
            stop=stop,
            tp1=tp1,
            tp2=tp2,
            notes=f"R:R {rr:.2f}",
        )
        return False
    paper_pipeline.inc("rr_pass")
    paper_pipeline.inc("qualified")
    paper_pipeline.last_qualified_at = datetime.now(timezone.utc).isoformat()
    paper_pipeline.inc("paper_open_attempted")

    counts_for_live = tier in ("major", "alt")
    tid = await paper_journal.open_trade(
        symbol=symbol,
        side=side,
        entry=price,
        signal_price=price,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        risk_usd=float(settings.perp_micro_risk_usd),
        regime=regime_norm,
        notes=f"ext={ext_pct:.2f}%|{reason}|live={counts_for_live}|regime={regime_norm}",
        source="perp_micro",
        strategy="rsi_extension_v1",
        signal_score=qscore,
        features={
            "rsi": rsi,
            "ext_pct": ext_pct,
            "sma20": sma20,
            "atr": atr,
            "vol": self._vol_map.get(symbol),
            "oi": self._oi_map.get(symbol),
            "rr": rr,
            "regime_normalized": regime_norm,
        },
        tier=tier,
        counts_for_live=counts_for_live,
    )
    if not tid:
        paper_pipeline.inc("paper_open_failed")
        return False
    paper_pipeline.inc("paper_open_succeeded")
    paper_pipeline.last_paper_open_at = datetime.now(timezone.utc).isoformat()
    await paper_journal.log_candidate(
        symbol=symbol,
        side=side,
        taken=True,
        signal_price=price,
        score=qscore,
        regime=f"rsi={rsi:.1f}",
        features={"rsi": rsi, "ext_pct": ext_pct},
        strategy="rsi_extension_v1",
    )
    shadow_research.record_evaluation(
        symbol=symbol,
        side=side,
        mark_price=price,
        score=qscore,
        required_score=min_score,
        qualified=True,
        failed_gates=[],
        features={
            "rsi": rsi,
            "ext_pct": ext_pct,
            "sma20": sma20,
            "atr": atr,
            "vol": self._vol_map.get(symbol),
            "oi": self._oi_map.get(symbol),
            "tier": tier,
            "rr": rr,
            "regime_normalized": regime_norm,
        },
        regime=regime_norm,
        rejection_stage="qualified",
        regime_normalized=regime_norm,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        notes="QUALIFIED paper path",
    )

    self._open[tid] = {
        "symbol": symbol,
        "side": side,
        "entry": price,
        "stop": stop,
        "tp1": tp1,
        "tp2": tp2,
        "mark": price,
        "trade_id": tid,
        "tier": tier,
        "counts_for_live": counts_for_live,
        "qscore": qscore,
        "mfe_r": 0.0,
        "mae_r": 0.0,
    }
    self._cooldowns[symbol] = datetime.now(timezone.utc)

    if is_discord_ready():
        paper_pipeline.inc("discord_trigger_attempted")
        live_tag = "live-stat" if counts_for_live else "experimental"
        dm_ok = await send_discord_alert(
            symbol=symbol,
            title=f"Paper TRIGGER · {symbol} · {side}",
            description=(
                f"**{symbol} · {side}** (paper · {tier} · **{live_tag}**)\n"
                f"Entry `{price}` · Stop `{stop:.6g}` · TP1 `{tp1:.6g}`\n"
                f"RSI `{rsi:.1f}` · ext `{ext_pct:.2f}%` · R:R `{rr:.1f}` · Q `{qscore:.0f}`\n"
                f"_{reason}_\n_Simulation only. No live execution._"
            ),
            price=price,
            severity="MEDIUM",
            opportunity=min(95, int(qscore)),
            confidence=min(90, int(50 + qscore / 3)),
            risk=45 if tier == "major" else (50 if tier == "alt" else 60),
        )
        if dm_ok:
            paper_pipeline.inc("discord_trigger_delivered")
            paper_pipeline.last_discord_alert_at = datetime.now(timezone.utc).isoformat()
    return True
