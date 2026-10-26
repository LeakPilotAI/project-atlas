"""Inert two-lane supervision over existing engines; no providers or startup hook.

The injected installation lease authenticates actual lane objects. Portfolio
custody owns durable reservations and cross-process exclusion, not this object's
thread lock. No default custodian, portfolio allocation or trading grant exists.
"""

import asyncio
from threading import Event, Lock

from app.services.paper_financial_replay import (
    ControlCapacityReached,
    FinancialSourceUncertain,
    body,
    digest,
    strict,
    text,
)
from app.services.paper_portfolio_risk import (
    LANES,
    check_portfolio_accounting_update,
    check_portfolio_cut,
    check_portfolio_reducing_exit,
)


class UnifiedMarketReadCapability:
    """Narrow capability passed to GET: no dispatch/start/stop surface."""

    def __init__(self, runtime):
        if type(runtime) is not UnifiedPaperRuntime:
            raise ValueError("UNIFIED_VERIFIED_RUNTIME_REQUIRED")
        self._read = runtime.read_snapshot
        self._runtime = runtime

    def read(self):
        value = self._read()
        from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
        if type(self._runtime.portfolio) is UnifiedPortfolioCustody:
            accounts = self._runtime.portfolio.read_accounts(self._runtime.grant)
            value['accounts'] = accounts
            if accounts['state'] != 'ACKNOWLEDGED': value['financial_state'] = 'UNKNOWN'
        return value


class UnifiedControlStopBridge:
    """Existing Control Center stop/loopback transport contract, never startup."""

    def __init__(self, runtime, *, owned_close=None):
        if type(runtime) is not UnifiedPaperRuntime:
            raise ValueError("UNIFIED_ACCEPTED_RUNTIME_REQUIRED")
        self.runtime = runtime
        self.owned_close = owned_close
        self._close_binding = owned_close
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
        financial_flat = complete = outcome["state"] == "STOPPED"
        process_state = 'NOT_REQUESTED'
        if self.owned_close is not None:
            process_state = 'UNVERIFIED'
            portfolio = self.runtime.portfolio
            verifier = getattr(getattr(portfolio, 'authority', None), 'verify_owned_shutdown', None)
            roster_reader = getattr(getattr(portfolio, 'ownership', None), 'owned_roster', None)
            try:
                if (self.owned_close is not self._close_binding or verifier is None or roster_reader is None
                        or not complete or portfolio.verify_drain(self.runtime.grant) is not True):
                    raise ValueError('UNIFIED_OWNED_CLOSE_DRAIN_REQUIRED')
                with portfolio.lease({'grant': self.runtime.grant}) as admitted:
                    if admitted.owner.check() is not True or portfolio.verify_drain(self.runtime.grant) is not True:
                        raise ValueError('UNIFIED_OWNERSHIP_CHANGED_BEFORE_CLOSE')
                    roster = strict(body(roster_reader(self.runtime.grant, portfolio.writers, self.runtime.clock())))
                    if (type(roster) is not dict or set(roster) != {'schema', 'session_id', 'processes', 'writer_binding', 'account_binding'}
                            or roster['schema'] != 'ATLAS_UNIFIED_OWNED_ROSTER_V1'
                            or roster['session_id'] != self.runtime.grant['session_id']
                            or type(roster['processes']) is not list or not 0 < len(roster['processes']) <= 32
                            or len({p['pid'] for p in roster['processes']}) != len(roster['processes'])
                            or any(set(p) != {'pid', 'created', 'image'} or type(p['pid']) is not int or p['pid'] <= 0
                                   or type(p['created']) is not int or p['created'] <= 0
                                   or type(p['image']) is not str or not p['image'] for p in roster['processes'])
                            or roster['writer_binding'] != portfolio.journal.manifest['roster_digest']
                            or roster['account_binding'] != digest({k: digest(w.manifest) for k,w in portfolio.writers.items()})):
                        raise ValueError('UNIFIED_EXACT_OWNED_ROSTER_REQUIRED')
                    context = {'grant': self.runtime.grant, 'roster': roster, 'outcome': outcome}
                    if verifier(context, self.owned_close, portfolio.components) is not True:
                        raise ValueError('UNIFIED_OWNED_CLOSE_AUTHORITY_REQUIRED')
                    if (self.owned_close.close_verified(strict(body(roster))) is not True
                            or self.owned_close.verify_exit(strict(body(roster))) is not True):
                        raise ValueError('UNIFIED_EXACT_OWNED_EXIT_UNACKNOWLEDGED')
                    process_state = 'VERIFIED_EXIT'
            except (ValueError, OSError, TimeoutError, KeyError, TypeError):
                complete, process_state = False, 'INCOMPLETE'
        self.progress = {"schema": "QD_CONTROL_STOP_V1", "phase": "FINISHED", "outcome": {
            "schema": "QD_AUTO_SHUTDOWN_V1", "mode": mode,
            "status": "FLATTENED" if complete else "SHUTDOWN_INCOMPLETE",
            "position_state": "FLAT" if financial_flat else "UNKNOWN" if self.runtime.uncertain else "POSITION_OPEN",
            "lanes": outcome["lanes"], "cash": None, "process_shutdown": process_state,
            "reason": "SEPARATE_ACKNOWLEDGED_LANE_OUTCOMES_REQUIRED"}}
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
                        except ControlCapacityReached:
                            self.stop()  # Existing bounded flatten/drain; no reset or automatic restart.
                            break
                        except FinancialSourceUncertain:
                            self.entry_closed.set()
                            self.uncertain, self.state = True, 'STOP_INCOMPLETE'
                            break
                        except Exception:  # noqa: BLE001 - isolate read-only strategy planning; never echo provider errors
                            self.observations[lane] = {**row, "signal": None, "connection": "UNAVAILABLE"}
                            continue
                        if proposal is not None:
                            try:
                                if proposal.get('kind') == 'RESTING_ORDER':
                                    self.admit_resting(proposal)
                                elif proposal.get('kind') == 'CANCEL_RESTING_ORDER':
                                    self.cancel_resting(proposal)
                                else:
                                    self.dispatch(lane, proposal)
                            except ControlCapacityReached:
                                self.stop()
                                break
                            except ValueError:
                                if self.uncertain:
                                    break
                    await asyncio.sleep(min(interval, max(0, deadline - asyncio.get_running_loop().time())))
            finally:
                self.pause()  # No automatic resumption after the bounded run ends.
        return self.read_snapshot()

    def dispatch(self, lane, proposal):
        return self._dispatch(lane, proposal, shutdown=False)

    def admit_resting(self, proposal):
        return self._resting(proposal, cancel=False)

    def cancel_resting(self, proposal):
        return self._resting(proposal, cancel=True)

    def _resting(self, proposal, *, cancel):
        """Reserve pending exposure before control publication; never a fill."""
        proposal = strict(body(proposal))
        if proposal.get('kind') != ('CANCEL_RESTING_ORDER' if cancel else 'RESTING_ORDER'):
            raise ValueError('UNIFIED_EXACT_RESTING_ACTION_REQUIRED')
        with self.gate, self._lease() as installation:
            self._verify(installation)
            expired = (cancel and self.state in ('RUNNING', 'PAUSED')
                       and type(proposal.get('order', {}).get('expires_at')) is int
                       and self.clock() >= proposal['order']['expires_at'])
            if (self.uncertain or (cancel and not expired and (self.state != 'STOPPING' or not self.entry_closed.is_set()))
                    or (not cancel and (self.state != 'RUNNING' or self.entry_closed.is_set()))):
                raise ValueError('UNIFIED_RESTING_ADMISSION_CLOSED_OR_UNKNOWN')
            lane = self.lanes['HYPERLIQUID']
            observation = self.observations['HYPERLIQUID']
            if not cancel and (observation is None or observation['connection'] != 'CONNECTED'
                    or observation['session'] != 'OPEN' or not 0 <= self.clock() - observation['at'] <= 5):
                raise ValueError('UNIFIED_RESTING_CURRENT_MARKET_REQUIRED')
            if lane.verify_resting(proposal, observation) is not True:
                raise ValueError('UNIFIED_RESTING_STRATEGY_UNVERIFIED')
            port = getattr(self.portfolio, 'order_lease', None)
            if port is None:
                raise ValueError('UNIFIED_ACCEPTED_PENDING_EXPOSURE_CUSTODY_REQUIRED')
            request = {'lane': 'HYPERLIQUID', 'grant': self.grant, 'proposal': proposal,
                       'mode': 'CANCEL_PENDING_EXPOSURE_V1' if cancel else 'RESERVE_PENDING_EXPOSURE_V1'}
            with port(request) as custody:
                if custody.verify(request) is not True:
                    raise ValueError('UNIFIED_PENDING_EXPOSURE_UNVERIFIED')
                lookup = getattr(custody, 'acknowledged', None)
                prior = lookup(request) if lookup is not None else None
                if prior is not None:
                    if prior.get('state') != 'ACKNOWLEDGED' or prior.get('binding') != digest(request):
                        raise ValueError('UNIFIED_ORDER_REPLAY_UNVERIFIED')
                    receipt = custody.replay(request, prior)
                    if custody.verify_receipt(request, receipt) is not True:
                        raise ValueError('UNIFIED_ORDER_REPLAY_RECEIPT_UNVERIFIED')
                    return receipt
                if cancel:
                    check_portfolio_reducing_exit(custody.policy, custody.before, custody.projected, now=self.clock())
                else:
                    check_portfolio_cut(custody.policy, custody.before, now=self.clock())
                    check_portfolio_cut(custody.policy, custody.projected, now=self.clock())
                reservation = custody.reserve(request)
                if reservation.get('state') != 'RESERVED' or reservation.get('binding') != digest(request):
                    self.uncertain, self.state = True, 'STOP_INCOMPLETE'
                    raise ValueError('UNIFIED_ORDER_RESERVATION_UNKNOWN')
                self.uncertain = True
                try:
                    receipt = lane.dispatch_resting(proposal, reservation)
                    if custody.verify_receipt(request, receipt) is not True:
                        raise ValueError('UNIFIED_ORDER_CONTROL_ACK_UNKNOWN')
                    self._verify(installation)
                    if custody.acknowledge(request, receipt) is not True:
                        raise ValueError('UNIFIED_ORDER_GLOBAL_ACK_UNKNOWN')
                except BaseException:
                    self.state = 'STOP_INCOMPLETE'
                    raise
                self.uncertain = False
                return receipt

    def dispatch_shutdown_exit(self, lane, proposal):
        """Exit-only Stop port; current installation/custody must approve it.

        No caller flag grants authority. The global admission must already be
        closed and custody independently checks this exact reducing transition.
        Ordinary strategy dispatch remains forbidden during STOPPING.
        """
        return self._dispatch(lane, proposal, shutdown=True)

    def _dispatch(self, lane, proposal, *, shutdown):
        """Serialize source-bound admission and delegate to the existing engine.

        The custody lease MUST durably reserve before dispatch, authenticate the
        projected cut, retain UNKNOWN after an ambiguous effect and authenticate
        replay receipts. These are required installed ports, never fabricated here.
        """
        if lane not in LANES or type(proposal) is not dict:
            raise ValueError("UNIFIED_EXPLICIT_LANE_REQUIRED")
        proposal = strict(body(proposal))
        text(proposal.get("operation_id"))
        accounting = proposal.get("kind") in ("FUNDING", "MARK")
        if proposal.get("kind") not in ("ENTRY", "EXIT", "FUNDING", "MARK") or accounting and lane != "HYPERLIQUID":
            raise ValueError("UNIFIED_EXPLICIT_OPERATION_REQUIRED")
        if shutdown and proposal["kind"] != "EXIT":
            raise ValueError("UNIFIED_SHUTDOWN_REDUCING_EXIT_ONLY")
        with self.gate, self._lease() as installation:
            self._verify(installation)
            admitted_state = (self.state == "STOPPING" and self.entry_closed.is_set()) if shutdown else self.state in ("RUNNING", "PAUSED")
            if (self.uncertain or not admitted_state
                    or (self.state == "PAUSED" or self.entry_closed.is_set()) and proposal["kind"] == "ENTRY"):
                raise ValueError("UNIFIED_ADMISSION_CLOSED_OR_UNKNOWN")
            observation = self.observations[lane]
            if not accounting and (observation is None or observation["connection"] != "CONNECTED"
                    or observation["session"] != "OPEN"
                    or not 0 <= self.clock() - observation["at"] <= 5):
                raise ValueError("UNIFIED_CURRENT_LANE_EVIDENCE_REQUIRED")
            if self.lanes[lane].verify_proposal(proposal, observation) is not True:
                raise ValueError("UNIFIED_STRATEGY_DECISION_UNVERIFIED")
            request = {"lane": lane, "grant": self.grant, "proposal": proposal}
            if shutdown:
                request["mode"] = "SHUTDOWN_REDUCING_EXIT_V1"
            with self.portfolio.lease(request) as custody:
                # This lease must exclude every competing financial writer.
                if custody.verify(request) is not True:
                    raise ValueError("UNIFIED_PORTFOLIO_CUSTODY_UNVERIFIED")
                if shutdown:
                    verifier = getattr(custody, "verify_shutdown_exit", None)
                    if verifier is None or verifier(request) is not True:
                        raise ValueError("UNIFIED_SHUTDOWN_CLOSURE_OR_EXIT_UNVERIFIED")
                # Optional read-only lookup is authenticated by this same held
                # custody lease. Already acknowledged effects are not re-admitted
                # as new trades or blocked by subsequently changed market limits.
                lookup = getattr(custody, "acknowledged", None)
                if lookup is not None:
                    previous = lookup(request)
                    if previous is not None:
                        if (previous.get("state") != "ACKNOWLEDGED" or previous.get("binding") != digest(request)):
                            raise ValueError("UNIFIED_REPLAY_BINDING_UNVERIFIED")
                        receipt = custody.replay(request, previous)
                        if custody.verify_receipt(request, receipt) is not True:
                            raise ValueError("UNIFIED_REPLAY_RECEIPT_UNVERIFIED")
                        return receipt
                if accounting:
                    # This must authenticate the actual canonical before/after
                    # transition and source evidence, not caller-supplied cuts.
                    verifier = getattr(custody, "verify_accounting", None)
                    if verifier is None or verifier(request) is not True:
                        raise ValueError("UNIFIED_CANONICAL_ACCOUNTING_UNVERIFIED")
                    check_portfolio_accounting_update(custody.policy, custody.before, custody.projected,
                                                     kind=proposal["kind"], now=self.clock())
                elif proposal["kind"] == "EXIT":
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
        native = any(getattr(lane, "requires_portfolio_drain", False) for lane in self.lanes.values())
        if native:
            close = getattr(self.portfolio, "close_entry_admission", None)
            try:
                closed = close is not None and close(self.grant) is True
            except (ValueError, OSError, TimeoutError):
                closed = False
            if not closed:
                self.uncertain = True
                self.state = "STOP_INCOMPLETE"
                return {"state": self.state, "lanes": {lane: {"state": "ADMISSION_UNVERIFIED"} for lane in LANES}, "auto_resume": False}
        outcomes = {}
        for lane in LANES:
            try:
                outcomes[lane] = self.lanes[lane].stop(emergency=emergency)
            except (ValueError, OSError, TimeoutError, KeyError, TypeError):
                outcomes[lane] = {"state": "INCOMPLETE"}
        drain = getattr(self.portfolio, "verify_drain", None)
        try:
            drained = not native or drain is not None and drain(self.grant) is True
            with self._lease() as lease:
                self._verify(lease)
        except (ValueError, OSError, TimeoutError):
            self.uncertain, drained = True, False
        with self.gate:
            complete = (not self.uncertain and not emergency and drained
                        and all(v.get("state") == "ACKNOWLEDGED_FLAT_AND_DRAINED" for v in outcomes.values()))
            finalize = getattr(self.portfolio, 'finalize_shutdown', None)
            if complete and finalize is not None:
                try:
                    complete = finalize(self.grant, outcomes, self.lanes) is True
                except (ValueError, OSError, TimeoutError):
                    self.uncertain, complete = True, False
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
