# Unified native writer and perpetual financial contracts — 2026-10-25

Base: 16e9d05cbe80419d3d9ba07e65b9d92d6ad3ccc0. Branch:
chatgpt/atlas-rebuild-v1. SOURCE/DISPOSABLE evidence only. The complete
UNIFIED_PERP_FINANCIAL_COMPLETENESS task remains ACTIVE, not independently accepted.

## Implemented and exercised

- Existing FS1 transition/replay and independent arithmetic audit now support
  separately versioned margin-entry/mark, IOC-entry, maker-fill, simulated book
  liquidation and late-funding recovery commands. Existing V1/manual/QD and base
  V2 financial record semantics remain unchanged.
- Pinned margin tiers use continuous maintenance deductions with explicit upward
  rounding to the accepted USDC quantum. Cash does not round to conceal a risk
  breach. New tier/maker entries reserve against the greater of executable and
  mark notional; reductions release the correct original margin basis.
- IOC partial entries fill only supported step-aligned quantity and durably cancel
  all remaining requested quantity in the same event/receipt. No latent order or
  automatic scale-in is created. Maker fills additionally require explicit rested
  order, queue-ahead, trade-through, size, clock, fee and cancellation evidence.
  Consumed maker order identities and trade liquidity cannot be replayed.
- Simulated book liquidation requires a verified mark/maintenance/equity trigger,
  executable side/quantity, fee schedule and execution reference. Regular fees,
  modeled slippage and additional liquidation fees reconcile independently. An
  unsupported backstop or negative-cash bankruptcy outcome refuses.
- Late funding recovery binds the exact preceding state, remaining quantity,
  hourly rate/oracle evidence, accepted clock and separate recovery authority.
  The old report scope keeps cross-day recovery INCOMPLETE. New explicitly enrolled
  FS3_PERP_REPORT_SCOPE_V2 separates posted cash from settlement-time accrual and
  unposted obligations; earlier reports remain immutable. A complete financial
  report never implies flat positions, current valuation or clean process shutdown.
- Existing native FinancialRecordStore supplies read-only verified-cut, preview
  and acknowledged-receipt access. These methods explicitly refuse operational
  codecs before handle access; they do not bypass existing operational admission.
- NativeFinancialWriter binds exact manifest, native root/head, canonical command,
  immutable operation identity and durable reservation. CanonicalWriterLane connects
  existing observer/planner/shutdown interfaces, without inventing a strategy.
  Component substitution, missing role authority and LOCAL_ENROLLED construction
  refuse. Special execution, margin and recovery require distinct verifiers.
- UnifiedPaperRuntime now coordinates FUNDING/MARK through the same reservation /
  native publication / ACK boundary. A paired accounting check cannot open, resize,
  remove or reverse positions, change collateral/fees or mutate the stock account.
  Entries retain their existing risk limits; adverse accounting is not new-entry
  authorization. Acknowledged retries read native receipts without invoking writers.
- Native-lane Stop requires durable global entry closure, complete writer drain,
  zero remaining positions and a current source-matching FS3 report. A lane's
  unsupported claim of flat/drained is insufficient. Missing reports, failed entry
  closure, pending effects, ownership substitution or uncertain ACK remain incomplete.
  Closure failure prevents shutdown callbacks. Restart never silently reopens it.

The actual existing FS2/FS3 source/projection/report interfaces were exercised with
explicit synthetic authorities and the existing disposable writer registry. The
combined IOC/tier/funding/full-exit/report/drain path passed, as did foreign-writer
interference, two supervisors, lost cross-store ACK, native retry and report refusal.
The fixture's USD/USDC conversion at 1 is explicitly synthetic, not accepted parity.

Primary maintenance reference inspected:
[Hyperliquid margin tiers](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margin-tiers).
Documentation and test identities are not provider rights or authenticated policy.

## Validation

Final relevant combined run: **559 passed, 0 failed, 1 skipped**. The skip is
NOT EXECUTED: Windows true-symlink privilege unavailable (1314). Separate disjoint
existing operational-codec regression: **14 passed, 0 failed, 0 skipped**.
Thus 573 distinct tests passed across those selections; earlier focused/intermediate
runs overlap and are not added. Six new test files contain 83 cases.

Targeted Ruff, changed-file compilation, static PAPER policy and diff/preservation
results are recorded in the private verification evidence. No new browser, native
WinForms, provider, 24/7 soak, actual Genesis-coexistence or power-loss test ran.
Existing alien UI, startup locks, seven roadmap phases and all 21 decisions remain
unchanged. No operational roots, accounts, issuer, keys, services or feeds were used.

## Still unfinished — not an operational completion claim

The new native writer explicitly supports DISPOSABLE_TEST only. It refuses
LOCAL_ENROLLED rather than relabeling FS2 test pins. A distinct operational perpetual
codec/enrollment and accepted current custody are not installed or implemented by
this increment. Generic planner/ownership/valuation callbacks are not actual scanner
or control-center acceptance. The two-supervisor test is concurrent native threads,
not a new cross-process global-registry acceptance; existing FS2 subprocess crash
tests remain relevant but do not prove exclusion of nonparticipating real writers.

Source work remains to connect the actual QD V5 runtime and actual perpetual signal
planner to one complete accepted-custody assembly, genuine two-lane continuous
financial/report/read-only HTTP acceptance, and the actual perpetual graceful Stop
coordinator. The native Stop proof currently requires a COMPLETE calendar report;
an earlier cutoff is explicitly incomplete until a separately reviewed session-cut
report policy is supplied. It must not be silently relabeled complete.

The reservation model is not authenticated exchange withdrawable collateral or a
cross-margin/backstop simulator. Missing real maker queues, historical settlement
oracles, applicable fees/tiers or bankruptcy evidence continue to refuse. Initial
leverage, notional, conversion and portfolio policy still require acceptance; the
stock $100 cap has not become perpetual exposure approval.

B1/C1/D1/E1 remain BLOCKED. Neither proposed 1000 USD QD nor 1000 hypothetical USDC
Hyperliquid inception was published. No protected account was initialized, migrated
or inspected. PAPER startup NO; production NO-GO. See the exact continuation; no
background process or autonomous continuation is claimed.

Final corrective finding: a historical COMPLETE report could have the current source head while its cutoff and cash were historical. The retained negative test reproduced a false STOPPED result. Native shutdown now also requires exact cutoff revision, current cash, epoch/policy/currency and no report positions. Final549 supersedes the intermediate548 run; neither is added to the other. An initial stale-revision test-setup failure is retained separately from the corrected failing reproducer.

Final read-only correction: verified-cut, preview and ACK receipt inspection never acquire the writer mutex or publish a latch. Three tests prove no abandoned-lock observation or financial file writes. Stable accepted pins are checked before/after immutable native reads; existing writer abandonment refusal remains intact. Final552 supersedes final549; no counts are added between overlapping runs.

## Subsequent shutdown dispatch repair

Ordinary dispatch correctly refuses STOPPING, but this prevented a future native
shutdown coordinator from using the same durable financial boundary. The new
dispatch_shutdown_exit port admits EXIT only during STOPPING after entry closure,
requires a separate custody verify_shutdown_exit check, and retains installation,
fresh observation, canonical reducing-risk, durable reservation, native ACK and
UNKNOWN checks. No regular strategy ENTRY/FUNDING/MARK is admitted by this port.
It does not install a coordinator, grant a session, publish a clean report or stop
processes. Actual native long/short exits after closure passed; missing/rejected
authority, stale price and lost custody ACK remain INCOMPLETE. No-report shutdown
remains INCOMPLETE even after a fully acknowledged exit; repeated Stop adds no fill.

Final combined559/0failed/1privilege NOT EXECUTED supersedes552;14 disjoint existing
operational-codec cases remain passed (573 distinct;83 new). Focused65 overlaps.
Two fixture-setup failures (missing manifest and under-reserved legacy SHORT)
were retained, then corrected using the explicit tier-margin model without
weakening risk assertions. Source work still remains exactly as listed above.
