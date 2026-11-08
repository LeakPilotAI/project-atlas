# Atlas V4 code-only native release selection verified — 2026-11-08

**Result: EXACT V4 CODE-ONLY SELECT PASSED + INDEPENDENT READBACK PASSED.** No financial PAPER activation, provider connection, launcher replacement, financial account inception or live trading is authorized by this decision. Canonical operational acceptance **0/9** remains unchanged.

## Approved scope and exact native change
- In this conversation the operator explicitly approved **code-only selection of the independently installed V4 candidate** `fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`. This was not authorization for financial Start, providers, support installation, shortcut rewiring or bypassing any gate.
- Before mutation, latest native selection was **revision 8**, selected `de437abe888a2d20746762a39402ae421417c1f6`, head `b72191583451f42f01fb4a44388b5f0211fd75f95c9f70bb029449d258db614a`. The exact expected head and selected release were checked by `ReleaseSelector.current()` under its native mutex.
- The candidate native installation receipt had SHA256 `2b282dc6ee1dc84e9742f672b972e7ebd5809ba3fda073e7073be5f25d7eadd7` and artifact digest `d7724787ef6f459d3a130f915dc7823ccc3de9c3d8337af4b948879e211ee5b5`. `NativeInstalledReleaseVerifier.open` checked its exact receipt, acknowledged install journal and frozen installed identities again before publication.
- Native `NativeSelectionStore` verified preexisting exact `D:\AtlasRuntime\selection` identity `[4004218753,65536,1532785]`; actual `LocalWindowsClock` used approved Google/Cloudflare peer roster without changing W32Time, trust thresholds or sources.
- A new, uniquely bound `QD_CODE_SELECTION_AUTHORIZATION_V1` with `action=SELECT`, `approved=True`, one-time operation `43af31778024f7ec456c7df747683f05` and exact expected head was submitted **once** through the existing `ReleaseSelector.change`. It returned successfully with **revision 9**, head `fc0d8eccac057b1b23f872a1b01da7cd614a44cfb763fc2594a171da1f1cfd55` and candidate V4 selected. No retry or rollback was attempted.

## Independent second-process verification
- A fresh second Python process opened the native Windows selector, obtained its own real clock, and independently called `ReleaseSelector.current()`. It verified the **new revision-9 V4 release and exact head**. The actual native `r0009.json` and `r0009.pending` were byte-equal and exactly represented the revision 9 SELECT, with parent equal to the prior head.
- Post-selection standalone selector/installation offline regressions: **59 passed, 8 skipped, zero failed**. No skipped case is construed as financial/operational acceptance.

## Remaining limitations and dependencies
- The **three existing installed nonfinancial support packages are pinned to earlier application releases** (`2c039af...` / `4fad7ac...`), not selected V4. This mismatch was present for the previously selected `de437abe...` release too. V4 code selection alone does **not** establish a compatible installed launch support package. No support package was installed or modified, and physical desktop observation-only shortcuts were not changed.
- Both existing draft enrollment documents (QD/HL) are still pinned to old revision-8 artifact `241a1650b65bec8f2127e14d8a7f7f17caba2cbf6049788759d65e702b4d23bf`, not V4 `d7724787...`. Their actual six native role roots were prepared, but drafts have no accepted writers or acceptance IDs; neither account has published financial inception. Never silently repin/convert either old epoch without explicit accepted binding and inception authority.
- Provider/source rights checks remain ON HOLD; actual paper Start/Stop, full flatten and durable closeout, restart/browser/listener and elapsed soak remain deferred to **FINAL LAUNCH CERTIFICATION**. Live order adapters remain disabled; do not touch Project Genesis or enable Windows boot auto-start.
- **Formal PAPER acceptance remains 0/9 gates** and no profitability proof exists. The immediate next offline milestone is a reviewed V4-compatible nonfinancial support and account binding proposal, followed by distinct authority for any installation or financial inception.

**Safety checkpoint:** frozen V4 installed payload, old release directories and all prior selector records retained; code-only selection changes only native append-only selector history.
