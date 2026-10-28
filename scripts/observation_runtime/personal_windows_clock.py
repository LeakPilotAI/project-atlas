"""Read-only, process-local Windows clock binding for personal PAPER.

No time setting, provider traffic, credentials, durable trust record or service
startup. Operational construction has no injected observation/test port. Local
authentication means a live capability over OS-collected evidence, not signed
UTC or protection against hostile same-user code.
"""

import base64
import ctypes
import json
import os
import re
import secrets
import subprocess
import time
from decimal import ROUND_CEILING, Decimal, InvalidOperation

from app.services.paper_financial_replay import body, strict
from app.services.quality_dips_personal_dependencies import PersonalClockContinuity

MAX_AGE = 120
READ_TTL_NS = 5 * 10**9
DRIFT = Decimal("0.0005")  # Explicit conservative 500ppm local holdover model.


def parse_status(text):
    """Unsupported localization, duplicate fields and incomplete status refuse."""
    if type(text) is not str or len(text) > 32768:
        raise ValueError("CLOCK_STATUS_FORMAT")
    fields = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            if key in fields:
                raise ValueError("CLOCK_DUPLICATE_STATUS_FIELD")
            fields[key] = value.strip()

    def number(key, seconds=False):
        value = fields[key]
        pattern = r"([+-]?\d+(?:\.\d+)?)s" if seconds else r"(\d+)(?:\s*\(.*\))?"
        match = re.fullmatch(pattern, value)
        if not match:
            raise ValueError("CLOCK_STATUS_NUMBER")
        return Decimal(match[1])

    try:
        result = {
            "leap": int(number("Leap Indicator")),
            "stratum": int(number("Stratum")),
            "last_error": int(number("Last Sync Error")),
            "source": fields["Source"],
            "last_sync": fields["Last Successful Sync Time"],
            "age": str(number("Time since Last Good Sync Time", True)),
            "dispersion": str(number("Root Dispersion", True)),
            "delay": str(number("Root Delay", True)),
            "offset": str(number("Phase Offset", True)),
        }
    except (KeyError, InvalidOperation) as exc:
        raise ValueError("CLOCK_STATUS_INCOMPLETE") from exc
    return result


def uncertainty_ms(evidence, *, expected_source, duration_ns, lifetime, observed_utc_ns,
                   wall_qpc_skew_ns):
    """Conservative NTP quality envelope, never an offset-only assertion.

    Root dispersion + half root delay + absolute phase offset + observed local
    wall/QPC skew + 1ms margin + 500ppm*(age+lifetime+collection interval).
    Query runtime ages the quality evidence; it is not itself UTC displacement.
    Values are estimates conditional on the accepted Windows/NTP source and
    oscillator model, not an adversarial or physical accuracy certification.
    """
    required = {"service", "configured_source", "configured_type", "status", "native", "last_sync_utc"}
    if type(evidence) is not dict or set(evidence) != required:
        raise ValueError("CLOCK_EVIDENCE_SCHEMA")
    if (type(expected_source) is not str or not expected_source
            or any(type(evidence[k]) is not str for k in ("service", "configured_source", "configured_type", "status"))):
        raise ValueError("CLOCK_EVIDENCE_FIELD_TYPE")
    if evidence["native"] is not True or evidence["service"] != "Running":
        raise ValueError("CLOCK_SERVICE_OR_PROVENANCE")
    if (evidence["configured_type"] != "NTP"
            or evidence["configured_source"].casefold() != expected_source.casefold()):
        raise ValueError("CLOCK_CONFIGURED_SOURCE_CHANGED")
    s = parse_status(evidence["status"])
    if (s["leap"] != 0 or not 1 <= s["stratum"] <= 15 or s["last_error"] != 0
            or not s["last_sync"] or s["last_sync"].casefold() == "unspecified"):
        raise ValueError("CLOCK_UNSYNCHRONIZED")
    if s["source"].casefold() != expected_source.casefold():
        raise ValueError("CLOCK_EFFECTIVE_SOURCE_CONFLICT")
    age, disp, delay, offset = (Decimal(s[k]) for k in ("age", "dispersion", "delay", "offset"))
    if not all(x.is_finite() for x in (age, disp, delay, offset)):
        raise ValueError("CLOCK_NONFINITE")
    if not 0 <= age <= MAX_AGE or min(disp, delay) < 0:
        raise ValueError("CLOCK_STALE_OR_NEGATIVE_QUALITY")
    if (type(duration_ns) is not int or not 0 <= duration_ns <= 12 * 10**9
            or type(lifetime) is not int or not 1 <= lifetime <= 240
            or type(wall_qpc_skew_ns) is not int or not 0 <= wall_qpc_skew_ns <= 10**7):
        raise ValueError("CLOCK_COLLECTION_OR_VALIDITY")
    if (type(observed_utc_ns) is not int or type(evidence["last_sync_utc"]) is not int
            or evidence["last_sync_utc"] * 10**9 > observed_utc_ns
            or abs(Decimal(observed_utc_ns) / 10**9 - evidence["last_sync_utc"] - age)
            > Decimal(duration_ns) / 10**9 + 2):
        raise ValueError("CLOCK_SYNC_TIMESTAMP_CONFLICT")
    error = (disp + delay / 2 + abs(offset) + Decimal(wall_qpc_skew_ns) / 10**9
             + Decimal("0.001") + DRIFT * (age + lifetime + Decimal(duration_ns) / 10**9))
    bound = int((error * 1000).to_integral_value(rounding=ROUND_CEILING))
    if bound > 1000:
        raise ValueError(f"CLOCK_UNCERTAINTY_EXCEEDED:{bound}ms")
    return bound, s


class _WindowsProbe:
    """Exact system-directory tools; read service/configuration before and after."""

    def __init__(self):
        if os.name != "nt":
            raise ValueError("CLOCK_WINDOWS_REQUIRED")
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.GetCurrentProcess.restype = ctypes.c_void_p
        self.kernel.GetSystemTimePreciseAsFileTime.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
        self.kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
        directory = ctypes.create_unicode_buffer(32768)
        if not self.kernel.GetSystemDirectoryW(directory, len(directory)):
            raise ctypes.WinError(ctypes.get_last_error())
        self.system = directory.value
        self.pid = os.getpid()
        self.created = self.identity()

    def identity(self):
        values = [ctypes.c_ulonglong() for _ in range(4)]
        if not self.kernel.GetProcessTimes(self.kernel.GetCurrentProcess(), *(ctypes.byref(x) for x in values)):
            raise ctypes.WinError(ctypes.get_last_error())
        return f"windows-process:{os.getpid()}:{values[0].value}"

    def wall_ns(self):
        value = ctypes.c_ulonglong()
        self.kernel.GetSystemTimePreciseAsFileTime(ctypes.byref(value))
        return (value.value - 116444736000000000) * 100

    @staticmethod
    def mono():
        # perf_counter uses Windows QPC also on Python3.12, avoiding the
        # coarser tick-count implementation used by older monotonic clocks.
        return time.perf_counter_ns()

    def read(self):
        # Get-AuthenticodeSignature authenticates the observed tool locally;
        # it does not authenticate the remote NTP server or certify its UTC.
        script = r"""
$ErrorActionPreference='Stop'
$exe=Join-Path ([Environment]::SystemDirectory) 'w32tm.exe'
$sig=Get-AuthenticodeSignature -LiteralPath $exe
if($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)'){throw 'CLOCK_WINDOWS_TOOL_SIGNATURE'}
$path='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'
$before=Get-ItemProperty -LiteralPath $path
$serviceBefore=[string](Get-Service W32Time).Status
$status=(& $exe /query /status /verbose 2>&1 | Out-String)
if($LASTEXITCODE -ne 0){throw ('CLOCK_STATUS_QUERY_FAILED:'+ $status)}
$lastSyncUtc=$null
$lastLines=@($status -split "`r?`n" | Where-Object {$_ -match '^Last Successful Sync Time:'})
if($lastLines.Count -ne 1){throw 'CLOCK_SYNC_TIMESTAMP_MISSING'}
$lastText=$lastLines[0].Substring('Last Successful Sync Time:'.Length).Trim()
if($lastText -ne 'unspecified'){
  $last=[datetime]::Parse($lastText,[Globalization.CultureInfo]::CurrentCulture).ToUniversalTime()
  $lastSyncUtc=[long][Math]::Floor(($last.Ticks-621355968000000000)/10000000)
}
$after=Get-ItemProperty -LiteralPath $path
$service=[string](Get-Service W32Time).Status
if($serviceBefore -ne $service -or $before.Type -ne $after.Type -or $before.NtpServer -ne $after.NtpServer){throw 'CLOCK_OBSERVATION_CHANGED'}
@{service=$service;configured_type=$after.Type;configured_source=$after.NtpServer;status=$status;native=$true;last_sync_utc=$lastSyncUtc}|ConvertTo-Json -Compress
"""
        executable = os.path.join(self.system, "WindowsPowerShell", "v1.0", "powershell.exe")
        env = dict(os.environ)
        env["PSModulePath"] = os.path.join(self.system, "WindowsPowerShell", "v1.0", "Modules")
        result = subprocess.run(
            [executable, "-NoProfile", "-NonInteractive", "-EncodedCommand",
             base64.b64encode(script.encode("utf-16le")).decode("ascii")],
            env=env, capture_output=True, timeout=12, creationflags=subprocess.CREATE_NO_WINDOW, check=False,
        )
        if result.returncode or len(result.stdout) > 65536:
            raise ValueError("CLOCK_NATIVE_QUERY_REFUSED:" + result.stderr.decode(errors="replace")[:300])
        return json.loads(result.stdout.decode("utf-8-sig"))


class LocalWindowsClock:
    """Ephemeral runtime-bound capability. No caller-supplied operational evidence."""

    def __init__(self, *, expected_source, runtime_id, lifetime=240):
        self._initialize(_WindowsProbe(), expected_source, runtime_id, lifetime, operational=True)

    def _initialize(self, probe, expected_source, runtime_id, lifetime, *, operational=False):
        if (type(expected_source) is not str or not expected_source
                or type(runtime_id) is not str or not runtime_id or len(runtime_id) > 256):
            raise ValueError("CLOCK_SOURCE_RUNTIME_BINDING_REQUIRED")
        if operational and type(probe) is not _WindowsProbe:
            raise ValueError("CLOCK_SYNTHETIC_OPERATIONAL_SUBSTITUTION")
        self._operational = operational
        self._probe, self._runtime_id = probe, runtime_id
        self._pid, self._identity = os.getpid(), probe.identity()
        # An ephemeral capability tag prevents a declaration collected by a
        # different instance/runtime from authenticating here. Not a UTC key.
        self._process_scope = self._identity + ":" + runtime_id + ":" + secrets.token_hex(16)
        self._expected_source, self._lifetime = expected_source, lifetime
        self._revoked = False
        start, wall = probe.mono(), probe.wall_ns()
        evidence = probe.read()
        end, wall_end = probe.mono(), probe.wall_ns()
        if abs((wall_end - wall) - (end - start)) > 10**7:
            raise ValueError("CLOCK_COLLECTION_DISCONTINUITY")
        bound, status = uncertainty_ms(evidence, expected_source=expected_source,
                                       duration_ns=end-start, lifetime=lifetime, observed_utc_ns=wall_end,
                                       wall_qpc_skew_ns=abs((wall_end-wall)-(end-start)))
        self._last_read, self._evidence = end, strict(body(evidence))
        self._origin_mono, self._origin_wall = end, wall_end
        self._bound = bound
        # Whole UTC seconds encode intervals. Align monotonic origin with the
        # actual OS UTC-second boundary instead of discarding its phase.
        fraction = wall_end % 10**9
        anchor = {"schema": "QD_PERSONAL_UTC_ANCHOR_V1", "utc": wall_end // 10**9,
                  "monotonic_ns": end - fraction, "boot_id": self._process_scope,
                  "source": expected_source, "expires_at": wall_end // 10**9 + lifetime,
                  "uncertainty_ms": bound}
        self._sealed = body(anchor)
        self.continuity = PersonalClockContinuity(
            anchor=anchor, authority=self, monotonic_ns=probe.mono,
            wall_utc=lambda: probe.wall_ns() // 10**9,
            boot_identity=lambda: self._process_scope if probe.identity() == self._identity else "RESTARTED",
        )
        self.evidence = {"schema": "ATLAS_LOCAL_WINDOWS_CLOCK_EVIDENCE_V1",
                         "budget_model": "NTP_QUALITY_WITH_MEASURED_SKEW_AND_QUERY_AGING_V2",
                         "domain": "LOCAL_WINDOWS" if operational else "DISPOSABLE_SYNTHETIC",
                         "runtime_id": runtime_id, "collected_utc_ns": wall_end,
                         "collection_ns": end-start, "valid_until": anchor["expires_at"],
                         "bound_ms": bound, "status": status, "origin": self._identity}

    def require_operational(self, runtime_id):
        if not self._operational or runtime_id != self._runtime_id:
            raise ValueError("CLOCK_OPERATIONAL_RUNTIME_BINDING")
        self.sample()
        return self

    def revoke(self):
        self._revoked = True

    def verify(self, value):
        if type(value) is dict and value.get("schema") == "QD_AUTO_NATIVE_CLOCK_V4":
            return self.continuity.verify(value)
        if (self._revoked or os.getpid() != self._pid or self._probe.identity() != self._identity
                or body(value) != self._sealed):
            return False
        now = self._probe.mono()
        if now < self._last_read:
            return False
        elapsed = now - self._origin_mono
        wall_delta = self._probe.wall_ns() - self._origin_wall
        if abs(wall_delta - elapsed) > Decimal(2_000_000) + Decimal(elapsed) * DRIFT:
            # The existing two-second validator is retained. This acquisition
            # authority also refuses excursions outside its own 500ppm model.
            self._revoked = True
            return False
        if now - self._last_read > READ_TTL_NS:
            start = now
            wall_start = self._probe.wall_ns()
            try:
                evidence = self._probe.read()
                end = self._probe.mono()
                wall_end = self._probe.wall_ns()
                remaining = max(1, self.continuity.anchor["expires_at"] - wall_end // 10**9)
                bound, _ = uncertainty_ms(evidence, expected_source=self._expected_source,
                                           duration_ns=end-start, lifetime=remaining,
                                           observed_utc_ns=wall_end,
                                           wall_qpc_skew_ns=abs((wall_end-wall_start)-(end-start)))
                if bound > self._bound:
                    raise ValueError("CLOCK_BOUND_WORSENED")
                self._last_read, self._evidence = end, strict(body(evidence))
            except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
                self._revoked = True  # No retry/revival of a failed capability.
                return False
        return True

    def sample(self):
        return self.continuity.sample()

    def __call__(self):
        return self.sample()["utc"]

    def runtime_sample(self):
        sample = self.sample()
        return {"schema": "QD_AUTO_CLOCK_V3", "utc": sample["utc"],
                "monotonic_ns": sample["monotonic_ns"], "uncertainty_ms": sample["uncertainty_ms"],
                "source_id": sample["source"]}

    def runtime_clock(self):
        """Existing runtime_dependencies['clock']; engine/native share this source."""
        owner = self

        class RuntimeClock:
            def sample(self):
                return owner.runtime_sample()

            def verify(self, sample):
                return owner.verify_runtime_sample(sample)

            def __call__(self):
                return owner()

        return RuntimeClock()

    def verify_runtime_sample(self, value):
        if type(value) is not dict or set(value) != {"schema", "utc", "monotonic_ns", "uncertainty_ms", "source_id"}:
            return False
        if value["schema"] != "QD_AUTO_CLOCK_V3":
            return False
        return self.verify({"schema": "QD_AUTO_NATIVE_CLOCK_V4", "utc": value["utc"],
                            "monotonic_ns": value["monotonic_ns"], "uncertainty_ms": value["uncertainty_ms"],
                            "source": value["source_id"]})
