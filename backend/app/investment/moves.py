"""Major-move unusualness score. Not a buy score. Not a probability."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from app.investment.bars import OhlcvBar
from app.investment.drawdown import DrawdownReport, analyze_drawdown, return_volatility
from app.investment.enums import (
    DataQuality,
    EvidenceQuality,
    MoveClassification,
    ThesisState,
)
from app.investment.relative import RelativeReport, period_return

MOVE_SCORE_VERSION = "atlas-move-7.0"


def _clip(x: float) -> int:
    return int(round(max(0.0, min(100.0, x))))


def _close(bar: Optional[OhlcvBar]) -> Optional[float]:
    if bar is None:
        return None
    for v in (bar.adjusted_close, bar.close):
        if v is None:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if x > 0:
            return x
    return None


def atr(bars: Sequence[OhlcvBar], period: int = 14) -> Optional[float]:
    if period <= 0 or len(bars) < period + 1:
        return None
    trs: List[float] = []
    prev_c: Optional[float] = None
    for b in bars:
        h, lo, c = b.high, b.low, b.close
        if h is None or lo is None or c is None:
            prev_c = c if c is not None else prev_c
            continue
        try:
            h_f, lo_f, c_f = float(h), float(lo), float(c)
        except (TypeError, ValueError):
            continue
        tr = h_f - lo_f
        if prev_c is not None:
            tr = max(tr, abs(h_f - prev_c), abs(lo_f - prev_c))
        if tr >= 0:
            trs.append(tr)
        prev_c = c_f
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / float(period)


def relative_volume(bars: Sequence[OhlcvBar], lookback: int = 20) -> Optional[float]:
    """Last volume / mean of prior `lookback` volumes. None if any required volume is missing."""
    if lookback <= 0 or len(bars) < lookback + 1:
        return None
    last = bars[-1].volume
    prior = [b.volume for b in bars[-1 - lookback : -1]]
    if last is None:
        return None
    try:
        last_f = float(last)
    except (TypeError, ValueError):
        return None
    vals: List[float] = []
    for v in prior:
        if v is None:
            return None
        try:
            x = float(v)
        except (TypeError, ValueError):
            return None
        if x < 0:
            return None
        vals.append(x)
    mean = sum(vals) / len(vals) if vals else 0.0
    if mean <= 0:
        return None
    return last_f / mean


def consecutive_down_days(bars: Sequence[OhlcvBar]) -> Optional[int]:
    if len(bars) < 2:
        return None
    n = 0
    i = len(bars) - 1
    while i > 0:
        a = _close(bars[i])
        b = _close(bars[i - 1])
        if a is None or b is None:
            return n if n else None
        if a < b:
            n += 1
            i -= 1
            continue
        break
    return n


def gap_magnitude(bars: Sequence[OhlcvBar]) -> Optional[float]:
    if len(bars) < 2:
        return None
    prev = _close(bars[-2])
    opn = bars[-1].open
    if prev is None or opn is None or prev <= 0:
        return None
    try:
        o = float(opn)
    except (TypeError, ValueError):
        return None
    return o / prev - 1.0


def _shock_score(ret_1d: Optional[float], vol_ann: Optional[float]) -> Optional[int]:
    if ret_1d is None or vol_ann is None or vol_ann <= 0:
        return None
    daily = vol_ann / math.sqrt(252.0)
    if daily <= 0:
        return None
    sigma = abs(float(ret_1d)) / daily
    return _clip(sigma / 5.0 * 100.0)


def _volume_score(rel_vol: Optional[float]) -> Optional[int]:
    if rel_vol is None:
        return None
    # 1.0x → 20, 2x → 55, 3x → 80, 4x+ → 100
    return _clip((float(rel_vol) - 0.6) / 3.4 * 100.0)


def _hist_score(dd: DrawdownReport) -> Optional[int]:
    if dd.drawdown_percentile is None:
        return None
    # percentile is share of days with shallower DD; high = unusual.
    return _clip(float(dd.drawdown_percentile) * 100.0)


def _rel_weak_score(rel: Optional[RelativeReport]) -> Optional[int]:
    if rel is None:
        return None
    vals = [v for v in (rel.vs_spy_1d, rel.vs_qqq_1d, rel.vs_sector_1d) if v is not None]
    if not vals:
        return None
    # More negative idiosyncratic return → higher unusualness.
    worst = min(vals)
    under = max(0.0, -float(worst))
    return _clip(under / 0.10 * 100.0)


def _atr_norm_score(ret_1d: Optional[float], atr_val: Optional[float], last: Optional[float]) -> Optional[int]:
    if ret_1d is None or atr_val is None or last is None or last <= 0 or atr_val <= 0:
        return None
    move = abs(float(ret_1d)) * last
    ratio = move / atr_val
    return _clip(ratio / 4.0 * 100.0)


@dataclass
class MoveBreakdown:
    price_shock: Optional[int] = None
    volume_anomaly: Optional[int] = None
    historical_unusualness: Optional[int] = None
    relative_weakness: Optional[int] = None
    volatility: Optional[int] = None

    def as_dict(self) -> Dict[str, Optional[int]]:
        return {
            "price_shock": self.price_shock,
            "volume_anomaly": self.volume_anomaly,
            "historical_unusualness": self.historical_unusualness,
            "relative_weakness": self.relative_weakness,
            "volatility": self.volatility,
        }

    def present(self) -> Dict[str, int]:
        return {k: v for k, v in self.as_dict().items() if v is not None}


@dataclass
class MoveReport:
    version: str = MOVE_SCORE_VERSION
    symbol: str = ""
    score: Optional[int] = None
    breakdown: MoveBreakdown = field(default_factory=MoveBreakdown)
    ret_1d: Optional[float] = None
    ret_5d: Optional[float] = None
    ret_20d: Optional[float] = None
    ret_intraday: Optional[float] = None
    ret_1h: Optional[float] = None
    atr: Optional[float] = None
    atr_norm: Optional[float] = None
    rel_volume: Optional[float] = None
    gap: Optional[float] = None
    down_days: Optional[int] = None
    vol_ann: Optional[float] = None
    drawdown: Optional[float] = None
    drawdown_percentile: Optional[float] = None
    classification: MoveClassification = MoveClassification.NORMAL
    quality: DataQuality = DataQuality.UNKNOWN
    notes: List[str] = field(default_factory=list)
    disclaimer: str = (
        "Move Score is unusualness 0–100, not a probability and not a buy recommendation."
    )

    def as_dict(self) -> Dict[str, object]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "score": self.score,
            "breakdown": self.breakdown.as_dict(),
            "ret_1d": self.ret_1d,
            "ret_5d": self.ret_5d,
            "ret_20d": self.ret_20d,
            "ret_intraday": self.ret_intraday,
            "ret_1h": self.ret_1h,
            "atr": self.atr,
            "atr_norm": self.atr_norm,
            "rel_volume": self.rel_volume,
            "gap": self.gap,
            "down_days": self.down_days,
            "vol_ann": self.vol_ann,
            "drawdown": self.drawdown,
            "drawdown_percentile": self.drawdown_percentile,
            "classification": self.classification.value,
            "quality": self.quality.value,
            "notes": list(self.notes),
            "disclaimer": self.disclaimer,
        }


_WEIGHTS = {
    "price_shock": 0.30,
    "relative_weakness": 0.25,
    "historical_unusualness": 0.20,
    "volume_anomaly": 0.15,
    "volatility": 0.10,
}


def _combine(bd: MoveBreakdown) -> Optional[int]:
    present = bd.present()
    if not present:
        return None
    wsum = 0.0
    acc = 0.0
    for k, v in present.items():
        w = _WEIGHTS.get(k, 0.0)
        acc += w * v
        wsum += w
    if wsum <= 0:
        return None
    return _clip(acc / wsum)


def score_move(
    *,
    symbol: str,
    bars: Sequence[OhlcvBar],
    relative: Optional[RelativeReport] = None,
    current_price: Optional[float] = None,
) -> MoveReport:
    notes: List[str] = []
    dd = analyze_drawdown(bars, current_price=current_price)
    last = _close(bars[-1]) if bars else None
    if current_price and current_price > 0:
        last = float(current_price)
    atr_v = atr(bars)
    rel_vol = relative_volume(bars)
    vol_ann = return_volatility(bars)
    ret_1d = period_return(bars, 1)
    ret_5d = period_return(bars, 5)
    ret_20d = period_return(bars, 20)
    gap = gap_magnitude(bars)
    down = consecutive_down_days(bars)
    ret_intraday = None
    if bars:
        o = bars[-1].open
        c = _close(bars[-1])
        if o is not None and c is not None:
            try:
                of = float(o)
                if of > 0:
                    ret_intraday = c / of - 1.0
            except (TypeError, ValueError):
                ret_intraday = None

    if rel_vol is None:
        notes.append("relative volume UNKNOWN (missing volume — not filled with 0)")
    notes.append("1-hour return UNKNOWN (daily bars only)")

    bd = MoveBreakdown(
        price_shock=_shock_score(ret_1d, vol_ann),
        volume_anomaly=_volume_score(rel_vol),
        historical_unusualness=_hist_score(dd),
        relative_weakness=_rel_weak_score(relative),
        volatility=_atr_norm_score(ret_1d, atr_v, last),
    )
    score = _combine(bd)
    quality = DataQuality.FRESH if score is not None and len(bd.present()) >= 3 else DataQuality.UNKNOWN
    if not bars:
        quality = DataQuality.MISSING
        notes.append("no bars")
    atr_norm = None
    if atr_v and last and last > 0 and ret_1d is not None:
        atr_norm = abs(ret_1d) * last / atr_v

    report = MoveReport(
        symbol=symbol,
        score=score,
        breakdown=bd,
        ret_1d=ret_1d,
        ret_5d=ret_5d,
        ret_20d=ret_20d,
        ret_intraday=ret_intraday,
        ret_1h=None,
        atr=atr_v,
        atr_norm=atr_norm,
        rel_volume=rel_vol,
        gap=gap,
        down_days=down,
        vol_ann=vol_ann,
        drawdown=dd.current_drawdown,
        drawdown_percentile=dd.drawdown_percentile,
        quality=quality,
        notes=notes,
    )
    report.classification = classify_from_score(report.score)
    return report


def classify_from_score(score: Optional[int]) -> MoveClassification:
    if score is None:
        return MoveClassification.UNKNOWN
    if score >= 90:
        return MoveClassification.EXTREME_DISLOCATION
    if score >= 80:
        return MoveClassification.MAJOR_DISLOCATION
    if score >= 65:
        return MoveClassification.ABNORMAL_SELLING
    if score >= 50:
        return MoveClassification.ELEVATED_SELLING
    if score >= 30:
        return MoveClassification.NORMAL_PULLBACK
    return MoveClassification.NORMAL


def apply_thesis_safety(
    move: MoveReport,
    *,
    thesis: ThesisState,
    evidence: EvidenceQuality,
    deteriorating: bool = False,
) -> MoveClassification:
    """Broken/damaged thesis cannot become an accumulation dislocation."""
    cls = move.classification
    if thesis is ThesisState.BROKEN:
        return MoveClassification.FUNDAMENTAL_BREAKDOWN
    if deteriorating or thesis in (ThesisState.DAMAGED, ThesisState.UNDER_PRESSURE):
        if cls in (
            MoveClassification.MAJOR_DISLOCATION,
            MoveClassification.EXTREME_DISLOCATION,
            MoveClassification.ABNORMAL_SELLING,
        ):
            return MoveClassification.THESIS_DETERIORATING
    if evidence in (EvidenceQuality.INSUFFICIENT, EvidenceQuality.UNKNOWN):
        if cls in (MoveClassification.MAJOR_DISLOCATION, MoveClassification.EXTREME_DISLOCATION):
            # unusual, but not an accumulation call
            return MoveClassification.ABNORMAL_SELLING
    return cls


def is_actionable_dislocation(
    cls: MoveClassification,
    *,
    thesis: ThesisState,
    evidence: EvidenceQuality,
) -> bool:
    if cls not in (MoveClassification.MAJOR_DISLOCATION, MoveClassification.EXTREME_DISLOCATION):
        return False
    if thesis not in (ThesisState.STRONG, ThesisState.INTACT):
        return False
    if evidence not in (EvidenceQuality.HIGH, EvidenceQuality.MEDIUM):
        return False
    return True
