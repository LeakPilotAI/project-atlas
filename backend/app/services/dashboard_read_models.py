"""Unregistered read models. No writer, provider, financial runtime or issuer.

An injected read port is not trusted merely because it implements an interface.
The evidence owner must authenticate the complete scoped financial snapshot.
"""

from decimal import DecimalException, Inexact, localcontext
from threading import RLock

from app.investment.quality_dips_candidate_evidence import verified
from app.services.paper_financial_replay import body, digest, number, strict
from app.services.unified_research_sources import UnifiedResearchSources

LANES = {"QUALITY_DIPS": "USD", "HYPERLIQUID": "USDC"}
FAILURES = (ValueError, OSError, KeyError, TypeError, AttributeError, DecimalException)


def unavailable_accounts(state="UNAVAILABLE"):
    return {
        "schema": "ATLAS_UNIFIED_ACCOUNT_CUTS_V1",
        "state": state,
        "accounts": None,
        "total_cash": None,
        "total_equity": None,
        "startup_authorized": False,
    }


class DashboardAccountRead:
    """Read/verify only; preserves the existing unified-account wire schema."""

    def __init__(self, *, reader, authority, scope, clock, execution_domain):
        if (
            reader is None
            or authority is None
            or execution_domain not in ("DISPOSABLE", "OPERATIONAL")
        ):
            raise ValueError("EXPLICIT_READ_ONLY_ACCOUNT_AUTHORITY_REQUIRED")
        self.reader, self.authority, self.clock = reader, authority, clock
        self.scope, self.execution_domain = strict(body(scope)), execution_domain
        self._binding = reader, authority, clock, body(scope), execution_domain
        self._high_water = None

    def read(self):
        if (
            self.reader,
            self.authority,
            self.clock,
            body(self.scope),
            self.execution_domain,
        ) != self._binding:
            raise ValueError("ACCOUNT_READ_COMPONENT_SUBSTITUTION")
        now = self.clock()
        value = strict(body(self.reader.read()))
        if (
            len(body(value).encode()) > 262144
            or value.get("schema") != "ATLAS_UNIFIED_ACCOUNT_CUTS_V1"
            or value.get("state") != "ACKNOWLEDGED"
            or value.get("startup_authorized") is not False
            or value.get("total_cash") is not None
            or value.get("total_equity") is not None
            or set(value.get("accounts", {})) != set(LANES)
        ):
            raise ValueError("COMPLETE_SEPARATE_ACCOUNT_CUTS_REQUIRED")
        if type(now) is not int or now < 0 or set(self.scope) != set(LANES):
            raise ValueError("EXACT_ACCOUNT_READ_SCOPE_REQUIRED")
        identities = {}
        for lane, currency in LANES.items():
            a, scope = value["accounts"][lane], self.scope[lane]
            if (
                set(scope) != {"account_id", "epoch"}
                or any(type(x) is not str or not x for x in scope.values())
                or a.get("epoch") != scope["epoch"]
                or a.get("strategy") != lane
                or a.get("currency") != currency
                or type(a.get("source_revision")) is not int
                or a["source_revision"] < 0
                or type(a.get("source_head")) is not str
                or not a["source_head"]
                or type(a.get("observed_at")) is not int
                or not 0 <= now - a["observed_at"] <= 5
                or a.get("valuation") is not None
                or a.get("valuation_status") != "UNAVAILABLE"
                or type(a.get("positions")) is not dict
                or len(a["positions"]) > 3
            ):
                raise ValueError("ACCOUNT_SCOPE_REVISION_OR_FRESHNESS_CONFLICT")
            for key in ("opening_cash", "cash", "gross", "realized_costs", "net"):
                if type(a.get(key)) is not str or len(a[key]) > 160:
                    raise ValueError("EXACT_DECIMAL_ACCOUNT_VALUES_REQUIRED")
                number(a[key])
            for key in ("fees", "slippage", "funding"):
                if a.get(key) is not None:
                    if type(a[key]) is not str or len(a[key]) > 160:
                        raise ValueError("EXACT_OPTIONAL_DECIMAL_REQUIRED")
                    value_number = number(a[key])
                    if key != "funding" and value_number < 0:
                        raise ValueError("NEGATIVE_TRADING_COST")
            with localcontext() as arithmetic:
                arithmetic.prec = 28
                arithmetic.traps[Inexact] = True
                net = number(a["gross"]) - number(a["realized_costs"])
            if (
                number(a["opening_cash"]) <= 0
                or number(a["cash"]) < 0
                or number(a["realized_costs"]) < 0
                or net != number(a["net"])
            ):
                raise ValueError("ACCOUNT_ARITHMETIC_CONFLICT")
            if a.get("available_cash") is not None and (
                type(a["available_cash"]) is not str
                or not 0 <= number(a["available_cash"]) <= number(a["cash"])
            ):
                raise ValueError("UNVERIFIED_SPENDABLE_CASH")
            for position in a["positions"].values():
                if (
                    type(position) is not dict
                    or type(position.get("symbol")) is not str
                    or position.get("side") not in ("LONG", "SHORT")
                    or not 0 < number(position["remaining"]) <= number(position["quantity"])
                ):
                    raise ValueError("INVALID_OPEN_POSITION")
            if (
                type(a.get("resting_orders", {})) is not dict
                or len(a.get("resting_orders", {})) > 32
                or a.get("resting_orders")
                and a.get("available_cash") is not None
            ):
                raise ValueError("RESTING_ORDER_RESERVATION_UNVERIFIED")
            identity = {k: v for k, v in a.items() if k != "observed_at"}
            identities[lane] = {"revision": a["source_revision"], "digest": digest(identity)}
        if (
            self.scope["QUALITY_DIPS"]["account_id"] == self.scope["HYPERLIQUID"]["account_id"]
            or self.scope["QUALITY_DIPS"]["epoch"] == self.scope["HYPERLIQUID"]["epoch"]
        ):
            raise ValueError("CROSS_ACCOUNT_ALIAS")
        if self._high_water is not None and any(
            row["revision"] < self._high_water[lane]["revision"]
            or row["revision"] == self._high_water[lane]["revision"]
            and row != self._high_water[lane]
            for lane, row in identities.items()
        ):
            raise ValueError("ACCOUNT_REVISION_ROLLBACK_OR_CONFLICT")
        context = {
            "scope": self.scope,
            "execution_domain": self.execution_domain,
            "accounts": value,
        }
        frozen = body(context)
        receipt = verified(
            self.authority.verify_read(context, now=now),
            digest(context),
            "ATLAS_DASHBOARD_ACCOUNTS_VERIFIED_V1",
        )
        if (
            receipt.get("execution_domain") != self.execution_domain
            or body(context) != frozen
            or self.reader.read() != value
            or (self.reader, self.authority, self.clock, body(self.scope), self.execution_domain)
            != self._binding
            or type(self.clock()) is not int
            or not 0 <= self.clock() - now <= 1
        ):
            raise ValueError("ACCOUNT_READ_CUT_CHANGED")
        self._high_water = identities  # Presentation anti-rollback only, no custody.
        return value


class DashboardReadModels:
    def __init__(self, *, research, clock, accounts=None):
        if research is not None and (
            type(research) is not UnifiedResearchSources or research.clock is not clock
        ):
            raise ValueError("EXACT_READ_ONLY_RESEARCH_PAIR_REQUIRED")
        if accounts is not None and (
            type(accounts) is not DashboardAccountRead or accounts.clock is not clock
        ):
            raise ValueError("EXACT_READ_ONLY_ACCOUNT_PORT_REQUIRED")
        self.research, self.clock, self.accounts = research, clock, accounts
        self._ports = research, clock, accounts
        self.lock, self._last = RLock(), None

    def snapshot(self):
        with self.lock:
            if (self.research, self.clock, self.accounts) != self._ports:
                raise ValueError("DASHBOARD_COMPONENT_SUBSTITUTION")
            now = self.clock()
            if type(now) is not int or now < 0:
                raise ValueError("DASHBOARD_CLOCK_REQUIRED")
            domain = (
                self.research.sources["QUALITY_DIPS"].execution_domain
                if self.research
                else self.accounts.execution_domain
                if self.accounts
                else "UNAVAILABLE"
            )
            lanes = {
                k: {
                    "currency": c,
                    "research": {"status": "UNAVAILABLE", "source": None, "data": None},
                    "connection": "UNAVAILABLE",
                }
                for k, c in LANES.items()
            }
            first = None
            try:
                if self.research is not None:
                    first = self.research.read_current()
                    for lane, row in first["lanes"].items():
                        packet = row["packet"]
                        data = (
                            packet
                            if lane == "QUALITY_DIPS"
                            else self.research.sources[lane].research()
                        )
                        lanes[lane]["research"] = {
                            "status": "FRESH",
                            "source": {
                                "source_id": packet["source_id"],
                                "revision": packet["revision"],
                                "digest": digest(packet),
                                "observed_at": packet["observed_at"],
                                "max_age_seconds": 30 if lane == "QUALITY_DIPS" else 5,
                                "account_id": row["account_id"],
                                "epoch": row["epoch"],
                            },
                            "data": data,
                        }
                    if self.research.read_current() != first:
                        raise ValueError("RESEARCH_CUT_CHANGED")
                    self._last = strict(body(lanes))
            except FAILURES:
                for lane, row in lanes.items():
                    old = self._last[lane]["research"]["source"] if self._last else None
                    stale = old and now - old["observed_at"] > old["max_age_seconds"]
                    row["research"] = {
                        "status": "STALE" if stale else "UNKNOWN",
                        "source": old,
                        "data": None,
                    }
                first = None
            accounts = unavailable_accounts()
            if self.accounts is not None:
                try:
                    if self.accounts.execution_domain != domain:
                        raise ValueError("DASHBOARD_DOMAIN_CONFLICT")
                    accounts = self.accounts.read()
                    if self.research is not None:
                        for lane, scope in self.accounts.scope.items():
                            if scope != {
                                k: self.research.sources[lane].enrollment[k]
                                for k in ("account_id", "epoch")
                            }:
                                raise ValueError("DASHBOARD_RESEARCH_FINANCIAL_ACCOUNT_CONFLICT")
                except FAILURES:
                    accounts = unavailable_accounts("UNKNOWN")
            if first is not None and self.research.read_current() != first:
                raise ValueError("DASHBOARD_FINAL_SOURCE_CUT_CHANGED")
            if (
                self.accounts is not None
                and accounts["state"] == "ACKNOWLEDGED"
                and self.accounts.read() != accounts
            ):
                raise ValueError("DASHBOARD_FINAL_ACCOUNT_CUT_CHANGED")
            if (
                (self.research, self.clock, self.accounts) != self._ports
                or type(self.clock()) is not int
                or not 0 <= self.clock() - now <= 1
            ):
                raise ValueError("DASHBOARD_FINAL_COMPONENT_OR_CLOCK_CHANGED")
            result = {
                "schema": "ATLAS_DASHBOARD_READ_MODEL_V1",
                "execution_domain": domain,
                "observed_at": now,
                "lanes": lanes,
                "accounts": accounts,
                "runtime": {"status": "UNAVAILABLE", "paper_startup_authorized": False},
                "stop": {
                    "status": "UNAVAILABLE",
                    "reason": "NO_SEPARATELY_ACCEPTED_OWNED_SESSION_CONTROL",
                },
                "continuation": {
                    "status": "UNAVAILABLE",
                    "reason": "NO_ENROLLED_OPERATIONAL_CONTINUATION_MAP",
                },
                "total_cash": None,
                "total_equity": None,
                "startup_authorized": False,
            }
            result["account_scope"] = (
                strict(body(self.accounts.scope))
                if self.accounts is not None
                else {
                    k: {n: s.enrollment[n] for n in ("account_id", "epoch")}
                    for k, s in self.research.sources.items()
                }
                if self.research
                else None
            )
            for lane in lanes.values():
                lane["research"]["completeness"] = (
                    "ACCEPTED_SOURCE_CUT_NOT_FULL_MARKET_COVERAGE"
                    if lane["research"]["status"] == "FRESH"
                    else "UNVERIFIED"
                )
            result["snapshot_id"] = digest(result)
            return strict(body(result))
