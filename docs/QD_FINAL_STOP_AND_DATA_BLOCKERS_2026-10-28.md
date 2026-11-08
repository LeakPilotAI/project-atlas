# Quality Dips final Stop/data acceptance — October 28, 2026

Source base: `ade5e2db9012c0edbd13a08c8adc2f515cb75b9b`. Branch: `chatgpt/atlas-rebuild-v1`. Existing conditional sole-operator QD commissioning authorization is preserved and its financial pilot remains unused. No new reviewer chain or gate acceptance is introduced.

## Source repairs

1. Fixed the actual graceful shutdown reader: it used the epoch as the account ID even though the selected operational account now has a separate stable ID. Normal and failure readbacks now bind the exact runtime/reader account and epoch and verify the financial manifest's epoch. Conflicting identities refuse without retargeting or inventing a flat position.
2. The commissioning driver now measures monotonic elapsed time across its Stop work and post-Stop authority verification. More than eight seconds refuses successful commissioning even if a synthetic/session clock has not yet expired. A genuinely acknowledged flat position and its cash remain visible; timing failure is `SHUTDOWN_INCOMPLETE`, not a fictional reversal or UNKNOWN financial effect. Repeated invocation cannot replay the pilot. This measurement does not claim external installed-process exit acceptance.
3. Removed repeated loading of report-verifier code. Only executable module loading is cached; financial bytes, current pins, identities, ACLs, replay, arithmetic audits, namespace and freshness checks are never cached or omitted by this change. Measurement did not establish a material timing improvement.
4. Disabled PowerShell progress chatter only inside the clock's diagnostic subprocess so the underlying service error is visible. No Windows clock, source, service or startup configuration changed; the one-second validator is unchanged.
5. Corrected the synthetic research fixture to issue metric timestamps at its explicit simulated observation time. After UTC midnight its previous use of wall-clock timestamps correctly triggered future-data rejection. Price/accounting assertions are unchanged.

## Real native shutdown evidence: eight-second acceptance FAILED

The earlier 6.875-second measurement omitted the actual runtime admission/current-cut/read/report orchestration. New disposable runs exercise `flatten_and_stop`, the operational native codec, real native writer leases, current custody, selected-reader replay/report verification, final ACK, runtime Stop, writer drain and final native readback. Operator/session/market/clock authority is explicitly synthetic. These runs neither install nor authenticate an operational release or execute the real installed Control Center/process closure. They provide a **lower bound**, not full installed lifecycle acceptance.

| Retained run | Native financial coordinator | Final acknowledged readback | Combined lower bound | Eight seconds |
|---|---:|---:|---:|---|
| J | 13.219 s | 2.922 s | 16.141 s | FAIL |
| K, instrumented | 12.078 s | 2.828 s | 14.906 s | FAIL |
| L, verifier-code reuse | 12.062 s | 2.891 s | 14.953 s | FAIL |

K/L profiling shows three current captures, fourteen native replays, eight selected reads and three selected verification calls. L inclusive timings: current captures 7.269 s; native replay 4.405 s; selected reads 6.160 s; selected verify 2.353 s; two report publications 0.654 s; two drains 0.070 s. **These are nested inclusive measurements, not additive.** Repeated coherent-cut validation is the main engineering target. Removing security checks, weakening the reserve or promoting the 6.875-second subtotal would be incorrect. A reviewed optimization must preserve immutable source/projection/report evidence, before/after custody, native identity/ACL/namespace checks, independent arithmetic and all UNKNOWN refusals.

All three native runs passed financial correctness/restart assertions: synthetic ending cash $1,015.9136; zero remaining quantity and remaining entry costs; 3 financial events, 4 reports, 36 coordination revisions, 114,688-byte image, 253 entries and 3,250,493 bytes per run. Exact retained reader children independently reopened the immutable account, refused writer rebinding, exited normally and left original hashes unchanged. There was no new financial session or operational account. Passing those assertions **does not** pass the timing criterion.

## The previous 97 unexecuted cases reconciled

Collection/fixture inspection establishes the exact prior gated inventory:

| Suite | Previously gated cases | This execution |
|---|---:|---|
| Autonomous native publication/replay | 23 | 23 passed |
| V3 runtime | 25 | 26 passed including one previously passing default-refusal case |
| Staged native read-only HTTP | 8 | 8 passed |
| Continuous runtime HTTP | 3 | 3 passed |
| Native enrollment/fixture rejection and V3 wrapper | 10 | 10 passed |
| Older synthetic V4/V5 binding path | 28 | NOT EXECUTED under the excluded V5 scope |

Thus **69 of the previous 97 gated cases are now executed and passed; 28 remain unexecuted**, not promoted to PASS. The older binding file contains 29 definitions; its default-refusal case was already executed. The 28 remaining cases are neither a new personal administrative prerequisite nor a waiver of the actual selected personal native path's required acceptance. This increment's real personal native tests cover that path's source/read/custody/accounting; complete installed timing still fails.

The first four groups ran 60 tests in 43.765 seconds overall, using 7 newly confined roots, 798 entries and 3,372,482 bytes. The enrollment group passed 10 tests in 1.33 seconds. Four exact test-owned loopback hosts exited through retained ownership/EOF, with port-release assertions; GET hash-preservation, forbidden legacy research GET/financial POST, wrong Host, disconnection and restart refusal passed. No retained-history host was started. No genuine browser acceptance is claimed in this increment.

Changed operational codec compatibility: **14 passed, zero failed/skipped, 2.48 seconds**. Final source/account/Stop/clock/research regression: **184 passed, zero failed/skipped, one dependency deprecation warning, 8.21 seconds**. These selections overlap prior evidence and must not be summed as new distinct cases. J/K/L are three executions of the same extended native case, not three distinct cases. Initial fixture failures (reused L1 sequence and future-dated synthetic research metrics) remain in retained artifacts/transcript; both were fixed without weakening assertions or production validation.

All 13 native/HTTP/codec evidence roots total **1,842 entries and 13,956,434 bytes**, below the stated test bounds. No reparse escape was followed. Test evidence is retained, not deleted. No unrelated process was enumerated or terminated, and no Genesis access occurred.

## Actual current-data and clock findings

- Local `config/alpaca.env` validation passed without printing credentials: IEX feed selected and trading disabled. **No provider connection occurred**, no entitlement was inferred, and no executable quote was obtained in this increment.
- Alpaca's current [Market Data API documentation](https://docs.alpaca.markets/us/docs/about-market-data-api) describes Basic IEX coverage for stocks/ETFs; that public product description is not authentication of this account's current agreements or live subscription. Actual account/feed rights, subscription and fresh quote evidence remain unverified. IEX is one venue, not NBBO; lot/share conversion, instrument identity, eligibility/fractional support, trading/halts status and execution rules still need accepted evidence.
- The existing fundamental/valuation/history acquisition uses `yfinance`/Yahoo. No accepted automated-source permission, authenticated current result or permitted alternative source was found in the active dependency path. Yahoo's published [terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html?ncid=mbr_idnedulnk00000001) state that automated collection requires express prior permission. Operator authorization does not itself supply provider permission. Exact missing scope: automated fundamentals, valuation and adjusted history acquisition plus permitted local derived research/display/retention. Do not invent that entitlement or fetch despite its absence.
- No accepted current native QD publication/archive, ranking revision/provenance, source evidence or instrument/execution-authority bundle is present in the current installed composition. The confined scanner and accepted-source consumer are code, not real current inputs. Old research, pure scoring results and IEX alone cannot be substituted for the missing publication.
- Existing calendar reported **MARKET_CLOSED** during these diagnostics (October 28 evening Central; UTC October 29). Normal October 28 core boundaries were 13:30–20:00 UTC, consistent with the [NYSE published core session](https://www.nyse.com/markets/hours-calendars). A calendar schedule does not certify symbol halt status or quote freshness.
- Fresh actual clock acquisition refused. Independent read-only Windows query observed **W32Time Stopped / Manual**, status-query error **0x80070426, service not started**. Earlier 298 ms evidence has expired. No service start, resync, source/startup change or manual clock adjustment was made. The required source remains unchanged in code; no new passing uncertainty is asserted.

## Exact remaining work and disposition

1. Engineering: optimize repeated native/current-cut work safely and prove the **whole** installed Stop, including real authority/clock, final session report, ACK/drain, owned process exit and final native readback, within eight seconds. The current lower bound already fails. Do not install/promote this as PAPER-ready or relax timing.
2. External/input evidence: provide accepted current research provider rights/results and the native publication/instrument/execution/current IEX evidence. The sole operator remains release authority; no mandatory committee or external signer is added. A permitted fundamentals/history source is required; no new paid service, subscription or provider was activated.
3. Environment: obtain fresh qualifying clock evidence with W32Time running under the existing authorized service policy, and regular market hours with actual fresh entitled observations. A service-settings/source/resync change is not implied.
4. After those gates pass, install a NEW immutable verified release preserving previous releases; bind real activation/resource/session/current custody; perform eligible once-only existing-epoch $1,000 simulated USD inception and readback; verify original dashboard/controls; execute the approved total 60-second pilot; reconcile, owned Stop and manual read-only restart. Never repeat uncertain publication.

Minimum remaining stages: one performance/native installed acceptance increment, current-data/enrollment evidence, then conditional installation/inception/pilot. A credible elapsed completion estimate cannot be given until the timing defect and permitted research source are resolved. The pilot itself remains limited to 60 seconds; longer operation is not authorized.

**SOURCE COMPLETE: NO. NEW INSTALLATION COMPLETE: NO. PAPER READY: NO. PILOT COMPLETE: NO.** Existing installed release remains `fca29cfe7760a28d2569b8b4b91ed1ea99804c3c`, inventory digest `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91`. No real activation, inception, account balance, provider quote or pilot is asserted. Original UI, protected financial state, seven phases and all 21 historical decisions are preserved. Production remains **NO-GO**.
