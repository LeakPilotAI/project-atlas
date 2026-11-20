"""Read-only joint view/preparation of the existing two canonical source lanes.

No journal, financial runtime construction, capital conversion or counterpart
account. Authority must accept the exact pair; neither lane authenticates the other.
"""

from app.investment.quality_dips_candidate_evidence import verified
from app.services.hyperliquid_current_producer import HyperliquidCurrentProducer
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_current_producer import QualityDipsCurrentProducer


class UnifiedResearchSources:
    def __init__(self, *, quality_dips, hyperliquid, authority, clock):
        if (
            type(quality_dips) is not QualityDipsCurrentProducer
            or type(hyperliquid) is not HyperliquidCurrentProducer
            or authority is None
            or clock is None
            or quality_dips.clock is not clock
            or hyperliquid.clock is not clock
            or quality_dips.execution_domain != hyperliquid.execution_domain
        ):
            raise ValueError("UNIFIED_EXACT_CURRENT_SOURCE_LANES_REQUIRED")
        self.sources = {"QUALITY_DIPS": quality_dips, "HYPERLIQUID": hyperliquid}
        self.authority, self.clock = authority, clock
        self._ports = dict(self.sources), authority, clock
        self._enrollments = body({k: v.enrollment for k, v in self.sources.items()})
        self._verify()

    def _verify(self):
        if (
            set(self.sources) != {"QUALITY_DIPS", "HYPERLIQUID"}
            or any(self.sources[k] is not v for k, v in self._ports[0].items())
            or self.authority is not self._ports[1]
            or self.clock is not self._ports[2]
            or body({k: v.enrollment for k, v in self.sources.items()}) != self._enrollments
        ):
            raise ValueError("UNIFIED_SOURCE_COMPONENT_SUBSTITUTION")
        q, h = self.sources.values()
        if (
            q.enrollment["account_id"] == h.enrollment["account_id"]
            or q.enrollment["epoch"] == h.enrollment["epoch"]
            or q.enrollment["source_id"] == h.enrollment["source_id"]
            or q.enrollment["root_id"] == h.enrollment["root_id"]
            or q.archive.images is h.archive.images
            or q.enrollment["release_digest"] != h.enrollment["release_digest"]
            or q.enrollment["source_commit"] != h.enrollment["source_commit"]
        ):
            raise ValueError("UNIFIED_SOURCE_ACCOUNT_ALIAS_OR_RELEASE_MISMATCH")

    def read_current(self):
        self._verify()
        now = self.clock()
        if type(now) is not int or now < 0:
            raise ValueError("UNIFIED_RESEARCH_CLOCK_REQUIRED")
        q, h = self.sources.values()
        packets = {"QUALITY_DIPS": q.read_publication(0.2), "HYPERLIQUID": h.read_cut()}
        context = {
            "execution_domain": q.execution_domain,
            "enrollments": strict(self._enrollments),
            "packets": packets,
        }
        frozen = body(context)
        receipt = verified(
            self.authority.verify_current(context, now=now),
            digest(context),
            "ATLAS_UNIFIED_RESEARCH_VERIFIED_V1",
        )
        if (
            body(context) != frozen
            or receipt.get("execution_domain") != q.execution_domain
            or q.read_publication(0.2) != packets["QUALITY_DIPS"]
            or h.read_cut() != packets["HYPERLIQUID"]
            or type(self.clock()) is not int
            or not 0 <= self.clock() - now <= 1
        ):
            raise ValueError("UNIFIED_RESEARCH_CUT_CHANGED_OR_DOMAIN")
        self._verify()
        return strict(
            body(
                {
                    "schema": "ATLAS_CURRENT_RESEARCH_VIEW_V1",
                    "execution_domain": q.execution_domain,
                    "lanes": {
                        k: {
                            "account_id": s.enrollment["account_id"],
                            "epoch": s.enrollment["epoch"],
                            "currency": "USD" if k == "QUALITY_DIPS" else "USDC",
                            "packet": packets[k],
                        }
                        for k, s in self.sources.items()
                    },
                    "acceptance": receipt,
                    "total_cash": None,
                    "total_equity": None,
                    "financial_startup_authorized": False,
                }
            )
        )

    def prepare_canonical_lanes(self, *, lanes, portfolio, risk):
        """Verify existing canonical identities without connecting/starting a runtime."""
        from app.services.unified_native_writer import CanonicalWriterLane
        from app.services.unified_portfolio_custody import UnifiedPortfolioCustody

        if (
            type(lanes) is not dict
            or set(lanes) != set(self.sources)
            or any(type(v) is not CanonicalWriterLane for v in lanes.values())
            or type(portfolio) is not UnifiedPortfolioCustody
            or portfolio.risk is not risk
            or portfolio.clock is not self.clock
            or risk is None
            or set(portfolio.writers) != set(lanes)
        ):
            raise ValueError("UNIFIED_ACTUAL_CANONICAL_LANES_CUSTODY_AND_RISK_REQUIRED")
        view = self.read_current()
        portfolio._verify()
        pins = []
        for lane, source in self.sources.items():
            lanes[lane]._verify()
            writer = lanes[lane].writer
            if (
                portfolio.writers[lane] is not writer
                or writer.manifest["epoch"] != source.enrollment["epoch"]
                or writer.manifest["currency"] != ("USD" if lane == "QUALITY_DIPS" else "USDC")
                or writer.store.enrollment["account_id"] != source.enrollment["account_id"]
                or writer.store.enrollment["epoch"] != source.enrollment["epoch"]
                or writer.store.enrollment["release_digest"] != source.enrollment["release_digest"]
            ):
                raise ValueError("UNIFIED_CANONICAL_ACCOUNT_SOURCE_MISMATCH")
            if (
                lane == "HYPERLIQUID"
                and digest(writer.manifest) != source.enrollment["parameters_digest"]
            ):
                raise ValueError("UNIFIED_PERP_PARAMETER_SOURCE_MISMATCH")
            if lane == "QUALITY_DIPS":
                if lanes[lane].planner.reader.source is not source:
                    raise ValueError("UNIFIED_QD_READER_SOURCE_MISMATCH")
            elif (
                lanes[lane].planner.source is not source
                or lanes[lane].observer.source is not source
            ):
                raise ValueError("UNIFIED_PERP_PLANNER_OBSERVER_SOURCE_MISMATCH")
            pins.append(
                (
                    lane,
                    lanes[lane],
                    writer,
                    writer.store,
                    lanes[lane].planner,
                    lanes[lane].observer,
                    body(writer.manifest),
                    body(writer.store.enrollment),
                )
            )
        context = {
            "view": view,
            "manifests": {k: digest(v.writer.manifest) for k, v in lanes.items()},
            "policy_digest": digest(portfolio.policy),
        }
        frozen = body(context)
        receipt = verified(
            self.authority.verify_canonical(context, lanes, portfolio, risk),
            digest(context),
            "ATLAS_UNIFIED_RESEARCH_BINDING_V1",
        )
        after = self.read_current()
        for lane, obj, writer, store, planner, observer, manifest, enrollment in pins:
            if (
                lanes[lane] is not obj
                or obj.writer is not writer
                or writer.store is not store
                or obj.planner is not planner
                or obj.observer is not observer
                or portfolio.writers.get(lane) is not writer
                or body(writer.manifest) != manifest
                or body(store.enrollment) != enrollment
            ):
                raise ValueError("UNIFIED_CANONICAL_COMPONENT_CHANGED")
            obj._verify()
            if lane == "QUALITY_DIPS":
                if planner.reader.source is not self.sources[lane]:
                    raise ValueError("UNIFIED_CANONICAL_COMPONENT_CHANGED")
            elif (
                planner.source is not self.sources[lane]
                or observer.source is not self.sources[lane]
            ):
                raise ValueError("UNIFIED_CANONICAL_COMPONENT_CHANGED")
        portfolio._verify()
        if (
            body(context) != frozen
            or portfolio.risk is not risk
            or digest(portfolio.policy) != context["policy_digest"]
            or {k: v for k, v in after.items() if k != "acceptance"}
            != {k: v for k, v in view.items() if k != "acceptance"}
        ):
            raise ValueError("UNIFIED_CANONICAL_PREPARATION_CHANGED")
        # The original composition factory still owns every financial/native
        # enrollment, installation lease, reservation and session startup check.
        return receipt
