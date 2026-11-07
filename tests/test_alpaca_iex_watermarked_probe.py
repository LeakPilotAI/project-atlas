"""Read-only probe CLI refusal tests; never contact a live provider."""
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.observation_runtime.alpaca_iex_watermarked_probe import bounded_observation
from scripts.observation_runtime.paper_readonly_watermark import advance_watermark, read_watermark


def test_probe_refuses_unenrolled_watermark_before_provider_start(tmp_path, monkeypatch):
    class Credentials:
        @staticmethod
        def load(path):
            return object()
    monkeypatch.setattr("scripts.observation_runtime.alpaca_iex_watermarked_probe.Credentials", Credentials)
    with pytest.raises(ValueError, match="PRIOR_STATE_REQUIRED"):
        bounded_observation(symbol="MSFT", seconds=1, watermark=tmp_path / "missing.json",
                            credentials_path=tmp_path / "credentials",
                            feed_factory=lambda symbols: pytest.fail("feed started without enrollment"))


def test_probe_accepts_only_bounded_explicit_symbols(tmp_path):
    for symbol, seconds in [("msft", 1), ("MSFT;X", 1), ("MSFT", 0), ("MSFT", 61)]:
        with pytest.raises(ValueError, match="ARGUMENTS_REFUSED"):
            bounded_observation(symbol=symbol, seconds=seconds, watermark=tmp_path / "unused",
                                credentials_path=tmp_path / "missing")
