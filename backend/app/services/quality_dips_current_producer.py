"""Explicit current research -> original QD projection -> acknowledged source cut.

Inert assembly only: no acquisition, defaults, account, financial runtime or root
initialization. A digest binds content; the injected source owner must separately
accept the exact input/domain/enrollment. Fixture acceptance stays DISPOSABLE.
"""

from datetime import UTC, datetime
from threading import Lock

from scripts.observation_runtime.personal_research_archive import (
    NativePersonalResearchArchive,
    validate_enrollment,
)

from app.investment.quality_dips_candidate_evidence import (
    CandidateEvidenceAdapter,
    timestamp,
    verified,
)
from app.services.paper_financial_replay import body, digest, strict, text
from app.services.paper_source_publication import QualityDipsSourcePublication
from app.services.quality_dips_research_only import project_explicit_research


class _Projection:
    def __init__(self):
        self.raw = None

    def read_current(self):
        if self.raw is None:
            raise ValueError("QD_CURRENT_INPUT_NOT_ASSEMBLED")
        return strict(body(self.raw))


class QualityDipsCurrentProducer:
    def __init__(
        self,
        *,
        source,
        input_authority,
        publication_authority,
        archive,
        candidates,
        clock,
        enrollment,
        execution_domain,
    ):
        self.enrollment = validate_enrollment(enrollment)
        if (
            execution_domain not in ("DISPOSABLE", "OPERATIONAL")
            or type(archive) is not NativePersonalResearchArchive
            or type(candidates) is not CandidateEvidenceAdapter
            or any(x is None for x in (source, input_authority, publication_authority, clock))
            or archive.enrollment != self.enrollment
            or archive.clock is not clock
        ):
            raise ValueError("QD_CURRENT_EXPLICIT_BOUND_PORTS_REQUIRED")
        self.source, self.input_authority = source, input_authority
        self.archive, self.clock = archive, clock
        self.execution_domain = execution_domain
        self._scope = body(self.enrollment)
        self._ports = source, input_authority, archive, clock, execution_domain
        self._projection = _Projection()
        self.publication = QualityDipsSourcePublication(
            research=self._projection,
            candidates=candidates,
            source_id=self.enrollment["source_id"],
            authority=publication_authority,
            archive=archive,
            clock=clock,
        )
        self._publication = self.publication
        self._lock = Lock()
        self._failed = False

    def _now(self):
        now = self.clock()
        if type(now) is not int or now < 0:
            raise ValueError("QD_CURRENT_CLOCK_REQUIRED")
        return now

    def _verify(self):
        if (
            self._failed
            or body(self.enrollment) != self._scope
            or self.archive.enrollment != self.enrollment
            or self.publication is not self._publication
            or self.publication.archive is not self.archive
            or self.publication.research is not self._projection
            or any(
                a is not b
                for a, b in zip(
                    (
                        self.source,
                        self.input_authority,
                        self.archive,
                        self.clock,
                        self.execution_domain,
                    ),
                    self._ports,
                    strict=True,
                )
            )
        ):
            raise ValueError("QD_CURRENT_BINDING_CHANGED_OR_PUBLICATION_UNCERTAIN")

    def _accept(self, cut, now):
        if (
            type(cut) is not dict
            or set(cut)
            != {
                "schema",
                "execution_domain",
                "source_id",
                "input_revision",
                "observed_at",
                "rows",
                "observations",
                "instruments",
                "quotes",
                "publication",
                "monitors",
                "provenance",
            }
            or cut["schema"] != "QD_CURRENT_RESEARCH_INPUT_V1"
            or cut["execution_domain"] != self.execution_domain
            or cut["source_id"] != self.enrollment["source_id"]
            or type(cut["input_revision"]) is not int
            or cut["input_revision"] < 1
            or type(cut["observed_at"]) is not int
            or not 0 <= now - cut["observed_at"] <= 30
            or type(cut["provenance"]) is not dict
            or not cut["provenance"]
            or len(body(cut).encode()) > 131072
        ):
            raise ValueError("QD_CURRENT_INPUT_SCOPE_FRESHNESS_OR_PROVENANCE")
        context = {
            "enrollment": self.enrollment,
            "execution_domain": self.execution_domain,
            "input": cut,
        }
        frozen = body(context)
        proof = self.input_authority.verify_current(context, now=now)
        proof = verified(proof, digest(strict(frozen)), "QD_CURRENT_RESEARCH_VERIFIED_V1")
        if body(context) != frozen or proof.get("execution_domain") != self.execution_domain:
            raise ValueError("QD_CURRENT_AUTHORITY_MUTATION_OR_DOMAIN")
        return proof

    def _project(self, cut, now):
        rows, observations = cut["rows"], cut["observations"]
        instruments, quotes, monitors = cut["instruments"], cut["quotes"], cut["monitors"]
        if (
            type(rows) is not list
            or not 0 < len(rows) <= 50
            or any(type(r) is not dict for r in rows)
            or type(observations) is not dict
            or set(observations) != {r.get("symbol") for r in rows}
            or type(instruments) is not list
            or not 0 < len(instruments) <= 16
            or any(type(i) is not dict for i in instruments)
            or type(quotes) is not dict
            or set(quotes) != {i.get("symbol") for i in instruments}
            or type(monitors) is not dict
            or len(monitors) > 16
        ):
            raise ValueError("QD_CURRENT_COMPLETE_INPUT_MAPS_REQUIRED")
        by_symbol = {i.get("symbol"): i for i in instruments}
        if (
            len(by_symbol) != len(instruments)
            or not set(by_symbol) <= set(observations)
            or len({i.get("instrument_id") for i in instruments}) != len(instruments)
        ):
            raise ValueError("QD_CURRENT_INSTRUMENT_ALIAS_OR_MISSING_RESEARCH")
        pub = cut["publication"]
        if (
            type(pub) is not dict
            or pub.get("schema") != "QD_RANKING_REVISION_V1"
            or pub.get("state") != "ACTIVE"
            or type(pub.get("generation")) is not int
            or pub["generation"] < 1
            or type(pub.get("source_revision")) is not int
            or pub["source_revision"] < 1
            or type(pub.get("issued_at")) is not int
            or type(pub.get("expires_at")) is not int
            or not 0 <= now - pub["issued_at"] <= 600
            or not pub["issued_at"]
            <= cut["observed_at"]
            <= now
            < pub["expires_at"]
            <= pub["issued_at"] + 600
        ):
            raise ValueError("QD_CURRENT_RANKING_NOT_CURRENT")
        text(pub.get("issuer"))
        text(pub.get("cohort_id"))
        for row in rows:
            if not 0 <= now - timestamp(row.get("timestamp")) <= 600:
                raise ValueError("QD_CURRENT_RESEARCH_STALE")
        board = project_explicit_research(rows, now=datetime.fromtimestamp(now, UTC))
        eligible = []
        for row in board:
            symbol = row["symbol"]
            plan = row["quality_dips_v2"]["quality_dips_v3"]
            obs = observations[symbol]
            if (
                type(obs) is not dict
                or obs.get("symbol") != symbol
                or obs.get("prediction") != plan
                or obs.get("classification") != plan["patient_state"]
                or obs.get("strategy_version") != "QUALITY_DIPS_V3"
                or obs.get("policy_version") != "quality-dips-v3-mos-15-20-25-30-v1"
                or obs.get("evidence_class") != "FORWARD_COLLECTION"
                or obs.get("execution") != "MANUAL_ONLY"
                or type(obs.get("missing_data")) is not list
                or not 0 <= now - timestamp(obs.get("source_timestamp")) <= 600
                or not timestamp(obs["source_timestamp"])
                <= timestamp(obs.get("timestamp"))
                <= pub["issued_at"]
            ):
                raise ValueError("QD_CURRENT_ORIGINAL_OBSERVATION_CONFLICT")
            if symbol not in by_symbol:
                continue
            instrument = by_symbol[symbol]
            self.publication.candidates.execution(instrument, quotes[symbol], now=now)
            ladder = plan["entry_ladder"]
            if (
                plan["patient_state"] in ("ACCUMULATION", "DEEP_VALUE", "GENERATIONAL")
                and not plan["blockers"]
                and ladder["ready"] is True
                and any(x["level"] == "L1" and x["reached"] is True for x in ladder["levels"])
                and not row["blockers"]
                and not row["missing_critical"]
                and not obs["missing_data"]
            ):
                eligible.append(instrument)
        for ident, monitor in monitors.items():
            if (
                type(monitor) is not dict
                or monitor.get("instrument") not in instruments
                or monitor["instrument"]["instrument_id"] != ident
                or monitor.get("symbol") != monitor["instrument"]["symbol"]
                or type(monitor.get("observed_at")) is not int
                or not 0 <= now - monitor["observed_at"] <= 30
            ):
                raise ValueError("QD_CURRENT_MONITOR_UNVERIFIED")
        return {
            "board": board,
            "observations": observations,
            "instruments": eligible,
            "quotes": quotes,
            "publication": pub,
            "monitors": monitors,
        }

    def _archived_input(self, record):
        evidence = record["sources"].get("current_input")
        if type(evidence) is not dict or set(evidence) != {"input", "acceptance", "enrollment"}:
            raise ValueError("QD_CURRENT_ARCHIVED_PROVENANCE_REQUIRED")
        cut = evidence["input"]
        if (
            evidence["enrollment"] != digest(self.enrollment)
            or type(cut) is not dict
            or cut.get("source_id") != self.enrollment["source_id"]
            or cut.get("execution_domain") != self.execution_domain
            or type(cut.get("input_revision")) is not int
            or cut["input_revision"] < 1
        ):
            raise ValueError("QD_CURRENT_ARCHIVED_ENROLLMENT_MISMATCH")
        binding = digest(
            {"enrollment": self.enrollment, "execution_domain": self.execution_domain, "input": cut}
        )
        receipt = verified(evidence["acceptance"], binding, "QD_CURRENT_RESEARCH_VERIFIED_V1")
        if receipt.get("execution_domain") != self.execution_domain:
            raise ValueError("QD_CURRENT_ARCHIVED_SOURCE_BINDING")
        return evidence

    def read_publication(self, timeout):
        self._verify()
        if type(timeout) not in (int, float) or not 0 < timeout <= 0.2:
            raise ValueError("QD_BOUNDED_SOURCE_READ_REQUIRED")
        head = self.archive.current()
        record = self.archive.read_evidence(head)
        evidence = self._archived_input(record)
        cut = evidence["input"]
        now = self._now()
        proof = self._accept(cut, now)
        verified(evidence["acceptance"], proof["binding"], "QD_CURRENT_RESEARCH_VERIFIED_V1")
        if (
            evidence["acceptance"].get("binding") != proof["binding"]
            or evidence["acceptance"].get("execution_domain") != self.execution_domain
        ):
            raise ValueError("QD_CURRENT_ARCHIVED_SOURCE_BINDING")
        raw = self._project(cut, now)
        bundles = [
            {
                "board": raw["board"],
                "observation": raw["observations"][i["symbol"]],
                "instrument": i,
                "quote": raw["quotes"][i["symbol"]],
                "publication": raw["publication"],
            }
            for i in raw["instruments"]
        ]
        if (
            record["sources"]["research"] != raw
            or record["sources"]["scanner_rows"] != raw["board"]
            or record["packet"]["bundles"] != bundles
            or record["packet"]["monitors"] != raw["monitors"]
            or record["packet"] != self.publication.read_publication(timeout)
            or self.archive.current() != head
            or not 0 <= self._now() - now <= 1
            or not 0 <= self._now() - cut["observed_at"] <= 30
        ):
            raise ValueError("QD_CURRENT_REPLAY_OR_SOURCE_CUT_CHANGED")
        self._verify()
        return strict(body(record["packet"]))

    def publish_current(self):
        self._verify()
        if not self._lock.acquire(blocking=False):
            raise ValueError("QD_CURRENT_PUBLICATION_ALREADY_ACTIVE")
        attempted = False
        try:
            now = self._now()
            cut = strict(body(self.source.read_current()))
            proof = self._accept(cut, now)
            raw = self._project(cut, now)
            head = self.archive.current()
            if head["revision"]:
                previous = self._archived_input(self.archive.read_evidence(head))
                prior = previous["input"]
                if cut["input_revision"] < prior["input_revision"]:
                    raise ValueError("QD_CURRENT_INPUT_ROLLBACK")
                if cut["input_revision"] == prior["input_revision"]:
                    if cut != prior:
                        raise ValueError("QD_CURRENT_INPUT_REVISION_CONFLICT")
                    return self.read_publication(0.2)
            if body(self.source.read_current()) != body(cut) or not 0 <= self._now() - now <= 1:
                raise ValueError("QD_CURRENT_INPUT_CHANGED_BEFORE_PUBLICATION")
            self._accept(cut, self._now())
            self._projection.raw = raw
            self._verify()
            attempted = True
            packet = self.publication.publish_scanner(
                raw["board"],
                datetime.fromtimestamp(cut["observed_at"], UTC).isoformat(),
                evidence={"input": cut, "acceptance": proof, "enrollment": digest(self.enrollment)},
                expected_head=head,
            )
            if self.archive.current()["revision"] != head["revision"] + 1:
                raise ValueError("QD_CURRENT_PUBLICATION_REVISION_UNCERTAIN")
            if (
                body(self.source.read_current()) != body(cut)
                or self.read_publication(0.2) != packet
            ):
                raise ValueError("QD_CURRENT_COMPLETION_SOURCE_CHANGED")
            return packet
        except BaseException:
            # Never retry an attempted publication on this assembly. Reopening
            # still requires native ACK/current custody and exact source evidence.
            if attempted:
                self._failed = True
            raise
        finally:
            self._projection.raw = None
            self._lock.release()
