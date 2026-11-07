"""Disposable read-only canonical lane planner adapter contracts; no native startup."""
from types import SimpleNamespace

import pytest

from app.services.paper_financial_replay import ControlCapacityReached, FinancialSourceUncertain
from app.services.unified_native_writer import CanonicalWriterLane


class Archive:
    def __init__(self, remaining):
        self.remaining = remaining

    def remaining_reports(self):
        return self.remaining


class Planner:
    def __init__(self):
        self.calls = []

    async def next_proposal(self, observation, cut):
        self.calls.append((observation, cut))
        return {"operation_id": "synthetic-only", "kind": "ENTRY"}


def lane_fixture(remaining=10, cut=None):
    lane = object.__new__(CanonicalWriterLane)
    planner = Planner()
    lane.writer = SimpleNamespace(_cut=lambda: {"head": "synthetic"} if cut is None else cut)
    lane.reports = SimpleNamespace(archive=Archive(remaining))
    lane.planner = planner
    lane._verify = lambda: None  # only bypass construction in disposable adapter unit test
    return lane, planner


@pytest.mark.asyncio
async def test_canonical_lane_passes_verified_observation_and_current_writer_cut():
    lane, planner = lane_fixture()
    observation = {"lane": "QUALITY_DIPS", "source": "SYNTHETIC"}
    proposal = await lane.next_proposal(observation)
    assert proposal["operation_id"] == "synthetic-only"
    assert planner.calls == [(observation, {"head": "synthetic"})]


@pytest.mark.asyncio
async def test_canonical_lane_refuses_report_reserve_without_planning():
    lane, planner = lane_fixture(remaining=1)
    with pytest.raises(ControlCapacityReached, match="REPORT_CAPACITY"):
        await lane.next_proposal({"lane": "QUALITY_DIPS"})
    assert planner.calls == []


@pytest.mark.asyncio
async def test_canonical_lane_refuses_uncertain_writer_cut_without_planning():
    lane, planner = lane_fixture()
    def failed_cut():
        raise OSError("synthetic source failure")
    lane.writer._cut = failed_cut
    with pytest.raises(FinancialSourceUncertain, match="CURRENT_FINANCIAL_SOURCE"):
        await lane.next_proposal({"lane": "QUALITY_DIPS"})
    assert planner.calls == []