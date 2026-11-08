"""Accepted installed personal PAPER Stop port; does not activate or start a runtime.

This object is in the *financial owner process*. The WinForms desktop process
receives no grant, token, ledger handle or native writer by constructing it.
A future audited process bridge must preserve this boundary.
"""

from app.services.paper_financial_replay import body, strict
from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger
from app.services.personal_paper_runtime import (
    PROFILE, PersonalOperatorInstallation, checked_personal_installation,
    validate_policy,
)
from app.services.unified_paper_runtime import (
    UnifiedControlStopBridge, UnifiedPaperRuntime,
)

LANES = frozenset(("QUALITY_DIPS", "HYPERLIQUID"))


class PersonalInstalledPaperStopOwner:
    """Narrow one-shot projection over a previously enrolled financial owner.

    Takes no paths, credentials, account parameters, source provider or Start
    capability. The exact activated installation must already have supplied a
    true unified runtime and native durable Stop ledger.
    """

    def __init__(self, *, bridge=None, installation=None):
        if (type(bridge) is not UnifiedControlStopBridge
                or type(installation) is not PersonalOperatorInstallation):
            raise ValueError("PERSONAL_INSTALLED_STOP_ACCEPTED_OWNER_REQUIRED")
        runtime = bridge.runtime
        if (type(runtime) is not UnifiedPaperRuntime
                or runtime.installation is not installation
                or runtime.state not in ("RUNNING", "PAUSED")
                or type(runtime.grant) is not dict
                or runtime.grant.get("test_only") is True
                or type(bridge.stop_ledger) is not PaperStopReceiptLedger
                or bridge.owned_close is None
                or bridge.owned_close is not bridge._close_binding
                or set(runtime.lanes) != LANES
                or set(installation.accounts) != LANES
                or bridge.session_id is None):
            raise ValueError("PERSONAL_INSTALLED_STOP_ACCEPTED_OWNER_REQUIRED")
        validate_policy(installation.policy)
        self._bridge = bridge
        self._runtime = runtime
        self._installation = installation
        self._session = bridge.session_id
        self._ledger = bridge.stop_ledger
        self._owner_close = bridge.owned_close
        self._ports = (runtime.lanes, runtime.portfolio, runtime.clock)
        self._used = False
        self._last_result = None
        self._verify_installed_lease()
        if self._ledger.inspect_session(self._session) is not None:
            runtime.entry_closed.set()
            raise ValueError("PERSONAL_INSTALLED_STOP_PRIOR_INTENT_RECONCILIATION_REQUIRED")

    @property
    def session_id(self):
        return self._session

    def _verify_installed_lease(self):
        i, r = self._installation, self._runtime
        if (r.installation is not i
                or self._bridge.runtime is not r
                or self._bridge.stop_ledger is not self._ledger
                or self._bridge.owned_close is not self._owner_close
                or self._bridge.session_id != self._session
                or r.grant.get("session_id") != self._session
                or any(actual is not expected for actual, expected in zip(
                    (r.lanes, r.portfolio, r.clock), self._ports, strict=True))
                or set(i.accounts) != LANES
                or set(r.lanes) != LANES):
            raise ValueError("PERSONAL_INSTALLED_STOP_OWNER_CHANGED")
        request = {"schema": "ATLAS_PERSONAL_UNIFIED_COMPOSITION_V1", "profile": PROFILE}
        with i.lease(request) as lease:
            proof = checked_personal_installation(lease, request)
            ports = {"lanes": r.lanes, "portfolio": r.portfolio, "clock": r.clock}
            if lease.check_components(ports) is not True or lease.check(proof) is not True:
                raise ValueError("PERSONAL_INSTALLED_STOP_OWNER_CHANGED")
        return True

    def verify_session(self):
        try:
            self._verify_installed_lease()
            return self._bridge.verify_session() is True
        except Exception:
            return False

    def request_stop(self, mode):
        if mode != "SHUTDOWN_FLATTEN" or self._used:
            raise ValueError("PERSONAL_INSTALLED_STOP_ONCE_ONLY_NORMAL_MODE")
        if not self.verify_session():
            raise ValueError("PERSONAL_INSTALLED_STOP_OWNER_UNVERIFIED")
        # Latch before dispatch: an exception after entering the real Stop
        # controller cannot authorize a second dispatch or optimistic receipt.
        self._used = True
        result = self._bridge.request_stop(mode)
        self._last_result = strict(body(result))
        return strict(body(self._last_result))

    def verify_durable_stop_receipt(self, mode, receipt):
        if (not self._used or mode != "SHUTDOWN_FLATTEN"
                or type(receipt) is not dict or receipt != self._last_result):
            return False
        try:
            self._verify_installed_lease()
            return self._bridge.verify_durable_stop_receipt(mode, receipt) is True
        except Exception:
            return False


def bind_personal_installed_gui_stop_owner(app, *, runtime, installation, owned_close,
                                            ledger_path, origin, token, connection_factory=None):
    """Opt-in commissioning composition, not a shortcut or Start command.

    Delegates to the *existing* activation-aware unified Stop binder and
    packages its accepted bridge into the narrower installed-owner port.
    No default runtime, account, token, provider, clock or operator authority.
    """
    from app.services.personal_paper_runtime import bind_personal_unified_paper_stop

    bridge = bind_personal_unified_paper_stop(
        app, runtime=runtime, installation=installation, owned_close=owned_close,
        ledger_path=ledger_path, origin=origin, token=token,
        connection_factory=connection_factory,
    )
    return PersonalInstalledPaperStopOwner(bridge=bridge, installation=installation)


def open_personal_installed_python_stop_signal(*, owner, offline_test_id=""):
    """Create the one native per-user event for an already accepted owner.

    The owning financial process must call ``poll(0)`` on its owning thread
    during its existing run loop and ``close()`` during its final teardown.
    Neither this source entry point nor its import starts Atlas, creates a
    background process, grants account rights, or installs desktop shortcuts.
    """
    if type(owner) is not PersonalInstalledPaperStopOwner or owner.verify_session() is not True:
        raise ValueError("PERSONAL_INSTALLED_STOP_ACCEPTED_OWNER_REQUIRED")
    from scripts.observation_runtime.personal_paper_python_stop_signal import (
        InstalledPythonPaperStopSignal,
    )
    return InstalledPythonPaperStopSignal(owner=owner, offline_test_id=offline_test_id)
