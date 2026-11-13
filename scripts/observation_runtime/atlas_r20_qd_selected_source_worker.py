"""Exact selected-owner Quality Dips forward publisher handoff (SOURCE ONLY).

An installed original Windows Job child with a retained original process identity
may drive the existing NativePersonalResearchArchive + QualityDipsCurrentProducer.
No inputs, source attestations, financial activation, accounts, defaults, clocks,
provider connections, or background worker are constructed here.

A completed native archive publication is NOT an accepted independent source
issuer, broker entitlement, financial Stop lease, or PAPER startup grant.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

from app.services.paper_financial_replay import body, digest
from app.services.quality_dips_current_producer import QualityDipsCurrentProducer

from scripts.observation_runtime.personal_native_selected_owned_job_preflight import (
    RetainedSelectedNativeOwnerPreflight,
)
from scripts.observation_runtime.personal_research_archive import (
    NativePersonalResearchArchive,
)
from scripts.observation_runtime.personal_version_safe_release_clock import (
    NativeVersionSafePaperOperatorClock,
    require_version_safe_release_digest,
)
from scripts.observation_runtime.quality_dips_read_service import observe_self

SCHEMA = "ATLAS_QD_ORIGINAL_SELECTED_OPERATING_SOURCE_HANDOFF_V1"
# An original QD source archive genesis requires CONNECT_APPROVED_DATA,
# which original later-release activation cannot grant before two FS1/FS3
# account ACKs. Refuse PREINCEPTION and PREINCEPTION_COORDINATION_READY:
# those phases cannot genuinely host an accepted native current-source CAS.
_ALLOWED_PHASES = frozenset(("INITIAL_READBACK_ONLY",))


def _installed_qd_source(origin):
    """The actual producer must come from selected immutable code, not workspace."""
    expected = (
        Path(origin.image).resolve().parents[1]
        / "backend/app/services/quality_dips_current_producer.py"
    )
    actual = Path(inspect.getfile(QualityDipsCurrentProducer)).resolve()
    expected_worker = (
        Path(origin.image).resolve().parents[1]
        / "scripts/observation_runtime/atlas_r20_qd_selected_source_worker.py"
    )
    # This new orchestration code must itself be installed into an auditable
    # successor release. Never invoke it from an unselected workspace.
    return actual == expected and Path(__file__).resolve() == expected_worker


class SelectedOwnerQDForwardPublisher:
    """Bind the real current source to the original installed process/Job.

    One explicit publication attempt per bound worker. No default archive or
    synthetic acceptance; the producer's original input and native archive
    authorities must independently accept the data and CAS publication.
    """

    def __init__(self, *, owner, producer, clock, runtime_id):
        if (type(owner) is not RetainedSelectedNativeOwnerPreflight
                or type(producer) is not QualityDipsCurrentProducer
                or type(clock) is not NativeVersionSafePaperOperatorClock
                or type(runtime_id) is not str or not runtime_id
                or not 1 <= len(runtime_id) <= 256
                or producer.execution_domain != "OPERATIONAL"
                or type(producer.archive) is not NativePersonalResearchArchive
                or producer.archive.clock is not clock
                or producer.clock is not clock
                or producer.archive.enrollment != producer.enrollment
                or producer.enrollment["release_digest"] != owner.release_digest):
            raise ValueError("QD_FORWARD_EXACT_SELECTED_NATIVE_OPERATIONAL_PORTS_REQUIRED")
        self.owner, self.producer = owner, producer
        self.clock, self.runtime_id = clock, runtime_id
        self._ports = (owner, producer, clock, runtime_id)
        self._enrollment = body(producer.enrollment)
        self._used = False
        self._uncertain = False
        self._verify()

    def _verify(self):
        if self._used or self._uncertain or (
                self.owner, self.producer, self.clock, self.runtime_id
        ) != self._ports:
            raise ValueError("QD_FORWARD_SOURCE_WORKER_USED_OR_CHANGED")
        owner, producer, clock = self.owner, self.producer, self.clock
        if (type(owner) is not RetainedSelectedNativeOwnerPreflight
                or type(producer) is not QualityDipsCurrentProducer
                or type(clock) is not NativeVersionSafePaperOperatorClock
                or producer.execution_domain != "OPERATIONAL"
                or producer.clock is not clock or producer.archive.clock is not clock
                or type(producer.archive) is not NativePersonalResearchArchive
                or producer.archive.enrollment != producer.enrollment
                or body(producer.enrollment) != self._enrollment
                or producer.enrollment["release_digest"] != owner.release_digest
                or owner._phase not in _ALLOWED_PHASES):
            raise ValueError("QD_FORWARD_ORIGINAL_PORTS_OR_PHASE_CHANGED")
        # A parked parent may hold the child's native handles, but must NOT
        # publish for the child. Source-only proof uses exact ORIGINAL identity.
        if (owner.verify_still_running() is not True
                or observe_self() != owner._identity
                or owner._identity.get("pid") != os.getpid()
                or not _installed_qd_source(owner)):
            raise ValueError("QD_FORWARD_ORIGINAL_INSTALLED_CHILD_ONLY")
        clock.require_operational(self.runtime_id)
        if require_version_safe_release_digest(
            clock=clock, runtime_id=self.runtime_id,
            release_digest=owner.release_digest,
        ) is not True:
            raise ValueError("QD_FORWARD_SELECTED_VERSION_SAFE_CLOCK_REQUIRED")
        return True

    def publish_one(self):
        """Request genuine source validation + one native CAS, never a trade."""
        self._verify()
        self._used = True
        self._uncertain = True  # Failure after attempting publish is not retried.
        packet = self.producer.publish_current()
        current = self.producer.read_publication(0.2)
        if (packet != current
                or packet.get("schema") != "QD_SCANNER_PUBLICATION_V1"
                or packet.get("source_id") != self.producer.enrollment["source_id"]
                or type(packet.get("revision")) is not int
                or packet["revision"] < 1
                or type(packet.get("bundles")) is not list
                or len(packet["bundles"]) > 16
                or type(packet.get("monitors")) is not dict):
            raise ValueError("QD_FORWARD_NATIVE_PUBLICATION_READBACK_UNCERTAIN")
        # The owner/clock remain original after source CAS. No standalone hash
        # may ever count as an independently accepted market/source issuer.
        if self.owner.verify_still_running() is not True:
            raise ValueError("QD_FORWARD_POST_PUBLICATION_ORIGINAL_JOB_UNCERTAIN")
        if (observe_self() != self.owner._identity
                or self.owner._identity.get("pid") != os.getpid()
                or not _installed_qd_source(self.owner)):
            raise ValueError("QD_FORWARD_PUBLISHER_ORIGINAL_PROCESS_LOST")
        self.clock.require_operational(self.runtime_id)
        head = self.producer.archive.current()
        if (head["revision"] != packet["revision"]
                or head["digest"] != digest(packet)
                or self.producer.archive.read(head) != packet):
            raise ValueError("QD_FORWARD_NATIVE_ARCHIVE_ACK_CHANGED")
        self._uncertain = False
        return {
            "schema": SCHEMA,
            "status": "ORIGINAL_NATIVE_SOURCE_CAS_READBACK_ONLY",
            "source_id": packet["source_id"],
            "revision": packet["revision"],
            "packet_sha256": digest(packet),
            "enrollment_sha256": digest(self.producer.enrollment),
            "selected_release_digest": self.owner.release_digest,
            "candidate_bundles": len(packet["bundles"]),
            "native_readback_observed": True,
            "independent_source_issuer_accepted": False,
            "valuation_issuer_accepted": False,
            "financial_inception_authorized": False,
            "paper_startup_authorized": False,
            "live_trading_authorized": False,
        }
