"""No-network deterministic checks for Atlas independent dual-NTP clock."""
import copy
import struct

import pytest

from scripts.observation_runtime.atlas_independent_ntp_clock import (
    IndependentNtpClock, MAX_UNCERTAINTY_NS, NTP_EPOCH, PEERS,
    SOURCE, combine_two_peers, parse_ntp_response,
)

BASE_UTC = 1794140000
BASE_MONO = 200_000_000_000


def timestamp(unix_ns):
    sec = unix_ns // 1_000_000_000 + NTP_EPOCH
    frac = ((unix_ns % 1_000_000_000) << 32) // 1_000_000_000
    return struct.pack("!II", sec, frac)


def response(*, nonce=b"abcdefgh", li=0, version=4, mode=4, stratum=2,
             root_delay=655, root_dispersion=655, recv_ns=BASE_UTC*10**9,
             processing_ns=1_000_000):
    packet = bytearray(48)
    packet[0] = li << 6 | version << 3 | mode
    packet[1] = stratum
    packet[4:8] = struct.pack("!i", root_delay)
    packet[8:12] = struct.pack("!I", root_dispersion)
    packet[24:32] = nonce
    packet[32:40] = timestamp(recv_ns)
    packet[40:48] = timestamp(recv_ns + processing_ns)
    return bytes(packet)


def good_samples():
    return [
        {"peer": PEERS[0], "mono_ns": BASE_MONO,
         "utc_ns": BASE_UTC * 10**9, "radius_ns": 20_000_000,
         "rtt_ns": 20_000_000},
        {"peer": PEERS[1], "mono_ns": BASE_MONO + 30_000_000,
         "utc_ns": BASE_UTC*10**9 + 32_000_000, "radius_ns": 20_000_000,
         "rtt_ns": 22_000_000},
    ]


def test_strict_ntp_response_roundtrip_and_era():
    obs = parse_ntp_response(response(), b"abcdefgh", BASE_MONO, BASE_MONO + 10_000_000,
                             peer=PEERS[0])
    assert obs["peer"] == PEERS[0]
    assert obs["rtt_ns"] == 10_000_000
    assert obs["radius_ns"] >= 7_000_000
    assert BASE_UTC*10**9 <= obs["utc_ns"] <= BASE_UTC*10**9 + 1_000_000


@pytest.mark.parametrize("change,reason", [
    ({"nonce": b"wrong123"}, "ORIGINATE_NONCE_MISMATCH"),
    ({"li": 3}, "UNSYNCHRONIZED"),
    ({"mode": 3}, "UNSYNCHRONIZED"),
    ({"version": 3}, "UNSYNCHRONIZED"),
    ({"stratum": 0}, "UNSYNCHRONIZED"),
    ({"stratum": 16}, "UNSYNCHRONIZED"),
    ({"root_delay": -1}, "ROOT_DELAY_REFUSED"),
    ({"root_dispersion": 65536}, "ROOT_DISPERSION_REFUSED"),
    ({"processing_ns": 400_000_000}, "SERVER_PROCESSING_TIME"),
    ({"recv_ns": 1_000_000_000_000}, "UNSUPPORTED_ERA"),
])
def test_corrupt_or_untrustworthy_ntp_response_refused(change, reason):
    packet = response(**change)
    with pytest.raises(ValueError, match=reason):
        parse_ntp_response(packet, b"abcdefgh", BASE_MONO, BASE_MONO + 10_000_000,
                           peer=PEERS[0])


@pytest.mark.parametrize("damage,reason", [
    ("truncated", "FORMAT"), ("oversized", "FORMAT"),
    ("rtt_zero", "ROUND_TRIP"), ("rtt_negative", "ROUND_TRIP"),
    ("rtt_excessive", "ROUND_TRIP"),
])
def test_ntp_transport_bounds_refused(damage, reason):
    packet = response()
    start, end = BASE_MONO, BASE_MONO + 10_000_000
    if damage == "truncated":
        packet = packet[:-1]
    elif damage == "oversized":
        packet += b"extension"
    elif damage == "rtt_zero":
        end = start
    elif damage == "rtt_negative":
        end = start-1
    elif damage == "rtt_excessive":
        end = start+1_000_000_001
    with pytest.raises(ValueError, match=reason):
        parse_ntp_response(packet, b"abcdefgh", start, end, peer=PEERS[0])


def test_dual_peer_agreement_and_conservative_drift():
    rows = good_samples()
    before = copy.deepcopy(rows)
    combined = combine_two_peers(rows)
    assert combined["peer_count"] == 2
    assert combined["peer_difference_ns"] == 2_000_000
    assert combined["uncertainty_ns"] < MAX_UNCERTAINTY_NS
    assert rows == before


@pytest.mark.parametrize("damage,reason", [
    ("missing", "TWO_PEERS_REQUIRED"),
    ("duplicate", "DISTINCT_PINNED"),
    ("fake_peer", "DISTINCT_PINNED"),
    ("disagree", "PEERS_DISAGREE"),
    ("bad_type", "PEER_EVIDENCE_INVALID"),
    ("too_slow", "COLLECTION_TOO_SLOW"),
    ("negative", "PEER_EVIDENCE_INVALID"),
    ("budget", "UNCERTAINTY_EXCEEDED"),
])
def test_two_peer_fail_closed(damage, reason):
    samples = good_samples()
    if damage == "missing":
        samples.pop()
    elif damage == "duplicate":
        samples[1]["peer"] = PEERS[0]
    elif damage == "fake_peer":
        samples[1]["peer"] = "evil.invalid"
    elif damage == "disagree":
        samples[1]["utc_ns"] += 300_000_000
    elif damage == "bad_type":
        samples[1]["mono_ns"] = True
    elif damage == "too_slow":
        samples[1]["mono_ns"] += 11_000_000_000
    elif damage == "negative":
        samples[0]["radius_ns"] = -1
    elif damage == "budget":
        samples[0]["radius_ns"] = 900_000_000
    with pytest.raises(ValueError, match=reason):
        combine_two_peers(samples)


class FakeProbe:
    def __init__(self):
        self.mono_time = BASE_MONO
        self.identity_value = "synthetic:123:created"
        self.reads = 0
        self.utc = BASE_UTC * 10**9
        self.fail = False
        self.mismatch = False

    def mono(self):
        return self.mono_time

    def identity(self):
        return self.identity_value

    def read(self):
        if self.fail:
            raise ValueError("NTP_TEST_NETWORK_UNAVAILABLE")
        self.reads += 1
        seconds = self.utc + self.mono_time - BASE_MONO
        if self.mismatch:
            seconds += 900_000_000
        return {"mono_ns": self.mono_time, "utc_ns": seconds,
                "uncertainty_ns": 150_000_000,
                "peer_difference_ns": 5_000_000, "peer_count": 2}

    def advance(self, seconds):
        self.mono_time += seconds * 10**9


def fixture():
    p = FakeProbe()
    c = IndependentNtpClock.__new__(IndependentNtpClock)
    c._initialize(p, "OFFLINE_NONOPERATIONAL", 240)
    return p, c


def test_synthetic_fixture_never_authorizes_operational_runtime():
    p, c = fixture()
    assert c.evidence["domain"] == "DISPOSABLE_SYNTHETIC"
    with pytest.raises(ValueError, match="OPERATIONAL_RUNTIME_BINDING"):
        c.require_operational("OFFLINE_NONOPERATIONAL")
    with pytest.raises(ValueError, match="SYNTHETIC_OPERATIONAL_SUBSTITUTION"):
        c._initialize(p, "OFFLINE_NONOPERATIONAL", 240, operational=True)


def test_monotonic_utc_sample_and_runtime_contract():
    p, c = fixture()
    a = c.sample()
    assert a["utc"] == BASE_UTC and a["source"] == SOURCE
    assert c.verify(a)
    r = c.runtime_sample()
    assert c.verify_runtime_sample(r)
    assert c.runtime_clock().verify(c.runtime_clock().sample())
    p.advance(4)
    assert c() == BASE_UTC+4
    assert c.verify(a) is False  # cannot replay beyond one second


def test_peer_refresh_makes_continuous_operation_independent_of_os_wall():
    p, c = fixture()
    for i in range(7):
        p.advance(46)
        a = c.sample()
        assert a["utc"] == BASE_UTC + (i+1)*46
    assert p.reads == 8 and c.evidence["os_windows_time_service_required"] is False
    assert not c._revoked


def test_persistently_missing_peer_revokes_without_restart():
    p, c = fixture()
    p.advance(46)
    p.fail = True
    with pytest.raises(ValueError, match="REFRESH_FAILED_CAPABILITY_REVOKED"):
        c.sample()
    p.fail = False
    with pytest.raises(ValueError, match="OWNER_OR_REVOCATION"):
        c.sample()


def test_cross_peer_refresh_disagreement_revokes():
    p, c = fixture()
    p.advance(46)
    p.mismatch = True
    with pytest.raises(ValueError, match="REFRESH_FAILED_CAPABILITY_REVOKED"):
        c.sample()


def test_mono_rollback_identity_reuse_and_process_scope_fail_closed():
    p, c = fixture()
    p.mono_time -= 1
    with pytest.raises(ValueError, match="MONOTONIC_ROLLBACK"):
        c.sample()
    p2, c2 = fixture()
    p2.identity_value = "recycled-process"
    with pytest.raises(ValueError, match="OWNER_OR_REVOCATION"):
        c2.sample()


@pytest.mark.parametrize("corruption", ["utc", "bound", "mono", "source", "schema", "unknown"])
def test_exact_same_process_sample_rejects_mutation(corruption):
    p, c = fixture()
    a = c.sample()
    b = dict(a)
    if corruption == "utc":
        b["utc"] += 1
    elif corruption == "bound":
        b["uncertainty_ms"] += 1
    elif corruption == "mono":
        b["monotonic_ns"] += 100
    elif corruption == "source":
        b["source"] = "ATTACKER"
    elif corruption == "schema":
        b["schema"] = "FALSE_CLOCK"
    elif corruption == "unknown":
        b["extra"] = True
    assert not c.verify(b)


def test_no_authority_to_start_financial_system():
    _, c = fixture()
    assert c.evidence["financial_authority"] is False
    assert c.evidence["source"] == SOURCE
