# QD final commissioning preparation — October 30, 2026

Base `a16c24fea48a9c7d9e84c716ea91b1ddab889bbb`; existing personal sole-operator policy, 21 historical decisions and seven phases preserved. No operational promotion, provider connection, financial account initialization, PAPER startup or Genesis action.

## Clock: measured variability, unchanged refusal

One bounded read-only diagnostic made **three native acquisitions in 30.421 seconds**, within its 90-second/four-acquisition ceiling. Same signed Windows tools and actual wall/QPC timing as the operational clock. No source, service, startup, synchronization, registry or clock change. All unchanged validator results refused: **1,867 / 1,874 / 1,812 ms** against **1,000 ms**. No operational clock capability was constructed from those failed samples.

| Component, milliseconds | Sample 1 | Sample 2 | Sample 3 |
|---|---:|---:|---:|
| Root dispersion |890.1957|890.1957|867.4196|
| Half root delay |15.8914|15.8914|15.8914|
| Absolute phase offset |819.2015|819.2015|804.6400|
| Measured wall/QPC skew |0.0364|0.0099|0.0090|
| Fixed margin |1|1|1|
| Drift over sync age |19.3123227|26.61605245|2.0938044|
| Drift over 240-second validity |120|120|120|
| Drift during acquisition |0.41863455|0.2139633|0.2079417|
| Rounded unchanged bound |1867|1874|1812|

Windows reported Leap 0, Stratum 5, Last Sync Error 0 and `time.windows.com,0x9`. Samples 1/2 share the last sync at **01:14:04 Central**. A normal update at **01:15:08 Central** occurred before sample 3: sync age fell from 53.2321 to 4.1876 seconds, dispersion fell 22.7761 ms and phase offset fell 14.5615 ms. Those changes explain the observed drop; no Atlas-triggered resync occurred. Acquisition durations were 0.8372691 / 0.4279266 / 0.4158834 seconds. Their uncertainty contributions are fractions of a millisecond, not the whole query duration.

The final sample's dispersion plus absolute offset alone is **1,672.0596 ms**. Even zero collection skew/age and removing the validity reserve would not make that sample meet 1,000 ms. Timing the query differently is not a legitimate remedy. The older accepted 915 ms cut had 406.9535 ms dispersion and 338.3635 ms offset; it was a different, now-expired Windows synchronization cut. The intervening 1,837 ms error-only record has no retained raw term breakdown and is not retroactively reconstructed. These observations establish which measured terms vary, not a unique remote-server, network, oscillator or hardware cause. Synchronization status alone remains insufficient.

Current disposition: **CLOCK REFUSED**. Normal Windows quality must improve and a fresh actual runtime acquisition must pass; any service/configuration/source correction still needs its own permission. No threshold change, offset-only declaration, shorter fake anchor or synthetic substitute.

## Implemented nonfinancial native research archive

`scripts/observation_runtime/personal_research_archive.py` fills the existing `QualityDipsSourcePublication` archive storage port using **the existing `NativePersonalCoordinationImages` protocol**, not another financial engine or custody registry. Its payload is a separately versioned JSON research image; it cannot adopt the financial SQLite image. It binds account, epoch, source, release digest/commit and native root identity to an explicitly accepted enrollment and authority.

Construction creates no directory, schema, initial state, key, grant or account. `initial_image` is a pure empty-source recipe; an explicitly authorized installer must separately initialize an accepted nonfinancial resource. Reads reuse native identity/ACL/namespace/predecessor/ACK checks and do not publish. The source archive accepts only the current expected pin, revision and exact packet; publication requires a scoped injected authority lease before effects and after ACK. Stale/future packets, missing custody, changed release/resource, foreign schema and malformed/oversized evidence refuse. Known pre-effect capacity/CAS refusal preserves the last readable cut; ambiguous effects or authority loss after publication retain the existing durable UNKNOWN latch, with no repair/retry API.

One adversarial test initially reproduced an unnoticed extra acknowledged native image with unchanged logical source revision. The correction binds every returned source pin to its **native revision, ACK and head**, enforcing native revision = logical source revision + one initial image. A nonparticipating native write now refuses instead of masquerading as the same research cut. The original red result is preserved in `logs/diagnostics/qd-final-prep-native-revision-repro-v1.txt`.

The original source producer round-trips its candidate bundle through this port and leaves the fixture financial ledger unchanged. No candidate score, V3 margin, valuation method, market quote, manual/strict contract or financial risk rule changed. Existing `SourcePublication` authority checks still authenticate research provenance and the current cut. **This storage adapter does not supply those authorities.** A coherent cold rollback test explicitly requires an independently supplied accepted current cut; same-user local hashes are not independent anti-rollback protection. The sole operator may own that personal custody mechanism; no external reviewer or committee is introduced.

Capacity remains **128 native images**, of which initialization consumes one, leaving at most **127 source publications** per enrolled resource, possibly fewer under existing byte limits. History remains immutable in prior native images. There is no rollover, reset or operational capacity expansion. A pilot must budget actual source publications and stop admission before exhaustion; longer operation still requires accepted continuation/capacity handling. This does not claim indefinite autonomous readiness.

## Tests and actual native evidence

- **419 relevant regression cases passed, 0 failed, 0 skipped**, 17.16 seconds, one existing Starlette/httpx deprecation warning. Includes source publication, source archive, native image memory protocol/page reuse, IEX/clock/current research, original research-only scanner, SEC original filings/exhibits, historical earnings valuation, dashboard read composition, release modules and accounting/restart preservation.
- **8 final genuine native cases passed**, 1.12 seconds: read/reopen without writes, two competing publishers with exactly one acknowledged successor, four interrupted publication stages with persistent UNKNOWN and cold-reopen refusal, missing custody without mutation, and a nonparticipating native image write rejected by the revision mapping.
- **427 distinct final passing pytest cases**, 0 final failures/skips, including **32 new cases** (24 offline + 8 native). Earlier 21/22/24 focused and seven native passes overlap and are not added. The reproduced red revision case is retained; no assertion was weakened.
- Native tests used only two fresh synthetic diagnostics roots `qd-research-archive-native-final-prep-v1` and `-v2`, each guarded at **180 seconds / 2,048 entries / 32 MiB**. Owner/SYSTEM permissions apply only to new fixture children. Total **145 entries / 31,978 bytes**; required evidence retained, no files deleted and zero bytes recovered. Native handles/mutexes closed. No process, provider, actual account or retained financial journal was needed.
- Existing isolated candidate reverified **read-only**: all **10,203 files / 903 directories**, native identities/ACLs/hashes/namespace, **4.890 seconds**, zero retained handles, zero child launch or mutation. Its source commit remains `2b9ba32a683b62933f29d3b52777a21753e50631`; this source increment is not silently installed into it.
- Prior installed-candidate Stop timings 4.372/4.292/4.764/4.446 seconds, browser refusal states and two Uvicorn cycles remain valid in their original synthetic scope and were not rerun without a relevant change. Actual operational Control Center acceptance remains pending.
- Ruff, compilation, source policy (640 files, zero issues) and preservation checks accompany publication. All prior 299-case and partial-acceptance evidence remains preserved; no production/startup authority follows from static checks.

## Current research and executable IEX: exact remaining inputs

Historical SEC Company Facts/original filing/exhibit/share-basis and approved historical earnings-multiple provenance remain unchanged and regression-covered. No new live research result or current valuation was acquired in this increment. Yahoo stays disabled; no FMP or paid source was introduced. The actual read-only scanner and IEX research ASK-reference binding remain implemented. A research ASK reference is not a fill or L1 financial admission.

An accepted current producer must still supply the existing `research.read_current()` envelope: original ranked board, forward observations, verified instrument mapping, original quote evidence, accepted ranking publication identity and current monitors. `QualityDipsSourcePublication`/`NativePersonalMarketInputs` retain their existing provenance, freshness, candidate and executable-price checks. The historical observation collector must **not** be called as a shortcut: `prospective_evidence.collect_board` also mirrors legacy financial PAPER records. No legacy collector, scanner background task, mutating research GET or financial writer was started here.

Actual source-root enrollment and its authority/head/lease bindings are **not installed or accepted**. Proposed separate nonfinancial root is `D:\AtlasCustody\QualityDips\<existing-private-epoch>\research-source`; it was not created. Exact native IDs and accepted release/account/epoch/source mapping must come from authorized provisioning, not this proposal. The archive authority must verify that context, the scoped publication lease and accepted current high-water; the source authority must verify actual scanner rows, original research timestamps, valuation/filing/price provenance, provider rights and the current ranking generation. Interface-shaped objects or synthetic test verifiers are not operational authority.

Executable IEX additionally requires the actual permitted connection, authenticated subscription **and actual fresh quotes**, instrument/fractional/round-lot mapping, session/calendar/halts, spread/size/participation and unchanged clock validation. No provider was contacted. The market was closed during these checks. Old observations and zero trades are not substitutes for current accepted inputs; a healthy current monitor may legitimately produce no eligible entry.

## Operational promotion preparation and boundary

The retained candidate remains isolated and unselected; the active `fca29cfe...` release, desktop shortcut, real financial roots, credentials and startup locks were unchanged. The new archive module is an explicit **one-module runtime delta**, so a future operational inventory must include it with the existing reader/writer pair. No prior receipt is relabelled for new code.

Prepare the expanded tracked-only source selection and its pins after the source commit; build only a new reviewed archive, not another installed clone. A future authorized immutable promotion must create a new absent `D:\AtlasRuntime\releases\<accepted-source-commit>` child using the existing D-resident interpreter/dependency pins, native creation handles, exact protected ACLs and complete independent readback. Preserve the active and previous releases. Failure or partial copying means retain evidence and withhold selection, never repair/adopt/reset. Rollback must not downgrade unreadable V2 data or reset financial custody.

Actual Control Center launch must inject the accepted read bridge and PAPER session into `Atlas-Background-Controls.ps1`. Default invocation still refuses. Reuse normal `SHUTDOWN_FLATTEN`, accepted writer/process ownership, final report/ACK/drain and exact owned close; no blanket-True callbacks, name/port kills, automatic restart or financial POST. Genuine operational authority/clock/session/current-resource checks and installed complete Stop must pass within eight seconds; the earlier synthetic timings do not prove that actual composition.

Remaining boundaries: fresh <=1,000 ms clock; authorized current research/source custody and executable IEX; explicitly permitted new operational resource/release enrollment and promotion; real Control Center/dashboard/Stop/restart acceptance; then separately authorized eligible once-only $1,000 simulated inception and one bounded 60-second pilot. Current directive grants preparation, not those actions. PERSONAL_PAPER_ONLY_V1 remains operator-controlled. B1/C1/D1/E1 and all 21 historical decisions unchanged. Seven-phase status: core reliability/evidence work ACTIVE (1/2); research/cross-market expansion deferred (3/4); future SaaS/institutional/commercial phases preserved (5/6/7).

**Engineering increment VERIFIED; source authority/custody/current data UNENROLLED; active promotion NOT EXECUTED; financial inception NO; PAPER startup NO; Production NO-GO.**
