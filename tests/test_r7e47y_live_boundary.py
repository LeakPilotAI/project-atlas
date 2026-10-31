"""R7E47Y offline boundary regression tests."""

from dataclasses import replace

import pytest

from scripts.observation_runtime.r7e47y_live_boundary import (
    LiveBoundaryRefused,
    ObservationPlan,
    execute,
    validate,
)


def test_default_plan_is_offline():
    result = validate(ObservationPlan())
    assert result["network_enabled"] is False
    assert result["execution"] == "REFUSED"
    assert result["max_requests"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"provider": "other"},
        {"endpoint": "https://example.com"},
        {"request_type": "candleSnapshot"},
        {"max_requests": 0},
        {"max_requests": 2},
        {"max_requests": True},
    ],
)
def test_invalid_configuration_refused(changes):
    with pytest.raises(LiveBoundaryRefused):
        validate(replace(ObservationPlan(), **changes))


@pytest.mark.parametrize(
    "plan",
    [
        ObservationPlan(),
        ObservationPlan(rights_approved=True),
        ObservationPlan(budget_approved=True),
        ObservationPlan(
            rights_approved=True,
            budget_approved=True,
        ),
    ],
)
def test_execution_always_refused(plan):
    with pytest.raises(LiveBoundaryRefused):
        execute(plan)


def test_approval_flags_do_not_create_verified_authority():
    result = validate(
        ObservationPlan(
            rights_approved=True,
            budget_approved=True,
        )
    )
    assert result["rights_verified"] is False
    assert result["budget_verified"] is False
    assert result["network_enabled"] is False
