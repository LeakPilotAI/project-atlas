"""Storage-neutral financial computation; inputs are not authenticated authority.

Compatibility V1 uses fixed 28-digit HALF_EVEN arithmetic. Native storage,
issuer, caller admission, source authenticity and projections are separate.
No database, filesystem, provider, startup or financial service imports.
"""
import copy
import hashlib
import json
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from zoneinfo import ZoneInfo


def body(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(body(value).encode()).hexdigest()


def number(value):
    if type(value) is not str:
        raise ValueError("Explicit decimal string required")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("Finite decimal required")
    return result


def text(value):
    if type(value) is not str or not value or len(value) > 256:
        raise ValueError("Bounded explicit identity required")
    return value


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate persisted field")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def validate_manifest(m):
    if (set(m) != {"schema", "epoch", "strategy", "currency", "opening_cash", "opened_at", "timezone",
                   "release", "provenance", "cost_policy", "fees_bps", "slippage_bps", "initial_net_r"}
            or m["schema"] != "PAPER_EPOCH_FIXTURE_V1"
            or m["strategy"] not in ("QUALITY_DIPS", "HYPERLIQUID_MANUAL") or m["currency"] != "USD"
            or m["cost_policy"] != "FIXTURE_ENTRY_NOTIONAL_ROUNDTRIP_V1"
            or type(m["opened_at"]) is not int or m["opened_at"] <= 0
            or number(m["opening_cash"]) <= 0
            or min(number(m["fees_bps"]), number(m["slippage_bps"])) < 0):
        raise ValueError("Exact explicit simulated inception required")
    for key in ("epoch", "release", "provenance"):
        text(m[key])
    ZoneInfo(m["timezone"])
    number(m["initial_net_r"])
    if m["strategy"] == "HYPERLIQUID_MANUAL" and (m["fees_bps"], m["slippage_bps"]) != ("2", "2"):
        raise ValueError("Preserve selected Hyperliquid cost assumptions")


def initial_state(manifest):
    return {"positions": {}, "cash": manifest["opening_cash"], "gross": "0", "costs": "0",
            "net": "0", "net_r": manifest["initial_net_r"], "revision": 0, "last_clock": manifest["opened_at"]}


def _transition_in_place(manifest, state, command):
    m = manifest
    common = {"schema", "epoch", "operation_id", "kind", "expected_source_revision", "timestamp", "manual", "quote"}
    extra = {"symbol", "side", "quantity", "risk_price", "origin_ref"} if command.get("kind") == "ENTRY" else {"position_id", "quantity", "expected_position_revision"}
    if (set(command) != common | extra or command["schema"] != "PAPER_COMMAND_FIXTURE_V1"
            or command["epoch"] != m["epoch"] or command["kind"] not in ("ENTRY", "EXIT")
            or command["manual"] is not True or type(command["expected_source_revision"]) is not int
            or command["expected_source_revision"] != state["revision"]
            or type(command["timestamp"]) is not int or command["timestamp"] < state["last_clock"]):
        raise ValueError("Unknown,stale or mismatched command")
    text(command["operation_id"])
    q = command["quote"]
    if (type(q) is not dict or set(q) != {"symbol", "price", "observed_at", "source_id"}
            or type(q["observed_at"]) is not int
            or not 0 <= command["timestamp"] - q["observed_at"] <= 30):
        raise ValueError("Fresh explicit fixture quote required")
    text(q["source_id"])
    price, qty = number(q["price"]), number(command["quantity"])
    if min(price, qty) <= 0:
        raise ValueError("Positive fill evidence required")
    if command["kind"] == "ENTRY":
        text(command["symbol"])
        text(command["origin_ref"])
        if any(p["origin_ref"] == command["origin_ref"] for p in state["positions"].values()):
            raise ValueError("Origin already associated")
        if command["symbol"] != q["symbol"] or command["side"] not in ("LONG", "SHORT"):
            raise ValueError("Instrument mismatch")
        risk = None if command["risk_price"] is None else number(command["risk_price"])
        if m["strategy"] == "HYPERLIQUID_MANUAL":
            if (command["symbol"] not in ("BTC", "ETH", "SOL") or risk is None or risk <= 0
                    or risk * qty > 1 or number(state["net_r"]) <= -3
                    or sum(number(p["remaining"]) > 0 for p in state["positions"].values()) >= 3):
                raise ValueError("Selected risk/position/session restriction")
        elif command["side"] != "LONG" or risk is not None:
            raise ValueError("Quality Dips is long-only,not a fabricated stop model")
        ident = m["epoch"] + ":" + digest([m["epoch"], command["operation_id"]])
        notional = price * qty
        if m["strategy"] == "QUALITY_DIPS":
            if notional > number(state["cash"]):
                raise ValueError("Insufficient simulated cash")
            state["cash"] = str(number(state["cash"]) - notional)
        state["positions"][ident] = {"symbol": command["symbol"], "side": command["side"], "entry": str(price),
            "quantity": str(qty), "remaining": str(qty), "risk_price": command["risk_price"],
            "revision": 1, "origin_ref": command["origin_ref"], "realized_net": "0"}
    else:
        ident = command["position_id"]
        p = state["positions"].get(ident)
        if (not p or type(command["expected_position_revision"]) is not int
                or p["revision"] != command["expected_position_revision"] or q["symbol"] != p["symbol"]
                or qty > number(p["remaining"])):
            raise ValueError("Position/revision/remaining quantity mismatch")
        entry = number(p["entry"])
        gross = (price - entry) * qty * (1 if p["side"] == "LONG" else -1)
        costs = 2 * entry * qty * (number(m["fees_bps"]) + number(m["slippage_bps"])) / 10000
        net = gross - costs
        p.update(remaining=str(number(p["remaining"]) - qty), revision=p["revision"] + 1,
                 realized_net=str(number(p["realized_net"]) + net))
        state.update(gross=str(number(state["gross"]) + gross), costs=str(number(state["costs"]) + costs),
                     net=str(number(state["net"]) + net),
                     cash=str(number(state["cash"]) + (price * qty - costs if m["strategy"] == "QUALITY_DIPS" else net)))
        if p["risk_price"] is not None:
            state["net_r"] = str(number(state["net_r"]) + net / (number(p["risk_price"]) * number(p["quantity"])))
    state.update(revision=state["revision"] + 1, last_clock=command["timestamp"])
    return {"schema": "PAPER_RECEIPT_FIXTURE_V1", "epoch": m["epoch"], "operation_id": command["operation_id"],
            "payload_digest": digest(command), "source_revision": state["revision"], "position_id": ident,
            "position_revision": state["positions"][ident]["revision"], "state_digest": digest(state),
            "production_authorized": False, "startup_authorized": False}


def apply_event(manifest, state, command):
    """Return an independent next-state/receipt; failure never mutates input."""
    validate_manifest(manifest)
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        candidate = copy.deepcopy(state)
        receipt = _transition_in_place(manifest, candidate, command)
        return candidate, receipt



def event_stream_record(revision, operation_id, command, parent, checksum, receipt):
    """Explicit neutral envelope; no persistence or authenticity assertion."""
    return {"schema": "PAPER_EVENT_STREAM_RECORD_V1", "revision": revision, "operation_id": operation_id,
            "command": command, "parent": parent, "digest": checksum, "receipt": receipt}



def replay_verified_events(manifest, records):
    """Verify V1 receipt/hash structure; 'verified' does not mean trusted origin."""
    validate_manifest(manifest)
    state, parent, operations = initial_state(manifest), digest(manifest), {}
    fields = {"schema", "revision", "operation_id", "command", "parent", "digest", "receipt"}
    for row in records:
        if type(row) is not dict or set(row) != fields or row["schema"] != "PAPER_EVENT_STREAM_RECORD_V1":
            raise ValueError("Exact versioned event stream required")
        if type(row["revision"]) is not int or row["revision"] < 1:
            raise ValueError("Integer event revision required")
        command = strict(row["command"])
        state, receipt = apply_event(manifest, state, command)
        stored = strict(row["receipt"])
        if type(stored.get("projection_required")) is not bool:
            raise ValueError("Missing projection contract")
        receipt["projection_required"] = stored["projection_required"]
        ident = row["operation_id"]
        if (row["revision"] != state["revision"] or ident != command["operation_id"] or ident in operations
                or row["parent"] != parent or row["digest"] != digest([parent, command, receipt])
                or body(stored) != body(receipt)):
            raise ValueError("Corrupt canonical event/receipt lineage")
        operations[ident] = (command, receipt)
        parent = row["digest"]
    return state, parent, operations
