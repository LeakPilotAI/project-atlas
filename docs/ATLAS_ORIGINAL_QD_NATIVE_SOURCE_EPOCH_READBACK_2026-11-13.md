# Atlas — original native QD source epoch readback (2026-11-13)

## Scope and outcome

This execution implements and verifies one real piece of the Quality Dips 127-publication reliability blocker: a typed **read-only predecessor/successor source archive link**, tested against genuine Windows native image handles in confined disposable storage. It also makes known archive capacity exhaustion a **pre-effect refusal** in the actual source publisher instead of attempting a native write and latching its unknown-outcome state.

**This is not a production epoch rollover.** It does not install/reselect a release, authorize a new source root, activate a financial account, commission an issuer, rebind the original PAPER reader, issue live or PAPER orders, or prove months-long continuity. Selected immutable R20 and the existing 12 empty original financial namespaces remain untouched.

## What was implemented

**1. `scripts/observation_runtime/personal_source_epoch_readback.py` (source-only, uninstalled)**

- `propose_link_readonly(predecessor, successor)` requires two actual `NativePersonalResearchArchive` ports with separate original native image roots and root IDs, shared account identity, selected release digest, source commit and clock, plus DIFFERENT source epochs and source IDs.
- Each source archive must read back its independently authority-verified native ACK and original identity. Before proposing a new epoch, the predecessor must contain at least one acknowledged source cut and the successor must contain **only its original initial image** (logical revision 0, native revision 1).
- A proposal binds the complete original predecessor head (including its original native ACK), root ID, source epoch/id, original account/release/commit and both original enrollment digests. No raw financial account secrets or provider keys.
- `verify_link_readonly(predecessor, successor)` requires the successor current original native image and `sources.epoch_link` to exactly match the verified predecessor head. This is checked at **each successor publication revision**, not only the first. It rejects missing or substituted epoch links, foreign account/release/source commits, root aliases, attempts to link before the previous first original publication, a successor without a genuine new native publication, rollback/changed original heads and a predecessor that continues publishing after the successor has linked to its old head.
- Original immutable successor replay guarantees all existing original native revision/ACL/ACK checks still run. The link verification does not allow a local digest to impersonate independent market issuer, authorization or custody. It always reports `market_issuer_independently_verified=false`, `operational_reader_switch_accepted=false`, `paper_startup_authorized=false`, `live_trading_authorized=false`.

**2. `backend/app/services/quality_dips_current_producer.py` pre-effect capacity refusal**

- For a genuinely new source cut, immediately before starting a native publication lease, the current producer calls the original archive's strict `capacity_readonly(horizon_seconds=30, publication_interval_seconds=30)` routine.
- It requires this read-only headroom to belong to exactly the source archive head it intends to CAS and to allow at least one additional original native publication. A known exhausted archive is refused with `QD_CURRENT_ORIGINAL_NATIVE_EPOCH_EXHAUSTED_NEW_ACCEPTED_SOURCE_EPOCH_REQUIRED` *before* any native financial/source write, lease attempt or unknown-state poisoning.
- An existing identical `input_revision` continues returning the already acknowledged original cut without extra native writes, subject to its existing exact freshness/issuer checks. A fake capacity report or changed head is a known refusal, not a new account/epoch.
- All other source issuer, current ranking, quote, valuation, monitor, and original archive ACK conditions are unchanged.

## Real tests, storage and limits

The `tests/test_personal_research_archive_native.py` suite ran with two genuine original Windows native image archives in the confined disposable D: test root. It covered original predecessor native ACK, successor genesis + first and second original native publications, complete successor epoch-link readback after restart, a changed predecessor invalidating its link, five foreign account/release/epoch/source mismatches, missing or fabricated successor evidence, attempted handoff with original predecessor still empty, and no write side effects from inspection. **19 passed / 0 failures**, and the complete temporary test root was removed after the test. Tests used synthetic approval ports **only within the disposable test folders**, never original financial roots.

`tests/test_quality_dips_current_producer.py` adds tests for fake exhausted capacity, forged logical head and contradictory within-epoch report: all refuse before original publication, never poison the existing native archive, preserve the old acknowledged source, and permit safe retry if actual independently verified capacity remains available. **127 focused tests passed** across current producer, source archive and owner scope; the broader relevant regression run is recorded in the final execution checkpoint.

The original 128 native revision / 127 publication cap is **unchanged**. At most 127 30-second publications cover 63.5 minutes; an uninterrupted 6.5-hour equity day needs ~780 source refreshes, and 90 days of 24/7 data would need 259,200. This bridge is a building block toward epoch rollover, **not** permission to start daily PAPER on an unimplemented rollover.

## Outstanding production integration

The operational path still requires:
- Authenticated original `QD_CURRENT_RESEARCH_VERIFIED_V1` input issuer, validated original valuation provenance, permitted data rights and truly current executable stock quotes. Today's synthetic test publisher does not supply these.
- Accepted source-epoch creation under original financial accounts with original native source installation authorization, distinct protected physical root/owner IDs, unchanged immutable previous root, original native source/Stop custody, and the exact issuer provenance bound into every successor cut.
- **Source-code publisher integration implemented, not installed**: `QualityDipsCurrentProducer` now accepts an optional exact original predecessor archive port, requires the two original archives' verified predecessor/successor handoff, carries the same link through `QualityDipsSourcePublication.publish_scanner` into original `sources.epoch_link` on **every** successor cut, verifies both original native source archives on read/reopen/next publish, and refuses reopening a linked successor without its original predecessor. Its independent publication authority STILL must authenticate the entire sources object. These changes are uninstalled workspace code, not R20 selected operational acceptance.
- **Actual reader switchover**: the original selected financial QD reader/Stop owner must atomically transition to the successor's new source ID and epoch with original reader high-water retained and fail-closed recovery across death/restart. It does not yet do this. A separate immutable selected release/code-only installation and independent market-session tests are prerequisites.
- Accepted Hyperliquid historical settlement/original fee sources, two original once-only simulated account inceptions, operator activation/readback and real financial Stop-first restart soak.

No change to original on-disk native format, no new financial archive in production and no paid market data. Keep all new source/test/docs under `D:\Work\Project Atlas`; preserve existing `D:\AtlasRuntime`, `D:\AtlasCustody` and `D:\AtlasPaper` native identities. Run approved Atlas-specific post-execution C: orphan-temp cleanup without deleting historic user evidence.

## Second execution pass — actual source-publisher link transport

Added an optional `predecessor_archive` port to `QualityDipsCurrentProducer` and optional `epoch_link` to `QualityDipsSourcePublication.publish_scanner`. The constructor requires an exact `NativePersonalResearchArchive` predecessor with the same clock but separate archive identity; its `_ports` guard retains predecessor instance identity for the entire source assembly. On the *first* successor cut, `propose_link_readonly` checks the original predecessor ACK and original empty successor genesis. On subsequent cuts, `verify_link_readonly` must read both original native heads and check the link in the current successor sources before any new original publication. On every successful publication, `epoch_link` is included in the original full sources payload passed to the independent original `verify_publication` authority and persisted through original native CAS.

The successor's original readback rejects missing links even if a different source producer is constructed with otherwise matching enrolled source details: `_archived_input` requires presence of original `sources.epoch_link` exactly when the bound `predecessor_archive` port is present. Without this, a restarted ordinary publisher could have silently dropped cross-epoch provenance. If the predecessor changes after publication, source read/restart/new input refuse before accepting additional published cuts. No fake rollover creates an operational grant or rewrites the old archive.

The new disposable tests use an explicitly **synthetic predecessor native facade** with the original exact Python class, and the existing synthetic native source archive for the successor. They prove first and subsequent link propagation, exact current-input revision, reboot-like new producer readback, capacity pre-effect refusal, missing-predecessor bypass rejection and no financial native effect. The separate 19 Windows-native tests verify the real original two-root image protocol, using confined D: scratch. **The combined two tests are not independent market issuer verification, a selected R20 installed release, an accepted source root in original financial custody, or an approved financial source-reader transition**.

The critical remaining code gap is original selected Stop-first financial ownership of an atomic cross-epoch switch (new native source/reader source_id, accepted activation and original financial account binding). It cannot be authorized by this uninstalled source-only bridge.
