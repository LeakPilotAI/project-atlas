# Atlas R22 — selected IEX 30-symbol research survey and release-bound cursor
**November 18, 2026 | Desktop Commander MADDOG | SOURCE-ONLY | NO PAPER**

## Executive result

**Verified development source compatibility, not installed financial readiness.** Selected native R22 has exact code source `2f0fcfd9741b8fd524f2e5921a79998373a689c9`, selector revision22 SHA-256 `9f206300bc243ebe938f4bf729c1eb5f2c239596ebf410b18773bb614c6b60f6`. Its original 12 financial roots are distinct and EMPTY. Original release neither modified nor reselected; no request/account/Stop/trading/provider action was made. Three legitimate dirty R23 PIN edits remain protected.

## Concrete source-only repair

After the preceding source checkpoint `b97ba9e347b87852e2c064b91008ae8342e1ad9d` repaired the historical-R15-only Alpaca `--inspect` and REST gate, two remaining modules still rejected current R22:

- `scripts/observation_runtime/alpaca_iex_basic_research_batch.py` required `selected_revision=14`, hardcoded `selected_native_release='R15'`; it now allows only **verified actual selected 14 (R15) or 22 (R22)** with source rights and trading still FALSE, and attaches the current release label to the deterministic single-connection 30-symbol RESEARCH roster/receipt. Unknown, forged or future revisions refuse; no wallet/brokerage market trading or financial source issuer is inferred.
- `scripts/observation_runtime/alpaca_iex_basic_subscription_cursor.py` had hardcoded report release `R15`. It now matches the approved, exactly-shaped report release to the currently rechecked original selected roster, and persists `selected_native_release` inside the cursor's digest-sealed record. Schema upgraded to `ATLAS_IEX_BASIC_SUBSCRIPTION_SURVEY_CURSOR_V2`. Existing v1 cursor files fail closed instead of being silently adopted. An R15 cursor cannot be resumed as R22 even with the identical catalog+symbol set. A release change mid-observation refuses without advancing the cursor. No old cursor existed on MADDOG at inspection, and none was created.
- Existing explicit data-only WebSocket scope, 5–20-second bounded connection, <=30 subscribed research symbols, no reconnects, no persisted quote prices, no financial position owner/source authorization, append/checkpoint lock and fail-closed original behavior were preserved. This patch does **not** grant another Alpaca WebSocket connection or spend any provider requests.

## Executed validation

1. Original native selected R22 Python `-I -B -S`, with its original native two-CPU budget, ran a source-only regression across four affected Alpaca test files. **149 distinct Python tests passed, 1 genuine subprocess native inspection case deselected** because nested CPU-guard admission would refuse. That real IEX selected-release inspection was independently executed successfully in the previous checkpoint; this execution additionally ran BOTH new actual `--inspect` commands separately.
2. Actual R22 batch `--inspect` returned `status=OFFLINE_ROSTER_NOT_CONNECTED`, `catalog_count=13487`, `requested_symbols_count=30`, `next_research_offset_uncommitted=30`, `data_provider_called=false`, `paper_start_authorized=false`, `live_money_authorized=false`. Actual cursor `--inspect` returned `selected_native_release=R22`, `saved_generation=0`, `next_research_offset=0`, `data_provider_called=false`, both financial flags false. Together they exited **0**, with no credentials or providers used.
3. New tests cover R22 bound rosters/reports, unknown revisions (13/15/21/23, bool and string), cross-R15-to-R22 cursor transfer, mid-observation release drift, and rejection of unbound v1 cursor state.
4. Scoped Ruff check passed with only the **existing** broad-exception CLI refusal handler's `BLE001` ignored; changing its fail-closed error behavior was outside this patch. Automatic safe import ordering/unused-import cleanup only. `git diff --check` PASS.
5. Independent selected native R22 audit exited **0**: hash-verified 149 JUnit testcase identities, four exact development-source hashes, current selected native rev22 and installed artifact, 12 financial namespaces empty, 10 protected original SHA-256 receipts unchanged, original research cursor absent, no r0023 selection. Original selected installed R22 was not repacked, repaired in place or promoted to a new version.

### Exact evidence

Diagnostics under `D:\Work\Project Atlas\logs\diagnostics\atlas-r22-iex-survey-current-20261118-r01`:
- `r22-iex-survey-junit.xml` initial 149-pass regression.
- `r22-iex-survey-postlint-junit.xml` final **149 pass / 1 deselected**, zero errors/failures/skips among the 149.
- `final-readonly-audit.json` SHA-256 `03c4490cd7e74b780e7696c30e8dc0456d60da0b7adde73a5fc69252a856d563`.

Final exact development-file hashes:
- Batch source: `39d7d1e40a5392e3e71bba4819460337dc441dc7d132b59f3bda9724b3dbd2e0`.
- Cursor source: `4cda091eaffb278bbb2de2ad773264e43d8f699fdb81159ce94afe297127d735`.
- Batch tests: `c0850cb0a512b715a6036fa2bab3c29a0db2d4a7dd391b6bd4394af15934d333`.
- Cursor tests: `42e5fe8104d710272ed7ed0c070958deff7bcbd01c8f74cde8fec23411c5563b`.

## Precisely remaining work before full PAPER production

This patch and the previous R22 preflight/REST patch are **not yet in a newly selected immutable native release**; the old R22 installed artifact is unchanged. Do not install or select without a fresh exact audited release candidate, native install-only and select-only Windows-local approvals, and new independent readbacks.

Even selection of the new code will not bypass Stage A: the original `ALPACA_IEX`, `HYPERLIQUID_PUBLIC`, and `QUALITY_DIPS_RESEARCH_PUBLICATION` E1 sources remain **0/3 accepted** for actual operational automated use/retention, license and budget, producer continuity and economics. Current executable IEX quotes are not accepted. The user's one-hour HL intrahour-flat method preference is already acknowledged, but original funding/settlement/fee policy and native owned Stop/FLAT remain unaccepted. Real fresh Windows owner with 5+7 original process roles, the original two preinception coordination journals, separate original FS1/FS3 simulation account inception approvals, the 1,000-USD QD WATCH and 1,000-USDC HL PAPER accounts, postinception `CONNECT_APPROVED_DATA`, actual <=8s durable financial FLAT/Stop, dashboard/Discord and first supervised pilot remain to be done.

**PAPER production NO-GO. No financial accounts or orders. Live-money trading OFF.** All diagnostics and temp D-only; no Codex, VPS, paid data, C-drive scratch, user credentials or automatic startup.
