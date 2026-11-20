# Atlas PAPER commissioning: execution-batch plan (2026-11-07)

**Status:** NO-GO. Estimate is planning only, not a countdown or an acceptance claim.
**Target:** local Windows Start Atlas -> unattended multi-strategy PAPER session -> Stop Atlas blocks entries, closes simulated positions, reconciles, persists verified receipts and exits owned processes. Hyperliquid-only perps; broad eligible equities via approved sources. No live orders, VPS or Genesis.

## Dependency-ordered remaining work (20-35 substantive execution batches)

| Stage | Estimated batches | Evidence required |
| --- | ---: | --- |
| 1. Source/provider commissioning | 4-7 | Independently authorized QD publication and Hyperliquid market data, bounded provider access, freshness/continuity, unsupported symbols excluded |
| 2. Native operator/account enrollment | 3-5 | Valid activation binding and trusted native storage/clock, QD and Hyperliquid simulated inception, account ownership and writer exclusivity |
| 3. Unified strategy and market integration | 4-7 | Both lanes use real accepted PAPER inputs, supported universe coverage, risk/cost constraints, persistent simulated entries/exits |
| 4. Desktop lifecycle and recovery | 3-5 | Owned Start/Stop, authenticated grant, admission close, flatten and ledger readback, restart and failure behavior; no legacy bypass |
| 5. Supervised acceptance and repairs | 4-7 | End-to-end runs, provider outages, daily rollover, market gaps, Discord/dashboard health, reconciliation and audit |
| 6. Release audit and operator handoff | 2-4 | Evidence matrix, reproducible launch/stop instructions, honest completion retrospective and documented limitations |

**Total:** 20-35 batches, assuming prerequisites can be supplied and no major provider incompatibilities. This is not 20-35 short prompts: each batch should implement, test, document, and commit a meaningful milestone. The estimate excludes time waiting for market hours, external approvals, and soak duration.

**Long-run unattended acceptance is separate:** multi-day to multi-week staged soak and recovery evidence are required before describing Atlas as months-ready. Calendar time cannot be replaced with more test executions.

## Immediate next gate
1. Verify QD operational source publication against independent current feed evidence; existing custody directory alone is not proof.
2. Commission Hyperliquid provider rights and bounded current data acquisition; public REST observations alone are not operational source authority.
3. Enroll separate native simulated accounts only when activation, storage, clock, provider and writer evidence pass.
4. Preserve startup NO-GO and protected legacy shortcuts until a verified owned unified session and safe Stop are accepted.

## Acceptance accounting
Current desktop checker reports nine NOT_INDEPENDENTLY_VERIFIED acceptance gates. Unified checker reports QD source, activation, financial inception and runtime authorization BLOCKED; Hyperliquid native account/provider and unified Stop NOT_INDEPENDENTLY_VERIFIED. Operator commissioning scope is approved but not runtime-consumable. These categories are dependencies, not individual prompt counts.
