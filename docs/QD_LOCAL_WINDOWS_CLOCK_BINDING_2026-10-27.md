# Local Windows clock binding completion — 2026-10-27

## Implemented

scripts/observation_runtime/personal_windows_clock.py supplies LocalWindowsClock(expected_source=...,runtime_id=...,lifetime=240). Construction collects actual evidence and refuses before issuing any anchor unless it qualifies. It does not configure Windows, start services, resync, fetch NTP packets, install credentials, initialize stores or activate financial code.

The existing PersonalClockContinuity validator is unchanged. Strict/manual/disposable accounting, original UI and deferred V5 sources are unchanged. Tests are in tests/test_personal_windows_clock.py.

### Actual acquisition and local authentication

- Native GetSystemDirectoryW resolves the Windows tool location; the child is fixed Windows PowerShell, with a process-local verified system module search path, no profile, hidden window and12second timeout. Its fixed script invokes only w32tm /query /status /verbose and read-only service/registry/signature queries. No shell-provided executable, user-supplied command, resync or network-provider request is accepted.
- Get-AuthenticodeSignature must validate w32tm.exe and identify Microsoft Corporation as signer. W32Time service status and configured NTP source/type must agree before/after status collection. Unavailable/denied queries, bad signatures, incomplete/duplicate/unrecognized-language output and contradictory effective/configured sources refuse.
- GetSystemTimePreciseAsFileTime supplies actual UTC readings; Windows QPC via perf_counter_ns supplies elapsed time. GetProcessTimes binds the live process creation identity. A random ephemeral capability tag additionally binds the particular runtime/instance. This process-local lifetime tag occupies the existing anchor boot_id field; it is NOT represented as a Windows boot GUID, signing key or independent UTC credential. Reboot/process replacement cannot preserve the capability.
- There is no injection argument for the public operational constructor. Internal synthetic test construction is marked DISPOSABLE_SYNTHETIC; require_operational(runtime_id) refuses it. In-memory sealed anchor comparison, process identity and per-instance tag prevent adopting a copied/recovered declaration. No persisted JSON flag/test fixture becomes an operational issuer.
- This is local OS/tool provenance authentication under the accepted personal same-user model. It is not cryptographic authentication of time.windows.com, remote-server honesty, hostile administrator resistance or independent rollback custody. No external reviewer, enterprise PKI or credential is introduced.

### Quality and uncertainty model

Require Running W32Time; Type NTP; exact accepted configured/effective source; Leap0; Stratum1..15; LastSyncError0; real successful-sync timestamp; source age0..120seconds. The parsed local sync timestamp must agree with measured age, allowing only collection duration and2seconds of display rounding. Unset zero dispersion in an unsynchronized status cannot pass.

Bound in milliseconds, rounded UP:

1000 * (root_dispersion + root_delay/2 + abs(phase_offset) + full_collection_elapsed +0.001 +0.0005*(source_age+anchor_lifetime)).

This conservatively includes advertised accumulated error, transport distance, residual offset, the entire local collection interval,1ms read/decimal margin and a500ppm aging allowance. Some terms may overlap Windows' own estimate; no term is subtracted to make the bound pass. Negative/nonfinite inputs, collection longer than12seconds, lifetime outside1..240seconds or result>1000ms refuse. The existing validator's1000ms limit and300second maximum anchor are unchanged; this binding chooses a shorter bound for the approved pilot.

The500ppm allowance is an explicit conservative local oscillator/holdover assumption, not a measurement or absolute physical guarantee. RFC5905 describes dispersion/half-delay quality metrics,15ppm nominal aging and500ppm frequency-clamp assumptions: https://www.rfc-editor.org/rfc/rfc5905 . Microsoft distinguishes precise timestamp resolution from clock accuracy: https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps . This personal model relies on accepted Windows/NTP quality reports; it does not turn public unauthenticated NTP into an independent UTC authority.

Anchor UTC remains whole-second interval encoding required by the existing contracts. Its monotonic origin is aligned to the observed UTC-second boundary instead of silently discarding subsecond phase. The quality envelope describes the underlying clock; whole-second schema resolution is not advertised as submillisecond timestamp precision.

Status evidence is recollected after5seconds on use. Worsening bound, expired/stale source, unavailable service or source change revokes the capability permanently; there is no blind renewal or revival. High-resolution wall/QPC excursions outside the same500ppm model plus2ms read margin also latch refusal, even below the existing validator's retained2second discontinuity threshold. Expiration and process restart require a new genuine collection and newly authorized runtime session; they do not replay financial actions.

### Existing injection points

- native_dependencies['clock']: clock.require_operational(the_same_runtime_id), producing existing QD_AUTO_NATIVE_CLOCK_V4 samples.
- runtime_dependencies['clock']: clock.runtime_clock(), producing existing QD_AUTO_CLOCK_V3 samples.
- engine/inception/read UTC callable: the same clock instance's __call__.
- Existing installed local runtime authority CLOCK handling can validate its sample via clock.verify_runtime_sample; that method does not fabricate a runtime authority proof, enrollment or acceptance record.

The supported ports are implemented; no default issuer, installed launcher or financial admission is silently registered. Existing personal installation must still bind exact component identities, accepted account/release, ownership, custody and bounded session.

## Actual Windows execution

Read-only collection succeeded through the signed Windows tool. Final QPC diagnostic result was retained locally in logs/diagnostics/qd-local-clock-binding-qpc-actual-20261027.json; earlier acquisition result also retained separately. These ignored files are not published.

- W32Time Running; configured NTP source time.windows.com,0x9 unchanged.
- Leap3,Stratum0,StateMachine0 Unset,LastSyncError1,Source Local CMOS Clock.
- Last successful sync unspecified; timestamp unavailable. Reported elapsed1324.9521089seconds is not a genuine age of a successful synchronization.
- RootDelay0/RootDispersion0 remain unset values, not zero uncertainty.
- Actual QPC collection929.5136ms; observed wall/QPC discrepancy8.8microseconds. Those local interval measurements do not prove UTC accuracy.
- Actual acquisition and operational constructor both REFUSED: CLOCK_UNSYNCHRONIZED. Calculated qualifying uncertainty is UNAVAILABLE, not0. No operational anchor was issued; the unchanged downstream PersonalClockContinuity validator could not be supplied with genuine qualifying evidence. Its successful acceptance/refusal behavior is demonstrated only in synthetic tests.
- No service restart/resync/source/settings action, provider connection, financial file access/publication or Genesis access.

## Validation

Final relevant combined regression: 349passed,0failed,0skipped,18deselected in11.02seconds. These are the actual final combined counts, not a sum of repeated runs. Selection covers the new clock module, existing personal anchor/session source tests, personal composition, in-memory inception/current pins, autonomous enrollment/risk/accounting, calendar reports, desktop lifecycle policy and PAPER-only capability policy. Native financial mutation and abrupt-child cases are deliberately outside this clock-only increment; their previous evidence is retained, not relabeled passed.

New tests exercise valid derived evidence through the existing validator, missing/unsynchronized/stale clocks, source contradictions, stopped service, incomplete/nontext/duplicate declarations, excessive dispersion, unknown localization, process replacement/restart, copied-anchor refusal, revocation/no-auto-recovery, runtime sample protocol, bounded age/collection/lifetime and subsecond clock discontinuity. Operational factory never accepts the synthetic probe used for these tests.

A development test initially expected58ms while its updated source age included the1ms collection: the independent Decimal budget is58.0005ms and correctly rounds UP to59ms. The failing run was1failed/51passed/3deselected. The assertion was corrected to the verified arithmetic; the implementation and1000ms threshold were not weakened. Original failure and subsequent passes remain documented. Ruff and AST checks pass.

## Commissioning disposition

The previously missing local binding is implemented. Commissioning is still BLOCKED_CURRENT_WINDOWS_UNSYNCHRONIZED. The next requirement is genuine synchronized Windows evidence with an error budget<=1000ms; no fake declaration or successful packet can substitute. No new financial permission or external reviewer is required by this engineering result. Normal service collection can be checked later. An explicit resync, source or Windows setting change still requires separate narrow authorization and does not guarantee a qualifying bound. No configuration change is claimed as a proven fix.

The existing QD-only installation/once-only1000simulatedUSD/authorizedQD-IEX/one60secondpilot/Stop/restart grant remains UNUSED. No balance,position,P&L or pilot result exists to report; the account is not initialized. Resume that same scope only after genuine clock/resource/financial/data checks pass. Hyperliquid inception,V5 native execution,live-money orders and Genesis remain prohibited. Production NO-GO.