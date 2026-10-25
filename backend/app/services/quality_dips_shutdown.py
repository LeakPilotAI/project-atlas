"""Graceful simulated flatten; no provider default or OS process control."""

from app.services.paper_financial_replay import body, digest, number, strict


def save_outcome(engine, outcome):
    """Append-only coordination evidence, never a replacement financial ledger."""
    with engine.ledger.connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS autonomous_shutdown(id TEXT PRIMARY KEY,body TEXT,digest TEXT)"
        )
        ident = outcome["shutdown_id"] + ":" + digest(outcome)
        row = db.execute(
            "SELECT body,digest FROM autonomous_shutdown WHERE id=?", (ident,)
        ).fetchone()
        if row:
            if row != (body(outcome), digest(outcome)):
                raise ValueError("SHUTDOWN_OUTCOME_CONFLICT")
            return
        db.execute(
            "INSERT INTO autonomous_shutdown VALUES(?,?,?)", (ident, body(outcome), digest(outcome))
        )


def flatten_and_stop(owner, evidence=None, owned_close=None):
    """Owner is the existing admitted V5 runtime. Evidence is a bounded L1 port.

    Missing evidence preserves positions. Closing a process is a separately
    verified injected capability; this module never enumerates/signals processes.
    """
    r, engine = owner.runtime, owner.runtime.engine
    engine.entry_admission_closed = True
    r.stopped.set()  # Stop the candidate feed before requesting shutdown quotes.
    if getattr(owner, "shutdown_result", None) is not None:
        return strict(body(owner.shutdown_result))
    grant = r.grant
    ident = "shutdown:" + digest([engine.ledger.manifest["epoch"], grant])
    result = {
        "schema": "QD_AUTO_SHUTDOWN_V1",
        "shutdown_id": ident,
        "mode": "SHUTDOWN_FLATTEN",
        "status": "SHUTDOWN_INCOMPLETE",
        "position_state": "UNKNOWN",
        "positions": None,
        "cash": None,
        "realized": None,
        "source_revision": None,
        "process_shutdown_allowed": False,
        "reason": None,
    }
    if not r.run_done.wait(2) or not r.gate.acquire(timeout=2):
        engine.dispatch_closed = True
        result["reason"] = "SHUTDOWN_DRAIN_TIMEOUT"
        return result
    try:
        try:
            with owner._action(), r._admission(r._now()):
                snapshot = r.reader.read_committed(
                    engine.ledger.manifest["epoch"], engine.ledger.manifest["epoch"]
                )
                positions = {
                    k: v
                    for k, v in snapshot["state"]["positions"].items()
                    if number(v["remaining"]) > 0
                }
                if len(positions) > 1:
                    raise ValueError("SHUTDOWN_UNEXPECTED_POSITION_COUNT")
                for position_id, position in positions.items():
                    if evidence is None:
                        raise ValueError("SHUTDOWN_PRICE_UNAVAILABLE")
                    request = strict(body(evidence.observe(strict(body(position)), timeout=2)))
                    if set(request) != {"quotes", "observation"}:
                        raise ValueError("SHUTDOWN_EVIDENCE_CONTRACT")
                    operation = ident + ":" + digest([position_id, position["revision"]])
                    filled = engine.step(
                        operation, bundles=[], **request, shutdown_mode="SHUTDOWN_FLATTEN"
                    )
                    if not filled.get("filled"):
                        raise ValueError(filled.get("reason", "SHUTDOWN_EXIT_REFUSED"))
                    r._publish_report(r._now())
                engine.reconcile()
                final = r.reader.read_committed(
                    engine.ledger.manifest["epoch"], engine.ledger.manifest["epoch"]
                )
                remaining = {
                    k: v
                    for k, v in final["state"]["positions"].items()
                    if number(v["remaining"]) > 0
                }
                if remaining:
                    raise ValueError("SHUTDOWN_POSITION_OPEN")
                result.update(
                    position_state="FLAT",
                    positions={},
                    cash=final["state"]["cash"],
                    realized={k: final["state"][k] for k in ("gross", "costs", "net")},
                    source_revision=final["source_revision"],
                )
            if owner.stop() != "STOPPED":
                raise ValueError("SHUTDOWN_WRITER_DRAIN_INCOMPLETE")
            result["status"] = "FLATTENED"
        except (OSError, ValueError, KeyError, TypeError) as error:
            result["reason"] = str(error)[:160]
            # No replay/repair. Attempt only an existing committed read; UNKNOWN
            # stays UNKNOWN if the coordinator/native evidence cannot reconcile.
            try:
                p = r.reader.read_committed(
                    engine.ledger.manifest["epoch"], engine.ledger.manifest["epoch"]
                )
                active = {
                    k: v for k, v in p["state"]["positions"].items() if number(v["remaining"]) > 0
                }
                result.update(
                    position_state="POSITION_OPEN" if active else "FLAT",
                    positions=active,
                    cash=p["state"]["cash"],
                    realized={k: p["state"][k] for k in ("gross", "costs", "net")},
                    source_revision=p["source_revision"],
                )
            except (OSError, ValueError, KeyError, TypeError):
                pass
            r._incomplete()
            owner.failed = True
        finally:
            engine.entry_admission_closed = engine.dispatch_closed = True
        # This is control/ownership evidence only, independent of market prices.
        request = {"enrollment": r.enrollment, "grant": grant}
        try:
            now = r._now()
            with r.ownership.lease(request, now=now) as lease:
                actual = strict(body(lease.snapshot))
                drain = r.ownership.drain(request, now=now)
                r._proof("DRAIN", drain, now)
                if (
                    actual.get("verified") is not True
                    or actual.get("process_identity") != r.enrollment["process_identity"]
                    or actual.get("writer_roster") != r.enrollment["writer_roster"]
                    or body(actual.get("resources")) != body(r.enrollment["reader_enrollment"])
                    or actual.get("unknown_writers") != []
                    or lease.check(actual, now) is not True
                    or type(drain.get("pending")) is not int
                    or drain["pending"] != 0
                    or drain.get("unknown") is not False
                    or drain.get("session_id") != grant["engine_grant"]["session_id"]
                    or drain.get("enrollment_digest") != digest(r.enrollment)
                ):
                    raise ValueError("SHUTDOWN_OWNERSHIP_OR_DRAIN_UNVERIFIED")
                result["process_shutdown_allowed"] = True
        except (OSError, ValueError, KeyError, TypeError):
            result["status"] = "SHUTDOWN_INCOMPLETE"
            result["reason"] = "SHUTDOWN_OWNERSHIP_OR_DRAIN_UNVERIFIED"
        try:
            save_outcome(engine, result)
        except (OSError, ValueError):
            result.update(
                status="SHUTDOWN_INCOMPLETE",
                reason="SHUTDOWN_OUTCOME_PERSISTENCE_FAILED",
                process_shutdown_allowed=False,
            )
        if result["process_shutdown_allowed"] and owned_close is not None:
            try:
                if (
                    owned_close.close_verified(strict(body(r.enrollment["process_identity"])))
                    is not True
                ):
                    raise ValueError("OWNED_CLOSE_UNACKNOWLEDGED")
            except (OSError, ValueError):
                result.update(status="SHUTDOWN_INCOMPLETE", reason="OWNED_PROCESS_CLOSE_FAILED")
                save_outcome(engine, result)
        owner.shutdown_result = strict(body(result))
        return strict(body(result))
    finally:
        r.gate.release()
