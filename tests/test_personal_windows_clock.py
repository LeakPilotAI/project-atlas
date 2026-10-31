"""In-memory Windows clock evidence tests; no service, native child or NTP call."""

import copy
import re

import pytest

from scripts.observation_runtime.personal_windows_clock import (
    LocalWindowsClock,
    parse_status,
    uncertainty_ms,
)

SOURCE = "time.windows.com,0x9"
STATUS = """Leap Indicator: 0(no warning)
Stratum: 5 (secondary reference - syncd by (S)NTP)
Root Delay: 0.0200000s
Root Dispersion: 0.0100000s
Last Successful Sync Time: 10/27/2026 9:06:21 AM
Source: time.windows.com,0x9
Phase Offset: -0.0050000s
Last Sync Error: 0
Time since Last Good Sync Time: 2.0000000s
"""


def evidence():
    return {"service": "Running", "configured_source": SOURCE, "configured_type": "NTP",
            "status": STATUS, "native": True, "last_sync_utc": 1_699_999_998}


class Probe:
    def __init__(self):
        self.ns = 10**12
        self.wall = 1_700_000_000 * 10**9
        self.origin = "SYNTHETIC_PROCESS"
        self.value = evidence()
        self.reads = 0

    def mono(self):
        return self.ns

    def wall_ns(self):
        return self.wall

    def identity(self):
        return self.origin

    def read(self):
        self.reads += 1
        self.ns += 10**6
        self.wall += 10**6
        value = copy.deepcopy(self.value)
        age = self.wall / 10**9 - value["last_sync_utc"]
        value["status"] = re.sub(r"Time since Last Good Sync Time: .*s",
                                 f"Time since Last Good Sync Time: {age:.7f}s", value["status"])
        return value

    def advance(self, seconds):
        self.ns += seconds * 10**9
        self.wall += seconds * 10**9


def fixture():
    probe = Probe()
    clock = LocalWindowsClock.__new__(LocalWindowsClock)
    clock._initialize(probe, SOURCE, "SYNTHETIC_RUNTIME", 60)
    return probe, clock


def test_derived_bound_and_existing_validator_acceptance():
    p, c = fixture()
    # 10ms dispersion +10ms half-delay +5ms phase +1ms margin.
    # 500ppm*(2.001s age+60s lifetime+.001s read) =57.001ms ->58ms.
    assert c.evidence["bound_ms"] == 58
    assert c.evidence["domain"] == "DISPOSABLE_SYNTHETIC"
    assert c.evidence["budget_model"] == "NTP_QUALITY_WITH_MEASURED_SKEW_AND_QUERY_AGING_V2"
    assert c.continuity.sample()["uncertainty_ms"] == 58
    sample = c.sample()
    assert c.verify(sample)
    assert c.verify_runtime_sample(c.runtime_sample())
    runtime = c.runtime_clock()
    assert runtime.verify(runtime.sample()) and runtime() == c()
    assert c() == p.wall // 10**9


@pytest.mark.parametrize("damage", ["unsync", "stratum", "last-error", "missing-sync", "stale",
                                    "delay", "source", "service", "config", "type", "native",
                                    "huge-dispersion", "missing", "duplicate", "local-cmos"])
def test_corrupt_missing_stale_or_unsynchronized_evidence_refuses(damage):
    e = evidence()
    replacements = {
        "unsync": ("0(no warning)", "3(not synchronized)"),
        "stratum": ("Stratum: 5", "Stratum: 0"),
        "last-error": ("Last Sync Error: 0", "Last Sync Error: 1"),
        "missing-sync": ("10/27/2026 9:06:21 AM", "unspecified"),
        "stale": ("2.0000000s", "121.0000000s"),
        "delay": ("0.0200000s", "-0.0200000s"),
        "source": ("Source: time.windows.com,0x9", "Source: foreign.invalid"),
        "huge-dispersion": ("0.0100000s", "7.8018211s"),
        "local-cmos": ("Source: time.windows.com,0x9", "Source: Local CMOS Clock"),
    }
    if damage in replacements:
        e["status"] = e["status"].replace(*replacements[damage])
    elif damage == "service":
        e["service"] = "Stopped"
    elif damage == "config":
        e["configured_source"] = "foreign.invalid,0x9"
    elif damage == "type":
        e["configured_type"] = "NoSync"
    elif damage == "native":
        e["native"] = False
    elif damage == "missing":
        e["status"] = "Source: time.windows.com,0x9"
    elif damage == "duplicate":
        e["status"] += "Root Dispersion: 0.0000000s\n"
    with pytest.raises(ValueError):
        uncertainty_ms(e, expected_source=SOURCE, duration_ns=10**6, lifetime=60, observed_utc_ns=1_700_000_000*10**9, wall_qpc_skew_ns=0)


def test_zero_unset_dispersion_cannot_override_unsync():
    e = evidence()
    e["status"] = e["status"].replace("0(no warning)", "3(not synchronized)").replace("0.0100000s", "0.0000000s")
    with pytest.raises(ValueError, match="UNSYNCHRONIZED"):
        uncertainty_ms(e, expected_source=SOURCE, duration_ns=10**6, lifetime=60, observed_utc_ns=1_700_000_000*10**9, wall_qpc_skew_ns=0)


def test_fixture_can_never_be_admitted_as_operational():
    p, c = fixture()
    with pytest.raises(ValueError, match="OPERATIONAL_RUNTIME_BINDING"):
        c.require_operational("SYNTHETIC_RUNTIME")
    with pytest.raises(ValueError, match="SYNTHETIC_OPERATIONAL_SUBSTITUTION"):
        c._initialize(p, SOURCE, "SYNTHETIC_RUNTIME", 60, operational=True)


@pytest.mark.parametrize("damage", ["boot", "revoke", "wall", "expiry", "mono", "anchor"])
def test_restart_discontinuity_recovery_and_altered_declaration_refuse(damage):
    p, c = fixture()
    if damage == "boot":
        p.origin = "OTHER_SYNTHETIC_PROCESS"
    elif damage == "revoke":
        c.revoke()
    elif damage == "wall":
        p.wall += 3 * 10**9
    elif damage == "expiry":
        p.advance(61)
    elif damage == "mono":
        p.ns -= 10**9
    elif damage == "anchor":
        c.continuity.anchor["uncertainty_ms"] = 0
    with pytest.raises(ValueError):
        c.sample()


def test_fresh_reads_required_and_failed_source_never_auto_recovers():
    p, c = fixture()
    assert p.reads == 1
    p.advance(6)
    assert c.verify(c.sample()) and p.reads == 2
    p.advance(6)
    p.value["service"] = "Stopped"
    with pytest.raises(ValueError):
        c.sample()
    p.value = evidence()
    with pytest.raises(ValueError):
        c.sample()


@pytest.mark.parametrize("elapsed,lifetime", [(12*10**9+1, 60), (-1, 60), (0, 241), (0, True)])
def test_collection_or_validity_over_budget_refuses(elapsed, lifetime):
    with pytest.raises(ValueError):
        uncertainty_ms(evidence(), expected_source=SOURCE, duration_ns=elapsed, lifetime=lifetime, observed_utc_ns=1_700_000_000*10**9, wall_qpc_skew_ns=0)


def test_unknown_localization_refuses_instead_of_guessing():
    with pytest.raises(ValueError, match="INCOMPLETE"):
        parse_status("Quelle: time.windows.com,0x9")


def test_old_or_foreign_protocol_samples_refuse():
    p, c = fixture()
    old = c.sample()
    p.advance(2)
    assert not c.verify(old)
    sample = c.runtime_sample()
    sample["source_id"] = "SYNTHETIC_FOREIGN_SOURCE"
    assert not c.verify_runtime_sample(sample)
    assert not c.verify_runtime_sample({"schema": "QD_AUTO_CLOCK_V3"})


@pytest.mark.parametrize("timestamp", [None, True, 1_600_000_000, 1_700_000_001])
def test_missing_future_or_contradictory_last_sync_timestamp_refuses(timestamp):
    value = evidence()
    value["last_sync_utc"] = timestamp
    with pytest.raises(ValueError, match="SYNC_TIMESTAMP_CONFLICT"):
        uncertainty_ms(value, expected_source=SOURCE, duration_ns=10**6,
                       lifetime=60, observed_utc_ns=1_700_000_000*10**9, wall_qpc_skew_ns=0)


def test_prior_instance_anchor_cannot_be_adopted_after_reconstruction():
    _, first = fixture()
    _, second = fixture()
    assert first.continuity.anchor != second.continuity.anchor
    assert not second.verify(first.continuity.anchor)
    assert first.verify(first.continuity.anchor)


def test_changed_source_on_fresh_observation_revokes_existing_capability():
    probe, clock = fixture()
    probe.value["configured_source"] = "foreign.invalid,0x9"
    probe.advance(6)
    with pytest.raises(ValueError):
        clock.sample()
    probe.value = evidence()
    with pytest.raises(ValueError):
        clock.sample()


def test_oversized_evidence_input_and_missing_native_fields_refuse():
    with pytest.raises(ValueError, match="STATUS_FORMAT"):
        parse_status("x" * 32769)
    value = evidence()
    del value["native"]
    with pytest.raises(ValueError, match="EVIDENCE_SCHEMA"):
        uncertainty_ms(value, expected_source=SOURCE, duration_ns=10**6,
                       lifetime=60, observed_utc_ns=1_700_000_000*10**9, wall_qpc_skew_ns=0)


def test_subsecond_clock_step_invalidates_the_declared_error_model():
    probe, clock = fixture()
    probe.wall += 100_000_000
    with pytest.raises(ValueError):
        clock.sample()
    probe.wall -= 100_000_000
    with pytest.raises(ValueError):
        clock.sample()  # No automatic revival after a discontinuity.


@pytest.mark.parametrize("field", ["service", "configured_source", "configured_type", "status"])
def test_nontext_native_field_refuses_cleanly(field):
    value = evidence()
    value[field] = None
    with pytest.raises(ValueError, match="FIELD_TYPE"):
        uncertainty_ms(value, expected_source=SOURCE, duration_ns=10**6,
                       lifetime=60, observed_utc_ns=1_700_000_000*10**9, wall_qpc_skew_ns=0)


def test_query_latency_ages_evidence_without_becoming_a_false_clock_offset():
    # A1.2second read is not a1.2second clock displacement. All actual clock
    # quality terms and measured3ms local disagreement still count.
    bound, _ = uncertainty_ms(evidence(), expected_source=SOURCE,
                              duration_ns=1_200_000_000, lifetime=60,
                              observed_utc_ns=1_700_000_000*10**9,
                              wall_qpc_skew_ns=3_000_000)
    # 10+10+5+3+1+500ppm*(2+60+1.2)*1000 =60.6ms ->61ms.
    assert bound == 61


@pytest.mark.parametrize("skew", [-1, True, None, 10_000_001])
def test_missing_invalid_or_excessive_wall_qpc_disagreement_refuses(skew):
    with pytest.raises(ValueError, match="COLLECTION_OR_VALIDITY"):
        uncertainty_ms(evidence(), expected_source=SOURCE, duration_ns=10**6,
                       lifetime=60, observed_utc_ns=1_700_000_000*10**9,
                       wall_qpc_skew_ns=skew)


def test_observed_high_windows_dispersion_remains_rejected_after_latency_repair():
    value = evidence()
    value["status"] = value["status"].replace("0.0100000s", "7.9358214s")
    with pytest.raises(ValueError, match="UNCERTAINTY_EXCEEDED"):
        uncertainty_ms(value, expected_source=SOURCE, duration_ns=1_200_000_000,
                       lifetime=60, observed_utc_ns=1_700_000_000*10**9,
                       wall_qpc_skew_ns=0)
