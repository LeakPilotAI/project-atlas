"""Explicit HL cache/evidence -> existing publication/archive, without acquisition.

The source owner authenticates provenance, continuity and domain. Local hashes,
mark touches and transport acknowledgements cannot manufacture executable proof.
"""

from decimal import Context, Inexact, localcontext
from fractions import Fraction
from threading import Lock
from types import SimpleNamespace

from scripts.observation_runtime.personal_perp_research_archive import (
    NativePersonalPerpResearchArchive,
    validate_enrollment,
)

from app.adapters.hyperliquid import HyperliquidAdapter
from app.investment.quality_dips_candidate_evidence import verified
from app.services.paper_financial_replay import body, digest, number, strict, validate_manifest
from app.services.paper_source_publication import PerpSourcePublication, parse_public_trades
from app.services.perp_resting_order import validate_order
from app.services.perp_source_planner import source_research_plans
from app.trading_core.perp_board import build_perp_board


def maker_from_window(order, window, trades, *, parameters, authority, execution_domain, now):
    """Derive only the existing queue/participation model from accepted raw facts."""
    validate_order(order, parameters)
    if (
        type(window) is not dict
        or set(window) != {"queue", "trade_ids", "queue_ahead"}
        or type(trades) is not dict
        or trades.get("symbol") != order["symbol"]
    ):
        raise ValueError("HL_EXACT_ORIGINAL_QUEUE_AND_TRADE_WINDOW_REQUIRED")
    context = {
        "order": order,
        "window": window,
        "trades": trades,
        "parameters_digest": digest(parameters),
        "execution_domain": execution_domain,
    }
    frozen = body(context)
    receipt = verified(
        authority.verify_maker_window(context, now=now),
        digest(context),
        "HL_MAKER_WINDOW_VERIFIED_V1",
    )
    if body(context) != frozen or receipt.get("execution_domain") != execution_domain:
        raise ValueError("HL_WINDOW_AUTHORITY_MUTATION_OR_DOMAIN")
    parsed = parse_public_trades(
        {"channel": "trades", "data": trades["rows"]}, received_ms=trades["received_ms"]
    )
    if any(trades.get(key) != value for key, value in parsed.items()):
        raise ValueError("HL_ORIGINAL_TRADE_PARSER_CONFLICT")
    ids = window["trade_ids"]
    if (
        type(ids) is not list
        or not 0 < len(ids) <= 256
        or any(
            type(v) is not list or len(v) != 2 or any(type(n) is not int for n in v) for v in ids
        )
        or len({tuple(v) for v in ids}) != len(ids)
    ):
        raise ValueError("HL_EXACT_UNIQUE_TRADE_IDS_REQUIRED")
    rows = [r for r in trades["rows"] if [r["time"], r["tid"]] in ids]
    buy = order["side"] == "LONG"
    if (
        len(rows) != len(ids)
        or len({r["px"] for r in rows}) != 1
        or any(
            r["coin"] != order["symbol"]
            or r["side"] != ("A" if buy else "B")
            or not order["created_at"] * 1000 < r["time"] <= now * 1000
            for r in rows
        )
    ):
        raise ValueError("HL_WINDOW_PRICE_SIDE_IDENTITY_OR_TIME_CONFLICT")
    queue = window["queue"]
    if (
        type(queue) is not dict
        or set(queue) != {"book", "metadata", "source_digest", "source_revision", "receipt"}
        or queue["receipt"] in (None, "", {}, [])
    ):
        raise ValueError("HL_ORIGINAL_QUEUE_RECEIPT_REQUIRED")
    from app.adapters.hyperliquid import _paper_execution_observation

    book = queue["book"]
    _paper_execution_observation(
        order["symbol"], queue["metadata"], book, book["time"], book["time"]
    )
    levels = book["levels"][0 if buy else 1]
    at_limit = [r for r in levels if number(r["px"]) == number(order["limit_price"])]
    ahead = number(window["queue_ahead"])
    if (
        len(at_limit) != 1
        or ahead < number(at_limit[0]["sz"])
        or book["time"] != order["created_at"] * 1000
        or book.get("coin") != order["symbol"]
        or queue.get("source_digest") != order["source_digest"]
        or queue.get("source_revision") != order["source_revision"]
    ):
        raise ValueError("HL_ORIGINAL_QUEUE_BINDING_REQUIRED")
    price = number(rows[0]["px"])
    if not (
        price <= number(order["limit_price"]) if buy else price >= number(order["limit_price"])
    ):
        raise ValueError("HL_TRADE_DOES_NOT_REACH_ORIGINAL_LIMIT")
    # Fraction prevents ambient Decimal rounding from increasing fill capacity.
    traded = sum((Fraction(number(r["sz"])) for r in rows), Fraction(0))
    capacity = (traded - Fraction(ahead)) * Fraction(
        number(parameters["perp_policy"]["participation"])
    )
    step, requested = number(order["plan"]["quantity_step"]), number(order["quantity"])
    units = min(Fraction(requested), capacity) // Fraction(step)
    if units <= 0:
        return {"queue": queue, "trade_ids": ids, "proof": None, "window_acceptance": receipt}
    with localcontext(Context(prec=28)) as context:
        context.traps[Inexact] = True
        filled = step * units
        total = sum((number(r["sz"]) for r in rows), number("0"))
        proof = {
            "schema": "SIMULATED_MAKER_QUEUE_FILL_V1",
            "order_id": order["order_id"],
            "limit_price": order["limit_price"],
            "rested_at": order["created_at"],
            "queue_ahead": str(ahead),
            "traded_quantity": str(total),
            "trade_price": str(price),
            "trade_side": "SELL" if buy else "BUY",
            "trade_at": max(r["time"] for r in rows) // 1000,
            "source_ref": digest({"queue": queue, "trades": trades}),
            "requested_quantity": str(requested),
            "filled_quantity": str(filled),
            "cancelled_quantity": str(requested - filled),
        }
    return {"queue": queue, "trade_ids": ids, "proof": proof, "window_acceptance": receipt}


class _Evidence:
    def __init__(self):
        self.cut = None
        self.makers = {}

    def settlement(self, symbol, at):
        return strict(body(self.cut["settlements"].get(f"{symbol}:{at}")))

    def maker(self, key):
        return strict(body(self.makers.get(key)))

    def setups(self):
        return strict(body(self.cut["setups"]))


class HyperliquidCurrentProducer:
    def __init__(
        self,
        *,
        source,
        input_authority,
        publication_authority,
        adapter,
        orders,
        archive,
        parameters,
        enrollment,
        clock,
        execution_domain,
    ):
        self.enrollment = validate_enrollment(enrollment)
        validate_manifest(parameters)
        if (
            execution_domain not in ("DISPOSABLE", "OPERATIONAL")
            or type(archive) is not NativePersonalPerpResearchArchive
            or type(adapter) is not HyperliquidAdapter
            or any(
                v is None for v in (source, input_authority, publication_authority, orders, clock)
            )
            or archive.enrollment != self.enrollment
            or archive.clock is not clock
            or digest(parameters) != self.enrollment["parameters_digest"]
            or parameters["epoch"] != self.enrollment["epoch"]
            or parameters["currency"] != "USDC"
            or parameters["release"] != self.enrollment["release_digest"]
            or parameters["schema"]
            != (
                "PAPER_EPOCH_PERP_FIXTURE_V2"
                if execution_domain == "DISPOSABLE"
                else "PAPER_EPOCH_PERP_OPERATIONAL_V1"
            )
            or body(orders.manifest) != body(parameters)
            or orders.execution_domain
            != ("DISPOSABLE_TEST" if execution_domain == "DISPOSABLE" else "LOCAL_ENROLLED")
        ):
            raise ValueError("HL_EXPLICIT_BOUND_SOURCE_COMPONENTS_REQUIRED")
        self.source, self.input_authority = source, input_authority
        self.adapter, self.orders, self.archive, self.clock = adapter, orders, archive, clock
        self.parameters, self.execution_domain = strict(body(parameters)), execution_domain
        self._scope = body([self.enrollment, self.parameters, execution_domain])
        self._ports = source, input_authority, adapter, orders, archive, clock
        self._evidence = _Evidence()
        self.publication = PerpSourcePublication(
            adapter=adapter,
            orders=orders,
            settlements=SimpleNamespace(read=self._evidence.settlement),
            maker=SimpleNamespace(read=self._evidence.maker),
            lifecycle=SimpleNamespace(read_current=self._evidence.setups),
            source_id=enrollment["source_id"],
            authority=publication_authority,
            archive=archive,
            clock=clock,
        )
        self._publication = self.publication
        self._lock, self._failed = Lock(), False

    def _now(self):
        now = self.clock()
        if type(now) is not int or now < 0:
            raise ValueError("HL_CURRENT_CLOCK_REQUIRED")
        return now

    def _verify(self):
        if (
            self._failed
            or body([self.enrollment, self.parameters, self.execution_domain]) != self._scope
            or any(
                a is not b
                for a, b in zip(
                    (
                        self.source,
                        self.input_authority,
                        self.adapter,
                        self.orders,
                        self.archive,
                        self.clock,
                    ),
                    self._ports,
                    strict=True,
                )
            )
            or self.publication is not self._publication
            or self.publication.archive is not self.archive
            or self.publication.adapter is not self.adapter
            or self.publication.orders is not self.orders
            or self.archive.enrollment != self.enrollment
            or body(self.orders.manifest) != body(self.parameters)
        ):
            raise ValueError("HL_CURRENT_BINDING_CHANGED_OR_UNCERTAIN")

    def _context(self, cut):
        return {
            "input": cut,
            "enrollment": self.enrollment,
            "execution_domain": self.execution_domain,
        }

    def _accept(self, cut, now):
        fields = {
            "schema",
            "source_id",
            "execution_domain",
            "input_revision",
            "observed_at",
            "cache",
            "orders",
            "maker_windows",
            "settlements",
            "setups",
            "provenance",
        }
        if (
            type(cut) is not dict
            or set(cut) != fields
            or cut["schema"] != "HL_CURRENT_RESEARCH_INPUT_V1"
            or cut["source_id"] != self.enrollment["source_id"]
            or cut["execution_domain"] != self.execution_domain
            or type(cut["input_revision"]) is not int
            or cut["input_revision"] < 1
            or type(cut["observed_at"]) is not int
            or not 0 <= now - cut["observed_at"] <= 5
            or type(cut["provenance"]) is not dict
            or not cut["provenance"]
            or len(body(cut).encode()) > 131072
            or cut["cache"] != self.adapter.paper_source_snapshot()
            or cut["orders"] != self.orders.snapshot()
            or type(cut["maker_windows"]) is not dict
            or len(cut["maker_windows"]) > 32
            or type(cut["settlements"]) is not dict
            or len(cut["settlements"]) > 256
            or type(cut["setups"]) is not list
            or len(cut["setups"]) > 32
        ):
            raise ValueError("HL_CURRENT_INPUT_SCOPE_OR_FRESHNESS")
        markets = cut["cache"]["facts"]["markets"]
        symbols = self.parameters["perp_policy"]["symbols"]
        if (
            type(markets) is not list
            or len(markets) != len(symbols)
            or {r["symbol"] for r in markets} != set(symbols)
        ):
            raise ValueError("HL_COMPLETE_CONFIGURED_SYMBOLS_REQUIRED")
        facts = cut["cache"]["facts"]
        if (
            any(set(facts[k]) != set(symbols) for k in ("books", "candles"))
            or any(not set(facts[k]) <= set(symbols) for k in ("funding", "trades"))
            or cut["orders"].get("execution_domain") != self.orders.execution_domain
        ):
            raise ValueError("HL_SOURCE_NAMESPACE_OR_CONTROL_DOMAIN")
        for row in markets:
            for name in ("price", "volume_24h", "open_interest", "funding_rate"):
                value = number(str(row[name]))
                if name != "funding_rate" and value <= 0:
                    raise ValueError("HL_MARKET_VALUE_INVALID")
        if any(
            row["order"]["epoch"] != self.enrollment["epoch"]
            or row["order"]["symbol"] not in symbols
            for row in cut["orders"]["state"]["orders"].values()
        ):
            raise ValueError("HL_FOREIGN_ACCOUNT_ORDER_REFUSED")
        context = self._context(cut)
        frozen = body(context)
        receipt = verified(
            self.input_authority.verify_current(context, now=now),
            digest(context),
            "HL_CURRENT_RESEARCH_VERIFIED_V1",
        )
        if body(context) != frozen or receipt.get("execution_domain") != self.execution_domain:
            raise ValueError("HL_CURRENT_AUTHORITY_MUTATION_OR_DOMAIN")
        return receipt

    def _prepare(self, cut, now):
        self._evidence.cut, self._evidence.makers = cut, {}
        receipts = {}
        orders = cut["orders"]["state"]["orders"]
        for key, window in cut["maker_windows"].items():
            row = orders.get(key)
            if row is None or row["state"] != "RESERVED" or row["order"]["order_id"] != key:
                raise ValueError("HL_ORIGINAL_RESERVED_ORDER_REQUIRED")
            trades = cut["cache"]["facts"]["trades"].get(row["order"]["symbol"])
            value = maker_from_window(
                row["order"],
                window,
                trades,
                parameters=self.parameters,
                authority=self.input_authority,
                execution_domain=self.execution_domain,
                now=now,
            )
            receipts[key] = value["window_acceptance"]
            if value["proof"] is not None:
                self._evidence.makers[key] = value
        packet, sources = self.publication.prepare_capture()
        source_research_plans(packet, orders, self.parameters["perp_policy"]["symbols"], now=now)
        sources["maker_receipts"] = receipts
        return packet, sources

    def _archived(self, record):
        value = record["sources"].get("current_input")
        if (
            type(value) is not dict
            or set(value) != {"input", "acceptance", "enrollment"}
            or value["enrollment"] != digest(self.enrollment)
        ):
            raise ValueError("HL_ARCHIVED_PROVENANCE_REQUIRED")
        cut = value["input"]
        if (
            cut.get("source_id") != self.enrollment["source_id"]
            or cut.get("execution_domain") != self.execution_domain
            or type(cut.get("input_revision")) is not int
            or cut["input_revision"] < 1
        ):
            raise ValueError("HL_ARCHIVED_SCOPE_MISMATCH")
        receipt = verified(
            value["acceptance"], digest(self._context(cut)), "HL_CURRENT_RESEARCH_VERIFIED_V1"
        )
        if receipt.get("execution_domain") != self.execution_domain:
            raise ValueError("HL_ARCHIVED_DOMAIN_MISMATCH")
        return cut

    def read_cut(self):
        self._verify()
        if not self._lock.acquire(blocking=False):
            raise ValueError("HL_SOURCE_OPERATION_ACTIVE")
        try:
            return self._read()
        finally:
            self._evidence.cut, self._evidence.makers = None, {}
            self._lock.release()

    def _read(self):
        now = self._now()
        head = self.archive.current()
        record = self.archive.read_evidence(head)
        cut = self._archived(record)
        self._accept(cut, now)
        expected, sources = self._prepare(cut, now)
        packet = self.publication.read_current()

        def content(p):
            return {k: v for k, v in p.items() if k not in ("revision", "observed_at")}

        self._accept(cut, self._now())
        saved_receipts = record["sources"].get("maker_receipts")
        if type(saved_receipts) is not dict or set(saved_receipts) != set(
            sources["maker_receipts"]
        ):
            raise ValueError("HL_ARCHIVED_WINDOW_RECEIPTS_REQUIRED")
        for key, receipt in sources["maker_receipts"].items():
            saved = verified(saved_receipts[key], receipt["binding"], "HL_MAKER_WINDOW_VERIFIED_V1")
            if saved.get("execution_domain") != self.execution_domain:
                raise ValueError("HL_ARCHIVED_WINDOW_DOMAIN_MISMATCH")
        if (
            content(expected) != content(packet)
            or packet != record["packet"]
            or any(record["sources"].get(k) != sources[k] for k in ("cache", "orders"))
            or self.archive.current() != head
            or self.adapter.paper_source_snapshot() != cut["cache"]
            or self.orders.snapshot() != cut["orders"]
            or not 0 <= self._now() - now <= 1
            or not 0 <= self._now() - cut["observed_at"] <= 5
        ):
            raise ValueError("HL_REPLAY_OR_COMPLETION_CUT_CHANGED")
        self._verify()
        return strict(body(packet))

    def research(self):
        packet = self.read_cut()
        record = self.archive.read_evidence(self.archive.current())
        if record["packet"] != packet:
            raise ValueError("HL_RESEARCH_CURRENT_CUT_CHANGED")
        result = build_perp_board(
            source_research_plans(
                packet,
                record["sources"]["orders"]["state"]["orders"],
                self.parameters["perp_policy"]["symbols"],
                now=self._now(),
            )
        )
        if self.read_cut() != packet:
            raise ValueError("HL_RESEARCH_COMPLETION_CUT_CHANGED")
        return result

    def publish_current(self):
        self._verify()
        if not self._lock.acquire(blocking=False):
            raise ValueError("HL_SOURCE_OPERATION_ACTIVE")
        attempted = False
        try:
            now = self._now()
            cut = strict(body(self.source.read_current()))
            receipt = self._accept(cut, now)
            head = self.archive.current()
            if head["revision"]:
                prior = self._archived(self.archive.read_evidence(head))
                if cut["input_revision"] < prior["input_revision"]:
                    raise ValueError("HL_INPUT_REVISION_ROLLBACK")
                if cut["input_revision"] == prior["input_revision"]:
                    if cut != prior:
                        raise ValueError("HL_INPUT_REVISION_CONFLICT")
                    return self._read()
            packet, sources = self._prepare(cut, now)
            # Original producer does all book/queue/settlement validation; retain
            # precisely those normalized sources and the authenticated raw cut.
            if body(self.source.read_current()) != body(cut) or not 0 <= self._now() - now <= 1:
                raise ValueError("HL_INPUT_CHANGED_BEFORE_PUBLICATION")
            self._accept(cut, self._now())
            sources["current_input"] = {
                "input": cut,
                "acceptance": receipt,
                "enrollment": digest(self.enrollment),
            }
            self._verify()
            attempted = True
            result = self.publication.publish(packet, sources, expected_head=head)
            if body(self.source.read_current()) != body(cut) or self._read() != result:
                raise ValueError("HL_COMPLETION_SOURCE_CHANGED")
            return result
        except BaseException:
            if attempted:
                self._failed = True
            raise
        finally:
            self._evidence.cut, self._evidence.makers = None, {}
            self._lock.release()
