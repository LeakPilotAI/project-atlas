"""Inert two-lane supervision over existing engines; no providers or startup hook.

The injected installation lease authenticates actual lane objects. Portfolio
custody owns durable reservations and cross-process exclusion, not this object's
thread lock. No default custodian, portfolio allocation or trading grant exists.
"""

import asyncio
from threading import Event, Lock

from app.services.paper_financial_replay import body, digest, strict, text
from app.services.paper_portfolio_risk import (
    LANES,
    check_portfolio_cut,
    check_portfolio_reducing_exit,
)


class UnifiedMarketReadCapability:
    """Narrow capability passed to GET: no dispatch/start/stop surface."""

    def __init__(self, runtime):
        if type(runtime) is not UnifiedPaperRuntime:
            raise ValueError("UNIFIED_VERIFIED_RUNTIME_REQUIRED")
        self._read = runtime.read_snapshot

    def read(self):
        return self._read()


class UnifiedControlStopBridge:
    """Existing Control Center stop/loopback transport contract, never startup."""

    def __init__(self, runtime):
        if type(runtime) is not UnifiedPaperRuntime:
            raise ValueError("UNIFIED_ACCEPTED_RUNTIME_REQUIRED")
        self.runtime = runtime
        self.progress = {"schema": "QD_CONTROL_STOP_V1", "phase": "IDLE", "outcome": None}

    def verify_session(self):
        try:
            self.runtime.read_snapshot()
            return True
        except (ValueError, OSError):
            return False

    def request_stop(self, mode):
        if mode not in ("SHUTDOWN_FLATTEN", "EMERGENCY") or not self.verify_session():
            raise ValueError("UNIFIED_CONTROL_SESSION_OR_MODE_UNVERIFIED")
        outcome = self.runtime.stop(emergency=mode == "EMERGENCY")
        complete = outcome["state"] == "STOPPED"
        self.progress = {"schema": "QD_CONTROL_STOP_V1", "phase": "FINISHED", "outcome": {
            "schema": "QD_AUTO_SHUTDOWN_V1", "mode": mode,
            "status": "FLATTENED" if complete else "SHUTDOWN_INCOMPLETE",
            "position_state": "FLAT" if complete else "UNKNOWN" if self.runtime.uncertain else "POSITION_OPEN",
            "lanes": outcome["lanes"], "cash": None, "reason": "SEPARATE_ACKNOWLEDGED_LANE_OUTCOMES_REQUIRED"}}
        return strict(body(self.progress))

    def status(self):
        if not self.verify_session():
            raise ValueError("UNIFIED_CONTROL_SESSION_UNVERIFIED")
        return strict(body(self.progress))


class UnifiedPaperRuntime:
    def __init__(self, *, lanes=None, installation=None, portfolio=None, clock=None):
        if (type(lanes) is not dict or set(lanes) != set(LANES)
                or any(x is None for x in (*lanes.values(), installation, portfolio, clock))):
            raise ValueError("UNIFIED_ACCEPTED_DEPENDENCIES_REQUIRED")
        self.lanes = dict(lanes)
        self.installation, self.portfolio, self.clock = installation, portfolio, clock
        self.grant = None
        self.state = "STOPPED"
        self.gate = Lock()
        self.stop_gate = Lock()
        self.stop_result = None
        self.run_lock = asyncio.Lock()
        self.entry_closed = Event()
        self.observations = dict.fromkeys(LANES)
        self.uncertain = False

    def _lease(self):
        # Reuse installed component-lease semantics, not a caller approval file.
        return self.installation.lease({"schema": "ATLAS_UNIFIED_PAPER_SESSION_V1", "grant": self.grant})

    def _verify(self, lease):
        if (self.grant is None or lease.check_components({"lanes": self.lanes,
                "portfolio": self.portfolio, "clock": self.clock}) is not True
                or lease.check(lease.snapshot) is not True):
            raise ValueError("UNIFIED_SESSION_OR_COMPONENTS_UNVERIFIED")

    def start(self, grant):
        with self.gate:
            if self.state != "STOPPED" or self.grant is not None or self.uncertain:
                raise ValueError("UNIFIED_NEW_SESSION_REQUIRED")
            self.grant = strict(body(grant))
            try:
                with self._lease() as lease:
                    self._verify(lease)
                    if self.portfolio.verify_restart(self.grant) is not True:
                        raise ValueError("UNIFIED_RESTART_UNRESOLVED")
                    self._verify(lease)
                self.state = "RUNNING"
            except BaseException:
                self.grant = None
                raise

    async def poll(self, *, timeout=2):
        """Observe both lanes independently, including when stocks are closed.

        Ports must be cancellation-safe read-only observers. No signal is a
        healthy monitoring result, not a forced-entry trigger. This method never
        invokes financial dispatch, provider start or a legacy mutating GET.
        """
        if type(timeout) not in (int, float) or not 0 < timeout <= 2:
            raise ValueError("UNIFIED_BOUNDED_OBSERVATION_REQUIRED")
        with self._lease() as lease:
            self._verify(lease)
            if self.state not in ("RUNNING", "PAUSED"):
                raise ValueError("UNIFIED_SESSION_NOT_RUNNING")

        async def observe(lane):
            try:
                value = await asyncio.wait_for(self.lanes[lane].observe(), timeout)
                value = strict(body(value))
                if (set(value) != {"lane", "at", "connection", "session", "signal", "source"}
                        or value["lane"] != lane or type(value["at"]) is not int
                        or not 0 <= self.clock() - value["at"] <= 5
                        or value["connection"] not in ("CONNECTED", "DISCONNECTED")
                        or value["session"] not in ("OPEN", "CLOSED", "UNKNOWN")
                        or self.lanes[lane].verify_observation(value) is not True):
                    raise ValueError("UNIFIED_OBSERVATION_UNVERIFIED")
                return value
            except Exception:  # noqa: BLE001 - isolate and redact a failed read-only lane
                return {"lane": lane, "at": self.clock(), "connection": "UNAVAILABLE",
                        "session": "UNKNOWN", "signal": None, "source": None}

        results = await asyncio.gather(*(observe(lane) for lane in LANES))
        with self.gate, self._lease() as lease:
            self._verify(lease)
            if self.state not in ("RUNNING", "PAUSED"):
                raise ValueError("UNIFIED_SESSION_STOPPED_DURING_OBSERVATION")
            self.observations = dict(zip(LANES, results, strict=True))
            return self.snapshot()

    async def run(self, *, seconds, interval=1, stop=None):
        """Bounded continuous supervision; accepted lane strategies own decisions.

        No signals or unknown decisions cause no trade. A failed lane's proposal
        does not stop the other scanner. Financial UNKNOWN closes global admission.
        Expiry ends monitoring in PAUSED; it never silently renews a session.
        """
        if (type(seconds) not in (int, float) or not 0 < seconds <= 86400
                or type(interval) not in (int, float) or not .05 <= interval <= 5
                or self.run_lock.locked()):
            raise ValueError("UNIFIED_BOUNDED_SINGLE_RUN_REQUIRED")
        async with self.run_lock:
            deadline = asyncio.get_running_loop().time() + seconds
            try:
                while (asyncio.get_running_loop().time() < deadline
                       and not (stop and stop.is_set()) and self.state in ("RUNNING", "PAUSED")):
                    await self.poll()
                    for lane in LANES:
                        row = self.observations[lane]
                        planner = getattr(self.lanes[lane], "next_proposal", None)
                        if planner is None or row["connection"] != "CONNECTED" or row["session"] != "OPEN":
                            continue
                        try:
                            proposal = await asyncio.wait_for(planner(row), 2)
                        except Exception:  # noqa: BLE001 - isolate read-only strategy planning; never echo provider errors
                            self.observations[lane] = {**row, "signal": None, "connection": "UNAVAILABLE"}
                            continue
                        if proposal is not None:
                            try:
                                self.dispatch(lane, proposal)
                            except ValueError:
                                if self.uncertain:
                                    break
                    await asyncio.sleep(min(interval, max(0, deadline - asyncio.get_running_loop().time())))
            finally:
                self.pause()  # No automatic resumption after the bounded run ends.
        return self.read_snapshot()

    def dispatch(self, lane, proposal):
        """Serialize source-bound admission and delegate to the existing engine.

        The custody lease MUST durably reserve before dispatch, authenticate the
        projected cut, retain UNKNOWN after an ambiguous effect and authenticate
        replay receipts. These are required installed ports, never fabricated here.
        """
        if lane not in LANES or type(proposal) is not dict:
            raise ValueError("UNIFIED_EXPLICIT_LANE_REQUIRED")
        proposal = strict(body(proposal))
        text(proposal.get("operation_id"))
        if proposal.get("kind") not in ("ENTRY", "EXIT"):
            raise ValueError("UNIFIED_EXPLICIT_OPERATION_REQUIRED")
        with self.gate, self._lease() as installation:
            self._verify(installation)
            if (self.uncertain or self.state not in ("RUNNING", "PAUSED")
                    or (self.state == "PAUSED" or self.entry_closed.is_set()) and proposal["kind"] != "EXIT"):
                raise ValueError("UNIFIED_ADMISSION_CLOSED_OR_UNKNOWN")
            observation = self.observations[lane]
            if (observation is None or observation["connection"] != "CONNECTED"
                    or observation["session"] != "OPEN"
                    or not 0 <= self.clock() - observation["at"] <= 5):
                raise ValueError("UNIFIED_CURRENT_LANE_EVIDENCE_REQUIRED")
            if self.lanes[lane].verify_proposal(proposal, observation) is not True:
                raise ValueError("UNIFIED_STRATEGY_DECISION_UNVERIFIED")
            request = {"lane": lane, "grant": self.grant, "proposal": proposal}
            with self.portfolio.lease(request) as custody:
                # This lease must exclude every competing financial writer.
                if custody.verify(request) is not True:
                    raise ValueError("UNIFIED_PORTFOLIO_CUSTODY_UNVERIFIED")
                if proposal["kind"] == "EXIT":
                    check_portfolio_reducing_exit(custody.policy, custody.before, custody.projected, now=self.clock())
                else:
                    check_portfolio_cut(custody.policy, custody.before, now=self.clock())
                    check_portfolio_cut(custody.policy, custody.projected, now=self.clock())
                self._verify(installation)
                reservation = custody.reserve(request)
                if reservation["state"] == "ACKNOWLEDGED":
                    return custody.replay(request, reservation)
                if reservation["state"] != "RESERVED" or reservation["binding"] != digest(request):
                    self.uncertain, self.state = True, "STOP_INCOMPLETE"
                    raise ValueError("UNIFIED_OPERATION_REPLAY_OR_UNKNOWN")
                # Mark uncertain in memory before even invoking an external writer.
                # Durable reservation remains the restart authority on any crash.
                self.uncertain = True
                try:
                    receipt = self.lanes[lane].dispatch(proposal, reservation)
                    if custody.verify_receipt(request, receipt) is not True:
                        raise ValueError("UNIFIED_UNACKNOWLEDGED_FINANCIAL_EFFECT")
                    self._verify(installation)
                    if custody.acknowledge(request, receipt) is not True:
                        raise ValueError("UNIFIED_ACKNOWLEDGEMENT_UNCERTAIN")
                except BaseException:
                    self.state = "STOP_INCOMPLETE"
                    raise
                self.uncertain = False
                return receipt

    def pause(self):
        with self.gate:
            if self.state == "RUNNING":
                self.state = "PAUSED"

    def stop(self, *, emergency=False):
        self.entry_closed.set()  # Immediate new-entry closure before waiting for an accepted drain.
        with self.stop_gate:
            if self.stop_result is not None:
                return strict(body(self.stop_result))
            result = self._stop(emergency=emergency)
            self.stop_result = strict(body(result))
            return result

    def _stop(self, *, emergency):
        # Close global admission before either lane starts its existing drain.
        with self.gate:
            self.state = "STOPPING"
        with self._lease() as lease:
            self._verify(lease)
        outcomes = {}
        for lane in LANES:
            try:
                outcomes[lane] = self.lanes[lane].stop(emergency=emergency)
            except (ValueError, OSError, TimeoutError):
                outcomes[lane] = {"state": "INCOMPLETE"}
        with self.gate:
            complete = (not self.uncertain and not emergency
                        and all(v.get("state") == "ACKNOWLEDGED_FLAT_AND_DRAINED" for v in outcomes.values()))
            self.state = "STOPPED" if complete else "STOP_INCOMPLETE"
        return {"state": self.state, "lanes": outcomes, "auto_resume": False}

    def snapshot(self):
        return {"schema": "ATLAS_UNIFIED_PAPER_VIEW_V1", "state": self.state,
                "lanes": strict(body(self.observations)), "financial_state": "UNKNOWN" if self.uncertain else "READ_SEPARATE_ACCOUNTS",
                "total_cash": None, "total_equity": None, "startup_authorized": False}

    def read_snapshot(self):
        with self.gate, self._lease() as lease:
            self._verify(lease)
            view = self.snapshot()
            for row in view["lanes"].values():
                if row is not None and not 0 <= self.clock() - row["at"] <= 5:
                    row.update(connection="STALE", signal=None)
            view["observed_at"] = self.clock()
            return view
