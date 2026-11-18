# Atlas R22 — single authorized Hyperliquid public-data check and independent receipt audit
**2026-11-17, America/Chicago (session crossed UTC into 2026-11-18)**

**DECISION: PUBLIC NEXT-FUNDING REFERENCE REFUSED. PAPER OFF; LIVE MONEY OFF. DO NOT REPEAT THIS SINGLE-USE SESSION.**

## Authority and exact scope

The operator explicitly authorized **ONE** bounded data-only public Hyperliquid check under immutable proposed scope SHA-256:

`05ed0a59dd4d614cec29abd4add5bc08e8eb0af5a202f7304ef91149d3796c93`.

Source proposal:
`D:\Work\Project Atlas\logs\diagnostics\atlas-r22-source-readiness-20261117-r01\public-hl-followup-proposal.json`.

Execution used **Desktop Commander only** on the original Windows host MADDOG and the selected R22 isolated installed Python. Native selected revision 22, exact installed successor artifact digest `5b23187f39316cd4e4d81659fec70758d9db661051604f4d91379938c5e92a51`, current original 12 distinct EMPTY financial roots and two-processor original host guard were checked. No original financial account, journal, PIN assignment, release, selector, source issuer or provider grant was changed.

Original request URL exclusively `POST https://api.hyperliquid.xyz/info`. Six permitted payloads in sequence: one `metaAndAssetCtxs`, one `predictedFundings`, three `l2Book` for BTC/ETH/SOL, then a second `predictedFundings` after at least 10 seconds. TLS verification on, environment proxies off, zero redirects, zero retries, one request at a time, 5-second per-request cap, 512 KiB each, at most 75 seconds, at most 80 reserved request-weight units, 4 MiB / 32 evidence entries, at most two logical CPUs. Exactly **six requests were attempted, weight 66, in 14.953 seconds**. The HTTP client closed and independent two-peer NTP clock was revoked.

No credentials, wallets, account IDs, private endpoints, `userFees`, `fundingHistory`, exchange order endpoint, WebSocket, financial activation, account inception, trade, simulated balance, source publication, auto-start or live-money action was used.

## Observed source result, not conjecture

- First `predictedFundings` received **2026-11-18 05:25:43.830 UTC** (Tuesday 11:25:43.830 PM Central).
- Second `predictedFundings` received **2026-11-18 05:25:54.068 UTC** (Tuesday 11:25:54.068 PM Central).
- Independent receipt check confirms the second prediction **started 10,021 ms after the first completed**, exceeding the 10-second minimum.
- Both provider responses for all three `HlPerp` markets advertised **`nextFundingTime=1794978000000` = 2026-11-18 05:00:00 UTC (11 PM Central)**, already past at both observations.
- Original UTC-hour proposal expects **`1794981600000` = 2026-11-18 06:00:00 UTC (midnight Central)**, one hour later. That expected time is derived locally and is **not** substituted for observed provider evidence.
- Both predicted-funding responses are **byte-for-byte identical**, SHA-256 `6ef7231882a6f038d4c8e1273abc33993bec302c90d2480024d460c4081e48dc`. Identical content does **not** independently establish caching, endpoint semantics or any provider fault. Root cause remains **UNRESOLVED**.
- Original selected R22 `atlas_r20_public_hl_rest_fallback.validate_cycle` passed all BTC/ETH/SOL books: BTC and ETH source age 892 ms, SOL 348 ms. Book freshness is not future-funding, fee, source entitlement, settlement-oracle, maker-fill or production availability evidence.
- The temporary NTP qualification retained **139 ms uncertainty** and two peer sources. The two-peer clock uses public, unauthenticated NTP: successful peer agreement is not cryptographic attestation.
- Original test returned **`PUBLIC_FUNDING_REFERENCES_REFUSED_NO_FINANCIAL_GRANT`**, selected Python exit **2**, as intended for a real source refusal. The PowerShell wrapper reported a failure to prevent accidental admission. The **single-use operator authorization is consumed**.

### Independent receipt and preservation audit

A **separate read-only** selected-R22 Python process independently verified exact proposal SHA-256, single-use intent, six allowed payloads, original six raw response files against six corresponding file hashes, 5-second request durations, 66-weight budget, 75-second budget, genuine >=10-second second-prediction delay, identical predicted funding byte hashes, all three original book validations, both stale timestamp comparisons, current native revision-22 selection, 12 original empty financial roots and all ten original protected hashes. It made **zero additional Hyperliquid requests** and exited **0**. This validates the evidence and the refusal, **not** financial source acceptance.

Immutable retained D:-only evidence directory:
`D:\Work\Project Atlas\logs\diagnostics\atlas-r22-source-readiness-20261117-r01\hl-public-six-reads-20261117-r01`

15 evidence files, **217,443 total bytes**, within the authorized cap; no other financial filesystem roots written.

- `session-intent.json` SHA-256: `cb9167d46967a54606ed8046ea3da962286057ae6f84d15b3bd3d0548dc8a1c5`
- `final-result.json` SHA-256: `b50dc95e41b988d5802072d8d1ed89320cd43853af4bbbf64a3d59bfd92eb5c3`
- `independent-readback.json` SHA-256: `fff1caeb2aab98834cf6f0c95fb5b768e2ee0e050d184e27b3440e9c3a86fc81`

**One reporter-label defect is documented without changing any preserved bytes:** `final-result.json` field `funding_observation_interval_seconds=4.719` was incorrectly computed from the start of the overall script to the first predicted response, not between the two predicted responses. The original independent receipt timestamps prove the actual minimum separation of **10.021 seconds between first completion and second request start** (and 10.238 seconds between both received instants). Do not reuse the mislabeled field as admission evidence or modify the consumed one-shot output. Any future source-only correction requires separate review; no new provider requests were triggered.

## What this does and does not resolve

The nonfinancial public book and clock portions passed. The operative published next-funding reference remains **stale for BTC, ETH and SOL** on a second independently authorized date, and its meaning/cause remains unresolved. Even a future successful predicted-funding response cannot certify signed Hypercore consensus settlement or account-specific maker/taker fees, maker fills, continuous provider source rights, or funding-fee settlement. No alternate authority was silently substituted, and the provider hold remains active.

Original code-only selected release revision 22 remains unchanged; Quality Dips remains WATCH-only. Twelve original financial namespaces still contain **no genuine account or balance**; there is no accepted native financial Job, original two-journal coordination, `INITIALIZE_SIMULATED_ACCOUNTS` FS1/FS3 inception, postinception `CONNECT_APPROVED_DATA`, genuine native <=8s Stop + durable FLAT, paper startup, dashboard/Discord operational session, or live-money trading grant.

**Next safest engineering work:** offline reconciliation of the *documented meaning* of `predictedFundings.HlPerp.nextFundingTime` with an independently accepted alternative forward-funding/settlement policy and the original source-issuer contract, followed by a separate operator review for any new bounded provider-access plan. No new repeated network request or account creation is approved by this exhausted one-shot permission. **PAPER remains OFF / production NO-GO.**
