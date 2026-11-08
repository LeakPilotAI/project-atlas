"""ASGI-in-process Stop contract. No sockets, Atlas launch or native account state."""
import copy

import httpx
import pytest
from fastapi import FastAPI

from app.services.quality_dips_stop_bridge import register_stop_routes

ORIGIN = "http://127.0.0.1:18799"
TOKEN = "offline-synthetic-not-operational-token-1234"
URL = "/_atlas/control/stop-session"
HEADERS = {"origin": ORIGIN, "x-atlas-control": TOKEN}


def outcome(mode):
    return {"schema": "QD_CONTROL_STOP_V1", "phase": "FINISHED", "outcome": {
        "schema": "QD_AUTO_SHUTDOWN_V1", "mode": mode,
        "status": "FLATTENED", "position_state": "FLAT",
        "process_shutdown": "VERIFIED_EXIT",
        "lanes": {"QUALITY_DIPS": {"state": "ACKNOWLEDGED_FLAT_AND_DRAINED"},
                  "HYPERLIQUID": {"state": "ACKNOWLEDGED_FLAT_AND_DRAINED"}},
    }}


class OfflineBridge:
    session_id = "offline-verified-session"

    def __init__(self, reply, *, persisted=True):
        self.reply = reply
        self.persisted = persisted
        self.calls = 0
        self.stop_ledger = self

    def verify_session(self):
        return True

    def request_stop(self, mode):
        self.calls += 1
        return copy.deepcopy(self.reply)

    def reserve_existing(self, session, mode):
        if not self.persisted:
            return {"state": "PENDING", "receipt": None}
        return {"state": "FINISHED", "receipt": copy.deepcopy(self.reply)}


async def post(bridge, *, session="offline-verified-session", mode="SHUTDOWN_FLATTEN", headers=HEADERS):
    app = FastAPI()
    register_stop_routes(app, bridge=bridge, origin=ORIGIN, token=TOKEN,
                         require_session=True, require_durable_receipt=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as client:
        return await client.post(URL, headers=headers, json={"session_id": session, "mode": mode})


@pytest.mark.asyncio
async def test_only_durable_two_lane_accepted_stop_receipt_can_reply_200():
    b = OfflineBridge(outcome("SHUTDOWN_FLATTEN"))
    r = await post(b)
    assert r.status_code == 200 and b.calls == 1
    assert r.json() == b.reply


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["missing_hl", "missing_qd", "wrong_qd", "wrong_hl",
                                     "foreign", "lowercase", "null_hl", "false_state"])
async def test_forged_global_flatness_or_missing_lane_rejected_even_with_matching_ledger(damage):
    receipt = outcome("SHUTDOWN_FLATTEN")
    lanes = receipt["outcome"]["lanes"]
    if damage == "missing_hl": lanes.pop("HYPERLIQUID")
    elif damage == "missing_qd": lanes.pop("QUALITY_DIPS")
    elif damage == "wrong_qd": lanes["QUALITY_DIPS"]["state"] = "INCOMPLETE"
    elif damage == "wrong_hl": lanes["HYPERLIQUID"]["state"] = "POSITION_OPEN"
    elif damage == "foreign": lanes["FOREIGN"] = {"state": "ACKNOWLEDGED_FLAT_AND_DRAINED"}
    elif damage == "lowercase": lanes["quality_dips"] = lanes.pop("QUALITY_DIPS")
    elif damage == "null_hl": lanes["HYPERLIQUID"] = None
    else: lanes["HYPERLIQUID"]["state"] = True
    b = OfflineBridge(receipt)
    r = await post(b)
    assert r.status_code == 409 and r.json() == {"status": "REFUSED"} and b.calls == 1


@pytest.mark.asyncio
async def test_missing_durable_receipt_refused_even_if_both_lanes_report_flat():
    b = OfflineBridge(outcome("SHUTDOWN_FLATTEN"), persisted=False)
    assert (await post(b)).status_code == 409
    assert b.calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["foreign_session", "missing_token", "wrong_mode"])
async def test_bad_transport_binding_refused_without_any_financial_stop_attempt(case):
    b = OfflineBridge(outcome("SHUTDOWN_FLATTEN"))
    params = ({"session": "other-session"} if case == "foreign_session"
              else {"headers": {"origin": ORIGIN}} if case == "missing_token"
              else {"mode": "UNKNOWN"})
    assert (await post(b, **params)).status_code in (403, 409)
    assert b.calls == 0
