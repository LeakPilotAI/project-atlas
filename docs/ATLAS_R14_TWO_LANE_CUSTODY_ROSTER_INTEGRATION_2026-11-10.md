# Project Atlas R14 — two-lane native writer-roster / custody read integration (2026-11-10)

## What was actually completed

**Offline integrated read/ownership acceptance tests passed.** The previous source-only fix in commit `eb03e5bb` requires `UnifiedWriterRoster.lease()` to reverify writer ownership on successful lease exit. New `tests/test_atlas_two_lane_custody_roster_final_read_offline.py` now exercises the actual production `UnifiedPortfolioCustody.read_accounts()` source with that modified roster, two completely inert financial writers, an unmodified read-only synthetic control journal, and an injected named roster observer/authority. This closes a distinct test gap: the first unit regression did not show that the **two-lane custody reader** properly reacts when native process/resource evidence changes *after its last internal account cut*.

**Positive:** A clean two-lane account snapshot reports `state=ACKNOWLEDGED`, includes both Quality Dips USD and Hyperliquid USDC, and has `startup_authorized=false`. The native writer observer is read at lease entry, during custody, and at final lease exit; no financial journal mutation, order, account startup or provider call occurs.

**Six post-read injected drift cases** independently refuse an apparently successful read after the second internal verified financial-cut callback: unregistered writer, unknown native operations, changed global custody process incarnation, changed perp native resource, revoked observation authority, and stale observer timestamp. Each would otherwise be positioned immediately before returning `ACKNOWLEDGED`, so the final lease-exit verification is the relevant safeguard. All cases require ValueError; original synthetic financial source cuts and the control-journal snapshot remain unchanged.

**Failure classification:** An error inside the independent account-cut verifier is deliberately caught by `read_accounts()` and returns `state=UNKNOWN`, `accounts=None`, `startup_authorized=false`; it is not converted into an accepted read. Initial test incorrectly expected that safe error to propagate. That test assertion was corrected, **without changing runtime implementation**.

## Verified evidence

The new test file SHA-256 is `71b679e1f3d6b72b8cc94c1798b94f1aa4ca75f92dbc759616f098607deecd3f`.

Windows IDLE-priority bounded combined tests:

- `tests/test_atlas_two_lane_custody_roster_final_read_offline.py`
- `tests/test_unified_writer_roster.py`
- `tests/test_unified_research_sources.py`
- `tests/test_paper_stop_receipt_ledger.py`
- `tests/test_personal_installed_owner_lifetime_offline.py`

**138 passed, 1 skipped, 0 failures**, 12.95 seconds; no uncontrolled worker fanout. The first run was 59 passed/1 failed from the bad exception expectation in the test only; corrected final run fully green.

The older, separately guarded AIP06 native-writer fixture test was **not** run or bypassed: its `AIP06_GUARDED_SESSION_REQUIRED` independent authorization still applies. Source-only synthetic success is not financial operating acceptance.

## Installed release and operating scope

Native selection stays revision 13 → R14, selected record SHA-256 `6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31`. The immutable installed R14 roster SHA-256 remains `e70ba05f7d297702bc14629fa458efee313573af7dba1687ff7fc22ba4c0a1c5`. The corrected **workspace** roster SHA-256 is `d26f821afee33855c8543f649f40f9f2fe25529043770dce59ecb8105945f697`. Their difference is intentional: the new source and this test have not been frozen into or selected as a later native release.

This test used neither Alpaca credentials, Hyperliquid public-request allowances (the prior budget remains 10 of 12 used), private accounts, live or simulated financial orders, native account enrollment, remote data, Windows boot services, installed-release mutation nor the legacy desktop Start/Stop. No Project Genesis changes.

**Next operating milestone:** qualify a genuine, separately accepted single-user two-lane PAPER owner/custody/financial clock and allowed current data, then rerun equivalent writer/reader/Stop/restart cases under verified native installation. A future frozen release must include the new roster exit-time check and the current data-only diagnostics. Only after independently verified provider rights, real PAPER writers, risk, owned Start/Stop and supervised trades can one-click financial PAPER activation be considered.

**Formal financial PAPER status remains NO-GO, 0/9 independently accepted operating gates.**
