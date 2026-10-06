"""E48 bounded typed cross-lane Discord event routing.

Pure notification policy. External payload text is inert data and this module has
no strategy, PAPER-entry, threshold, promotion, or live-capital authority.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

Sender = Callable[..., Awaitable[bool]]

ROUTES = {
    "ALPHA_CATALYST": {"destination": "DISCORD_DM", "event_types": {"REGULATORY", "MACRO"}, "cooldown_seconds": 900},
    "PREDICTION_ELIGIBLE": {"destination": "DISCORD_DM", "event_types": {"ELIGIBLE_CANDIDATE"}, "cooldown_seconds": 900},
    "PERP_ALERT": {"destination": "DISCORD_DM", "event_types": {"SETUP", "RISK", "LIFECYCLE"}, "cooldown_seconds": 300},
    "SYSTEM": {"destination": "DISCORD_DM", "event_types": {"HEALTH", "SESSION"}, "cooldown_seconds": 300},
}
SEVERITIES = {"INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"}

@dataclass(frozen=True)
class DiscordEvent:
    event_id: str
    lane: str
    event_type: str
    severity: str
    title: str
    body: str
    provenance: tuple[str, ...] = ()
    material: bool = True

def _clean(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]

def make_event(*, lane: str, event_type: str, severity: str, title: str, body: str,
               provenance: list[str] | tuple[str, ...] = (), identity: str = "",
               material: bool = True) -> DiscordEvent:
    lane=_clean(lane,64).upper(); event_type=_clean(event_type,64).upper()
    severity=_clean(severity,16).upper(); title=_clean(title,256); body=_clean(body,4096)
    if lane not in ROUTES or event_type not in ROUTES[lane]["event_types"]:
        raise ValueError("event is not eligible for an E48 Discord route")
    if severity not in SEVERITIES or not title:
        raise ValueError("invalid typed Discord event")
    prov=tuple(_clean(x,512) for x in provenance if _clean(x,512))
    seed="|".join((lane,event_type,_clean(identity,512) or title,*prov))
    event_id=hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
    return DiscordEvent(event_id,lane,event_type,severity,title,body,prov,bool(material))

def route(event: DiscordEvent) -> dict[str, Any]:
    policy=ROUTES[event.lane]
    return {"eligible": bool(event.material and event.event_type in policy["event_types"]),
            "destination": policy["destination"], "cooldown_seconds": policy["cooldown_seconds"],
            "execution_authority": False, "paper_entry_authority": False,
            "strategy_mutation_authority": False, "membership_mutation_authority": False,
            "threshold_mutation_authority": False, "promotion_authority": False,
            "live_capital_allowed": False}


class DiscordDeliveryState:
    """In-memory bounded delivery state; acknowledge only confirmed sends."""
    def __init__(self) -> None:
        self.acked: set[str] = set()
        self.last_attempt: dict[str, datetime] = {}

    def reset(self) -> None:
        self.acked.clear(); self.last_attempt.clear()

    async def deliver(self, event: DiscordEvent, *, sender: Sender) -> dict[str, Any]:
        decision=route(event)
        if not decision["eligible"]:
            return {**decision,"event_id":event.event_id,"attempted":False,"acknowledged":False,"deduped":False,"retryable":False}
        if event.event_id in self.acked:
            return {**decision,"event_id":event.event_id,"attempted":False,"acknowledged":True,"deduped":True,"retryable":False}
        self.last_attempt[event.event_id]=datetime.now(timezone.utc)
        # Body/title remain data only. They are never parsed as commands or authority.
        try:
            ok=bool(await sender(symbol=event.lane,title=event.title,description=event.body,
                                 severity=event.severity,opportunity=0,confidence=0,risk=0))
        except Exception:
            ok=False
        if ok:
            self.acked.add(event.event_id)
        return {**decision,"event_id":event.event_id,"attempted":True,"acknowledged":ok,
                "deduped":False,"retryable":not ok,
                "provenance":list(event.provenance),"external_text_inert":True}

delivery_state=DiscordDeliveryState()

# E49 adapter: producers can use the typed contract while retaining their own
# durable success journals as the authoritative restart dedupe.
def legacy_payload_event(*, lane: str, event_type: str, identity: str,
                         payload: dict[str, Any], provenance=(), material: bool=True) -> DiscordEvent:
    return make_event(lane=lane,event_type=event_type,
        severity=str(payload.get("severity") or "MEDIUM"),
        title=str(payload.get("title") or ""),body=str(payload.get("description") or ""),
        provenance=tuple(provenance),identity=identity,material=material)

async def deliver_legacy_payload(event: DiscordEvent, *, sender: Sender) -> dict[str, Any]:
    """Typed route/authority gate with legacy Discord payload compatibility."""
    decision=route(event)
    if not decision["eligible"]:
        return {**decision,"event_id":event.event_id,"attempted":False,"acknowledged":False,"retryable":False}
    try:
        ok=bool(await sender(symbol=event.lane,title=event.title,description=event.body,
                             severity=event.severity,opportunity=0,confidence=0,risk=0))
    except Exception:
        ok=False
    return {**decision,"event_id":event.event_id,"attempted":True,"acknowledged":ok,
            "retryable":not ok,"external_text_inert":True,"provenance":list(event.provenance)}
