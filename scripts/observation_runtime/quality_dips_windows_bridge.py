"""Injected stdio control for an exactly owned local read host; no default CLI."""
from app.services.paper_financial_replay import body, digest, strict


def serve_bridge(host, *, control_authority, clock, reader, writer):
    """A trusted launcher retains this child and all injected dependencies.

    Stdio is control transport, not enrollment authority. Missing/revoked read
    custody prevents OPEN/VERIFY. CLOSE/EOF may only gracefully close the retained
    owned listener even after financial custody expires. Nothing force-kills.
    """
    if control_authority is None or not host.composition.operational:
        raise ValueError("ACCEPTED_OPERATIONAL_BRIDGE_REQUIRED")
    c = host.composition
    context = {"schema": "QD_OP_BRIDGE_CONTEXT_V1", "host_id": c.host_id, "process": c.identity,
               "account_id": c.account, "epoch": c.epoch, "enrollment_digest": digest(c.enrollment)}
    sequence = 0
    try:
        while True:
            line = reader.readline(8193)
            if not line:
                return
            request = None
            try:
                if len(line) > 8192 or not line.endswith("\n"):
                    raise ValueError("BOUNDED_BRIDGE_MESSAGE_REQUIRED")
                request = strict(line)
                if (type(request) is not dict or set(request) != {"schema", "sequence", "host_id", "process", "action", "ready"}
                        or request["schema"] != "QD_OP_BRIDGE_COMMAND_V1"
                        or type(request["sequence"]) is not int or request["sequence"] != sequence + 1
                        or request["host_id"] != c.host_id or request["process"] != c.identity
                        or c.observer() != c.identity or request["action"] not in ("OPEN", "VERIFY", "CLOSE")):
                    raise ValueError("BRIDGE_OWNERSHIP_OR_SEQUENCE_REFUSED")
                action = request["action"]
                if action == "OPEN":
                    if request["ready"] is not None:
                        raise ValueError("OPEN_CONTEXT_REFUSED")
                    with control_authority.lease(strict(body(context)), clock()) as lease:
                        if lease.check(context, clock()) is not True:
                            raise ValueError("BRIDGE_CONTROL_AUTHORITY_REQUIRED")
                        ready = host.open_read_only_session()
                        if lease.check(context, clock()) is not True:
                            raise ValueError("BRIDGE_CONTROL_AUTHORITY_CHANGED")
                elif action == "VERIFY":
                    with control_authority.lease(strict(body(context)), clock()) as lease:
                        if (lease.check(context, clock()) is not True
                                or host.verify_read_only_session(request["ready"]) is not True
                                or lease.check(context, clock()) is not True):
                            raise ValueError("BRIDGE_READINESS_REFUSED")
                    ready = host.ready
                else:
                    if host.close_read_only_session(request["ready"]) is not True:
                        raise ValueError("BRIDGE_EXIT_UNCONFIRMED")
                    ready = None
                sequence += 1
                response = {"schema": "QD_OP_BRIDGE_RESPONSE_V1", "sequence": sequence, "status": "OK", "ready": ready}
            except (ValueError, OSError, TypeError, KeyError, RuntimeError):
                response = {"schema": "QD_OP_BRIDGE_RESPONSE_V1", "sequence": sequence + 1, "status": "REFUSED", "ready": None}
            writer.write(body(response) + "\n")
            writer.flush()
            if response["status"] == "OK" and request["action"] == "CLOSE":
                return
    finally:
        # Exact owned shutdown only; timeout/mismatch remains an error, no kill.
        if host.listener is not None:
            host.close(host.ready)


if __name__ == "__main__":
    raise SystemExit("REFUSED: accepted injected composition and retained child ownership required")
