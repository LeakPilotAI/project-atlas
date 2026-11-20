# Atlas R22 — Hyperliquid funding semantics and installed intrahour policy audit
**2026-11-17 (America/Chicago) | Desktop Commander only | NO PAPER / NO LIVE MONEY**

## Result
**SOURCE-ONLY POLICY FEASIBILITY QUALIFIED; FINANCIAL/PAPER PRODUCTION STILL NO-GO.**

The selected Windows-native R22 code-only release remains commit `2f0fcfd9741b8fd524f2e5921a79998373a689c9` at native selector revision 22. No installed release mutation, source publication, producer activation, financial account/journal, native financial Start/Stop, brokerage/wallet/private request, public Hyperliquid HTTP request, new data entitlement or operator financial grant occurred during this investigation. The original one-use six-request November 17 authorization is consumed and was not reused. No C: working files or Codex were used.

### Direct documented facts (public documentation read; no new provider API)
- Hyperliquid's official **Perpetuals Info Endpoint** documents `POST /info` `type:predictedFundings` as an array of venue predictions carrying `fundingRate` and `nextFundingTime`. It says that endpoint is for the first perp DEX. https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals
- Its official **Funding** documentation says funding for perpetual contracts is paid hourly and payment uses the original *oracle price* at that funding interval, not the current mark price. https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
- The official info endpoint separately documents `fundingHistory` (historical funding rates), not an authenticated prior consensus settlement-oracle action. The original Atlas `app.services.hyperliquid_consensus_settlement.require_consensus_settlement_oracle` correctly rejects absent original event provenance. This code did not change.
- The observed `nextFundingTime` field is **not accepted as an actual future event** merely because the documentation labels it that way. It may be a publication/aggregation delay or a venue-specific scheduling/semantics issue, but **no root cause has been independently established**. Do not assert that Hyperliquid is broken, caching, or that a provider replacement would solve it.

### Actual current evidence (two independent authorized dates)
- **November 16, 2026, 15:39:45.375 UTC:** retained `HlPerp` `nextFundingTime` for BTC/ETH/SOL all **15:00 UTC**, already past. Independent local next-hour arithmetic **16:00 UTC**. Original five-response data-only authorization was consumed.
- **November 18, 2026, 05:25:43.830 and 05:25:54.068 UTC** (November 17 local Central): genuine one-time six-request session returned all three `HlPerp` next references **05:00 UTC** in BOTH snapshots. Local next-hour arithmetic was **06:00 UTC**. Both `predictedFundings` response hashes matched exactly; minimum second-request-start separation was **10.021 seconds**. Public BTC/ETH/SOL books passed original native R22 `validate_cycle`. Predicted funding reference admission **REFUSED**; all original 15 raw evidence files (217,443 bytes) and SHA-256 receipts remain preserved unchanged under `logs/diagnostics/atlas-r22-source-readiness-20261117-r01/hl-public-six-reads-20261117-r01`.
- One-shot final-result SHA-256 `b50dc95e41b988d5802072d8d1ed89320cd43853af4bbbf64a3d59bfd92eb5c3`, independent receipt/readback SHA-256 `fff1caeb2aab98834cf6f0c95fb5b768e2ee0e050d184e27b3440e9c3a86fc81`. The original `funding_observation_interval_seconds` reporting label is incorrect; use the independently verified native receipt timestamps, **never rewrite the consumed evidence**.

### Already-installed, immutable risk-reducing policy
The original R22 installed files are byte-identical to the corresponding source checkout:
- `backend/app/services/hyperliquid_forward_flat_paper_policy.py`: SHA-256 `b683f4b18c598c5b4dcb4659e00fd2e36c1b2d1029367722ccbc4ab675c7286d`.
- `backend/app/services/hyperliquid_intrahour_stop_supervisor.py`: SHA-256 `71d3af562561234aa7fe33e98d7298184adfb5febb0ff196370620c3d3c2ec2e`.

A dedicated **isolated installed R22 Python, original native two-CPU guard, no network** tested every second of a model UTC hour for BTC, ETH and SOL: **10,800 structural candidate evaluations**. With simulated 139ms clock uncertainty, 1,200-second maximum hold and no unverified initial positions, only elapsed UTC-hour seconds **32 through 2097 inclusive** (2,066 candidate seconds) are structurally eligible, never financially authorized. Entry fails outside that window, or if native positions/close are not verified. The policy uses a conservative complete worst-case hold instead of a requested 1-second hold to bypass late-hour limits. The genuine one-shot Stop requires:
- **T−8 minutes (480 seconds):** request original `SHUTDOWN_FLATTEN` via an already accepted living `PersonalInstalledPaperStopOwner`, latch all new entries before dispatch.
- **By T−5 minutes (300 seconds):** original native durable FLAT, verified process exit and Stop receipt must succeed. Late, ambiguous or uncertain reports terminally refuse; never replay a used Stop.
- Original fee assumption of 10bp taker and 5bp slippage **each side** is an illustration, not a verified actual account tier. Zero funding is not assumed merely because time was within the window.
- Both deliberately invalid `NativeIntrahourPaperStopSupervisor(owner=object())` and missing `require_consensus_settlement_oracle(None,...)` were confirmed to refuse. Neither scope, funding settlement, source rights, trading, nor live-money permissions can be constructed from this isolated check.

Standalone native read-only feasibility report:
`logs/diagnostics/atlas-r22-source-readiness-20261117-r01/hl_intrahour_funding_feasibility_readonly.json`
SHA-256 `722461305f7eab50b33b9e4cd5b38fbf89e1959d1f817ed7c6c59837cd194b91`; selected process exit 0, zero provider requests, original **12 financial namespaces empty**.

### Why first true PAPER remains blocked
Installed R22's `scripts.observation_runtime.atlas_paper_actual_commissioning_order` defines original Stage A as **accepted source/valuation, Alpaca IEX rights, original Hyperliquid settlement/funding/fee methodology**, before Stage C manifests and Stage D two coordination journals. Actual original 12 native roots are all empty. Temporary Job/clock tests and this deterministic policy study are *not* a durable native enrollment.

The existing flat-before-funding proposal is **not an approved, already wired financial issuer alternative**: its own module explicitly says "no original financial issuer integration". Approving structural entry windows would not independently establish original source-data rights, original account fee/settlement policy, QD WATCH source, two original financial manifests, genuinely retained writer generation/owner, or safe Stop/FLAT proof. No financial authority was approved or created by this run.

**Two legitimate next source-policy paths remain distinct:**
1. **Original oracle-bound funding model:** independently authenticate original rate and *historical consensus oracle action*, source rights and applicable fees, and prove the initial current feed/producer and owner together. Stale `nextFundingTime` cannot be replaced with arithmetic. This continues the original model.
2. **Explicitly reviewed strict intrahour-flat PAPER-only model:** acquire a new explicit original source/fee/financial-policy approval that permits using verified pre-hour native FLAT without claiming historical settlement oracle/cost waiver for any unresolved interval; keep stop-first and all initial dual-account validations. This is a **PROPOSED change in financial source policy**, not implemented or authorized for PAPER. It would still require real native owner, genuine FS1/FS3 account inception, authentic live data rights, bounded Stop and readback and a supervised session.

No further public `predictedFundings` polling alone will prove the consensus oracle or real account fees. A third repeat under a consumed data-only authorization is expressly forbidden.

## Remaining production gates
Source-policy acceptance (QD WATCH + HL), actual owner/real independent clock, exact two original coordination journals and account approvals, actual nominal 1,000 USD WATCH + 1,000 USDC PAPER simulated-account FS1/FS3 acceptance, postinception data activation, true STOP_FIRST with ≤8s native Stop and durable FLAT, current writer fencing/restart, and supervised HL-only PAPER pilot/dashboard/Discord receipt acceptance. These are **not** satisfied by the read-only audit. *PAPER OFF; live-money OFF; no VPS, no paid data, no automatic startup.*

## Verification boundaries
Historical controlled test profiles remain 358 passing Hyperliquid source/settlement and 105 passing HL-only source/Stop, with 15 original AIP06 guarded native-fixture test refusals **separate and unaccepted**. This execution did not reset the fixture or relabel tests. No new installed release selection is required simply to keep this report; future code changes would need their own immutable release/approval sequence.
