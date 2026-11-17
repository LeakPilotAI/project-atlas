"""Selected-original Quality Dips SEC-only WATCH issuer; NEVER executable.

Operational original issuer for a narrowly authenticated **NO-ENTRY** research
cut only, after genuine TWO native PAPER accounts, local Windows owner,
postinception CONNECT_APPROVED_DATA activation and independent release/NTP.

Rechecks directly cached ORIGINAL SEC 10-Q plus SEC Company Facts using the
existing original parsing/corroboration routine. The SEC has no price target;
this class NEVER manufactures one. Exactly ZERO instruments, quotes and
monitors, and every projected candidate state must be WATCH. Analyst research,
Alpaca executable quotes, source rights, financial PAPER grants, private
brokerage information, fees and live trades are NOT authorized by this issuer.

No network on import, no source file/financial root creation, and no startup.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_research_only import project_explicit_research

from scripts.observation_runtime.personal_local_authority import (
    NativePersonalOperatorAuthority,
)
from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_writer_generation import NativeRecoveredFinancialWriterOwner
from scripts.observation_runtime.personal_research_archive import (
    NativePersonalResearchArchive,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock,
    require_version_safe_release_digest,
)
from scripts.observation_runtime.qd_sec_original_quarter_replay import (
    inspect_original_quarter,
)

SCHEMA = "QD_CURRENT_RESEARCH_VERIFIED_V1"
WATCH = "ATLAS_ORIGINAL_SEC_WATCH_ONLY_V1"
CIKS = {"MSFT": "0000789019", "AVGO": "0001730168"}
SECONDS = 30


class NativeSelectedQualityDipsSecWatchIssuer:
    """No arbitrary issuer injection: exact original Windows account/owner."""

    def __init__(self, *, owner, operator, clock, archive, qd, perp):
        if (
            type(owner) not in (RetainedSelectedNativeOwnerPreflight,NativeRecoveredFinancialWriterOwner)
            or type(operator) is not NativePersonalOperatorAuthority
            or type(clock) is not NativeVersionSafePaperOperatorClock
            or type(archive) is not NativePersonalResearchArchive
            or type(qd) is not dict or type(perp) is not dict
            or owner._phase not in ("INITIAL_READBACK_ONLY", "CURRENT_READBACK_ONLY")
            or owner.release_digest != qd.get("release_digest")
            or owner.release_digest != perp.get("release_digest")
            or archive.enrollment["release_digest"] != owner.release_digest
            or archive.enrollment["account_id"] != qd.get("account_id")
            or archive.clock is not clock or operator.clock is not clock
            or operator.enrollment != qd
            or operator.accounts != {
                "QUALITY_DIPS": digest(qd),
                "HYPERLIQUID": digest(perp),
            }
        ):
            raise ValueError("QD_SEC_WATCH_ORIGINAL_TWO_ACCOUNTS_OWNER_REQUIRED")
        self.owner, self.operator, self.clock, self.archive = (
            owner, operator, clock, archive,
        )
        self.qd, self.perp = strict(body(qd)), strict(body(perp))
        self._ports = (owner, operator, clock, archive)
        self._enrollments = digest([self.qd, self.perp, archive.enrollment])
        self._activation = None
        self._revision = 0
        self._last = None

    def _original(self, *, now):
        if (
            type(now) is not int
            or self.owner._phase not in ("INITIAL_READBACK_ONLY", "CURRENT_READBACK_ONLY")
            or any(a is not b for a, b in zip(
                (self.owner, self.operator, self.clock, self.archive),
                self._ports, strict=True,
            ))
            or digest([self.qd, self.perp, self.archive.enrollment])
            != self._enrollments
            or self.operator.accounts != {
                "QUALITY_DIPS": digest(self.qd),
                "HYPERLIQUID": digest(self.perp),
            }
        ):
            raise ValueError("QD_SEC_WATCH_NATIVE_IDENTITY_CHANGED")
        if self.owner.verify_still_running() is not True:
            raise ValueError("QD_SEC_WATCH_ORIGINAL_JOB_REVOKED")
        self.owner.require_exact_roster(qd=self.qd, perp=self.perp)
        self.clock.require_operational(self.operator.runtime_id)
        if require_version_safe_release_digest(
            clock=self.clock, runtime_id=self.operator.runtime_id,
            release_digest=self.owner.release_digest,
        ) is not True:
            raise ValueError("QD_SEC_WATCH_SELECTED_RELEASE_REQUIRED")
        actual = self.clock()
        # Original SEC cache reparse can cross an integer UTC second.
        # Keep the entire trusted cut within the 30-second source TTL.
        if type(actual) is not int or not 0 <= actual - now <= SECONDS:
            raise ValueError("QD_SEC_WATCH_TRUSTED_UTC_REQUIRED")
        current_activation = self.operator.activation("CONNECT_APPROVED_DATA")
        if type(current_activation) is not dict:
            raise ValueError("QD_SEC_WATCH_POSTINCEPTION_DATA_ACTIVATION_REQUIRED")
        activation_binding = digest(current_activation)
        if self._activation is not None and activation_binding != self._activation:
            raise ValueError("QD_SEC_WATCH_OPERATOR_ACTIVATION_CHANGED")
        self.archive.current()
        return activation_binding

    def verify_current(self, context, *, now):
        """Accept only current independent SEC-corroborated NONTRADE cuts."""
        activation = self._original(now=now)
        if (
            type(context) is not dict
            or set(context) != {"enrollment", "execution_domain", "input"}
            or context["execution_domain"] != "OPERATIONAL"
            or context["enrollment"] != self.archive.enrollment
            or type(context["input"]) is not dict
        ):
            raise ValueError("QD_SEC_WATCH_EXACT_OPERATIONAL_SCOPE_REQUIRED")
        cut = context["input"]
        if (
            set(cut) != {
                "schema", "execution_domain", "source_id",
                "input_revision", "observed_at", "rows",
                "observations", "instruments", "quotes",
                "publication", "monitors", "provenance",
            }
            or cut.get("schema") != "QD_CURRENT_RESEARCH_INPUT_V1"
            or cut.get("execution_domain") != "OPERATIONAL"
            or cut.get("source_id") != self.archive.enrollment["source_id"]
            or type(cut.get("input_revision")) is not int
            or cut["input_revision"] < 1
            or type(cut.get("observed_at")) is not int
            or not 0 <= now - cut["observed_at"] <= SECONDS
            or type(cut.get("instruments")) is not list
            or cut["instruments"] != []
            or type(cut.get("quotes")) is not dict
            or cut["quotes"] != {}
            or type(cut.get("monitors")) is not dict
            or cut["monitors"] != {}
            or type(cut.get("rows")) is not list
            or not 1 <= len(cut["rows"]) <= len(CIKS)
            or type(cut.get("observations")) is not dict
            or type(cut.get("provenance")) is not dict
            or set(cut["provenance"]) != {"schema", "sec_quarters"}
            or cut["provenance"]["schema"] != WATCH
            or type(cut["provenance"]["sec_quarters"]) is not dict
            or type(cut.get("publication")) is not dict
            or cut["publication"].get("issuer") != WATCH
            or cut["publication"].get("schema") != "QD_RANKING_REVISION_V1"
            or cut["publication"].get("state") != "ACTIVE"
            or type(cut["publication"].get("issued_at")) is not int
            or type(cut["publication"].get("expires_at")) is not int
            or not cut["publication"]["issued_at"] <= cut["observed_at"]
            <= now < cut["publication"]["expires_at"]
            <= cut["publication"]["issued_at"] + 600
        ):
            raise ValueError("QD_SEC_WATCH_NONEXECUTABLE_EXACT_CUT_REQUIRED")
        rows = cut["rows"]
        symbols = [r.get("symbol") for r in rows if type(r) is dict]
        if (
            len(symbols) != len(rows)
            or len(set(symbols)) != len(rows)
            or not set(symbols) <= set(CIKS)
            or set(cut["provenance"]["sec_quarters"]) != set(symbols)
            or set(cut["observations"]) != set(symbols)
            or any(
                r.get("valuation_sources") not in (None, [])
                or r.get("normalization_sources") not in (None, [])
                for r in rows
            )
        ):
            raise ValueError("QD_SEC_WATCH_MISSING_INDEPENDENT_VALUATION_NO_ENTRY")
        previous = body(context)
        date = datetime.fromtimestamp(now, UTC)
        projected = project_explicit_research(rows, now=date)
        for row in projected:
            symbol = row["symbol"]
            plan = row["quality_dips_v2"]["quality_dips_v3"]
            observed = cut["observations"][symbol]
            if (
                plan["patient_state"] != "WATCH"
                or type(observed) is not dict
                or observed.get("prediction") != plan
                or observed.get("classification") != "WATCH"
                or observed.get("evidence_class") != "FORWARD_COLLECTION"
                or observed.get("execution") != "MANUAL_ONLY"
                or observed.get("missing_data") != []
            ):
                raise ValueError("QD_SEC_WATCH_PROJECTION_OR_ORIGINAL_OBSERVATION")
        originals = {}
        for symbol in symbols:
            result = inspect_original_quarter(
                symbol=symbol, cik=CIKS[symbol], now=date,
            )
            if (
                type(result) is not dict
                or result.get("status")
                != "DIRECT_SEC_ORIGINAL_AND_COMPANYFACTS_CORROBORATED"
                or result.get("original_filing_and_companyfacts_matched")
                is not True
                or result.get("operational_source_accepted") is not False
                or result.get("financial_paper_authorized") is not False
                or result.get("live_order_authorized") is not False
                or result != cut["provenance"]["sec_quarters"][symbol]
            ):
                raise ValueError("QD_SEC_WATCH_PRIMARY_ORIGINAL_RECEIPT_REQUIRED")
            originals[symbol] = digest(result)
        if (
            body(context) != previous
            or self.archive.current() is None
            or not 0 <= self.clock() - now <= SECONDS
            or self._revision > cut["input_revision"]
            or self._revision == cut["input_revision"]
            and self._last is not None and self._last != digest(context)
        ):
            raise ValueError("QD_SEC_WATCH_CONTEXT_CHANGED_OR_REPLAY")
        self._original(now=now)
        self._activation = activation
        self._revision = cut["input_revision"]
        self._last = digest(context)
        return {
            "schema": SCHEMA,
            "verified": True,
            "binding": digest(context),
            "receipt_id": digest({
                "scope": WATCH, "account": digest(self.qd),
                "original_sec": originals, "activation": activation,
                "source_id": self.archive.enrollment["source_id"],
                "input": digest(cut),
            }),
            "execution_domain": "OPERATIONAL",
            "no_entry_only": True,
            "independent_equity_valuation_accepted": False,
            "executable_market_quote_accepted": False,
            "financial_paper_startup_authorized": False,
            "live_trading_authorized": False,
        }
