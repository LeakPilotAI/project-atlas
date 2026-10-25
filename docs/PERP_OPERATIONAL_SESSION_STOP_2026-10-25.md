# Perpetual operational codec, session reports and graceful Stop

Base: 9211bdac633c439da27bd27c82377204b8014960, branch
chatgpt/atlas-rebuild-v1. Source and confined disposable evidence only.
UNIFIED_PERP_FINANCIAL_COMPLETENESS remains ACTIVE: actual two-strategy assembly
and operational acceptance are not complete.

## Implemented

- Distinct PERP_AUTO_NATIVE_ENROLLMENT_V1 validates the D:-only account, epoch,
  policy/inception/release commitments, six resource identities and seven writer
  roles, including funding and marks. JSON validity grants no authority.
- PAPER_EPOCH_PERP_OPERATIONAL_V1 is a separate calculation-parameter schema on
  the existing FS1 perpetual transition/replay and independent audit. It requires
  the explicit 1000 hypothetical USDC inception parameters and accepted provenance
  label; the label itself is not authentication. No fixture manifest is converted.
- OperationalPerpStore reuses existing FS2 publication with distinct operational
  inception, pin, intent, record, commit, ACK and reservation-ACK schemas. It requires
  authenticated admission, exact native identities, clock and current custody.
  Provisioning/default construction refuse. Test/QD/manual pins cannot be adopted.
  Stable read leases inspect native evidence without acquiring writer mutexes or
  publishing latches. Native writer guards require active admission.
- OperationalPerpFinancialWriter connects that cut to the existing unified writer
  seam. Both source admission and portfolio/component authority remain mandatory.
  OperationalPerpReportArchive/Service use distinct report pins/documents and a
  separate admitted reservation/ACK boundary. Report reads verify immutable history
  under both source and report custody, without writer locks or repair writes.
- FS3_PERP_REPORT_SCOPE_V3 explicitly opts into inclusive session-cut reporting;
  prior scopes retain existing semantics. The new FS3_PERP_SESSION_REPORT_V1 uses
  canonical events/receipts, independently audited cash, costs, funding, collateral
  and quantity inventory. An exit at the cutoff is included. Calendar reports
  remain end-exclusive and incomplete before day-end. Pending funding, missing
  projections or source advancement cannot certify a complete current session.
  Open holdings can have complete financial accounting, but no flat/valuation/
  process-drain claim is invented. Lifecycle remains NOT_EVALUATED.
- PerpShutdownCoordinator closes only acknowledged remaining quantities through
  UnifiedPaperRuntime.dispatch_shutdown_exit, using accepted fresh executable
  evidence and the same reservation/native ACK boundary. It publishes the session
  cut and requires independently verified drain. Long/short and prior partial exits
  use existing FS1 costs; emergency Stop preserves holdings. It never kills a
  process, connects a provider, settles invented funding or installs a startup path.
  Existing owned-process controls still require a complete accepted global outcome.

## Findings and validation

The generic report-service path could otherwise access a new operational store
outside its admission lease: the new store/archive refuse that route. Loss of
source authority after report ACK now retains cross-store UNKNOWN. A generic
BoundReader compatibility failure caused by missing new schema attributes was
reproduced and repaired with unchanged original schema defaults. Original failures
remain in private diagnostics. Two test setup errors (serialized event-envelope
fields and empty-account clock setup) were corrected without weakening assertions.

Final disjoint Python selections: **582 passed/0 failed/1 skipped**, **14 passed**
(existing QD operational codec), **30 passed** (new operational perp codec/report),
and **1 passed** (existing genuine loopback HTTP/read/owned-close compatibility).
Total **627 distinct passed, 0 failed, 1 NOT EXECUTED**. The skip is Windows
true-symlink privilege unavailable (1314), not PASS. New cases: 53 across three
files. Focused 10/13/23/25/26 runs overlap and are not added.

Existing shipped frontend VM/DOM/fetch suite: **40 passed/0 failed/0 skipped**;
three Windows Control Center/read-only/shutdown module parses passed. Ruff,
compilation, policy and diff/preservation checks apply to changed files. The
static PAPER audit inspected 580 runtime files with zero findings. No new real
browser, WinForms-click, provider, Genesis-coexistence, seven-day soak or physical
power-loss acceptance was executed. The existing HTTP regression does not prove
the new operational perp financial account is connected to the dashboard.

## Unfinished and unaccepted

Actual QD V5 and actual perpetual strategy planner must still share pre-effect
portfolio reservation/custody and acknowledged financial cuts. The QD accept path
currently decides and persists inside its own runtime; a proposal-only synthetic
lane is not an acceptable substitute. Existing strategy filters and actual market
evidence must be retained. Continuous two-lane/native cross-process/HTTP acceptance
and owned Windows lifecycle assembly remain unfinished.

No issuer, current-pin custodian, clock, provider right, perpetual leverage/fee/FX
policy, source completeness or actual ownership is accepted by these tests. Local
hashes do not establish independent rollback custody. Cross-margin top-ups,
bankruptcy/backstop simulation and unobserved maker liquidity remain unsupported
and refuse. Original UI, legacy financial evidence, protected 13 directories,
strict/manual contracts, seven phases and all21 historical decisions are preserved.
B1/C1/D1/E1 BLOCKED. Neither hypothetical inception was published.
PAPER startup NO; production NO-GO.
