# Operational runtime and Control Center wiring — 2026-10-25

Base: e06f16a9f88feae5022343b4202d527f854819e6, chatgpt/atlas-rebuild-v1.
Source-only implementation and confined disposable acceptance. No installed
operational authority, inception, provider connection or PAPER startup.

## Implemented source

- `backend/app/services/quality_dips_operational_runtime.py`: separately typed
  operational V3/V4/V5 composition over existing AutonomousNativePublication,
  operational native reader/store, FS3 service, session reservation, clock,
  ownership, acceptance and current-custody ports. No second financial engine.
  Construction requires an injected installation lease authenticating enrollment,
  current pins AND exact dependency objects. Every runtime action rechecks it.
  All B1/C1/D1/E1 acceptance proofs remain mandatory. No environment/file/CLI
  approval loader, test-pin conversion, credential installation or account creation.
- Existing V3 constructor resource checks extracted into an overridable method;
  original V3 and V5 classes still refuse operational inputs. The new operational
  classes are explicit alternatives, not a startup-lock bypass. V5 requires an
  exact financial-binding class and preserves native admission on every action.
- `scripts/volume_inspector/operational_autonomous_store.py`: existing-only native
  verification of all six enrolled roots; file identities and protected ACLs use
  the existing native handle primitives. Operational source/projection/report/
  coordination identity and revision equality are checked before financial action.
- `backend/app/services/quality_dips_stop_bridge.py`: one injected Stop action for
  the Control Center and disposable HTTP tests. Normal Stop explicitly chooses
  SHUTDOWN_FLATTEN; Emergency stops dispatch while preserving holdings. Operational
  bridge construction also requires a retained owned-close capability. An HTTP
  nonce protects transport only; it never grants enrollment or financial authority.
  Exact loopback Host/Origin, bounded command bodies and session ownership apply.
- `scripts/windows/Atlas-Control-Center.psm1`: exported Invoke-AtlasPaperStop checks
  the accepted session before dispatch. `Atlas-Background-Controls.ps1` normal Stop
  calls this action, displays progress/outcome, and has NO legacy backend Stop
  fallback. Missing enrollment leaves Stop disabled/refused. Emergency is a
  separate tray action. Production/Gaming startup refusal remains unchanged.
- Existing shutdown coordinator persists entry-admission closure progress before
  financial effects and final outcome afterwards. Existing native acknowledgement,
  report/replay, exact remaining quantity and drain checks remain in effect.
- Original selected-account JS displays shutdown phase, position state and
  unresolved errors in the existing layout. Historical remembered L1 is now marked
  STALE at read time rather than incorrectly appearing FRESH. No theme redesign.

## Actual validation

Three disjoint final Python selections: 114 + 43 + 9 = 166 passed, 0 failed,
0 skipped. There are 26 new cases: 17 factory/operational-binding cases and
9 genuine loopback/PowerShell/ownership cases. Existing selected frontend suite:
32 passed, 0 failed/skipped. Counts do not add overlapping intermediate runs.

- 114: shutdown flatten, V3/V5/engine, passive GUI and recovery-hardening regressions.
- 43: operational factory, operational native store/reader, personal clock/session
  dependencies, Python production startup lock.
- 9 real native Windows HTTP cases: full and partial position flatten; repeat Stop;
  closed/stale/disconnected/UNKNOWN outcomes; restart refusal; transport forgery;
  separate emergency behavior; shipped PowerShell action invoking genuine HTTP;
  retained-host foreign-close refusal; unchanged unrelated test-owned sentinel;
  graceful exact-host exit and released listener port.
- 2 genuine in-app browser scenarios: normal/repeated Stop and original dashboard
  final cash1019.912/gross20/costs0.088/net19.912/no remaining shares; disconnected
  Stop and original dashboard STOP_INCOMPLETE/SHUTDOWN_INCOMPLETE/POSITION_OPEN,
  one retained share/cash899.96/unresolved error/STALE synthetic quotes. The browser
  clicked a separate disposable test harness that invokes the same injected Stop
  action, then inspected the original page. No native WinForms mouse click was
  automated; the shipped handler was executed through Windows PowerShell/HTTP.
- Eleven native financial JSON hashes were byte-identical before/after real
  browser read refresh in the unresolved scenario. HTTP cases also compare native
  financial JSON bytes across repeated Stop and reads.
- Ruff, compilation, JavaScript syntax, PowerShell parse and PAPER policy checks.
  The policy scan covers569 runtime files with0issues. No new browser provider
  access, privilege-dependent symlink attacks, physical power-loss, operational
  service acceptance or real Genesis coexistence test is claimed.

The dashboard truthfully retains calendar report INCOMPLETE at the current
exclusive cutoff. FLATTENED is the acknowledged position/cash outcome, not a claim
that the entire calendar day or operational release is accepted. No future cutoff
or synthetic market price is invented to make a report complete.

## Retained failures and limits

Initial factory fixtures exposed a missing PROFILE import and incorrect
coordination resource path; both corrected without weakening identity checks.
The first confined HTTP attempt hit the existing Windows sandbox socket-startup
restriction. Retained-child EOF did not confirm exit within12seconds; no forced
termination occurred. A later native read-only process query filtered to that
exact unique fixture root found0matches. This is current absence evidence, not a
claim that the original timeout never occurred. Native reruns preserved the
original failure. Further native attempts caught a future-dated synthetic fixture
clock/monotonic pair and an empty403 test-client parsing assumption; corrected
fixtures/client, preserving financial and transport assertions.

Synthetic verifiers live only in disposable tests. Merely labeling a proof
OPERATIONAL_ACCEPTED cannot make it trustworthy: an independently accepted
installed trust anchor must authenticate its lease and exact objects. Arbitrary
malicious Python injected by the same Windows user cannot be sandboxed by this
factory. Same-user/D:-only custody is not independent anti-rollback protection.
No issuer, key, accepted local dependency loader, service or provider was installed.

The injectable L1 port must honor its bounded timeout. The existing framework
never force-kills arbitrary callbacks or foreign processes. Retained-close
implementations must reverify lifetime/ownership and gracefully close only their
original owned processes; fixture financial Stop deliberately leaves the HTTP
observer up for read verification, then its original parent closes it via EOF.

## Remaining real-world prerequisites (no new architecture milestone)

1. Required profile-scoped B1/C1/D1/E1 dispositions and named acceptance roles:
   account/historical exclusions, actual all-writer roster/exclusion, accepted
   issuer/session and current/high-water custody, clock/discontinuity and recovery.
   The operator's earlier reduced-assurance acknowledgement is preserved and is
   not independent acceptance of those gates.
2. Separately authorize verification/installation of the reviewed dependency
   implementations under D:/existing Windows account. Bind the installed verifier
   to exact component objects and native identities, local durable session
   reservations, real process ownership/retained-close and Control Center session
   object. No JSON/env switch or fixture verifier may substitute for enrollment.
3. Separately authorize once-only account inception and acknowledged native
   source/projection/report publication; preserve the13 existing directories and
   all unresolved legacy exclusions. Accept backup/restore and interruption rules.
4. Select/authorize an entitled L1 stock/ETF feed and its data-only adapter. Verify
   bid/ask timestamps, instrument mapping, sizes/spread, calendars/halts, freshness,
   disconnect and reconnect refusal. No provider was contacted during this work.
5. Explicit bounded operational launch permission, native WinForms Start/Stop and
   installed process-ownership acceptance, then supervised autonomous PAPER
   sessions. Reboot/Stop never resumes trading without new session authorization.
   Seven-session and extended30–60-session trials remain unstarted.

The original HTML/theme, real13resources, legacy financial records, Genesis,
strict/manual contracts, startup lock, all21 decisions and seven phases are
preserved. BLOCKED_WAIT, zero ACTIVE tasks at the real installation/acceptance
boundary. PAPER startup NO; Production NO-GO.
