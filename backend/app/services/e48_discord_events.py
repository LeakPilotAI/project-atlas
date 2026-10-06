"""E48 bounded typed cross-lane Discord event routing.

Pure notification policy. External payload text is inert data and this module has
no strategy, PAPER-entry, threshold, promotion, or live-capital authority.
"""
from __future__ import annotations
import hashlib
from collections import deque
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
_OBSERVATIONS = deque(maxlen=200)

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



def _observe(event: DiscordEvent, result: dict[str, Any]) -> None:
    _OBSERVATIONS.append({
        "observed_at": datetime.now(timezone.utc).isoformat(), "event_id": event.event_id,
        "lane": event.lane, "event_type": event.event_type, "severity": event.severity,
        "eligible": bool(result.get("eligible")), "attempted": bool(result.get("attempted")),
        "acknowledged": bool(result.get("acknowledged")), "deduped": bool(result.get("deduped")),
        "retryable": bool(result.get("retryable")), "destination": result.get("destination"),
        "external_text_inert": True,
    })


def delivery_observability() -> dict[str, Any]:
    rows = list(_OBSERVATIONS)
    return {
        "retention_limit": 200, "observations": rows,
        "counts": {
            "total": len(rows),
            "attempted": sum(bool(x["attempted"]) for x in rows),
            "acknowledged": sum(bool(x["acknowledged"]) for x in rows),
            "retryable": sum(bool(x["retryable"]) for x in rows),
        },
        "read_only": True, "execution_authority": False, "paper_entry_authority": False,
        "strategy_mutation_authority": False, "threshold_mutation_authority": False,
        "promotion_authority": False, "live_capital_allowed": False,
    }


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
        result={**decision,"event_id":event.event_id,"attempted":False,"acknowledged":False,"retryable":False}
        _observe(event,result)
        return result
    try:
        ok=bool(await sender(symbol=event.lane,title=event.title,description=event.body,
                             severity=event.severity,opportunity=0,confidence=0,risk=0))
    except Exception:
        ok=False
    result={**decision,"event_id":event.event_id,"attempted":True,"acknowledged":ok,
            "retryable":not ok,"external_text_inert":True,"provenance":list(event.provenance)}
    _observe(event,result)
    return result

async def deliver_attachment_payload(event: DiscordEvent, *, sender: Sender,
                                     attachment_bytes: bytes | None,
                                     attachment_name: str = "chart.png") -> dict[str, Any]:
    """Typed binary delivery; observability retains bounded metadata, never raw bytes."""
    decision = route(event)
    data = bytes(attachment_bytes or b"")
    name = _clean(attachment_name, 128) or "attachment.bin"
    if not decision["eligible"]:
        result = {**decision, "event_id": event.event_id, "attempted": False,
                  "acknowledged": False, "retryable": False}
    else:
        try:
            ok = bool(await sender(
                symbol=event.lane, title=event.title, description=event.body,
                severity=event.severity, opportunity=0, confidence=0, risk=0,
                chart_bytes=data or None, attachment_name=name,
            ))
        except Exception:
            ok = False
        result = {**decision, "event_id": event.event_id, "attempted": True,
                  "acknowledged": ok, "retryable": not ok,
                  "external_text_inert": True, "provenance": list(event.provenance)}
    _observe(event, result)
    if _OBSERVATIONS:
        _OBSERVATIONS[-1]["attachment_present"] = bool(data)
        _OBSERVATIONS[-1]["attachment_size_bytes"] = min(len(data), 10000000)
        _OBSERVATIONS[-1]["attachment_name"] = name
        _OBSERVATIONS[-1]["attachment_bytes_retained"] = False
    return result
