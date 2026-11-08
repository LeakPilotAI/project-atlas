"""One native aggregate envelope above the existing per-launch Jobs.

Explicit initialization is for a future dedicated disposable controller only.
It changes no service or persistent Windows setting. There is no PID-open,
breakaway, process adoption, budget reset or termination of the root controller.
Job user-time limits are NOT described as kernel+user CPU enforcement: total
CPU is independently queried, cumulative, and checked at each guarded boundary.
"""

import copy

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_harness import LIMITS, need


class AggregateJobBudget:
    def __init__(self, *, calls, resources, allocations, clock_ns):
        self.calls, self.resources, self.allocations, self.clock = (
            calls,
            resources,
            allocations,
            clock_ns,
        )
        self.job = self.controller_handle = None
        self.controller = None
        self.held, self.rows, self.finished = [], {}, set()
        self.last_cpu = 0
        self.last_parent_cpu = 0
        self.last_job_cpu = 0
        self.failed = False
        self.closed_keys = set()
        self.generation = 0
        self.native_cpu_history = {}
        self.dormant = False
        self.closed_at = None
        self.limits = {
            "processes": LIMITS["processes"],
            "private_bytes": LIMITS["private_bytes"],
            "child_private_bytes": LIMITS["private_bytes"],
            "cpu_ns": LIMITS["cpu_ns"],
            # A root containing the controller cannot kill that controller just
            # because its local handle is closed. Leaf Jobs retain kill-on-close.
            "kill_on_close": False,
        }

    def initialize(self):
        need(self.job is None and not self.failed, "ONE_AGGREGATE_JOB")
        self.failed = True
        owner = self.resources.state["controller"]
        self.controller = copy.deepcopy(self.resources.state["owners"][owner])
        ticket = self.allocations.reserve("aggregate-controller-original", "handle")
        self.controller_handle = self.calls.duplicate(
            self.calls.current(), self.calls.current()
        )
        self.held.append((ticket, self.controller_handle))
        actual = self.calls.native(self.controller_handle)
        need(
            all(actual[k] == self.controller[k] for k in ("pid", "created", "image")),
            "AGGREGATE_ORIGINAL_CONTROLLER_CHANGED",
        )
        ticket = self.allocations.reserve("aggregate-root", "job")
        self.job = self.calls.create_job(
            "Local\\Atlas-AIP06-Aggregate-" + digest(self.controller)[:32] + f'-{self.generation:02d}', self.limits
        )
        self.held.append((ticket, self.job))
        need(
            self.calls.job_limits(self.job) == self.limits
            and self.calls.members(self.job) == set(),
            "AGGREGATE_NEW_EMPTY_FINITE_JOB",
        )
        self.calls.assign(self.job, self.controller_handle)
        need(
            self.calls.in_job(self.controller_handle, self.job)
            and self.calls.members(self.job) == {actual["pid"]},
            "AGGREGATE_CONTROLLER_ASSIGNMENT",
        )
        self.failed = False
        return self.observe()

    def attach_created(self, *, handle, job, native):
        """Called while the original child is suspended, before leaf assignment."""
        need(
            not self.failed and self.job is not None,
            "AGGREGATE_INITIALIZATION_REQUIRED",
        )
        self._controller()
        need(
            self.calls.native(handle) == native
            and not self.calls.lifecycle(handle)["exited"],
            "AGGREGATE_ORIGINAL_SUSPENDED_CHILD",
        )
        need(
            native["pid"] not in self.rows and native["pid"] != self.controller["pid"],
            "AGGREGATE_PROCESS_ADOPTED_TWICE",
        )
        if not self.calls.in_job(handle, self.job):
            self.calls.assign(self.job, handle)
        self.rows[native["pid"]] = {
            "handle": handle,
            "native": copy.deepcopy(native),
            "job": job,
            "binding": None,
            "cpu_ns": 0,
        }
        need(self.calls.in_job(handle, self.job), "CHILD_OUTSIDE_AGGREGATE_JOB")
        self.observe()

    def bind_retained(self, binding, *, handle, job):
        from scripts.observation_runtime.launch_ownership import RetainedLaunchBinding

        need(
            type(binding) is RetainedLaunchBinding,
            "AGGREGATE_RETAINED_BINDING_REQUIRED",
        )
        binding.verify()
        native = self.calls.native(handle)
        row = self.rows.get(native["pid"])
        if row is None:
            # Descendants inherit the full root chain. Never assign a running
            # unknown process just because a reported PID appears in that chain.
            need(self.calls.in_job(handle, self.job), "DESCENDANT_NOT_IN_AGGREGATE_JOB")
            row = {
                "handle": handle,
                "native": native,
                "job": job,
                "binding": None,
                "cpu_ns": 0,
            }
            self.rows[native["pid"]] = row
        need(
            row["native"] == native and row["job"] == job,
            "AGGREGATE_RETAINED_IDENTITY_CONFLICT",
        )
        need(
            binding.runtime["pid"] == native["pid"]
            and binding.runtime["created"] == native["created"],
            "AGGREGATE_BINDING_BIRTH_CONFLICT",
        )
        row["binding"] = binding
        # Guard receipt names the exact reservation cut captured before BIND.
        # Check the native aggregate without advancing that ledger cut midway
        # through the handshake. The next guard boundary durably samples usage.
        return self.observe(commit=False)

    def _controller(self):
        need(
            self.controller_handle is not None and self.job is not None,
            "AGGREGATE_ORIGINAL_HANDLES_REQUIRED",
        )
        now = self.calls.native(self.controller_handle)
        need(
            all(now[k] == self.controller[k] for k in ("pid", "created", "image"))
            and not self.calls.lifecycle(self.controller_handle)["exited"]
            and self.calls.in_job(self.controller_handle, self.job),
            "AGGREGATE_CONTROLLER_IDENTITY_OR_MEMBERSHIP",
        )

    def bind_query(self, capability, *, handle, job):
        from scripts.observation_runtime.aip06_native_query import CommandLifetime
        need(type(capability) is CommandLifetime, 'ORIGINAL_NATIVE_QUERY_CAPABILITY_REQUIRED')
        capability.verify()
        native = self.calls.native(handle)
        row = self.rows.get(native['pid'])
        need(row is not None and row['native'] == native and row['handle'] == handle
             and row['job'] == job and row['binding'] is None
             and capability.runtime_handle == handle
             and all(capability.runtime[k] == native[k] for k in ('pid','created','image')),
             'QUERY_REQUIRES_PRIOR_SUSPENDED_ROOT_ATTACHMENT')
        row['binding'] = capability
        return self.observe(commit=False)

    def retire_failed_query(self, handle, native):
        """Failure-only terminal accounting; never financial ACK or Stop PASS."""
        row = self.rows.get(native['pid'])
        life = self.calls.lifecycle(handle)
        need(row is not None and row['native'] == native and row['handle'] == handle
             and life['pid'] == native['pid'] and life['created'] == native['created']
             and life['exited'] and not self.calls.members(row['job']),
             'FAILED_QUERY_ORIGINAL_TERMINAL_EVIDENCE')
        cpu = self.calls.usage(handle)[1]
        need(type(cpu) is int and cpu >= row['cpu_ns'], 'FAILED_QUERY_CPU_ROLLBACK')
        row['cpu_ns'] = cpu
        self.finished.add(native['pid'])
        return {'release_only': True, 'financial_ack': False, 'query_passed': False}

    def observe(self, *, commit=True):
        need(not self.failed, "AGGREGATE_FAILURE_LATCHED")
        if self.dormant:
            return self.observe_closed(commit=commit)
        try:
            self._controller()
            need(
                self.calls.job_limits(self.job) == self.limits,
                "AGGREGATE_LIMIT_CONFIGURATION_CHANGED",
            )
            expected = {self.controller["pid"]}
            active = {self.resources.state["controller"]} | {
                r["owner"]
                for r in self.resources.state["resources"].values()
                if r["kind"] == "process" and not r["closed"]
            }
            memory = {key: 0 for key in active}
            known = {self.resources.state["controller"]}
            owner = self.resources.state["controller"]
            amount, parent_cpu = self.calls.usage(self.controller_handle)
            need(
                type(amount) is int
                and 0 <= amount <= LIMITS["private_bytes"]
                and type(parent_cpu) is int
                and parent_cpu >= 0,
                "AGGREGATE_CONTROLLER_USAGE_INVALID",
            )
            memory[owner] = amount
            need(parent_cpu >= self.last_parent_cpu, 'AGGREGATE_PARENT_CPU_ROLLBACK')
            self.last_parent_cpu = parent_cpu
            total_private = memory[owner]
            for pid, row in self.rows.items():
                if row["binding"] is not None:
                    known.add(digest(row["binding"].runtime))
                if pid in self.finished:
                    continue
                need(
                    self.calls.native(row["handle"]) == row["native"],
                    "AGGREGATE_PID_REUSE_OR_HANDLE_CHANGED",
                )
                life = self.calls.lifecycle(row["handle"])
                amount, cpu = self.calls.usage(row["handle"])
                need(
                    type(cpu) is int and row["cpu_ns"] <= cpu,
                    "AGGREGATE_PROCESS_CPU_ROLLBACK",
                )
                row["cpu_ns"] = cpu
                if life["exited"]:
                    continue
                need(
                    self.calls.in_job(row["handle"], self.job),
                    "AGGREGATE_CHILD_ESCAPED",
                )
                need(
                    self.calls.job_limits(row["job"])
                    == {
                        "processes": LIMITS["processes"],
                        "private_bytes": LIMITS["private_bytes"],
                        "child_private_bytes": LIMITS["child_private_bytes"],
                        "cpu_ns": LIMITS["cpu_ns"],
                        "kill_on_close": True,
                    },
                    "AGGREGATE_LEAF_LIMIT_CONFIGURATION_CHANGED",
                )
                expected.add(pid)
                total_private += amount
                need(
                    type(amount) is int
                    and 0 <= amount <= LIMITS["child_private_bytes"],
                    "AGGREGATE_CHILD_MEMORY_LIMIT",
                )
                identity = (
                    row["binding"].runtime if row["binding"] is not None else None
                )
                if identity is not None and digest(identity) in active:
                    memory[digest(identity)] = amount
            observed = self.calls.members(self.job)
            need(observed == expected, "AGGREGATE_UNEXPECTED_OR_MISSING_MEMBER")
            account = self.calls.job_accounting(self.job)
            need(
                set(account)
                == {"user_ns", "kernel_ns", "active", "total", "terminated"}
                and all(type(x) is int and x >= 0 for x in account.values())
                and account["active"] == len(expected) <= LIMITS["processes"]
                and account["terminated"] == 0,
                "AGGREGATE_NATIVE_ACCOUNTING_DISAGREEMENT",
            )
            job_cpu = account["user_ns"] + account["kernel_ns"]
            need(self.native_cpu_history.get(self.generation, 0) <= job_cpu, "AGGREGATE_JOB_CPU_ROLLBACK")
            # Count full original process lifetimes as a conservative lower
            # bound too: Job assignment must not hide the controller bootstrap
            # prefix. Exited process CPU stays recorded after handles close.
            process_cpu = parent_cpu + sum(r["cpu_ns"] for r in self.rows.values())
            cpu = max(job_cpu, process_cpu, self.last_cpu)
            need(
                self.last_cpu <= cpu <= LIMITS["cpu_ns"],
                "AGGREGATE_CPU_LIMIT_OR_COUNTER_ROLLBACK",
            )
            need(active <= known, "AGGREGATE_UNBOUND_LEDGER_PROCESS")
            need(
                total_private <= LIMITS["private_bytes"],
                "AGGREGATE_PRIVATE_MEMORY_LIMIT",
            )
            self.last_cpu = cpu
            self.last_job_cpu = job_cpu
            self.native_cpu_history[self.generation] = job_cpu
            if commit:
                self.resources.usage(memory=memory, cpu_ns=cpu)
            return {
                "members": sorted(expected),
                "cpu_ns": cpu,
                "memory": memory,
                "total_private_bytes": total_private,
                "at_ns": self.clock(),
            }
        except BaseException:
            self.failed = True
            raise

    def exited(self, binding, *, handle):
        pid = binding.runtime["pid"]
        need(
            pid in self.rows and pid not in self.finished,
            "AGGREGATE_ONE_EXIT_PER_BIRTH",
        )
        row = self.rows[pid]
        life = self.calls.lifecycle(handle)
        need(
            life["pid"] == pid
            and life["created"] == row["native"]["created"]
            and life["exited"] is True
            and self.calls.members(row["job"]) == set(),
            "AGGREGATE_CHILD_EXIT_OR_JOB_INCOMPLETE",
        )
        cpu = self.calls.usage(handle)[1]
        need(type(cpu) is int and row["cpu_ns"] <= cpu, "AGGREGATE_EXIT_CPU_ROLLBACK")
        row["cpu_ns"] = cpu
        self.finished.add(pid)
        return self.observe()

    def close(self, *, deadline_ns):
        if self.dormant:
            need(all(self.allocations.closed(self.resources.state['controller'], k) for k in self.closed_keys),
                 'AGGREGATE_REPEATED_RELEASE_CONFLICT')
            return {'controller_job_membership_lasts_until_process_exit': True,
                    'owned_handles_closed': True, 'financial_ack': False}
        self.observe()
        need(
            self.calls.members(self.job) == {self.controller["pid"]}
            and all(
                self.calls.lifecycle(r["handle"])["exited"]
                for p, r in self.rows.items()
                if p not in self.finished
            ),
            "AGGREGATE_CHILDREN_NOT_RELEASED",
        )
        for key, handle in reversed(self.held):
            need(self.clock() < deadline_ns, "AGGREGATE_RELEASE_DEADLINE")
            self.calls.close(handle)
            need(self.calls.closed(handle), "AGGREGATE_HANDLE_RELEASE_UNVERIFIED")
            self.allocations.release(key)
            self.closed_keys.add(key)
        self.held.clear()
        self.dormant = True
        self.closed_at = self.clock()
        return {
            "controller_job_membership_lasts_until_process_exit": True,
            "owned_handles_closed": True,
            "financial_ack": False,
        }

    def observe_closed(self, *, commit=True):
        """No live worker may reappear after its original normal exit.

        The controller is still the caller; GetCurrentProcess is its kernel
        capability, not OpenProcess(PID). Existing kernel Job limits remain in
        force after the last query handle closes. No Job is reopened/adopted.
        A new worker requires a fresh create-new nested envelope first.
        """
        need(not self.failed and self.dormant and not self.held and self.closed_at is not None
             and set(self.rows) == self.finished, 'AGGREGATE_CLOSED_LIFETIMES_REQUIRED')
        current = self.calls.current()
        actual = self.calls.native(current)
        need(all(actual[k] == self.controller[k] for k in ('pid','created','image'))
             and not self.calls.lifecycle(current)['exited'], 'AGGREGATE_CLOSED_CONTROLLER_CHANGED')
        memory, cpu = self.calls.usage(current)
        total = cpu + sum(r['cpu_ns'] for r in self.rows.values())
        need(type(memory) is int and 0 <= memory <= LIMITS['private_bytes']
             and type(cpu) is int and cpu >= self.last_parent_cpu and 0 <= total <= LIMITS['cpu_ns'], 'AGGREGATE_CLOSED_USAGE_LIMIT')
        self.last_parent_cpu = cpu
        total = max(total, self.last_cpu)
        self.last_cpu = total
        values = {self.resources.state['controller']: memory}
        need(all(r['closed'] or (r['owner'] == self.resources.state['controller']
                 and r['kind'] in ('file','directory','handle') and k not in self.closed_keys)
                 for k,r in self.resources.state['resources'].items()), 'AGGREGATE_CLOSED_RESOURCE_LEAK')
        if commit:
            self.resources.usage(memory=values,cpu_ns=total)
        return {'members':[self.controller['pid']], 'cpu_ns':total, 'memory':values,
                'total_private_bytes':memory,'at_ns':self.clock()}

    def rearm(self, sample):
        """Create a new finite envelope after a successful, fully closed sample.

        The old kernel membership persists, but no old handle, root, ledger or
        account is adopted. All charges, old terminal CPU and generations remain.
        """
        need(not self.failed and self.dormant and sample in (2,3) and sample == self.generation + 2
             and not self.resources.recovered and self.resources.state['mode'] == 'WORK'
             and not any(v['state'] != 'CLOSED' for v in self.resources.state['stops'].values()),
             'ONLY_SUCCESSFUL_NEXT_STOP_SAMPLE_CAN_REARM')
        self.observe_closed()
        self.generation += 1
        self.failed = True
        ticket = self.allocations.reserve('aggregate-controller-original','handle')
        self.controller_handle = self.calls.duplicate(self.calls.current(), self.calls.current())
        self.held.append((ticket,self.controller_handle))
        ticket = self.allocations.reserve('aggregate-root','job')
        self.job = self.calls.create_job('Local\\Atlas-AIP06-Aggregate-' + digest(self.controller)[:32] + f'-{self.generation:02d}',self.limits)
        self.held.append((ticket,self.job))
        need(self.calls.job_limits(self.job) == self.limits and not self.calls.members(self.job), 'AGGREGATE_REARM_CREATE_NEW')
        self.calls.assign(self.job,self.controller_handle)
        need(self.calls.members(self.job) == {self.controller['pid']}, 'AGGREGATE_REARM_EXACT_CONTROLLER')
        self.dormant, self.failed = False, False
        return self.observe()
