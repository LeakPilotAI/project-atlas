"""Cause inference. Headline+timestamp+source required. Else UNKNOWN. Never guess."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.investment.enums import CauseCategory, DataQuality
from app.investment.relative import RelativeReport

CAUSE_VERSION = "atlas-cause-7.0"

_EARNINGS = ("earnings", "eps", "beat", "miss", "results")
_GUIDANCE = ("guidance", "outlook", "forecast", "cut full-year", "raises full-year")
_ANALYST = ("downgrade", "upgrade", "price target", "initiates")
_REG = ("sec", "doj", "ftc", "antitrust", "regulator", "probe")
_LIT = ("lawsuit", "litigation", "settlement", "class action")
_MACRO = ("fed", "cpi", "inflation", "rates", "payrolls", "treasury")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CauseRecord:
    category: CauseCategory = CauseCategory.UNKNOWN
    headline: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[datetime] = None
    quality: DataQuality = DataQuality.MISSING
    evidence: str = "INSUFFICIENT"
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "headline": self.headline,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "quality": self.quality.value,
            "evidence": self.evidence,
            "notes": list(self.notes),
            "version": CAUSE_VERSION,
        }


def _classify_headline(text: str) -> CauseCategory:
    t = text.lower()
    if any(k in t for k in _EARNINGS):
        return CauseCategory.EARNINGS
    if any(k in t for k in _GUIDANCE):
        return CauseCategory.GUIDANCE
    if any(k in t for k in _ANALYST):
        return CauseCategory.ANALYST
    if any(k in t for k in _REG):
        return CauseCategory.REGULATORY
    if any(k in t for k in _LIT):
        return CauseCategory.LITIGATION
    if any(k in t for k in _MACRO):
        return CauseCategory.MACRO
    return CauseCategory.COMPANY_SPECIFIC


def _parse_ts(raw: object) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except Exception:
            return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def infer_cause(
    *,
    headlines: Optional[List[Dict[str, Any]]] = None,
    relative: Optional[RelativeReport] = None,
) -> CauseRecord:
    """Only uses a headline when title, source, and timestamp are all present.

    Market-wide / sector labels from relative performance are structural, not news.
    They never invent a company catalyst.
    """
    notes: List[str] = []
    usable: List[Dict[str, Any]] = []
    for row in headlines or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or row.get("headline") or "").strip()
        source = str(row.get("source") or row.get("publisher") or "").strip()
        ts = _parse_ts(row.get("timestamp") or row.get("providerPublishTime") or row.get("time"))
        if title and source and ts is not None:
            usable.append({"title": title, "source": source, "timestamp": ts})
        elif title:
            notes.append("headline skipped — missing source or timestamp")

    if usable:
        hit = usable[0]
        cat = _classify_headline(hit["title"])
        return CauseRecord(
            category=cat,
            headline=hit["title"][:240],
            source=hit["source"][:80],
            timestamp=hit["timestamp"],
            quality=DataQuality.FRESH,
            evidence="HIGH",
            notes=notes,
        )

    # Structural context from relative performance — still not a guessed catalyst.
    if relative is not None:
        spy = relative.vs_spy_1d
        sector = relative.vs_sector_1d
        asset = relative.asset_1d
        if asset is not None and spy is not None and asset < -0.03 and spy < -0.025 and abs(asset - spy) < 0.02:
            notes.append("price move tracks the broad market; company catalyst UNKNOWN")
            return CauseRecord(
                category=CauseCategory.MARKET_WIDE,
                quality=DataQuality.UNKNOWN,
                evidence="LOW",
                notes=notes + ["no sourced headline"],
            )
        if asset is not None and sector is not None and asset < -0.03 and sector < -0.025 and abs(asset - sector) < 0.02:
            notes.append("price move tracks the sector ETF; company catalyst UNKNOWN")
            return CauseRecord(
                category=CauseCategory.SECTOR,
                quality=DataQuality.UNKNOWN,
                evidence="LOW",
                notes=notes + ["no sourced headline"],
            )

    notes.append("CAUSE = UNKNOWN — no sourced headline")
    return CauseRecord(notes=notes, quality=DataQuality.MISSING, evidence="INSUFFICIENT")


async def fetch_yahoo_headlines(symbol: str, *, limit: int = 3) -> List[Dict[str, Any]]:
    """Best-effort. Empty list on any failure — caller treats as UNKNOWN."""
    try:
        import yfinance as yf

        def _load() -> List[Dict[str, Any]]:
            t = yf.Ticker(symbol)
            raw = getattr(t, "news", None) or []
            out: List[Dict[str, Any]] = []
            for item in raw[: max(1, limit)]:
                if not isinstance(item, dict):
                    continue
                content = item.get("content") if isinstance(item.get("content"), dict) else item
                title = content.get("title") or item.get("title")
                src = (
                    (content.get("provider") or {}).get("displayName")
                    if isinstance(content.get("provider"), dict)
                    else None
                ) or item.get("publisher") or item.get("source")
                ts = (
                    content.get("pubDate")
                    or item.get("providerPublishTime")
                    or content.get("displayTime")
                )
                if title and src and ts:
                    out.append({"title": title, "source": src, "timestamp": ts})
            return out

        import asyncio

        return await asyncio.to_thread(_load)
    except Exception:
        return []
