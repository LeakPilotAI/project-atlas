import json

import pytest

from scripts.observation_runtime.r7e47ch_observation_controller import (
    OfflineObservationController,
    ObservationControllerRefused,
)


def test_live_operation_refused():
    controller = OfflineObservationController()

    with pytest.raises(ObservationControllerRefused):
        controller.observe_live()


def test_non_bytes_refused():
    controller = OfflineObservationController()

    with pytest.raises(ObservationControllerRefused):
        controller.observe("not bytes")


def test_one_attempt_only():
    controller = OfflineObservationController()

    with pytest.raises(Exception):
        controller.observe(b"invalid JSON")

    with pytest.raises(ObservationControllerRefused):
        controller.observe(b"invalid JSON")


def test_parser_receives_offline_fixture(monkeypatch):
    from scripts.observation_runtime import (
        r7e47ch_observation_controller as module
    )

    calls = []

    def fake_parser(raw):
        calls.append(raw)
        return [{"symbol": "BTC", "price": 100.0}]

    monkeypatch.setattr(module, "parse_response", fake_parser)

    controller = OfflineObservationController()
    result = controller.observe(b"offline-fixture")

    assert calls == [b"offline-fixture"]
    assert result.provider == "hyperliquid"
    assert result.source == "CALLER_SUPPLIED_OFFLINE"
    assert result.market_count == 1
    assert result.markets[0]["symbol"] == "BTC"

    with pytest.raises(ObservationControllerRefused):
        controller.observe(b"offline-fixture")
