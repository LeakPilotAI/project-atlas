import pytest

from scripts.observation_runtime.r7e47ck_equities_budget import (
    EquitiesBudgetRefused,
    EquitiesObservationBudget,
)


def test_default_denied(tmp_path):
    with pytest.raises(EquitiesBudgetRefused):
        EquitiesObservationBudget(tmp_path / "budget.sqlite")


def test_budget_consumed_once(tmp_path):
    budget = EquitiesObservationBudget(
        tmp_path / "budget.sqlite",
        access_approved=True,
        max_attempts=1,
    )

    assert budget.remaining() == 1
    assert budget.consume_before_attempt() == 0

    with pytest.raises(EquitiesBudgetRefused):
        budget.consume_before_attempt()


def test_shared_durable_budget(tmp_path):
    path = tmp_path / "budget.sqlite"

    first = EquitiesObservationBudget(
        path, access_approved=True, max_attempts=2
    )
    second = EquitiesObservationBudget(
        path, access_approved=True, max_attempts=2
    )

    assert first.consume_before_attempt() == 1
    assert second.consume_before_attempt() == 0

    with pytest.raises(EquitiesBudgetRefused):
        first.consume_before_attempt()


def test_configuration_change_refused(tmp_path):
    path = tmp_path / "budget.sqlite"

    EquitiesObservationBudget(
        path, access_approved=True, max_attempts=2
    )

    with pytest.raises(EquitiesBudgetRefused):
        EquitiesObservationBudget(
            path, access_approved=True, max_attempts=3
        )


def test_invalid_limit_refused(tmp_path):
    for limit in (0, -1, True, 1.5):
        with pytest.raises(EquitiesBudgetRefused):
            EquitiesObservationBudget(
                tmp_path / "invalid.sqlite",
                access_approved=True,
                max_attempts=limit,
            )
