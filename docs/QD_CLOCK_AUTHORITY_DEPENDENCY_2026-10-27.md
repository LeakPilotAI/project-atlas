# Quality Dips clock authority dependency resolution — 2026-10-27

## Finding

BLOCKED: there is no installed or implemented operational acquisition/authentication procedure for the existing personal clock anchor in the reviewed repository. Repeating Windows service starts or resyncs cannot install this missing binding. A second independent problem remains: current Windows system-clock status is unsynchronized. No financial stages were executed.

This corrects the emphasis of earlier clock reports, without deleting them: <=1000ms is an existing runtime check, but an external cryptographic time issuer is NOT a personal-profile prerequisite. The approved policy explicitly removes CRYPTOGRAPHIC_UTC_AUTHORITY and separate independent clock-custodian roles. Do not request enterprise credentials, an outside reviewer or another financial authorization to solve this local engineering dependency.

## Exact dependency chain

1. Approved personal release policy, docs/ATLAS_PERSONAL_PAPER_RELEASE_POLICY.json, retains LOCAL_CLOCK_BOOT_AND_DISCONTINUITY_REFUSAL; local operator is sole release authority. Historical strict policy is unchanged.
2. backend/app/services/personal_paper_runtime.py::compose_personal_qd requires explicit runtime and native dependencies plus PersonalOperatorInstallation. Technical facts must include CLOCK_CONTINUITY=True; they are not inferred from policy approval. No installed default launcher or clock factory is supplied here.
3. PersonalNativeEnrollment inherits AutonomousNativeEnrollment._clock in quality_dips_autonomous_enrollment.py. Each admission validates QD_AUTO_NATIVE_CLOCK_V4 with utc,monotonic_ns,uncertainty_ms,source; source must equal enrollment.clock_source; uncertainty must be integer0..1000; clock.verify must return exactly True. Continuity is checked across calls.
4. OperationalRuntime inherits AutonomousRuntime._now in quality_dips_autonomous_runtime.py. Its distinct QD_AUTO_CLOCK_V3 sample uses source_id,utc,monotonic_ns,uncertainty_ms, bound0..1000, engine-clock equality and runtime authority.verify('CLOCK',bound request,now). The personal composition does not override or waive this check. Runtime/native clock adapters must preserve their distinct protocols, not substitute schemas.
5. quality_dips_personal_dependencies.py::PersonalClockContinuity is a possible existing native-clock consumer, not an acquisition client. It takes anchor,authority,monotonic_ns,wall_utc,boot_identity. Constructor stores a canonical copy in memory. sample requires authority.verify(anchor) is True and the exact anchor schema below. It does not contact Windows, select a trusted issuer, obtain a signature, calculate accuracy or install a source.
6. Its sample output QD_AUTO_NATIVE_CLOCK_V4 can satisfy the native interface only when the injected authority and real evidence genuinely qualify. verify requires exact sample shape/source/uncertainty, monotonic timestamp no earlier than anchor and at most1second old, and UTC derived from anchor. It does not independently measure clock accuracy.
7. The once-only personal bootstrap receives an injected clock callable and issuer/installation binding; it supplies no independent clock-acquisition mechanism. Inception authorization therefore does not create a valid clock dependency.

## Required declaration, authentication and storage

Exact QD_PERSONAL_UTC_ANCHOR_V1 fields: schema,utc,monotonic_ns,boot_id,source,expires_at,uncertainty_ms. utc/monotonic_ns/expires_at/uncertainty_ms are strict integers, not bool. utc<=expires_at<=utc+300. uncertainty_ms in[0,1000]. boot_id must match injected boot identity; monotonic time must not reverse; wall UTC must be integer and within2seconds of derived UTC; expiry must not be exceeded.

There is NO signature field, signing algorithm, named remote issuer, credential requirement, certificate endpoint or acquisition URL in this contract. Authentication is a caller-injected authority.verify(anchor) interface. Under the approved personal profile this may be a legitimate locally installed operator-bound implementation; it must not be the test always-True verifier. Absence of cryptographic authentication does not permit an unsupported uncertainty declaration.

There is NO specified on-disk operational clock-anchor path or installed clock-authority record. The consumer keeps its supplied anchor in memory. NativePersonalActivationReader reads a different, handle-bound activation.json contract; that file is not a UTC accuracy certificate. The activation bundle specifies an anchor lifetime, but contains no executable acquisition, clock-issuer installation or uncertainty-estimation procedure. It is an installation plan, not installed clock evidence.

Tracked-source search for PersonalClockContinuity and QD_PERSONAL_UTC_ANCHOR_V1 found only the consumer and its test module. Broader clock-source search found other injected validators and synthetic fixtures, not a supported Windows uncertainty acquisition implementation. Tests inject explicitly synthetic authorities and cannot commission a real account.

## Does it apply to this pilot?

Yes: compose_personal_qd reuses the unchanged enrollment/runtime checks above. Neither the personal override nor 60second pilot scope bypasses them. The source policy's removal of enterprise PKI does not remove numerical uncertainty or continuity validation. Disposable/synthetic and research-only paths exist, but they cannot initialize the real simulated account or be presented as the authorized real-observation financial pilot. No supported alternative operational clock provider was found. No bypass was used.

## Current Windows check

One fresh read only; no service action, explicit resync, settings change or NTP stripchart in this execution. W32Time Running/Manual; configured NTP peer remains time.windows.com,0x9. System status still Leap3,Stratum0,Local CMOS Clock,StateMachine0 Unset,LastSyncError1,LastSuccessfulSync unspecified,RootDelay0/RootDispersion0. Those zero values are unset, not a bound. Reported Time since Last Good Sync534.9609119seconds is not a usable synchronization age while no successful sync exists. Prior service starts, morning success and measured offsets remain historical; no declaration was manufactured from them.

## Independent validation completed

Added eight pure in-memory adversarial cases to the existing test_quality_dips_personal_dependencies.py: seven uncertainty values(-1,0,999,1000,1001,True,1.0), plus authentication refusal even for declared zero uncertainty. Valid integer1000 is accepted;1001,bool,float,negative and unverified anchors refuse. Tests explicitly use SYNTHETIC_BOOT/CLOCK and are not operational evidence.

Command: backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_quality_dips_personal_dependencies.py -k 'clock or anchor', with PYTHONDONTWRITEBYTECODE=1,PYTEST_DISABLE_PLUGIN_AUTOLOAD=1,PYTHONPATH=backend. Actual result17passed,0failed,0skipped,3deselected in2.48seconds. The three deselected tests exercise durable session reservations, outside this pure clock check; no failure excluded. Ruff, AST parse and diff whitespace checks passed. Production clock validator and thresholds unchanged. No full accounting suite repeated.

## Exact next dependency and authorization disposition

The missing item is a supported local clock evidence acquisition/authentication binding, with a documented and defensible <=1second total-uncertainty budget, matching the accepted source, boot and monotonic runtime. No additional credential or external reviewer is specified by this contract or required by the approved personal policy. Source-only implementation/testing remains within standing authorization; this report does not invent a new administrative approval requirement. A method must actually justify its bound before any operational anchor can be issued. No currently supported mechanism was found that can do that now, and this task forbids fabricating declarations or replacing acquisition with a new framework.

No further Windows configuration change is recommended as a demonstrated fix. Normal future synchronization can be read without new permission; explicit resync/source/startup changes still require their narrow separate authorization and cannot by themselves fill the missing adapter. Any new external time provider/credential installation or expanded Windows action would need separate scope, if actually chosen; none is presumed necessary or performed.

Once genuine clock evidence and its local binding pass the unchanged validators, continue the SAME unused QD commissioning grant: revalidate resources/eligibility, accepted D:installation, once-only1000simulatedUSD inception/native audit, entitled QD/IEX observations, one60second autonomous session without forced trades, reconciliation/ownedStop/restart and actual desktop verification. Existing missing installed runtime/reader/writer/start bindings remain commissioning work, not falsely reported complete. No second account, Hyperliquid inception,V5 execution,live orders or Genesis.

Balance,positions,P&L and financial startup readiness remain UNAVAILABLE/account not initialized. Approval is not consumed. Production NO-GO. All historical decisions, unrelated native source edits and original UI preserved.