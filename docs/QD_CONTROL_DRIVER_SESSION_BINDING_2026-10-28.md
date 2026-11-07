# Quality Dips Control Center driver and native engine-session binding

Continues `7b46bc74406e2f5f5615120750538c22b3cc6ce5`. This is a source increment, not completed commissioning. The original QD-only commissioning authorization remains unused. Production NO-GO. Historical 21 decisions and seven phases remain unchanged.

## Implemented and verified

- The existing `PaperStopBridge` accepts the exact personal commissioning runner. Its authenticated HTTP action queues Stop to the driver thread rather than executing financial shutdown on a worker thread. This corrects a conflict with the native coordination Stop reserve's thread ownership. Existing action leases, ownership checks, CSRF/Host checks and retained-process closer remain required. No default endpoint or startup route was registered.
- The driver rechecks the action lease on its own thread and delegates to existing financial Stop. Repeated requests do not duplicate shutdown; Emergency Stop cannot be downgraded to graceful liquidation. A failed action verification latches refusal and closes dispatch. A Stop that overruns the grant cannot report successful completion. The 60-second grant still includes its final eight-second Stop reserve; no extra trading authority is created.
- `NativePersonalEngineSession` translates the existing concrete Windows operator/activation verifier into the existing engine-session proof. It binds the exact manifest/epoch, current activation/session, unchanged clock, IEX feed and explicit calendar identity. Fixture grants, foreign identities, revocation and expired or overlong grants refuse. This proof explicitly does **not** authenticate market evidence. The installed composition now requires this concrete adapter with the same operator and manifest.
- No original frontend files or styling were changed. Source-level Control Center/HTTP routing was tested in-process; no real browser, installed GUI or operational HTTP pilot is claimed.

## Actual validation

Final relevant offline accounting, risk, inception, custody, native-I/O-double, authority, clock, IEX-fixture, read-composition and driver selection: **366 passed, zero failed, zero skipped, one existing dependency deprecation warning, 19.18 seconds**. Output: `logs/diagnostics/qd-control-session-final-20261028.txt`.

Earlier selection: **365 passed, zero failed, 13 skipped, one warning, 17.94 seconds**. Those 13 are confined native V4/V5 shutdown cases whose explicit test-root prerequisite was absent. They were not executed or represented as passing, and were excluded from the final offline selection. No V5 containment execution was attempted. Output: `logs/diagnostics/qd-control-session-regression-20261028.txt`. Earlier focused runs: 48 and 76 passed, overlapping final coverage. Ruff passed for all six changed/new Python modules; compilation and Git whitespace checks performed.

Fresh actual read-only Windows clock validation: UTC epoch **1793181859**, **361 ms PASS**, unchanged `time.windows.com,0x9`. The first restricted query refused; the ordinary authorized read-only Windows execution succeeded. No service, resync or source setting was changed. Output: `logs/diagnostics/qd-control-session-clock-20261028.txt`. This observation is historical evidence and must be refreshed before commissioning.

## Remaining concrete work and evidence

1. Complete factual installation technical checks and runtime CLOCK/SESSION/CURRENT/OBSERVATION/DRAIN and read-authority assembly around the existing native components. The new engine-session adapter does not finish these other interfaces.
2. Bind genuine current research publications, instrument/lot/fractional/session/halt facts and execution authority to the existing publication reader and IEX input. Operator data permission exists; no additional enterprise reviewer is required. Missing actual research and execution facts cannot be replaced with synthetic verifiers, local digests or an empty board. IEX quotes alone do not supply Quality Dips fundamental/valuation research.
3. Measure complete inception/session/reservation/financial-event/pin/report/Stop/restart write amplification and native latency against the existing 128-revision, 1-MiB image and 32-commit/256-KiB Stop allocations. The offline driver tests prove enforcement and refusal, not full-path native capacity or eight-second shutdown performance.
4. Finish the installed Control Center ownership/composition and genuine browser validation. In-process ASGI tests are not a Windows GUI acceptance result.
5. Only when all dependencies pass: create a NEW immutable release, verify identities/ACL/inventory/readback and fresh clock, perform the already-approved once-only $1,000 simulated USD inception and ONE bounded pilot, reconcile, owned Stop and read-only manual restart. No duplicate account or automatic restart.

No release was installed, no operational account was initialized, no provider was connected, and no pilot or real trade was attempted. Installed release remains `fca29cfe7760a28d2569b8b4b91ed1ea99804c3c`. Actual balance/positions/P&L are not asserted. Protected financial directories, Genesis, existing releases, historical journals and unrelated V5 working-tree changes were left untouched.
