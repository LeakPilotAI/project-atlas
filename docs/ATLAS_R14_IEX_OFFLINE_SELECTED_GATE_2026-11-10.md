# R14 selected Alpaca IEX offline observation gate repaired — 2026-11-10

## Result

**SOURCE-ONLY DIAGNOSTIC FIX IMPLEMENTED, NO PROVIDER CONNECTION OR PAPER AUTHORIZATION.** The existing `scripts/observation_runtime/alpaca_iex_probe.py --inspect` was incorrectly coupled to `atlas_r12_alpaca_source_admission.assess()`, which must reject the current R14 native selected revision 13. This made it impossible to inspect readiness for the currently selected R14 without an error.

The offline IEX probe now dispatches to the **existing R14 two-lane source preflight** when the exact R14 revision-13 selection record exists. That R14 preflight independently verifies the native 13-record selection, installed R14 source/writer identities, and research-only Alpaca/Hyperliquid inventories. Any malformed/changed R14 evidence is refused: it cannot fall back to the older R12 check. The R12 legacy path remains available for pre-R14 deployments. The explicit data-only `--execute-data-only --confirm-scope ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING` gate was **not changed or invoked with its scope**; credentials and network access remain restricted.

The real R14 command:
`backend\.venv\Scripts\python.exe -B -m scripts.observation_runtime.alpaca_iex_probe --inspect`

**Returned exit 0** with `selected_revision=13`, `source_catalog_symbols=13487`, `status=REQUIRES_EXPLICIT_DATA_ONLY_SESSION_APPROVAL`, `forward_source_verified=false`, and **false** for credentials accessed, provider connected/authenticated/rights independently accepted, current executable quotes verified, Robinhood universe verified, sample already verified, and trading authorized.

The unapproved command `--execute-data-only --seconds 1 --symbols MSFT` **returned exit 1** with a sanitized `REFUSED` result; no private data loaded or socket opened.

## Regression

Low-resource Windows idle runner, combined existing IEX probe/per-symbol/watermark and selected R14 source/readiness tests: **84 passed, 0 failed in 8.87 seconds**. Added explicit unit tests for the actual selected R14 revision, a simulated pre-R14 R12 path, credential/network refusal during offline inspection, fake R14 gate promotions/changed revision, invalid selected native chain, and an unscoped credentialed probe. Existing credentialed synthetic quote callback and watermark behavior retained.

**Evidence is diagnostic only.** R14 remains the selected native code release (revision-13 record SHA-256 `6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31`). This change is source-only in the workspace, not a new native code release or installed runtime modification. The formal financial operating gates remain **NO-GO, 0/9**. No actual IEX quote was collected, provider entitlement established, native financial ledger opened, account created, order submitted, desktop Start/Stop enabled, or live trading authorized.

**Next critical task:** obtain explicit data-only permission and execute the existing bounded Alpaca IEX authenticated fresh-quote sample (max 60 seconds, up to 10 symbols, one-shot, no orders) if user authorizes private credential access. Then separately qualify continuous quote freshness and allowed data rights; Hyperliquid public market source eligibility, native PAPER writer, financial clock, supervised owned Stop and PAPER commission remain separate. Do not infer market breadth from the 13,487 research symbols or claim free IEX is consolidated NBBO.
