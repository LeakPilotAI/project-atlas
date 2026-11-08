# QD source planning and globally reserved shutdown increment

Base2716d645cdf525a21d98d2786d9e56026ef8a1f2, chatgpt/atlas-rebuild-v1.
UNIFIED_PERP_FINANCIAL_COMPLETENESS remains ACTIVE and incomplete.

## Actual engineering

QualityDipsUnifiedPlanner connects the existing IEXMarketObserver, IEXPaperQuotes,
source ranking/monitor reader and EnrolledQualityDipsWriter. Components and source
requests require explicit authenticated bindings. Original bundles/publication
revisions and original L1 evidence reach the existing V5 candidate, entry, risk,
partial and thesis-exit logic. Preview remains pre-effect; actual native and SQL
ACK semantics are unchanged. There is no scanner/provider refresh or default trust.
Only explicit healthy no-trade decisions return no proposal; UNKNOWN, authority,
stale source or invalid price failures refuse. No-signal scans do not consume V5
sequence slots. A stopped planner refuses before reading another candidate.

QualityDipsUnifiedShutdown closes local candidate admission and uses the existing
guarded engine/publication inside V5 action/admission leases. Each shutdown EXIT
requires global shutdown-exit verification and durable reservation before effects.
It never calls native store.execute in parallel. It checks ACKs, flat quantity,
current source/cash, complete session report and verified final drain. Emergency,
stale prices, missing authority, report failure, unknown commits or drain failure
remain INCOMPLETE. Actual CanonicalWriterLane checks the session report too.
No process-killing capability or operational dispatch was registered.

## Demonstrated report defect and repair

A stronger final report check reproduced an actual QD integration gap: the old
calendar report has an exclusive cutoff and CUTOFF_NOT_REACHED before day-end.
An exit at the current timestamp was absent from its cutoff inventory/cash.
It must not certify a current flattened shutdown.

The existing FS3 daily builder and independent auditor now support a separate
FS3_QD_REPORT_SCOPE_V2 with explicit ACKNOWLEDGED_EVENT_TIME_INCLUSIVE_CUT_V1
policy and FS3_QD_SESSION_REPORT_V1. This reuses existing event replay, independent
cash/quantity/cost arithmetic, immutable native report archive and publication.
The inclusive event cutoff is represented mathematically as cutoff+1 for the
existing integer-second arithmetic; observed clock is not advanced or fabricated.
Timezone/date, scope, source versions, ACKs and session boundaries remain checked.
Old scopes cannot publish this report and old calendar semantics remain unchanged.
No real account or scope is upgraded. A separately accepted session-report scope
is required for future operational QD global flatten acceptance.

The native fixture builders have an explicit opt-in for NEW disposable session
report roots. All existing defaults remain unchanged. Tests retain incomplete
calendar revisions alongside the current session cut and reject altered cash,
costs, counts, cutoffs, source heads and inventory through the independent auditor.

## Perpetual finding and source correction

Inspection confirms the legacy automatic resting-limit mirror imports the legacy
financial singleton and opens on mark-touch. It is not a source of canonical
executable spread or authenticated maker queue/trade-through evidence. It was
not imported, run or wired into the protected accounts. Manual planning labels
are not autonomous authority. Existing canonical perp arithmetic, native writer,
funding/mark paths, session reports and PerpShutdownCoordinator remain intact.

The actual manual-plan positive-number helper accepted NaN/infinity and could
produce nonfinite ladders. It now refuses those inputs before a plan exists.
Twelve source-input cases verify this without changing valid strategy filters,
prices, fees, risk or execution assumptions.

## Evidence and limits

Final actual counts are recorded in autonomous state. Tests use original IEX
parsing/cache, candidate/monitor policies, actual V5/FS1-FS3/native writer,
CanonicalWriterLane and unified global reservation/Stop. All quotes and authority
implementations are explicitly synthetic and confined to disposable roots.
The QD Stop counterpart perp lane is synthetic; this is NOT complete two-lane
strategy integration or operational acceptance. Genuine existing QD HTTP/owned
host tests run in the combined selection. No new real browser, WinForms Control
Center or complete two-lane native cross-process acceptance is claimed.

Final selections:622passed/0failed/1skipped financial/perp/report/startup/archive;
155passed/0failed/0skipped actual QD source/native/global-Stop/runtime/HTTP;
32passed operational QD codec/factory;30passed operational perp codec. Forty-seven
cases overlap the first two selections: **792distinctpassed,0failed,1skipped**,
not839distinct or a single combined run. There are33new cases and15additional
existing discovery/board cases beyond the prior selection. The skip is the
existing true-symlink Windows privilege1314 probe: NOT EXECUTED.

Retained failures include an initial receipt-field assertion, correctly refused
reused quote sequence with changed price, reproduction of the calendar-cut defect,
and a test assuming duplicate calendar publication appends another revision.
Fixtures/assertions were corrected to use canonical state revision, new quote
identity and immutable report deduplication. Safety assertions were retained.
Private diagnostics and native identities are excluded from publication.

Targeted lint/compilation, PAPER policy audit582files/0issues and archival
preservation are checked. The legacy perp planner has3 preexisting lint findings
before/after;0new findings. Original QD UI, startup lock and FS1 legacy golden
remain byte-identical. No physical power-loss or independent custody claim.

## Exact remaining work and first trial prerequisites

1. Install no authority yet. Complete authenticated actual scanner ranking/monitor
   publication and accepted reader bindings for the QD source port. Synthetic
   verifiers are not an operational issuer or current-ranking custodian.
2. Finish actual perp discovery/signal/resting-order admission and canonical
   execution routing, including durable pending-order identity, maker queue/trade
   evidence or an independently accepted alternative execution policy. Do not
   convert a mark-touch/manual plan into a taker fill. Bind funding/mark producers
   and both lanes to accepted global custody with separate USD/USDC accounting.
3. Assemble the existing PerpShutdownCoordinator and new QD global coordinator
   with the COMPLETE actual writer roster, final global drain and exact retained
   owned-process close capability. No accepted complete native roster exists yet.
4. Run genuine two-real-strategy continuous sessions, abrupt cross-process custody
   recovery, Windows lifecycle and Control Center acceptance. These remain
   engineering/acceptance work; current tests must not be substituted for them.
5. Obtain scoped B1 account/source/epoch acceptance, C1 actual writer/exclusion/drain,
   D1 personal-profile issuer/custody/clock/resources/recovery acceptance, E1 provider
   rights/executable data and supervised release acceptance. Then separately
   authorize installation, isolated account inception and bounded launch. Only
   then begin the seven-day autonomous PAPER trial and collect daily reconciliation,
   data-continuity, restart and owned-shutdown evidence. The trial has not started.

All21 decisions/seven phases and protected directories preserved. No operational
providers, services, accounts, credentials or Genesis access. D:-only/existing
account/original UI/PAPER-only. B1/C1/D1/E1 BLOCKED;PAPER startup NO;production NO-GO.
Source work remains: this is not VERIFIED completion or an external-only wait.
