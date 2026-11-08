"""Atlas independent two-peer NTP time authority (nonfinancial commissioning stage).

Read-only UDP NTPv4, two pinned hostnames and a Windows QPC/perf_counter
monotonic anchor. No w32tm, OS clock sync, system-time correction or provider
trading request. Neither the NTP protocol nor the host DNS is authenticated:
peer agreement limits accidents but is NOT a cryptographic time certificate.

The operational constructor has no network/test substitution port. Test-only
inert probes use _initialize(operational=False), which cannot grant authority.
"""
import math
import os
import secrets
import socket
import struct
import time
from pathlib import Path

PEERS = ("time.cloudflare.com", "time.google.com")
SOURCE = "ATLAS_NTP_V1:time.cloudflare.com+time.google.com"
NTP_EPOCH = 2208988800
MAX_RTT_NS = 1_000_000_000
MAX_PEER_DIFFERENCE_NS = 250_000_000
MAX_ROOT_DISP_NS = 300_000_000
MAX_PROCESSING_NS = 300_000_000
NTP_REFRESH_NS = 45_000_000_000
DRIFT_PPM = 500
MAX_UNCERTAINTY_NS = 1_000_000_000
# Coarse era sanity check for this release: fails closed at 2036 rollover.
MIN_UNIX_SEC = 1577836800  # 2020-01-01 UTC
MAX_UNIX_SEC = 2085978495  # 2036-02-07 UTC, before NTP era 0 rollover


def _decode_ntp_utc_ns(raw):
    if type(raw) is not bytes or len(raw) != 8 or raw == bytes(8):
        raise ValueError("NTP_TIMESTAMP_MISSING")
    seconds, fraction = struct.unpack("!II", raw)
    unix = seconds - NTP_EPOCH
    if not MIN_UNIX_SEC <= unix <= MAX_UNIX_SEC:
        raise ValueError("NTP_UNSUPPORTED_ERA_OR_TIMESTAMP")
    return unix * 1_000_000_000 + fraction * 1_000_000_000 // (1 << 32)


def parse_ntp_response(packet, nonce, mono_sent, mono_received, *, peer):
    """Strict RFC5905-style public unicast response; fixed safe refusal codes."""
    if peer not in PEERS or type(nonce) is not bytes or len(nonce) != 8:
        raise ValueError("NTP_SOURCE_BINDING")
    if (type(packet) is not bytes or len(packet) != 48
            or type(mono_sent) is not int or type(mono_received) is not int):
        raise ValueError("NTP_RESPONSE_FORMAT")
    duration = mono_received - mono_sent
    if not 0 < duration <= MAX_RTT_NS:
        raise ValueError("NTP_ROUND_TRIP_BOUNDS")
    li, version, mode = packet[0] >> 6, (packet[0] >> 3) & 7, packet[0] & 7
    if li == 3 or version != 4 or mode != 4 or not 1 <= packet[1] <= 15:
        raise ValueError("NTP_SERVER_UNSYNCHRONIZED")
    if packet[24:32] != nonce:
        raise ValueError("NTP_ORIGINATE_NONCE_MISMATCH")
    # Root delay is signed 16.16; root dispersion is unsigned 16.16.
    delay = struct.unpack("!i", packet[4:8])[0]
    dispersion = struct.unpack("!I", packet[8:12])[0]
    if delay < 0 or delay * 1_000_000_000 // 65536 > MAX_RTT_NS:
        raise ValueError("NTP_ROOT_DELAY_REFUSED")
    disp_ns = dispersion * 1_000_000_000 // 65536
    if disp_ns > MAX_ROOT_DISP_NS:
        raise ValueError("NTP_ROOT_DISPERSION_REFUSED")
    recv_ns = _decode_ntp_utc_ns(packet[32:40])
    transmit_ns = _decode_ntp_utc_ns(packet[40:48])
    processing = transmit_ns - recv_ns
    if processing < 0 or processing > MAX_PROCESSING_NS:
        raise ValueError("NTP_SERVER_PROCESSING_TIME")
    if processing > duration + 5_000_000:
        raise ValueError("NTP_SERVER_PROCESSING_EXCEEDS_RTT")
    # Server time at the midpoint of the local monotonic exchange; half
    # observed network duration accounts conservatively for asymmetry.
    radius = (duration + 1) // 2 + disp_ns + max(0, delay) * 1_000_000_000 // (2 * 65536) + 2_000_000
    return {"peer": peer, "mono_ns": (mono_sent + mono_received) // 2,
            "utc_ns": (recv_ns + transmit_ns) // 2,
            "radius_ns": radius, "rtt_ns": duration}


def combine_two_peers(samples, *, lifetime=240):
    """Cross-check independent measurements on one common monotonic instant."""
    if (type(samples) not in (tuple, list) or len(samples) != 2
            or type(lifetime) is not int or not 1 <= lifetime <= 240):
        raise ValueError("NTP_TWO_PEERS_REQUIRED")
    if {s.get("peer") for s in samples if type(s) is dict} != set(PEERS):
        raise ValueError("NTP_TWO_DISTINCT_PINNED_PEERS_REQUIRED")
    if any(type(s) is not dict or set(s) != {"peer", "mono_ns", "utc_ns", "radius_ns", "rtt_ns"}
           or any(type(s[k]) is not int for k in ("mono_ns", "utc_ns", "radius_ns", "rtt_ns"))
           or s["radius_ns"] <= 0 or not 0 < s["rtt_ns"] <= MAX_RTT_NS for s in samples):
        raise ValueError("NTP_PEER_EVIDENCE_INVALID")
    ref = max(s["mono_ns"] for s in samples)
    if ref - min(s["mono_ns"] for s in samples) > 10_000_000_000:
        raise ValueError("NTP_PAIR_COLLECTION_TOO_SLOW")
    utc_estimates = [s["utc_ns"] + ref - s["mono_ns"] for s in samples]
    disagreement = abs(utc_estimates[0] - utc_estimates[1])
    if disagreement > MAX_PEER_DIFFERENCE_NS or disagreement > sum(s["radius_ns"] for s in samples):
        raise ValueError("NTP_PEERS_DISAGREE")
    utc = sum(utc_estimates) // 2
    budget = max(s["radius_ns"] + abs(u - utc) for s, u in zip(samples, utc_estimates))
    budget += (lifetime * 1_000_000_000 * DRIFT_PPM + 999_999) // 1_000_000 + 3_000_000
    if budget > MAX_UNCERTAINTY_NS:
        raise ValueError("NTP_UNCERTAINTY_EXCEEDED")
    if not MIN_UNIX_SEC <= utc // 1_000_000_000 <= MAX_UNIX_SEC:
        raise ValueError("NTP_UTC_OUT_OF_SUPPORTED_ERA")
    return {"mono_ns": ref, "utc_ns": utc, "uncertainty_ns": budget,
            "peer_difference_ns": disagreement, "peer_count": 2}


class _NetworkNtpProbe:
    """Production-only one-shot UDP access; no mutable OS time authority."""

    def __init__(self):
        if os.name != "nt":
            raise ValueError("NTP_OPERATIONAL_WINDOWS_HOST_REQUIRED")
        self.pid = os.getpid()
        # Actual PID plus Windows process creation time pins the capability;
        # no financial/security claim is made against hostile same-user code.
        from scripts.observation_runtime.personal_windows_clock import _WindowsProbe
        self.owner = _WindowsProbe()

    def identity(self):
        return self.owner.identity()

    def mono(self):
        return time.perf_counter_ns()

    def read(self):
        rows = []
        for peer in PEERS:
            nonce = secrets.token_bytes(8)
            request = bytes([0x23]) + bytes(39) + nonce
            try:
                addresses = socket.getaddrinfo(peer, 123, socket.AF_INET, socket.SOCK_DGRAM,
                                                socket.IPPROTO_UDP)
                if not addresses:
                    raise ValueError("NTP_DNS_UNAVAILABLE")
                family, sock_type, proto, _, dest = addresses[0]
                with socket.socket(family, sock_type, proto) as conn:
                    conn.settimeout(2.5)
                    conn.connect(dest)  # restrict incoming packets to selected peer socket
                    start = self.mono()
                    if conn.send(request) != 48:
                        raise ValueError("NTP_SEND_INCOMPLETE")
                    response = conn.recv(512)
                    end = self.mono()
                rows.append(parse_ntp_response(response, nonce, start, end, peer=peer))
            except (socket.timeout, OSError) as exc:
                raise ValueError("NTP_PINNED_PEER_UNREACHABLE") from exc
        return combine_two_peers(rows)


class IndependentNtpClock:
    """Ephemeral independent UTC; no Windows wall-time read in sample/verify.

    Full PAPER commissioning is NOT granted by this standalone clock.
    """

    def __init__(self, *, runtime_id, lifetime=240):
        self._initialize(_NetworkNtpProbe(), runtime_id, lifetime, operational=True)

    def _initialize(self, probe, runtime_id, lifetime, *, operational=False):
        if (type(runtime_id) is not str or not runtime_id or len(runtime_id) > 256
                or type(lifetime) is not int or not 1 <= lifetime <= 240):
            raise ValueError("NTP_RUNTIME_SCOPE_INVALID")
        if operational and type(probe) is not _NetworkNtpProbe:
            raise ValueError("NTP_SYNTHETIC_OPERATIONAL_SUBSTITUTION")
        self._operational = operational
        self._probe, self._runtime_id, self._lifetime = probe, runtime_id, lifetime
        self._identity, self._pid = probe.identity(), os.getpid()
        self._scope = self._identity + ":" + runtime_id + ":" + secrets.token_hex(16)
        self._revoked = False
        self._issued = {}
        initial = probe.read()
        if (type(initial) is not dict or set(initial) != {
            "mono_ns", "utc_ns", "uncertainty_ns", "peer_difference_ns", "peer_count"}
                or initial["peer_count"] != 2 or initial["uncertainty_ns"] > MAX_UNCERTAINTY_NS):
            raise ValueError("NTP_TWO_PEER_INITIAL_PROOF_REQUIRED")
        self._anchor = initial
        self._last_refresh = initial["mono_ns"]
        self._expires = initial["mono_ns"] + lifetime * 1_000_000_000
        self.evidence = {"schema": "ATLAS_INDEPENDENT_TWO_NTP_CLOCK_V1",
                         "domain": "TWO_PUBLIC_UNAUTHENTICATED_NTP_PEERS" if operational else "DISPOSABLE_SYNTHETIC",
                         "source": SOURCE, "runtime_id": runtime_id,
                         "bound_ms": math.ceil(initial["uncertainty_ns"] / 1_000_000),
                         "peer_difference_ms": math.ceil(initial["peer_difference_ns"] / 1_000_000),
                         "os_windows_time_service_required": False,
                         "financial_authority": False}

    def revoke(self):
        self._revoked = True

    def require_operational(self, runtime_id):
        if not self._operational or runtime_id != self._runtime_id:
            raise ValueError("NTP_OPERATIONAL_RUNTIME_BINDING")
        self.sample()
        return self

    def _check(self):
        if self._revoked or os.getpid() != self._pid or self._probe.identity() != self._identity:
            self._revoked = True
            raise ValueError("NTP_CLOCK_OWNER_OR_REVOCATION")
        now = self._probe.mono()
        if (type(now) is not int or now < self._anchor["mono_ns"]
                or now > self._expires):
            self.revoke()
            raise ValueError("NTP_MONOTONIC_ROLLBACK_OR_EXPIRED")
        if now - self._last_refresh >= NTP_REFRESH_NS:
            try:
                refreshed = self._probe.read()
                if (type(refreshed) is not dict or refreshed.get("peer_count") != 2
                        or type(refreshed.get("uncertainty_ns")) is not int
                        or refreshed["uncertainty_ns"] > MAX_UNCERTAINTY_NS):
                    raise ValueError("NTP_REFRESH_EVIDENCE_REFUSED")
                # Must agree with the existing independent monotonic UTC
                # anchor within combined conservative uncertainty intervals.
                predicted = self._anchor["utc_ns"] + refreshed["mono_ns"] - self._anchor["mono_ns"]
                if abs(refreshed["utc_ns"] - predicted) > (
                    refreshed["uncertainty_ns"] + self._anchor["uncertainty_ns"]):
                    raise ValueError("NTP_MONOTONIC_UTC_RECHECK_CONFLICT")
                self._last_refresh = refreshed["mono_ns"]
                # A valid, independently re-observed anchor extends this
                # process for months; no restarting a revoked capability.
                self._anchor = refreshed
                self._expires = refreshed["mono_ns"] + self._lifetime * 1_000_000_000
                self.evidence["bound_ms"] = math.ceil(refreshed["uncertainty_ns"] / 1_000_000)
                self.evidence["peer_difference_ms"] = math.ceil(refreshed["peer_difference_ns"] / 1_000_000)
            except (ValueError, OSError, TypeError):
                self.revoke()
                raise ValueError("NTP_REFRESH_FAILED_CAPABILITY_REVOKED") from None
        return now

    def sample(self):
        now = self._check()
        if now < self._anchor["mono_ns"]:
            # A blocking network refresh can advance the reference instant.
            now = self._probe.mono()
        if now < self._anchor["mono_ns"] or now > self._expires:
            self.revoke()
            raise ValueError("NTP_MONOTONIC_REFRESH_DISCONTINUITY")
        utc_ns = self._anchor["utc_ns"] + now - self._anchor["mono_ns"]
        result = {"schema": "QD_AUTO_NATIVE_CLOCK_V4", "utc": utc_ns // 1_000_000_000,
                  "monotonic_ns": now,
                  "uncertainty_ms": self.evidence["bound_ms"], "source": SOURCE}
        # Exact same-process issuance prevents a caller from fabricating
        # timestamp/uncertainty combinations. Bounded one-second cache.
        self._issued = {k: v for k, v in self._issued.items() if now - k <= 1_000_000_000}
        self._issued[now] = result.copy()
        return result

    def __call__(self):
        return self.sample()["utc"]

    def runtime_sample(self):
        s = self.sample()
        return {"schema": "QD_AUTO_CLOCK_V3", "utc": s["utc"],
                "monotonic_ns": s["monotonic_ns"],
                "uncertainty_ms": s["uncertainty_ms"], "source_id": s["source"]}

    def runtime_clock(self):
        owner = self

        class RuntimeClock:
            def sample(self):
                return owner.runtime_sample()

            def verify(self, value):
                return owner.verify_runtime_sample(value)

            def __call__(self):
                return owner()

        return RuntimeClock()

    def verify(self, value):
        if type(value) is not dict or set(value) != {
            "schema", "utc", "monotonic_ns", "uncertainty_ms", "source"}:
            return False
        try:
            now = self.sample()
        except ValueError:
            return False
        mono = value.get("monotonic_ns")
        return (type(mono) is int
                and 0 <= now["monotonic_ns"] - mono <= 1_000_000_000
                and self._issued.get(mono) == value
                and type(value.get("utc")) is int
                and type(value.get("uncertainty_ms")) is int
                and value["uncertainty_ms"] <= 1000)

    def verify_runtime_sample(self, value):
        if type(value) is not dict or set(value) != {
            "schema", "utc", "monotonic_ns", "uncertainty_ms", "source_id"}:
            return False
        return self.verify({"schema": "QD_AUTO_NATIVE_CLOCK_V4", "utc": value["utc"],
                            "monotonic_ns": value["monotonic_ns"],
                            "uncertainty_ms": value["uncertainty_ms"],
                            "source": value["source_id"]})
