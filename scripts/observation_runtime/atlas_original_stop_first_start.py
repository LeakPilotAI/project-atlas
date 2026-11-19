"""Original installed PAPER Stop-first startup, one guarded native owner.

This is the missing operational caller for existing account/activation, source,
Stop and unified-runtime components. It grants no source rights, constructs no
accounts, retrieves no credentials, and never sends external venue orders.

Only run INSIDE the currently selected installed native financial worker, after
two original FS1/FS3 accounts, approved sources, separate AUTO_PAPER and
SHUTDOWN_FLATTEN activation, and authentic native Stop custody are already held.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _require_selected_source(release_digest):
    from scripts.observation_runtime.personal_native_financial_release_origin import (
        require_selected_native_origin,
    )
    installed = Path(sys.executable).resolve().parent.parent
    if Path(__file__).resolve() != (
        installed / "scripts/observation_runtime/atlas_original_stop_first_start.py"
    ).resolve():
        raise ValueError("ATLAS_ORIGINAL_START_INSTALLED_NATIVE_SOURCE_REQUIRED")
    require_selected_native_origin(release_digest=release_digest)
    return True


def start_accepted_original_paper_once(
        *, runtime, grant, installation, owner, operator, clock,
        qd_source, hl_source, qd, perp, app, owned_close,
        ledger_path, origin, token, source_lane, qd_instrument=None,
        connection_factory=None):
    """Arm Stop, bind its actual durable owner, then release accepted sources.

    All dependencies are already commissioned original ports. This operation
    does not issue a grant or make an existing financial account. The returned
    pair must remain owned by the same long-lived worker. The worker supervises
    Stop through run_personal_installed_owner_session() before exiting.
    """
    from app.services.personal_paper_runtime import PersonalOperatorInstallation
    from app.services.unified_paper_runtime import UnifiedPaperRuntime
    from app.services.personal_installed_stop_owner import (
        PersonalInstalledPaperStopOwner,
        bind_personal_installed_gui_stop_owner,
    )
    from scripts.observation_runtime.personal_selected_paper_operation_issuer import (
        NativeSelectedPaperOperationIssuer,
    )

    if (type(runtime) is not UnifiedPaperRuntime
            or type(installation) is not PersonalOperatorInstallation
            or runtime.installation is not installation
            or runtime.state != "STOPPED"
            or runtime.grant is not None
            or runtime.uncertain
            or runtime._stop_first_state != "UNUSED"
            or type(grant) is not dict
            or grant.get("test_only") is True
            or grant.get("live_trading_authorized") is True
            or type(grant.get("session_id")) is not str
            or not grant["session_id"]
            or type(owner.release_digest) is not str
            or type(source_lane) is not str
            or source_lane not in ("QUALITY_DIPS", "HYPERLIQUID", "BOTH")
            or (source_lane == "HYPERLIQUID" and qd_instrument is not None)
            or (source_lane in ("QUALITY_DIPS", "BOTH")
                and type(qd_instrument) is not dict)
            or any(value is None for value in (
                app, owned_close, ledger_path, origin, token,
                operator, clock, qd_source, hl_source, qd, perp,
            ))):
        raise ValueError("ATLAS_ORIGINAL_STOP_FIRST_EXACT_PRECOMMISSIONED_INPUTS_REQUIRED")

    # No financial session or entry latch is touched if installed code is not
    # the active native image. Owner/clock/sources are revalidated downstream.
    _require_selected_source(owner.release_digest)

    # No old .start(): the original runtime always closes entries FIRST.
    armed = runtime.arm_stop_first(grant)
    if (type(armed) is not dict
            or armed.get("state") != "PAUSED"
            or armed.get("entry_closed") is not True
            or armed.get("native_stop_binding_required") is not True
            or armed.get("paper_entry_authorized") is not False
            or not runtime.entry_closed.is_set()
            or runtime.state != "PAUSED"):
        runtime.entry_closed.set()
        runtime.uncertain = True
        runtime.state = "STOP_INCOMPLETE"
        raise ValueError("ATLAS_ORIGINAL_STOP_FIRST_ARMING_UNVERIFIED")

    stop_owner = None
    try:
        stop_owner = bind_personal_installed_gui_stop_owner(
            app, runtime=runtime, installation=installation,
            owned_close=owned_close, ledger_path=ledger_path,
            origin=origin, token=token, connection_factory=connection_factory,
        )
        if (type(stop_owner) is not PersonalInstalledPaperStopOwner
                or stop_owner._runtime is not runtime
                or stop_owner.verify_session() is not True):
            raise ValueError("ATLAS_ORIGINAL_DURABLE_STOP_OWNER_NOT_BOUND")
        issuer = NativeSelectedPaperOperationIssuer(
            owner=owner, operator=operator, clock=clock,
            stop_owner=stop_owner, qd_source=qd_source, hl_source=hl_source,
            qd=qd, perp=perp,
        )
        outcome = runtime.resume_stop_first(
            stop_owner=stop_owner, issuer=issuer,
            qd_instrument=qd_instrument, source_lane=source_lane,
        )
        if (type(outcome) is not dict
                or outcome.get("state") != "RUNNING"
                or outcome.get("native_stop_bound") is not True
                or outcome.get("external_live_orders_authorized") is not False
                or runtime.state != "RUNNING"
                or runtime.entry_closed.is_set()
                or stop_owner.verify_session() is not True):
            raise ValueError("ATLAS_ORIGINAL_FINANCIAL_START_NOT_VERIFIED")
        return stop_owner, issuer
    except BaseException:
        # A failed issuer must never make a retryable paper Start. If a durable
        # Stop owner is present, attempt one original SHUTDOWN_FLATTEN, then
        # require its actual persisted FLAT ACK. No optimistic success claim.
        runtime.entry_closed.set()
        if stop_owner is not None:
            try:
                if stop_owner._used:
                    raise ValueError("ATLAS_ORIGINAL_STOP_ALREADY_DISPATCHED_UNKNOWN")
                receipt = stop_owner.request_stop("SHUTDOWN_FLATTEN")
                if stop_owner.verify_durable_stop_receipt(
                        "SHUTDOWN_FLATTEN", receipt) is not True:
                    raise ValueError("ATLAS_ORIGINAL_DURABLE_FLAT_NOT_VERIFIED")
            except BaseException as error:
                runtime.uncertain = True
                runtime.state = "STOP_INCOMPLETE"
                raise ValueError(
                    "ATLAS_ORIGINAL_START_FAILED_STOP_RECONCILIATION_REQUIRED"
                ) from error
        else:
            runtime.uncertain = True
            runtime.state = "STOP_INCOMPLETE"
        raise


async def run_accepted_original_paper_session(
        *, startup, seconds, interval=1, intrahour_flat_before_funding=True):
    """One bounded genuine PAPER run with mandatory verified financial Stop.

    A selected native worker calls this after all external/source/financial
    approvals are installed. The existing original run loop owns its Stop
    signal and hourly funding protection. No auto-start or external orders.
    """
    from app.services.personal_installed_stop_owner import (
        run_personal_installed_owner_session,
    )

    if (type(startup) is not dict or not startup
            or type(seconds) not in (int, float) or not 0 < seconds <= 86400
            or type(interval) not in (int, float) or not 0.05 <= interval <= 5
            or type(intrahour_flat_before_funding) is not bool):
        raise ValueError("ATLAS_ORIGINAL_EXACT_BOUNDED_SESSION_REQUIRED")

    stop_owner, issuer = start_accepted_original_paper_once(**startup)
    try:
        receipt = await run_personal_installed_owner_session(
            owner=stop_owner, seconds=seconds, interval=interval,
            intrahour_flat_before_funding=intrahour_flat_before_funding,
        )
        if (type(receipt) is not dict
                or receipt.get("schema") != "QD_CONTROL_STOP_V1"
                or receipt.get("phase") != "FINISHED"
                or type(receipt.get("outcome")) is not dict
                or receipt["outcome"].get("status") != "FLATTENED"
                or receipt["outcome"].get("position_state") != "FLAT"
                or receipt["outcome"].get("process_shutdown") != "VERIFIED_EXIT"
                or stop_owner.verify_durable_stop_receipt(
                    "SHUTDOWN_FLATTEN", receipt) is not True):
            raise ValueError("ATLAS_ORIGINAL_SESSION_DURABLE_FLAT_REQUIRED")
        return receipt
    except BaseException:
        # An exception after RUNNING may follow a partially committed Stop.
        # There is no automatic retry or optimistic flat/cash accounting.
        stop_owner._runtime.entry_closed.set()
        stop_owner._runtime.uncertain = True
        if stop_owner._runtime.state != "STOPPED":
            stop_owner._runtime.state = "STOP_INCOMPLETE"
        raise
    finally:
        # The financial operation lease must never outlive the bounded run,
        # whether the Stop was acknowledged or the outcome is uncertain.
        issuer.revoke()
