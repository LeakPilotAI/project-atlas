# Atlas R15 code delivery — complete offline installer and selector handoff (2026-11-10)

## Scope and verified outcome

**SOURCE-COMPLETE NONFINANCIAL R15 DELIVERY PIPELINE, NOT INSTALLED OR SELECTED, FINANCIAL PAPER NO-GO.** The R15 960-file source-only archive at Git source commit `2c79a8d846d6b33669008114732ae5896153812a` (SHA-256 `f6cb597a53373efee929c306ae42537e16abcbcf6e57f7bd23ee92e8570160c0`) and exact native dependency plan (9,566 files) remain unchanged. The proposed code-only native target is `D:\AtlasRuntime\releases\2c79a8d846d6b33669008114732ae5896153812a`, **still nonexistent**, with 10,526 files / 263,545,933 bytes planned. Selected native release remains R14 revision 13, `r0013.json` SHA-256 `6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31`.

This session implemented the previously missing **three-stage R15 code-only delivery adapter**, deliberately with separately pinned one-shot approvals disabled. No installed releases, native selector, financial accounts, provider credentials, market-data request budgets or trades were modified.

### 1. Native code installer — source complete, approval locked

`scripts/atlas_r15_code_only_installer.py` SHA-256 `fdc05ae16db98f92ae49f97f044c9df67278009f80ed8ecdd51cc7621b6a6100`.

- Requires an exact source/archive/inventory and dependency SHA, selected original native R14 head, unopened target, original Windows operator SID, installer-source SHA and independent exact one-shot consent record (`APPROVAL_SHA256=None` until independently granted). No historic R14 approval is reusable.
- Acquires fresh Google+Cloudflare two-peer independent UTC with **180-second / 37+ sample** qualification before protected work. No Windows time-service change.
- Runs the existing pinned native source/dependency copier with **Windows IDLE-priority single-process envelope**, frequent host/memory/game/time/selector checks, pacing, a 500-second bound and no retry on unknown partial copying.
- Uses a create-only durable intent journal, genuine native file/ACL/original-handle checks and an isolated native Python child for installed readback. A successful final installed receipt is written LAST.
- Caught and fixed a potential self-refusal: after creating the install intent journal, a subsequent active-copy admission must not repeat the *pre-install empty-target* gate and accidentally reject its own journal.
- Aligned the R15 terminal `UNSELECTED_CODE_INSTALL_VERIFIED` ACK to the **existing native selected-release verifier**; the exact expected final-receipt SHA is written to the journal BEFORE publishing the final create-only receipt. Positive and negative tests prove the old verifier's actual contract, not an invented new version.
- No default install or selection, no PAPER/live orders, no financial/credential access, no startup-on-boot.

### 2. Installed receipt → proposed selector — source complete, no mutation

`scripts/atlas_r15_selection_handoff.py` SHA-256 `9c589f90ac8314ab1c2fd465b789d3a38b39360f2cd742b873064c34ca185771`.

- Before installation returns `WAITING_FOR_SEPARATELY_AUTHORIZED_R15_CODE_ONLY_NATIVE_INSTALL`, `NO` selection grant.
- For a hypothetical *genuinely completed* install, validates canonical source receipt bytes, all **10,526 files/912 directories**, artifact digest, source/archive pins, exact two-row create-only journal, generic installed ACK and nonfinancial flags. Produces a deterministic **proposed** revision-14 `SELECT` extending the exact verified native revision-13 R14 head. Rejects partial/journal/receipt/ancestor/financial-rights tampering. Never writes `r0014.json`.

### 3. Exact native code selection publisher — source complete, approval locked

`scripts/atlas_r15_code_only_selection_publisher.py` SHA-256 `42a37338d0319ab31e189ac65d3b70e5b6273b04ccf5d03a4023ee37437c61ca`.

- Requires its own future **new one-shot exact SID-bound and publisher-source-SHA-pinned consent** (`APPROVAL_SHA256=None` now), separate from install consent and any financial authority.
- After installation and explicit consent, obtains a fresh in-process 180-second/37+ sample independent dual-peer clock, native original selection mutex, accepted revision-13 R14 head, independently reopens/validates the installed R15 native original handles and isolated child readback, and rechecks native receipt/ACK using *the held original native lock*.
- Avoids reentering the native selector mutex from within itself: when it holds the lock it validates the receipt/journal directly rather than calling a nested `handoff.inspect()`.
- Only then performs one irreversible native revision-14 publish and checks readback of all 14 records under the same lock. Uncertain result is not replayed.
- Separate code-only selection is **not** authorization for financial PAPER startup or live trading.

### Evidence

- Actual low-resource host preflight: resource admitted with approximately **100.69 GiB free RAM, 754.3 GiB free disk**, no listed foreground game; **not** an installation permission.
- Read-only checks `python -B -m scripts.atlas_r15_code_only_installer --inspect`, `python -B -m scripts.atlas_r15_selection_handoff --inspect` (expected exit 2) and `python -B -m scripts.atlas_r15_code_only_selection_publisher --inspect` all returned expected states: installer not approved; R15 not installed; selection not published; financial authority false.
- Final single Windows IDLE-priority targeted regression `tests/test_atlas_r15_code_only_installer_offline.py`, `test_atlas_r15_selection_handoff_offline.py`, `test_atlas_r15_selection_publisher_offline.py`, `test_atlas_r15_code_install_plan_preflight.py`, `test_atlas_r15_frozen_source_archive.py`, `test_atlas_r15_offline_closeout.py`, `test_atlas_two_lane_custody_roster_final_read_offline.py`, `test_atlas_r14_selected_native_owner_interpreter.py`, `test_kalshi_new_listing_exclusive_entry_policy.py`, `test_paper_stop_receipt_ledger.py`, `test_bound_daily_report.py`: **206 passed, 1 skipped, zero failed in 26.77 seconds**. One expected dependency deprecation warning, no load spike/full-suite fanout.
- Create-only machine report `docs/ATLAS_R15_CODE_DELIVERY_OFFLINE_HANDOFF_2026-11-10.json`, SHA-256 `cb2ba64038be26e74c106de5edfbee1d613900a6aea0292b3dc5c37ebdbaefc9`. R14 native selection unchanged, no r0014, no R15 target, no install/selection approval pin, unchanged Hyperliquid public-info request ledger **10 of 12 consumed, 2 remaining**.

## Remaining milestones, separate from market hours

1. **Independent exact code-only native installation consent**, then fresh NTP/resource qualification and immutable R15 copy/readback. Its 263 MB protected native operation was deliberately NOT started. Refusal or partial target means no automatic retry.
2. **Independent exact code-only native selection consent**, only after complete R15 installed receipt and native original-handle proof. No approval can be inferred from source tests or the user's previous R14 decision.
3. **Real local PersonalPaper financial account/owner enrollment**, clock/custody/ledger, and actual two-lane Quality Dips/Hyperliquid automatic startup and Stop flatten/durable restart. Current PersonalPaper activation candidates remain zero. These protected operations do **not inherently require stock market hours** but need independent native and operator acceptance.
4. **Current authorized data and real supervised PAPER evidence:** Alpaca IEX actual fresh eligible quotes, limited subscription coverage and Robinhood-listed universe mapping; Hyperliquid current book/rights (previous one-shot BTC public probe refused; 2 requests preserved); Kalshi newly listed single YES/NO strategy separately uncommissioned. Only after these are accepted can actual provider-backed simulated entries and market-hours monitoring be demonstrated.
5. Independent extended multi-session PAPER soak and profitability/accounting review before any decision about live execution. One-click desktop Start/Stop stays deliberately blocked until actual owned financial Stop has been verified.

**Formal financial PAPER operating gates: 0/9 accepted, NO-GO.** This checkpoint removes release-tool implementation gaps, not operator approval or trading/data requirements. No source-only success has been reported as financial production.
