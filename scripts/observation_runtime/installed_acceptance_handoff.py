"""Deadline-bound browser-test handoff. Never issues financial/startup authority.

UI signoffs come from the actual browser driver. This module cannot establish
that a browser was inspected, and never manufactures that signoff. Disposable
tickets stay explicitly separate from installed-run tickets.
"""

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

WINDOW_NS = 45 * 10**9
MAX_BYTES = 65536
SIGNOFFS = (
    "ready_image_verified",
    "dashboard_rendered",
    "financial_unavailable",
    "test_tab_closed",
)


def _read(path):
    path = Path(path)
    if path.is_symlink() or path.is_junction():
        raise ValueError("BROWSER_HANDOFF_ALIAS_REFUSED")
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("BROWSER_HANDOFF_CAPACITY")
    return json.loads(data)


def _create(path, value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    if len(data) > MAX_BYTES:
        raise ValueError("BROWSER_HANDOFF_CAPACITY")
    with Path(path).open("xb") as stream:
        stream.write(data)


def validate_ticket(ticket):
    required = {
        "schema",
        "domain",
        "cycle",
        "nonce",
        "ready_ns",
        "deadline_ns",
        "host_id",
        "head",
        "image",
        "release",
        "url",
    }
    if type(ticket) is not dict or set(ticket) != required:
        raise ValueError("BROWSER_TICKET_SCHEMA")
    if (
        ticket["schema"] != "QD_BROWSER_HANDOFF_V3"
        or ticket["domain"] not in ("WINDOWS_LOCAL", "DISPOSABLE")
        or type(ticket["cycle"]) is not int
        or ticket["cycle"] not in (1, 2)
        or any(
            type(ticket[k]) is not int or ticket[k] <= 0
            for k in ("ready_ns", "deadline_ns")
        )
        or ticket["deadline_ns"] - ticket["ready_ns"] != WINDOW_NS
    ):
        raise ValueError("EXACT_BROWSER_45_SECOND_WINDOW_REQUIRED")
    for key, length in (("nonce", 32), ("host_id", 32), ("head", 64)):
        if type(ticket[key]) is not str or not re.fullmatch(
            f"[0-9a-f]{{{length}}}", ticket[key]
        ):
            raise ValueError("BROWSER_TICKET_IDENTITY")
    if any(
        type(ticket[k]) is not str or not ticket[k] for k in ("image", "release", "url")
    ):
        raise ValueError("BROWSER_TICKET_IDENTITY")
    url = urlsplit(ticket["url"])
    if (
        url.scheme != "http"
        or url.hostname != "127.0.0.1"
        or not url.port
        or url.username is not None
        or url.password is not None
        or url.path not in ("", "/")
        or url.query
        or url.fragment
    ):
        raise ValueError("EXACT_BROWSER_LOOPBACK_ORIGIN_REQUIRED")
    if ticket["domain"] == "WINDOWS_LOCAL" and (
        ticket["release"] != "2c039af29dfefd1df77e0caa3db3fdf5ed188118"
        or Path(ticket["image"])
        != Path(
            r"D:\AtlasRuntime\releases\2c039af29dfefd1df77e0caa3db3fdf5ed188118\python\python.exe"
        )
    ):
        raise ValueError("INSTALLED_BROWSER_BINDING_REQUIRED")
    return ticket


def submit_browser_ack(root, ticket, signoffs, *, monotonic_ns=time.perf_counter_ns):
    """Publish ONLY after genuine checks/tab close, BEFORE optional diagnostics.

    The consumer's own receipt time decides timeliness. A producer timestamp
    cannot turn an acknowledgement received after the deadline into a pass.
    No-replace publication avoids partial JSON reads and concurrent overwrite.
    This is test coordination, not native financial publication or its codec.
    """
    validate_ticket(ticket)
    if (
        type(signoffs) is not dict
        or set(signoffs) != set(SIGNOFFS)
        or any(signoffs[k] is not True for k in SIGNOFFS)
    ):
        raise ValueError("GENUINE_BROWSER_SIGNOFFS_REQUIRED")
    now = monotonic_ns()
    if not ticket["ready_ns"] <= now <= ticket["deadline_ns"]:
        raise ValueError("BROWSER_ACK_LATE")
    root = Path(root)
    recorded = _read(root / f"cycle-{ticket['cycle']}-browser-request.json")
    if recorded != ticket:
        raise ValueError("BROWSER_REQUEST_SUBSTITUTION")
    packet = {
        "schema": "QD_BROWSER_ACK_V3",
        "ticket": ticket,
        "observed_ns": now,
        "signoffs": signoffs,
    }
    pending = (
        root / f"cycle-{ticket['cycle']}-browser-ack-{secrets.token_hex(8)}.pending"
    )
    _create(pending, packet)
    # Validate again after file I/O and before publication. No late pre-ack.
    if not now <= monotonic_ns() <= ticket["deadline_ns"]:
        raise ValueError("BROWSER_ACK_LATE_BEFORE_PUBLICATION")
    target = root / f"cycle-{ticket['cycle']}-browser-ack.json"
    if os.name == "nt":
        # Windows rename is atomic and refuses an existing target. No extra
        # hardlink privilege or ACL changes are needed for test coordination.
        os.rename(pending, target)
    else:
        os.link(pending, target)  # POSIX rename would overwrite the target.
    return packet


class BrowserWindow:
    """One READY-bound window; timeout/refusal latches and never auto-resumes."""

    def __init__(
        self,
        *,
        root,
        cycle,
        ready,
        expected,
        ready_ns,
        domain,
        monotonic_ns=time.perf_counter_ns,
    ):
        if (
            type(ready) is not dict
            or type(expected) is not dict
            or set(expected) != {"release", "head", "image"}
            or any(ready.get(k) != expected[k] for k in ("release", "head"))
            or Path(ready.get("image", "")) != Path(expected["image"])
            or ready.get("mode")
            != (
                "INSTALLED_NONFINANCIAL_ONLY"
                if domain == "WINDOWS_LOCAL"
                else "DISPOSABLE_CONTROL_FIXTURE"
            )
            or any(
                ready.get(k) is not False
                for k in (
                    "providers",
                    "financial_writers",
                    "trading",
                    "automatic_startup",
                )
            )
        ):
            raise ValueError("VERIFIED_NONFINANCIAL_READY_REQUIRED")
        self.root, self.clock = Path(root), monotonic_ns
        self.owner = os.getpid(), threading.get_ident()
        self.refused, self.receipt = False, None
        self.ticket = validate_ticket(
            {
                "schema": "QD_BROWSER_HANDOFF_V3",
                "domain": domain,
                "cycle": cycle,
                "nonce": secrets.token_hex(16),
                "ready_ns": ready_ns,
                "deadline_ns": ready_ns + WINDOW_NS,
                "host_id": ready["host_id"],
                "head": ready["head"],
                "release": ready["release"],
                "image": ready["image"],
                "url": ready["url"],
            }
        )
        if not ready_ns <= self.clock() <= self.ticket["deadline_ns"]:
            raise ValueError("BROWSER_READY_WINDOW_ALREADY_EXPIRED")
        _create(self.root / f"cycle-{cycle}-browser-request.json", self.ticket)

    def receive(self):
        if self.owner != (os.getpid(), threading.get_ident()):
            raise ValueError("EXACT_BROWSER_RECEIVER_OWNER_REQUIRED")
        if self.refused:
            raise ValueError("BROWSER_WINDOW_REFUSAL_LATCHED")
        if self.receipt is not None:
            return self.receipt
        try:
            packet = _read(self.root / f"cycle-{self.ticket['cycle']}-browser-ack.json")
        except FileNotFoundError:
            now = self.clock()
            if now < self.ticket["ready_ns"]:
                self.refused = True
                raise ValueError("BROWSER_ACK_CLOCK_REVERSED") from None
            if now > self.ticket["deadline_ns"]:
                self.refused = True
                raise ValueError("BROWSER_ACK_MISSING_AT_DEADLINE") from None
            return None
        except (ValueError, OSError):
            self.refused = True
            raise
        # Capture complete receipt immediately. No reports/HTTP/audits intervene.
        received_ns = self.clock()
        try:
            if not self.ticket["ready_ns"] <= received_ns <= self.ticket["deadline_ns"]:
                raise ValueError("BROWSER_ACK_RECEIVED_LATE")
            if (
                type(packet) is not dict
                or set(packet) != {"schema", "ticket", "observed_ns", "signoffs"}
                or packet["schema"] != "QD_BROWSER_ACK_V3"
                or packet["ticket"] != self.ticket
                or type(packet["observed_ns"]) is not int
                or not self.ticket["ready_ns"] <= packet["observed_ns"] <= received_ns
                or type(packet["signoffs"]) is not dict
                or set(packet["signoffs"]) != set(SIGNOFFS)
                or any(packet["signoffs"][k] is not True for k in SIGNOFFS)
            ):
                raise ValueError("BROWSER_ACK_IDENTITY_OR_WITNESS_REFUSED")
            receipt = {
                "accepted": True,
                "received_ns": received_ns,
                "packet": packet,
            }
            # Persist the actual receiver timestamp before unrelated work so a
            # later HTTP/Stop failure cannot erase a timely browser observation.
            _create(
                self.root / f"cycle-{self.ticket['cycle']}-browser-receipt.json",
                receipt,
            )
            self.receipt = receipt
            return self.receipt
        except (ValueError, OSError, KeyError, TypeError):
            self.refused = True
            raise

    def wait(self, *, sleep=time.sleep):
        while True:
            receipt = self.receive()
            if receipt is not None:
                return receipt
            sleep(0.01)
