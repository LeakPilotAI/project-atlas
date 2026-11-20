# R14 version-specific native selector compatibility — source-only gate (2026-11-10)

## Terminal result and authority

**SOURCE-ONLY SELECTOR COMPATIBILITY IMPLEMENTED AND TESTED.** R14 native code was already successfully installed and physically verified, but R12 remains selected. This change makes R14's newer verified-before-publication journal eligible for the existing NativeInstalledReleaseVerifier, and introduces a separate R14-specific independent-two-peer-NTP code-selection profile. **NO ACTUAL CODE RELEASE SELECTION, FINANCIAL PAPER/PROVIDER ACCESS, SERVICE START, NATIVE INSTALLED-FILE RESCAN, OR REAL SELECTOR MUTATION** was attempted or authorized.

Exact installed R14 source: `7ff9d3dba2eabe110f843c13efac49464805de2a`. Native installation receipt SHA-256: `4cbf4f78c4da879f0e7d35f7ab1c3e119b4e0e7fc04640f0984ad4c8ce912ba7`. Original verified native-file artifact digest: `da64e2436d23fc2e3aa7ea14888e3fa0429bea801b83886c181ec3a72fd16fa8`.

## Implementation

`scripts/release_selection.py` retains all historical `WINDOWS_LOCAL` and `DISPOSABLE` schema, immutable-root/receipt, locked-selector head, dedicated owner, and installed native runtime re-read requirements. New pure `validate_native_install_ack()` supports **exactly one** R14 native release and retains the legacy final-journal protocol for every other release.

- For the exact R14 source, the file receipt must match the pinned R14 receipt SHA and artifact digest; native receipt stage must be `D_RUNTIME_LAYOUT_VERIFIED`, pinned archive/inventory hashes must match, and it must contain exactly **10,519 native files and 912 directories**.
- The R14 installation journal is read by the existing safe `source_bytes` admission with a tight **4096-byte** maximum. It must have **exactly two** duplicate-key-free JSON rows: the first is the source/target-bound `ATLAS_R14_UNSELECTED_LOW_IMPACT_CODE_INSTALL_INTENT_V1` with false selection/financial/provider permissions, and the second is `NATIVE_READBACK_VERIFIED_FINAL_RECEIPT_PENDING` with the pinned native-file digest and false selection/financial permissions. A pending marker **alone never proves installation**: the separate pinned fully verified final native receipt and `NativePersonalReleaseIdentity` plus independent `installed_readback` remain required before any selector publication.
- Older releases continue to require their preexisting final `UNSELECTED_CODE_INSTALL_VERIFIED` ACK with exact receipt SHA; their original journal read budget remains unchanged. Read-only inspection of only the last 1024 bytes of R12's existing ~50 MB journal confirmed its terminal legacy ACK is **still valid**. No old-file migration, deletion, rewrite or large history read.
- The existing `INDEPENDENT_TWO_PEER_NTP_CODE_SELECTION_V1` remains **V7-only**, including the previous error pin. The new opt-in `INDEPENDENT_TWO_PEER_NTP_R14_CODE_SELECTION_V1` accepts only the real `IndependentNtpClock` and a `SELECT` target with the exact R14 release/receipt/artifact digest. R14 is explicitly **refused** via the legacy Windows-clock profile or historical V7-only NTP profile. The prior `ReleaseSelector.change(grant,approved=True)` explicit grant and current-head/unique-operation, native store lock, original native verifier, and owned clock checks are retained; none of them were invoked with the actual operating store during this work.

## Executed verification

Single idle-priority Windows Python runner: `tests/test_release_selection_r14_compatibility.py` plus historical `tests/test_release_selection.py`; **87 passed, 0 failed/skipped, 17.20s**. Synthetic tests cover actual pinned R14 receipt + two-entry journal read-only parsing, 17 malformed/tampered/expanded journal forms, receipt/source/digest pin loss, old ACK compatibility, and **intercepted** `NativeInstalledReleaseVerifier.open()` that never opens or scans any real native installed-file handle. In-memory fake selector tests confirm R14 old Windows/V7 NTP refusal, exact-only R14 profile, explicit approval requirement, and one **synthetic in-memory selection** with no native selection store/write.

Checked current selector metadata read-only: existing selected revision 12 is `2d4879878bf58bea5a3ed0a986b809791f638fec`, R12 selection receipt SHA-256 `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`. The R12 journal tail (131 bytes) matches historical ACK; only the tail was read rather than its ~50 MB body. R14 remains installed but **unselected**. Its one-shot installation approval is permanently revoked.

## Genuine next gate

A distinct **R14 code-only selection proposal** must pin the exact current R12 selected-head digest, native selector resource identity, R14 receipt/source/archive/digest, code-eligibility implementation hash, fresh 180-second independent two-peer UTC continuity, and bounded installed native re-verification. A **new operator one-time approval** must be obtained to make that code-only selection. That permission must not include activation, PAPER/live orders, provider/account access, or unattended startup. R14's installed native target is permanently occupied and must **not** be recopied.

Even when R14 is selected as the nonfinancial code release, supervised Quality Dips/Hyperliquid source and financial PAPER runtime commissioning is a separate workstream. **Formal financial PAPER operating gates: NO-GO, 0/9 independently accepted**. No Project Genesis edits, Windows boot/time changes, paid data/VPS, trade, GitHub push, or cleanup occurred.
