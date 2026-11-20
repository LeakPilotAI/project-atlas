"""AIP03 source-only boundary review with real AIP01/02 producer fixtures.

No native filesystem, operational selectors, provider or financial runtime.
"""

import copy
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import digest
from app.services.unified_writer_roster import EXCLUSIONS, ROLES
from test_quality_dips_current_producer import proof
from test_unified_research_sources import pair

from scripts.observation_runtime.continuation_routing import (
    GLOBAL,
    IMAGE_RESOURCES,
    MAX_LOCAL,
    MAX_SEGMENTS,
    RESEARCH,
    RESOURCES,
    ROLE_RESOURCES,
    capacity_review,
    review_disposable_route,
)


def prepared(monkeypatch):
    f = pair(monkeypatch)
    enrollments = {k: s.enrollment for k, s in f.joint.sources.items()}
    before = {
        "schema": "ATLAS_DISPOSABLE_RESOURCE_CUT_V1",
        "execution_domain": "DISPOSABLE",
        "revision": 0,
        "previous": None,
        "resources": {},
        "roles": copy.deepcopy(ROLE_RESOURCES),
        "exclusions": {k: "SYNTHETIC_EXCLUDED:" + k for k in EXCLUSIONS},
        "boundary": {
            "final": True,
            "flat": True,
            "drained": True,
            "resting": False,
            "unknown": False,
        },
    }
    for index, name in enumerate(sorted(RESOURCES), 10):
        lane = (
            "GLOBAL"
            if name in GLOBAL
            else "QUALITY_DIPS"
            if name.startswith("QD_")
            else "HYPERLIQUID"
        )
        root = [10, index, 1]
        records = [digest([name, "synthetic-committed-record", i]) for i in range(4)]
        applied, input_revision = None, None
        state = digest([name, "SYNTHETIC_FINAL_CUT"])
        if name.endswith(("_PROJECTION", "_REPORT")):
            applied = 4
        if name in RESEARCH:
            producer = f.joint.sources[lane]
            head = producer.archive.current()
            evidence = producer.archive.read_evidence(head)
            root = producer.enrollment["root_id"]
            assert head["revision"] == 1
            records = [digest(evidence["packet"])]
            state = digest(evidence)
            input_revision = evidence["sources"]["current_input"]["input"][
                "input_revision"
            ]
        before["resources"][name] = {
            "account": {k: e["account_id"] for k, e in enrollments.items()}
            if lane == "GLOBAL"
            else enrollments[lane]["account_id"],
            "epoch": {k: e["epoch"] for k, e in enrollments.items()}
            if lane == "GLOBAL"
            else enrollments[lane]["epoch"],
            "currency": None
            if lane == "GLOBAL"
            else "USD"
            if lane == "QUALITY_DIPS"
            else "USDC",
            "segments": [
                {
                    "root": root,
                    "index": 0,
                    "base": 0,
                    "local": len(records),
                    "initial_images": 1 if name in IMAGE_RESOURCES else 0,
                    "previous": None,
                }
            ],
            "records": records,
            "state_digest": state,
            "revisions": {
                "logical": len(records),
                "applied_financial": applied,
                "input": input_revision,
            },
        }
    after = copy.deepcopy(before)
    after.update(revision=1, previous=digest(before))
    for index, row in enumerate(after["resources"].values(), 100):
        row["segments"].append(
            {
                "root": [10, index, 2],
                "index": 1,
                "base": row["revisions"]["logical"],
                "local": 0,
                "initial_images": row["segments"][0]["initial_images"],
                "previous": digest(row["segments"]),
            }
        )
    costs = {
        k: {"work": 3, "stop": 8, "entries": 100, "bytes": 1024 * 1024}
        for k in RESOURCES
    }
    accepted = SimpleNamespace(valid=True, mutate=False, domain="DISPOSABLE")

    def verify(context, *, now):
        assert now == f.q.s.now[0]
        if not accepted.valid:
            return False
        receipt = proof(
            "ATLAS_DISPOSABLE_CONTINUATION_REVIEWED_V1",
            context,
            execution_domain=accepted.domain,
        )
        if accepted.mutate:
            context["before"]["resources"]["QD_SOURCE"]["state_digest"] = "0" * 64
        return receipt

    authority = SimpleNamespace(verify_boundary=verify)
    args = {
        "research": f.joint,
        "predecessor": before,
        "successor": after,
        "demand": costs,
        "entries_remaining": 8192,
        "bytes_remaining": 64 * 1024 * 1024,
        "authority": authority,
    }
    return SimpleNamespace(**locals())


def test_exact_role_map_and_current_source_carry_review_is_readonly(monkeypatch):
    s = prepared(monkeypatch)
    files = copy.deepcopy((s.f.q.s.s.files, s.f.h.io.files))
    result = review_disposable_route(**s.args)
    assert len(ROLES) == 15 and len(RESOURCES) == 11 and len(EXCLUSIONS) == 8
    assert ROLE_RESOURCES["QD_DECISION"] == "QD_COORDINATION"
    assert ROLE_RESOURCES["SESSION_RESERVATION"] == "GLOBAL_CUSTODY"
    assert (
        ROLE_RESOURCES["PERP_FUNDING"] == ROLE_RESOURCES["PERP_MARK"] == "PERP_SOURCE"
    )
    assert MAX_LOCAL == 128 and MAX_SEGMENTS == 2
    assert result["predecessor"] == digest(s.before) and result["successor"] == digest(
        s.after
    )
    assert not result["operational_admission"] and not result["selection_performed"]
    assert result == review_disposable_route(**s.args)
    assert (s.f.q.s.s.files, s.f.h.io.files) == files


@pytest.mark.parametrize(
    "damage",
    [
        "domain",
        "missing-role",
        "missing-resource",
        "alias",
        "undeclared-alias",
        "currency",
        "account",
        "global-account",
        "epoch",
        "exclusion",
        "unknown",
        "resting",
        "not-flat",
        "not-drained",
        "not-final",
        "parent",
        "root-reuse",
        "carry",
        "records",
        "duplicate-record",
        "local",
        "base",
        "index",
        "local-bool",
        "logical",
        "source-input",
        "initial-image",
        "source-head",
        "source-record",
        "projection",
        "report",
        "incomplete-segment",
        "third-segment",
        "numeric-boundary",
        "synthetic-aux-alias",
    ],
)
def test_incomplete_or_conflicting_boundary_refuses_without_effect(monkeypatch, damage):
    s = prepared(monkeypatch)
    b, a = s.before, s.after
    row = a["resources"]["QD_SOURCE"]
    if damage == "domain":
        a["execution_domain"] = "OPERATIONAL"
    elif damage == "missing-role":
        del a["roles"]["PERP_MARK"]
    elif damage == "missing-resource":
        del a["resources"]["QD_COORDINATION"]
    elif damage == "alias":
        a["roles"]["QD_PROJECTION"] = "QD_SOURCE"
    elif damage == "undeclared-alias":
        a["resources"]["PERP_SOURCE"]["segments"][-1]["root"] = row["segments"][-1][
            "root"
        ]
    elif damage == "currency":
        row["currency"] = "USDC"
    elif damage == "account":
        row["account"] = "OTHER"
    elif damage == "global-account":
        a["resources"]["GLOBAL_CUSTODY"]["account"] = "NETTED"
    elif damage == "epoch":
        row["epoch"] = "NEW_INCEPTION"
    elif damage == "exclusion":
        del a["exclusions"]["INCEPTION_PUBLISHER"]
    elif damage in ("unknown", "resting"):
        a["boundary"][damage] = True
    elif damage.startswith("not-"):
        a["boundary"][damage[4:]] = False
    elif damage == "parent":
        a["previous"] = "0" * 64
    elif damage == "root-reuse":
        row["segments"][-1]["root"] = row["segments"][0]["root"]
    elif damage == "carry":
        row["state_digest"] = "0" * 64
    elif damage == "records":
        row["records"][0] = "0" * 64
    elif damage == "duplicate-record":
        row["records"][1] = row["records"][0]
    elif damage == "local":
        row["segments"][-1]["local"] = 1
    elif damage == "base":
        row["segments"][-1]["base"] -= 1
    elif damage == "index":
        row["segments"][-1]["index"] = True
    elif damage == "local-bool":
        row["segments"][-1]["local"] = False
    elif damage == "logical":
        row["revisions"]["logical"] = 0
    elif damage == "source-input":
        for cut in (b, a):
            cut["resources"]["QD_RANKING_PUBLICATION"]["revisions"]["input"] = 99
        a["previous"] = digest(b)
    elif damage == "initial-image":
        a["resources"]["QD_RANKING_PUBLICATION"]["segments"][-1]["initial_images"] = 0
    elif damage in ("source-head", "source-record"):
        for cut in (b, a):
            cut["resources"]["QD_RANKING_PUBLICATION"][
                "state_digest" if damage == "source-head" else "records"
            ] = "0" * 64 if damage == "source-head" else ["0" * 64]
        a["previous"] = digest(b)
    elif damage in ("projection", "report"):
        a["resources"]["QD_" + damage.upper()]["revisions"]["applied_financial"] = 3
    elif damage == "incomplete-segment":
        del row["segments"][-1]["previous"]
    elif damage == "numeric-boundary":
        a["boundary"]["flat"] = 1
    elif damage == "synthetic-aux-alias":
        a["roles"]["QD_DECISION"] = "QD_DECISION"
    else:
        row["segments"].append(copy.deepcopy(row["segments"][-1]))
    files = copy.deepcopy((s.f.q.s.s.files, s.f.h.io.files))
    with pytest.raises((ValueError, KeyError, TypeError)):
        review_disposable_route(**s.args)
    assert (s.f.q.s.s.files, s.f.h.io.files) == files


@pytest.mark.parametrize(
    "damage", ["plain-true", "missing", "mutation", "domain", "stale", "changed-source"]
)
def test_review_requires_bound_authority_and_fresh_unchanged_sources(
    monkeypatch, damage
):
    s = prepared(monkeypatch)
    if damage == "plain-true":
        s.authority.verify_boundary = lambda *a, **k: True
    elif damage == "missing":
        s.accepted.valid = False
    elif damage == "mutation":
        s.accepted.mutate = True
    elif damage == "domain":
        s.accepted.domain = "OPERATIONAL"
    elif damage == "stale":
        s.f.q.s.now[0] += 6
    else:
        original = s.authority.verify_boundary

        def changed(context, **kwargs):
            r = original(context, **kwargs)
            s.f.h.cut["input_revision"] += 1
            return r

        s.authority.verify_boundary = changed
    with pytest.raises((ValueError, KeyError, TypeError)):
        review_disposable_route(**s.args)


def test_rollover_preserves_global_source_revisions_and_capacity_reserves(monkeypatch):
    s = prepared(monkeypatch)
    before, after = s.before["resources"], s.after["resources"]
    for name in RESOURCES:
        assert before[name]["revisions"] == after[name]["revisions"]
        assert after[name]["segments"][-1]["local"] == 0
        assert (
            after[name]["segments"][-1]["base"] == before[name]["revisions"]["logical"]
        )
    for name in RESOURCES:
        cut = copy.deepcopy(s.before)
        segment = cut["resources"][name]["segments"][-1]
        segment["local"] = 128 - segment["initial_images"] - 10
        with pytest.raises(ValueError, match="RESERVED_FOR_STOP"):
            capacity_review(
                cut, s.costs, entries_remaining=8192, bytes_remaining=64 * 1024 * 1024
            )
    assert (
        review_disposable_route(**s.args)["capacity"]["after_reserved_stop"][
            "QD_RANKING_PUBLICATION"
        ]
        == 116
    )


@pytest.mark.parametrize(
    "damage",
    [
        "missing-cost",
        "stop-zero",
        "work-bool",
        "negative",
        "undercharged-entries",
        "undercharged-bytes",
        "entry-limit",
        "byte-limit",
    ],
)
def test_complete_stop_and_disk_budget_refusal(monkeypatch, damage):
    s = prepared(monkeypatch)
    row = s.costs["GLOBAL_CUSTODY"]
    if damage == "missing-cost":
        del s.costs["GLOBAL_CUSTODY"]
    elif damage == "stop-zero":
        row["stop"] = 0
    elif damage == "work-bool":
        row["work"] = True
    elif damage == "negative":
        row["work"] = -1
    elif damage == "undercharged-entries":
        row["entries"] = 10
    elif damage == "undercharged-bytes":
        row["bytes"] = 100
    elif damage == "entry-limit":
        s.args["entries_remaining"] = len(RESOURCES) * 100 - 1
    else:
        s.args["bytes_remaining"] = len(RESOURCES) * 1024 * 1024 - 1
    with pytest.raises(ValueError):
        review_disposable_route(**s.args)


def test_exact_capacity_boundary_reserves_every_planned_stop(monkeypatch):
    s = prepared(monkeypatch)
    for name in RESOURCES:
        slots = 127 if name in IMAGE_RESOURCES else 128
        s.costs[name] = {
            "work": slots - 8,
            "stop": 8,
            "entries": 1000,
            "bytes": 4096000,
        }
    s.args.update(entries_remaining=11000, bytes_remaining=11 * 4096000)
    result = review_disposable_route(**s.args)
    assert set(result["capacity"]["after_reserved_stop"].values()) == {0}
    assert result["capacity"]["accounted"] == {"entries": 11000, "bytes": 45056000}
    assert not result["operational_admission"]
