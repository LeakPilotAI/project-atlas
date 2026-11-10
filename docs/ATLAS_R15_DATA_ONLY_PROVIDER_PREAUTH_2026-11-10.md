# Atlas R15 — selected-provider preauthentication readiness (November 10, 2026)

## Outcome

**Meaningful R15 pre-market commissioning defect fixed. Financial PAPER still NO-GO, 0/9 accepted gates.** Both bounded provider-data-only preview tools previously assumed R14 when its historical `r0013.json` selection file existed. This was incorrect after the newer, verified selected R15 `r0014.json` file was published, because native selection history deliberately preserves old files.

The **Alpaca IEX data-only preflight** (`scripts/observation_runtime/alpaca_iex_probe.py --inspect`) now checks R15 *before* R14, verifies the actual full selected R15 native chain and current no-financial-authority evidence, and returns `selected_revision=14`, catalog of **13,487 research symbols**, with no accepted fresh quote. Its explicit `--execute-data-only --confirm-scope ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING` path now rechecks selected release **before any private Alpaca key bytes or provider connection**; failed/tampered release state refuses, never falls back to R14/R12. **This source-only update does not read credentials or authorize a probe.**

The existing **Hyperliquid two-request public-info preflight** (`scripts/observation_runtime/atlas_r14_hyperliquid_public_book_probe.py --inspect`) now recognizes selected R15, verifies the installed HL source via selected R15 financial-readiness evidence and returns `ATLAS_SELECTED_R15_HL_PUBLIC_BOOK_PREFLIGHT_V1`, native revision 14, current release `2c79a8d846d6b33669008114732ae5896153812a`. The exact, create-only durable request budget remains **12 total, 10 consumed, 2 remaining**. An eventual separately authorized data-only BTC/ETH/SOL sample will be labeled `ATLAS_R15_HL_PUBLIC_BOOK_DATA_ONLY_SAMPLE_V1` rather than falsely labeled R14; the native selection revision 14 correctly maps to **software R15** (not software R14). Off-line tests replaced the HTTP/request gate, independent NTP, and fee/source objects with disposable fakes; no public info request was made by this work.

The existing **PersonalPaper installation preflight** no longer incorrectly reports `TRUSTED_WINDOWS_CLOCK_UNVERIFIED` as if Windows Time were part of the architecture. It now correctly reports `CONTINUOUS_INDEPENDENT_FINANCIAL_CLOCK_LEASE_UNVERIFIED`. That remains a genuine blocker: prior one-shot Google/Cloudflare NTP diagnostics and code identity do not prove a continuous financial session/authority. Native activation and writer ownership remain unverified and financial startup false.

An **actual Windows native-handle inspection** of the pre-existing Quality Dips epoch (six role roots: source, projection, report, control, coordination and custody) returned **all six real, distinct, verified**; no financial account enrollment, current QD forward publication or writer ownership is implied.

**Focused final offline regression: 119 passed, zero failures** across Alpaca scope/precredential guards, R15 selection, provider refusal, Hyperliquid public book format/clock/budget, account preflight and R15 selected native financial readiness. The two tools were also run with their real `--inspect` CLI and returned R15 status without reading credentials, making external market calls or spending budget.

Machine-readable create-only checkpoint: `docs/ATLAS_R15_DATA_ONLY_PROVIDER_PREAUTH_CHECKPOINT_2026-11-10.json`, SHA-256 `dd2f708298836698ed5b60b8b8ee1dcfa9c115627d5c7a015b3a8fdbe519defc`.

## Remaining genuine blockers

Separate bounded **Alpaca IEX credentialed quote observation** requires explicit scope/authorization, and the equity session should be checked when regular-hours prices are available. A positive 1–60-second quote only proves a narrow data observation—not independent provider rights/Robinhood universe coverage, a continuous executable market-data source, or financial PAPER acceptance.

A **Hyperliquid** fresh book sample can be attempted even when U.S. equities are closed, but consumes **the last two pre-enrolled public requests** and requires its own exact two-request authorization; the prior refused BTC observation had an unknown cause and was not cured merely by a code preview.

Even if both probes pass, **PersonalPaper currently has zero accepted activation children and no two-lane enrolled financial owners**. The local PAPER-only operator commissioning scope is conditional on independent source/rights, native account root/enrollment, policy and signed action, and continuous financial clock/ledger/owned Stop readback. Genuine simulated-account and writer enrollment, supervised two-lane entry/monitor/Stop/restart, daily accounting/Discord and extended multiday soak remain to be performed. Kalshi brand-new single YES/NO markets are a separate uncommissioned financial strategy. No real-money trading, VPS/paid feed, OS startup, Project Genesis modification, selected native R15 release rewrite or selector mutation is permitted by this checkpoint.

**Do not republish code selection or reset public request allowances. All current edits live in the development workspace and data-only inspection tools; immutable selected native R15 remains unchanged.**
