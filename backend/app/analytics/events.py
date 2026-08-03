from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional


@dataclass
class MarketEvent:
    name: str
    event_type: str          # fomc | cpi | jobs | other
    start: datetime
    end: datetime
    impact: str              # high | medium
    notes: str = ""


# Static high-impact windows (UTC). Expand as needed.
# These are approximate recurring windows — update periodically.
STATIC_EVENTS: List[MarketEvent] = [
    # Example placeholders — replace with real upcoming dates
    # MarketEvent(
    #     name="FOMC Decision",
    #     event_type="fomc",
    #     start=datetime(2026, 9, 17, 18, 0, tzinfo=timezone.utc),
    #     end=datetime(2026, 9, 17, 20, 30, tzinfo=timezone.utc),
    #     impact="high",
    #     notes="Fed rate decision + press conference",
    # ),
]


def get_active_events(now: Optional[datetime] = None) -> List[MarketEvent]:
    """Return events that are currently active or about to start."""
    if now is None:
        now = datetime.now(timezone.utc)

    active = []
    for ev in STATIC_EVENTS:
        # Consider event active from 60 min before start to end
        window_start = ev.start - timedelta(minutes=60)
        if window_start <= now <= ev.end:
            active.append(ev)
    return active


def is_high_impact_window(now: Optional[datetime] = None) -> bool:
    events = get_active_events(now)
    return any(e.impact == "high" for e in events)


def event_context_message(now: Optional[datetime] = None) -> Optional[str]:
    events = get_active_events(now)
    if not events:
        return None
    names = ", ".join(e.name for e in events)
    return f"High-impact event window active: {names}"