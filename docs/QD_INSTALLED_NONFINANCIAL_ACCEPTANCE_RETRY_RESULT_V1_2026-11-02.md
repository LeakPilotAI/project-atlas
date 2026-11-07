# Installed acceptance-only retry — partial acceptance, port cleanup refused

Starting commit **21094d04dc0e1e9777d0e1fc9b4dfc3dec61df76**, branch `chatgpt/atlas-rebuild-v1`. The sole operator authorized one acceptance-only session against the existing installation. **That authorization is consumed. No second session or automatic retry occurred.**

**First installed Open, timely browser acknowledgement and first normal Stop verified. Full paired acceptance remains INCOMPLETE: the subsequent Windows port audit refused, so the second Open was not attempted. Reviewed rollback restored UNSELECTED.** This does not supersede the previous browser-timeout failure or establish financial readiness.

## Preflight and preserved installation

- Fresh genuine installed clock accepted **224 ms uncertainty**, source age **29.2377481 seconds**, `time.windows.com,0x9`, Leap 0 / Stratum 5 / last error 0. The observation capability was revoked. Selection and rollback used their own genuine clock binding. No time-service/configuration/resynchronization action occurred. This measurement is historical, not continuing clearance.
- All **eight grouped native preflight checks** passed before selection: exact support/source pins; existing receipt/ACK/native identities/protected ACLs/namespaces; actual application inventory of **10,204 files / 903 directories / 260,369,081 bytes**; original application receipt and 44-record ACK; 638-source archive parity; required installed dependencies; retained older release preservation; exact two-record UNSELECTED selector and known-head rollback readiness; resource/isolation contracts. Corrected scalar-helper identity checks also passed.
- Unchanged application: **2c039af29dfefd1df77e0caa3db3fdf5ed188118**. Artifact digest **94ec8b392dd9d0db13e01a8180dd7574baeb468b5e7bd9f3c209af05df048867**.
- Reused support: **5b027d7dc0853975ee751c2c83145a9820a95da28041263b3585b56a4312eccc**. Deployment manifest **7947f54e82d74079b378ad14c238dadb4259671ee7ed5c9d03e952d5d8327cd3**; ZIP **dc6269c8b7ff6babcf73340c5aa5987a128ae1d76e6092ce1def653814af01bf**.
- Existing support receipt **01bb0f6efb04c706e594acb8c63759ee682e4bce2f2062882015edff36d6ce91** and durable ACK passed before/after readback. **No support installation, copy, receipt replacement, ACL repair, journal reset, deletion or recreation.** Original support intent/receipt/ACK, application receipt/ACK journal and selector revision-1/revision-2 files retained identical SHA-256 hashes.

The application and support remain at their previously reviewed D:-resident paths. Native machine identities and detailed process evidence remain private.

## Selection and rollback receipts

The verified initial state was revision 2, selected null, head:

**a83f5c2f1cf8d6ee4c2932802e9547d5b298e076e9da86de9c534b76cf5b76cf**.

The existing reviewed selector appended **SELECT revision 3**, selecting only the exact application, head:

**1ccea9013a9785feb770332bb7cd4477ac6f3892fa300c4bead10566f8e34b9e**.

After refusal, the reviewed general `ReleaseSelector.change` rollback appended **revision 4**, restoring the verified earlier revision-2 null target. It did not use the initial-selection-only `BASELINE` convenience command. Final native readback returned selected null and head:

**bdfe3b9a58605667dbf3a1b74b035236c196445697759cc82cd9124e22f7a419**.

**Final state: UNSELECTED; four immutable records retained.** No historical record was removed or renumbered, and support remains installed.

## Actual Open, browser and Stop results

| Check | Actual result |
|---|---|
| First genuine installed PowerShell adapter Open | READY accepted; exact image, creation identity, release/head and installed origins verified |
| Provider/writer/trading/autostart flags | All false |
| Six original HTML routes | All 200; same-origin browser connection policy present |
| Selected-account GET | Cash and positions null; startup authorization false |
| Financial/command POST | 403 |
| Genuine browser | Original alien-themed hub, Perp cockpit, Quality Dips and Selected PAPER Account inspected |
| Selected financial view | UNAVAILABLE; NO_ACCEPTED_FINANCIAL_ENROLLMENT_OR_INCEPTION; STOPPED / UNAVAILABLE_NO_FINANCIAL_RUNTIME |
| Browser acknowledgement | **27.3332249 seconds** after wait start, within unchanged **45 seconds**; exact cycle/host/head bound |
| First normal Stop, adapter | **0.591364 seconds**, closed true, financial actions zero |
| First normal Stop, outer observer | **0.6167427 seconds**; below eight seconds |
| Post-Stop resource check | **REFUSED** — Windows CIM reported two State=2 rows on the test port |
| Second Open / second Stop | **Not attempted / no timing** |

The test-owned browser tab closed before acknowledgement. Screenshot/accessibility evidence in this execution shows the original interface and financial-unavailable state. No populated current-market or financial-account acceptance is claimed. This exercised the genuine installed Control Center-facing PowerShell adapter, not desktop-shortcut retargeting or a separate interactive WinForms acceptance.

### Separate timing evidence (UTC, 2026-11-02)

| Stage | Timestamp / observation |
|---|---|
| Browser tab preparation requested | 12:53:40.645119 |
| Test tab prepared | 12:54:00.469010; prepared before bounded application execution |
| Outer controller launch requested | 12:54:51.484195 |
| Actual installed controller process start | 12:54:52.1334236, obtained from native process creation time |
| Application READY returned | 12:55:14.3330813 |
| Harness observed READY | 12:55:14.3522244 |
| Browser acknowledgement wait started | 12:55:14.4442705 |
| Browser navigation requested | 12:55:23.0792425 |
| Financial view render observed | Before 12:55:41.7772251; accessibility/screenshot preceded tab closure and acknowledgement |
| Browser acknowledgement written | 12:55:41.7772251 |
| Harness observed acknowledgement | 12:55:41.8084452 |
| Scheduled 45-second wait ceiling | 12:55:59.4442705 equivalent; **timeout did not fire** |
| Stop completed, PowerShell adapter | 12:55:42.4202909 |

Monotonic timestamps, rather than UTC subtraction, governed acceptance. Navigation-request to render/ack marker was **18.6985566 seconds**, including browser interaction and observation. The renderer's independent first-paint timestamp was **not captured**: the render/ack marker is a verified upper bound after observation, not a fabricated precise paint measurement. The pre-run tab-preparation interval also includes orchestration work and is not a browser-engine launch benchmark. These timing limitations remain explicit.

## Cleanup finding — not a passing port-release result

The reviewed Stop returned a verified financial-isolated close within eight seconds. The supervisor subsequently verified **zero owned Job processes**, closed the Job/worker handles and used **no forced termination**. A read-only closing Atlas executable-path roster found **zero Atlas processes**.

Nevertheless, the immediate CIM TCP audit reported two State=2 rows. A subsequent read-only query exposed rows with owner PID 0 and changing numeric states. Independent native `netstat` also reported a **LISTENING / PID 0** row on the same port, alongside residual TIME_WAIT/CLOSED rows. **The port is not proven released.** Absence of owned processes cannot override that socket evidence. Its origin and whether it represents a residual kernel/provider state or another cause are **UNRESOLVED**. No unrelated process was terminated and no networking setting was changed.

There is also a confirmed orchestration defect: the audit raised after the first Stop had already succeeded, but the cleanup branch still retained the old READY state and attempted another Stop. It then encountered `INSTALLED_READINESS_PIPE_REFUSED`, closed its outer process handle before collecting that process's return code, and emitted a `Popen` finalization WinError 6 warning. The outer orchestration-controller final exit code is therefore unavailable; it is not inferred as zero. This error does not erase the earlier accepted application Stop or the later zero-process Job observation. Handle finalization and exact-once Stop state handling need an offline harness correction before another native acceptance attempt. The executed harness and failures remain unchanged as evidence.

**No full process/port/handle-cleanup acceptance and no two-cycle pass are claimed.**

## Limits and regression evidence

The single bounded native session, including rollback, ended in **95.4885676 seconds**, below 600. Immediately before supervisor-result publication its conservatively monitored declared scope contained **72 entries / 1,813,117 logical bytes / 2,108,029 accounted bytes**, below 8,192 entries / 67,108,864 bytes. This includes existing monitored support/control/selector entries, not just newly created entries. The selector added only the four aliases for two complete immutable record pairs. Later read-only diagnostics, fixture regressions and documentation are separately identified; the native-session timer is not represented as a whole-machine write audit.

- Existing focused fixture suite: `test_support_deployment.py`, `test_release_selection.py`, `test_installed_nonfinancial_launcher.py`: **162 passed / 0 failed / 0 skipped, 11.50 seconds**, normal Windows-user process. These are fixture regressions, not another operational Open session.
- The initial confined execution is retained separately: **137 passed / 25 failed / 0 skipped, 12.62 seconds, one thread warning**. Its failures were 24 denied synthetic hardlinks (WinError 5) and one denied synthetic localhost socket (WinError 10013). No validator was relaxed; the same suite passed in the normal Windows context.
- Operational acceptance: **one bounded session refused after first Stop; zero complete paired-cycle acceptances**. No native re-execution followed.
- Six confined Python orchestration files and three PowerShell files parsed before execution. No pinned product/support source was changed. The unrelated research test and all untracked evidence/backups were preserved.

Raw native identities, helper claims, controller timing, port records, original result/error, hashes and regression logs remain private in `D:\Work\Project Atlas\logs\diagnostics\qd-installed-nonfinancial-acceptance-v1-20261102`.

## Next work and authority boundary

1. Eligible source-only work: correct the harness's post-Stop state transition and handle-finalization error with offline fault tests; record independent render-observation and acknowledgement stages. Preserve this executed harness and its original refusal.
2. Before another launch, resolve the TCP cleanup discrepancy with a separately scoped bounded read-only Windows socket/ownership diagnostic. Do not assume PID 0 authorizes any process or service termination. No Windows configuration change is justified by the current evidence.
3. Any further installed Open requires a **new acceptance-only authorization**. Its preflight must use the actual **revision-4 UNSELECTED head**, existing unchanged support receipt and complete journal, fresh clock and all original checks; preserve 45 seconds, eight seconds, 120 seconds / 96 attempts and global limits. Do not reuse the consumed grant, reinstall support or reset selector history.

Financial enrollment/activation/current custody, accepted current research and executable entitled IEX observations, financial Stop/restart and the supervised PAPER pilot remain separate and unaccepted. No financial accounts, providers, orders, retained journals, credentials, Windows settings, shortcuts, autostart or Genesis resources were activated or modified. **B1/C1/D1/E1, all 21 decisions and seven phases remain unchanged. PAPER startup NO; production NO-GO.**
