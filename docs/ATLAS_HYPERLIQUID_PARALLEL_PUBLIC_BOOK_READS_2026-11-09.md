# Atlas Hyperliquid parallel bounded public order-book reads — 2026-11-09

**Outcome: source implementation and 152 offline regressions verified. No new external provider request, fee grant, financial account, PAPER order, release installation or financial startup.**

## Why this helps the actual 24/7 PAPER critical path

The existing `HyperliquidAdapter.paper_execution_observation` read the public `metaAndAssetCtxs` and `l2Book` responses **sequentially**, then validated both against a strict **10-second observation window** and a separate **5-second provider-book freshness bound**. The source reader could therefore spend unnecessary time waiting for the first HTTP response before even requesting the book. This is a structural latency cost independent of strategy or financing.

Previous genuinely capped Hyperliquid public-data campaigns on November 8 proved at least one strict BTC and SOL order-book sample, but ETH was refused. The exact historic ETH cause remains **UNKNOWN** because the original raw failure conditions were not retained; this optimization is **not** claimed as a definitive ETH fix. The preexisting `_paper_book_admission_reason` safe timing/shape reason-code diagnostic was already implemented and has **not** been duplicated or weakened.

## Bounded change

Modified `backend/app/adapters/hyperliquid.py::HyperliquidAdapter.paper_execution_observation` only, to launch the two existing *public info endpoint* calls concurrently in one bounded operation. The existing preflight requires an existing HTTP-only client, a preinstalled request gate, a selected BTC/ETH/SOL symbol and an explicit clock. **Every** `_post` still consumes one independent durable SQLite logical HTTP attempt before I/O; concurrency is **not** a request-budget discount or way around an exhausted gate. There are exactly two attempted reads and **no automatic retry**.

The original start timestamp is captured **before both requests**, and observation time is measured **after both complete**, so neither metadata latency nor the book's provider age is hidden. No timestamp is backdated, no book is used after a failure, and both old admission bounds remain unchanged. If either public HTTP request fails or the parent is cancelled, pending work is cancelled and joined; no orphan HTTP read continues or cache is published. Only a fully validated result is cached in the existing nonfinancial source cache. Funding settlement historical oracle, maker queue, account fee schedule, native issuer and financial PAPER authority remain absent.

## Independent offline tests

New `tests/test_hyperliquid_parallel_public_book_reads.py` uses a fake HTTP transport and a **real disposable durable `HyperliquidRequestGate` SQLite ledger** to verify overlap (the first fake response waits for the second request to begin), exactly two consumed logical attempts, strict parsed book identity and no financial permission, sibling cancellation on provider error, parent cancellation of both pending tasks, unchanged stale/future/overlong refusal categories and zero new budget consumption when no preexisting client is supplied.

Expanded existing source, funding, public book, safer admission reason, source-consistency and current-producer suites: **152 passed, zero failed/skipped**, one preexisting third-party Starlette/httpx deprecation warning. `git diff --check` passed.

## Operations / next verified dependency

The older V4 r9 and V5 r10 real public observation campaigns each consumed their original 7/7 authorized requests. They must **never be reset or automatically restarted**. A future **separately scoped and approved** public-data observation with its own reviewed rights and budget can measure actual book age/refusal codes for BTC/ETH/SOL using an independently selected current source release. This source-only change remains in the workspace; the installed selected R12 financial reader is not silently updated. The project still needs independently accepted fee/margin/oracle settlement provenance, continuous authenticated market data, financial clock, USDC PAPER account writer ownership/inception, one-click owned Start/Stop flatten and supervised forward observation.

**NO-GO:** Formal Quality Dips + Hyperliquid financial operating gates remain 0/9. No private accounts, wallet, live trading, simulated orders, financial writer, Windows clock/boot/shortcuts, Project Genesis, or GitHub push.
