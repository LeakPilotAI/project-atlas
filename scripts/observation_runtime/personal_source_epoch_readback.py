"""Exact predecessor/successor QD source epoch READBACK, not an epoch issuer.

This is an explicit bridge for the 127-publication native image limit. Each
archive is initialized by its OWN original approved source genesis and writes
through its OWN original native publisher and leases; this module creates no
roots, approvals, source receipts, simulated accounts, trades, or file effects.
Source authorization for *actually switching readers* remains independent.

The old immutable native head must remain readable with its ORIGINAL ACK, and
every successor publication's original native sources must carry exactly
the bound predecessor root/enrollment/head/packet reference. A digest is only
a binding, not independent authenticity of market research, sources or rights.
"""
from __future__ import annotations

from app.services.paper_financial_replay import body, digest, strict

from scripts.observation_runtime.personal_research_archive import (
    NativePersonalResearchArchive,
)

SCHEMA = "QD_ORIGINAL_NATIVE_SOURCE_EPOCH_LINK_V1"
READBACK = "QD_ORIGINAL_NATIVE_SOURCE_EPOCH_READBACK_ONLY_V1"


def _check_ports(old, new):
    if (
        type(old) is not NativePersonalResearchArchive
        or type(new) is not NativePersonalResearchArchive
        or old is new or old.images is new.images
        or old.clock is not new.clock
        or type(old.enrollment) is not dict
        or type(new.enrollment) is not dict
        or old.enrollment["account_id"] != new.enrollment["account_id"]
        or old.enrollment["release_digest"] != new.enrollment["release_digest"]
        or old.enrollment["source_commit"] != new.enrollment["source_commit"]
        or old.enrollment["epoch"] == new.enrollment["epoch"]
        or old.enrollment["source_id"] == new.enrollment["source_id"]
        or old.enrollment["root_id"] == new.enrollment["root_id"]
        or old.images.root_id != old.enrollment["root_id"]
        or new.images.root_id != new.enrollment["root_id"]
    ):
        raise ValueError("QD_EPOCH_DISTINCT_NATIVE_SAME_ACCOUNT_PORTS_REQUIRED")


def _link(old, new, previous_head):
    return strict(body({
        "schema": SCHEMA,
        "account_id": old.enrollment["account_id"],
        "release_digest": old.enrollment["release_digest"],
        "source_commit": old.enrollment["source_commit"],
        "predecessor": {
            "epoch": old.enrollment["epoch"],
            "source_id": old.enrollment["source_id"],
            "root_id": old.enrollment["root_id"],
            "enrollment_digest": digest(old.enrollment),
            "head": previous_head,
        },
        "successor": {
            "epoch": new.enrollment["epoch"],
            "source_id": new.enrollment["source_id"],
            "root_id": new.enrollment["root_id"],
            "enrollment_digest": digest(new.enrollment),
        },
    }))


def propose_link_readonly(*, predecessor, successor):
    """From two original readback-valid heads, propose a nonauthorizing link.

    The previous source must already have an acknowledged publication.
    Successor MUST have only its original immutable empty genesis image.
    This proposal is not itself permission to publish, create or activate.
    """
    _check_ports(predecessor, successor)
    old = predecessor.current()
    new = successor.current()
    if (
        type(old.get("revision")) is not int or old["revision"] < 1
        or type(new.get("revision")) is not int or new["revision"] != 0
        or type(old.get("native_revision")) is not int
        or old["native_revision"] != old["revision"] + 1
        or new.get("native_revision") != 1
    ):
        raise ValueError("QD_EPOCH_HANDOFF_ORIGINAL_FINAL_AND_EMPTY_NEW_REQUIRED")
    precursor = predecessor.read_evidence(old)
    if (
        precursor["packet"]["source_id"] != predecessor.enrollment["source_id"]
        or precursor["packet"]["revision"] != old["revision"]
        or digest(precursor["packet"]) != old["digest"]
        or predecessor.current() != old
        or successor.current() != new
    ):
        raise ValueError("QD_EPOCH_PREDECESSOR_CUSTODY_CHANGED")
    return _link(predecessor, successor, old)


def verify_link_readonly(*, predecessor, successor):
    """Verify both original heads and the link in the CURRENT successor cut.

    Every current successor publication must carry the same immutable
    predecessor link, including after successor revision 1. Underlying native
    replay validates all immutable prior revisions. This is NOT an accepted
    reader switch, research issuer, or financial authority.
    """
    _check_ports(predecessor, successor)
    previous_head = predecessor.current()
    following_head = successor.current()
    if (
        type(previous_head.get("revision")) is not int
        or previous_head["revision"] < 1
        or type(following_head.get("revision")) is not int
        or not 1 <= following_head["revision"] <= 127
        or following_head.get("native_revision") != following_head["revision"] + 1
    ):
        raise ValueError("QD_EPOCH_SUCCESSOR_PUBLISHED_IMAGE_REQUIRED")
    old = predecessor.read_evidence(previous_head)
    new = successor.read_evidence(following_head)
    if (
        old["packet"]["source_id"] != predecessor.enrollment["source_id"]
        or digest(old["packet"]) != previous_head["digest"]
        or old["packet"]["revision"] != previous_head["revision"]
        or new["packet"]["source_id"] != successor.enrollment["source_id"]
        or new["packet"]["revision"] != following_head["revision"]
        or digest(new["packet"]) != following_head["digest"]
        or type(new["sources"]) is not dict
        or new["sources"].get("epoch_link") != _link(
            predecessor, successor, previous_head
        )
        or predecessor.current() != previous_head
        or successor.current() != following_head
    ):
        raise ValueError("QD_EPOCH_ORIGINAL_CHAIN_LINK_MISSING_OR_CHANGED")
    return strict(body({
        "schema": READBACK,
        "predecessor_epoch": predecessor.enrollment["epoch"],
        "successor_epoch": successor.enrollment["epoch"],
        "predecessor_native_revision": previous_head["native_revision"],
        "successor_native_revision": following_head["native_revision"],
        "original_predecessor_ack_readback": True,
        "original_successor_ack_readback": True,
        "root_identities_distinct": True,
        "cross_epoch_link_structurally_verified": True,
        "market_issuer_independently_verified": False,
        "operational_reader_switch_accepted": False,
        "financial_custody_or_accounts_mutated": False,
        "paper_startup_authorized": False,
        "live_trading_authorized": False,
    }))
