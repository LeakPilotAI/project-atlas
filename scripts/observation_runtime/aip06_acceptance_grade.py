"""Independent source grader; native evidence authority is deliberately unbound.

Reads original observer ports itself, not a controller's PASS flag. The same
validation is exercised offline, with explicitly injected provenance. There is
no native PASS from these ports or from caller-supplied JSON/native booleans.
"""

import copy
from types import SimpleNamespace
from subprocess import list2cmdline

from app.services.paper_financial_replay import digest
from scripts.observation_runtime.aip06_acceptance_control import INJECTED, NS
from scripts.observation_runtime.aip06_cleanup_providers import ThreeReaderCleanup
from scripts.observation_runtime.aip06_harness import LIMITS, ROOTS, SCOPE_HASH, need
from scripts.observation_runtime.launch_ownership import identity

READERS = ('HANDLES', 'JOB', 'LEDGER', 'FINANCIAL', 'RESTART', 'OBJECTS',
           'CIM', 'IP_HELPER', 'NETSTAT', 'PROCESS')


class IndependentGrader:
    domain = INJECTED

    def __init__(self, *, plan, manifest_sha256, readers, clock_ns, output, owner_launch):
        need(set(readers) == set(READERS) and len({id(v) for v in readers.values()}) == len(READERS),
             'COMPLETE_DISTINCT_INDEPENDENT_READERS_REQUIRED')
        need(all(r.domain == INJECTED and r.source_path in plan['source_pins']
                 and r.source_sha256 == plan['source_pins'][r.source_path] for r in readers.values()),
             'EXPLICIT_PINNED_INJECTED_READER_PROVENANCE')
        self.plan, self.pin, self.readers = copy.deepcopy(plan), manifest_sha256, dict(readers)
        self.clock, self.output, self.sequence, self.failed = clock_ns, output, {}, False
        self.owner_launch = owner_launch

    def grade_native(self, *args, **kwargs):
        raise ValueError('NATIVE_READER_ATTESTATION_AND_RUNTIME_BINDING_NOT_QUALIFIED')

    @staticmethod
    def inspect_scoped(context, request, *, deadline_ns):
        from scripts.observation_runtime.aip06_scoped_context import ReaderContext, ReaderExecutionContext
        need(type(context) in (ReaderContext, ReaderExecutionContext), 'CONCRETE_SCOPED_READER_CONTEXT_REQUIRED')
        return context.collect(request, deadline_ns=deadline_ns)

    @staticmethod
    def inspect_windows(adapters, request, *, plan, manifest_sha256, deadline_ns):
        """Collect raw concrete providers; never promote them to a native PASS.

        Raw Windows evidence is not the injected summary schema. In particular
        a cached financial reply or owner-supplied booleans cannot replace the
        original cold-reader/StopVerification chain and reader admission.
        """
        from scripts.observation_runtime.aip06_acceptance_plan import validate_plan
        from scripts.observation_runtime.aip06_windows_acceptance_adapters import WindowsReaderSet
        validate_plan(plan)
        need(digest(plan) == manifest_sha256 and type(adapters) is WindowsReaderSet
             and adapters.pin == manifest_sha256,
             'EXACT_CONCRETE_WINDOWS_ADAPTERS_AND_MANIFEST')
        result = adapters.collect(request, deadline_ns=deadline_ns)
        need(result['native_acceptance'] is False, 'RAW_OBSERVATION_IS_NOT_NATIVE_ACCEPTANCE')
        return result

    def _read(self, name, request, started_ns, deadline_ns):
        cut = copy.deepcopy(self.readers[name].read(request, deadline_ns=deadline_ns))
        now = self.clock()
        need(type(cut) is dict and set(cut) == {'reader', 'domain', 'request', 'sequence', 'started_ns',
             'finished_ns', 'complete', 'error', 'payload'}, 'CLOSED_OBSERVER_CUT_REQUIRED:' + name)
        need(cut['reader'] == name and cut['domain'] == INJECTED and cut['request'] == digest(request)
             and cut['complete'] is True and cut['error'] is None, 'OBSERVER_PROVENANCE_OR_COMPLETENESS:' + name)
        need(type(cut['sequence']) is int and cut['sequence'] == self.sequence.get(name, 0) + 1,
             'OBSERVER_REPLAY_OR_SEQUENCE_GAP:' + name)
        need(type(cut['started_ns']) is int and type(cut['finished_ns']) is int
             and started_ns <= cut['started_ns'] <= cut['finished_ns'] <= now <= deadline_ns
             and now - cut['started_ns'] <= 2 * NS, 'OBSERVER_STALE_OR_UNBOUNDED:' + name)
        self.sequence[name] = cut['sequence']
        self.output.append({'schema': 'AIP06_INDEPENDENT_SOURCE_CUT_V1', 'manifest': self.pin,
                            'request': digest(request), 'cut': cut})
        return cut

    def qualify_offline(self, scenario, reservation, result, *, started_ns, deadline_ns):
        need(not self.failed, 'GRADER_FAILURE_LATCHED')
        self.failed = True
        need(digest(self.plan) == self.pin, 'GRADER_PLAN_PIN_MISMATCH')
        need(type(result) is dict and result.get('domain') == INJECTED
             and result.get('native_acceptance') is False
             and result.get('scenario') == scenario.id and result.get('reservation') == reservation['key'],
             'SIMULATED_OR_UNCORRELATED_RESULT_CANNOT_CLAIM_NATIVE_ACCEPTANCE')
        request = {'scope': SCOPE_HASH, 'manifest': self.pin, 'scenario': scenario.id,
                   'reservation': reservation['key'], 'root': ROOTS['E']}
        cuts = {name: self._read(name, request, started_ns, deadline_ns)
                for name in READERS[:6]}
        data = {name: cut['payload'] for name, cut in cuts.items()}
        handles = data['HANDLES']
        owner, controller = identity(handles['owner']), identity(handles['controller'])
        need((owner, controller) == self.owner_launch.verify(self.plan, self.pin)
             and owner != controller and handles['controller_parent'] == owner
             and handles['original_launch_handle_retained'] is True
             and handles['controller_command'] == reservation['controller_command'],
             'RETAINED_CONTROLLER_ANCESTRY_AND_EXACT_COMMAND_REQUIRED')
        rows = handles['descendants']
        need(type(rows) is list and len(rows) == len(scenario.roles)
             and {r['role'] for r in rows} == set(scenario.roles), 'COMPLETE_EXPECTED_DESCENDANT_ROSTER')
        identities = []
        for row in rows:
            current = identity(row['current'])
            need(current == identity(row['launched']) and row['parent'] == controller
                 and row['original_handle_retained'] is True and row['exited_normally'] is True
                 and row['command'] == reservation['commands'][row['role']]
                 and row['current']['command_line'] == list2cmdline(list(row['command']))
                 and row['current']['parent_pid'] == controller[0] and current[1] >= controller[1]
                 and current[2:] == controller[2:],
                 'DESCENDANT_IDENTITY_ANCESTRY_COMMAND_OR_RETAINED_HANDLE')
            identities.append(current)
        need(len(set(identities + [owner, controller])) == len(identities) + 2, 'PID_REUSE_OR_IDENTITY_ALIAS')
        need(len({i[0] for i in identities + [owner, controller]}) == len(identities) + 2, 'PID_ALIAS')
        job = data['JOB']
        need(job['unknown'] is False and job['admitted'] == [owner, controller] + identities
             and job['members'] == [owner, controller] and job['unexpected'] == []
             and job['retained_job_handle'] is True, 'COMPLETE_JOB_MEMBERSHIP_REQUIRED')
        ledger = data['LEDGER']
        need(ledger['reservation'] == reservation['key'] and ledger['stop_reserved'] is True
             and ledger['unreleased'] == [] and ledger['unknown'] is False,
             'AGGREGATE_RESOURCE_RECONCILIATION_REQUIRED')
        limits = {'processes': LIMITS['processes'], 'private_bytes': LIMITS['private_bytes'],
                  'child_private_bytes': LIMITS['child_private_bytes'], 'cpu_ns': LIMITS['cpu_ns'],
                  'entries': LIMITS['entries'], 'bytes': LIMITS['bytes']}
        need(set(ledger['peaks']) == set(limits) and all(type(ledger['peaks'][k]) is int
             and 0 <= ledger['peaks'][k] <= v for k, v in limits.items()), 'NATIVE_CAPACITY_LIMIT_OR_MISSING_ACCOUNTING')
        financial = data['FINANCIAL']
        need(financial['scenario'] == scenario.id and financial['proof'] == scenario.proof
             and financial['ack'] == financial['committed'] == financial['drain_request']
             and type(financial['ack']) is dict and financial['ack'].get('reservation') == reservation['key']
             and financial['ack'].get('scope') == SCOPE_HASH and financial['ack'].get('operation') == scenario.id
             and type(financial['pending']) is int and financial['pending'] == 0
             and financial['unknown'] is False, 'CORRELATED_COMMITTED_ACK_AND_COMPLETE_DRAIN_REQUIRED')
        need(financial['accounts'] == {'QUALITY_DIPS': 'USD', 'HYPERLIQUID': 'USDC'}
             and type(financial['account_ids']) is dict and set(financial['account_ids']) == set(financial['accounts'])
             and all(type(v) is str and v for v in financial['account_ids'].values())
             and len(set(financial['account_ids'].values())) == 2, 'USD_USDC_ACCOUNT_ISOLATION_REQUIRED')
        recovery = data['RESTART']
        need(recovery['scenario'] == scenario.id and recovery['before_hashes']
             and recovery['before_hashes'] == recovery['after_hashes']
             and recovery['reapplied'] == 0 and recovery['unknown'] is False,
             'INDEPENDENT_RESTART_READBACK_REQUIRED')
        objects = data['OBJECTS']
        need(objects['unknown'] is False and objects['open_descendant_handles'] == []
             and objects['unreleased_objects'] == [] and objects['unexpected'] == []
             and objects['retained_identity_verified_before_close'] is True, 'NATIVE_OBJECT_RELEASE_INCOMPLETE')

        # Use the established TCP policy, including State 0 / PID-0 refusal.
        # A successful complete empty table is distinct from missing output.
        grader = self
        class SocketReader:
            def __init__(self, name): self.name = name
            def read(self, *, deadline_ns):
                cut = grader._read(self.name, request, started_ns, deadline_ns)
                return {'complete': True, 'error': None, 'rows': cut['payload']['rows'],
                        'started_ns': cut['started_ns'], 'finished_ns': cut['finished_ns']}
        port = SimpleNamespace(aggregate=SimpleNamespace(rows={i[0]: {'native': {'pid': i[0]}} for i in identities}))
        socket_cut = ThreeReaderCleanup(readers={n: SocketReader(n) for n in ('CIM', 'IP_HELPER', 'NETSTAT')},
            port=port, output=self.output, clock_ns=self.clock,
            endpoints=tuple(reservation['endpoints'])).collect(started_ns=started_ns, deadline_ns=deadline_ns)
        process = self._read('PROCESS', request, socket_cut['at_ns'], deadline_ns)
        need(process['payload']['survivors'] == [] and process['payload']['unknown'] is False
             and process['payload']['controller'] == controller and process['payload']['owner'] == owner,
             'FRESH_STRICT_PROCESS_CLEANUP_REQUIRED')
        finished = self.clock()
        need(started_ns <= finished <= deadline_ns, 'GRADER_OVERALL_DEADLINE')
        if scenario.sample is not None:
            need(result.get('sample') == scenario.sample and type(result.get('stop_started_ns')) is int
                 and type(result.get('stop_finished_ns')) is int
                 and started_ns <= result['stop_started_ns'] <= result.get('stop_finished_ns', -1) <= finished
                 and finished - result['stop_started_ns'] <= 8 * NS
                 and financial.get('cash') == '1015.9136' and financial.get('revision') == 3,
                 'COMPLETE_STOP_WITHIN_EIGHT_SECONDS_AND_EXACT_READBACK_REQUIRED')
        evidence = {'scenario': scenario.id, 'manifest': self.pin, 'reservation': reservation['key'],
                    'status': 'SOURCE_OBLIGATIONS_QUALIFIED_NOT_NATIVE', 'native_acceptance': False,
                    'started_ns': started_ns, 'finished_ns': finished, 'request': digest(request)}
        self.output.append(copy.deepcopy(evidence))
        self.failed = False
        return evidence

    def finish(self, results):
        from scripts.observation_runtime.aip06_acceptance_control import scenarios
        need(not self.failed and [r['scenario'] for r in results] == [s.id for s in scenarios()]
             and all(r['manifest'] == self.pin and r['native_acceptance'] is False
                     and r['status'] == 'SOURCE_OBLIGATIONS_QUALIFIED_NOT_NATIVE'
                     and r.get('aggregate_released') is True for r in results),
             'ALL_FINANCIAL_FAULT_AND_THREE_RESTART_SAMPLES_REQUIRED')
        return {'status': 'SOURCE_MATRIX_QUALIFIED_NOT_NATIVE', 'native_acceptance': False}

    def complete_release(self, scenario, reservation, result, evidence, *, deadline_ns):
        need(not self.failed, 'GRADER_FAILURE_LATCHED')
        self.failed = True
        request = {'scope': SCOPE_HASH, 'manifest': self.pin, 'scenario': scenario.id,
                   'reservation': reservation['key'], 'root': ROOTS['E']}
        cut = self._read('LEDGER', request, evidence['finished_ns'], deadline_ns)
        need(cut['payload']['reservation_released'] is True and cut['payload']['unreleased'] == []
             and cut['payload']['unknown'] is False, 'INDEPENDENT_FINAL_LEDGER_RELEASE_REQUIRED')
        cut = self._read('OBJECTS', request, evidence['finished_ns'], deadline_ns)
        need(cut['payload']['open_descendant_handles'] == [] and cut['payload']['unreleased_objects'] == []
             and cut['payload']['unexpected'] == [] and cut['payload']['unknown'] is False,
             'INDEPENDENT_FINAL_HANDLE_RELEASE_REQUIRED')
        now = self.clock()
        need(now <= deadline_ns and (scenario.sample is None or now - result['stop_started_ns'] <= 8 * NS),
             'COMPLETE_STOP_RELEASE_AND_GRADING_DEADLINE')
        self.failed = False
        return {**evidence, 'finished_ns': now, 'aggregate_released': True}
