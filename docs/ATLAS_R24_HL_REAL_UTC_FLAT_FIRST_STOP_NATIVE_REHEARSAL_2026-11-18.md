# Atlas R24 — existing native Hyperliquid flat-before-funding method verified against genuine UTC

**November 18, 2026 | MADDOG Windows | R24 selected code-only | Financial PAPER NO-GO / LIVE OFF**

## Original design and independence
The original, *already installed in selected R24*, `backend/app/services/hyperliquid_forward_flat_paper_policy.py` has native SHA256 **`b683f4b18c598c5b4dcb4659e00fd2e36c1b2d1029367722ccbc4ab675c7286d`**. The selected original `backend/app/services/hyperliquid_intrahour_stop_supervisor.py` has SHA256 **`71d3af562561234aa7fe33e98d7298184adfb5febb0ff196370620c3d3c2ec2e`**. Each hash is **identical** to the current worktree file's hash. There is no need to create a second proposal or routine R25 release to obtain this source-only method; it is already in selected R24 code.

Hyperliquid's own funding documentation <https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding> states standard hourly funding, and its API docs <https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals> distinguish public `predictedFundings` from `fundingHistory`. The earlier November 18 six-POST data-only observation's original `HlPerp.nextFundingTime` for BTC/ETH/SOL was actually stale and its one-use approval remains consumed. The flat-first proposal uses **independently issued UTC hours**, not fabricated predicted HL funding timestamps. It does **not** waive any original settlement oracle, infer historical zero funding, grant rights, or authorize financial orders.

Original policy bounds: BTC/ETH/SOL only, 20-minute maximum synthetic position hold, reject new entries in the last 25 minutes of the UTC hour and in the first 30 seconds after an hourly funding boundary. A future accepted original native Stop owner would request **`SHUTDOWN_FLATTEN` at T minus 480 seconds** and require **durable native `FLAT` by T minus 300 seconds**, with one-shot original Stop receipt. Uncertain orders, close ACK, clock, owner or source must latch STOP_INCOMPLETE and disable further entry. Hypothetical USDC notional cap $100 per position and 10-bp taker fee plus 5-bp slippage **per side** remain unverified scenario assumptions, NOT actual Hyperliquid account fees or economic acceptance. Three original finance positions may be proposed but still no true account/authority.

## Genuine selected R24 original native all-five-suite test
A separate original selected R24 installed interpreter `python.exe -I -B -S`, `NativeR17CpuBudget` and original Windows native source import roots (not current development `app` modules) executed five focused source-only tests from the current checkout:

- `test_hyperliquid_forward_flat_paper_policy.py`
- `test_hyperliquid_intrahour_stop_supervisor.py`
- `test_hyperliquid_intrahour_run_loop.py`
- `test_hyperliquid_consensus_settlement.py`
- `test_hyperliquid_funding_publication_lag.py`

**127 tests passed, zero failures/skips/errors**, with async testing explicitly enabled via the already-installed native `pytest_asyncio.plugin`. Verified original installed policy and Stop supervisor bytes and the R24 selection envelope remain unchanged; original 12/12 financial namespace roots stayed distinct and EMPTY. Original native JUnit evidence `logs/diagnostics/atlas-r24-hl-flat-first-method-20261118-r01/native-flat-first-with-async-junit.xml` SHA256 **`98c2e6c6e82ea2a89cbc64a3f87902c2f8bcd394de523e86720609db3431dc73`**. The *initial* test runner had disabled plugin auto-discovery and thus reached 71 passes before the first async test failed as unsupported; its original failure evidence was preserved separately at `initial-async-plugin-missing-junit.xml` SHA256 **`5a35b8c11d27c5d88a59ba97a5c945e21627f6e244eb286b9b75ef937ac3578d`**. The failure was a test-runner loading defect, not a financial Stop acceptance failure; selected native R24 was not modified.

## Genuine real-two-NTP instantaneous readback
From the **same actual selected immutable R24 source**, another isolated Python process executed original `IndependentNtpClock` with independent Google+Cloudflare public UDP NTP, cryptographically random request-origin binding, Windows monotonic anchor, original 2-logical-CPU native budget and full 12-empty-original-financial-root readback. At the sampled instant:

- Actual verified UTC: **2026-11-18 12:35:12 UTC**, independently measured uncertainty **139ms**.
- Next documented hourly boundary: **13:00:00 UTC**.
- Original Stop supervisor trigger at or before **12:52:00 UTC** (T minus 8 min).
- Mandatory **durable FLAT deadline 12:55:00 UTC** (T minus 5 min).
- **Actual financial account/ledger not initialized**. For this reason the reader invoked the original policy with *unverified position count 1 and unresolved close TRUE*, conservatively refusing ANY entry: `FLATTEN_OR_RECONCILE_UNVERIFIED_NATIVE_POSITION`.
- A separate counterfactual `native_unverified_positions=0` candidate check is **NOT** actual position evidence and cannot grant entry. At 12:35:12 UTC it was structurally ineligible anyway due to the last-25-minute entry cutoff. No actual financial Stop was executed.

Actual durable D-only evidence `logs/diagnostics/atlas-r24-hl-flat-first-method-20261118-r01/real-selected-r24-utc-flat-first-readonly.json` SHA256 **`ff6113d1365f7da615f5d19a45e19e265e8f0699b0b1499573cd1aabf76616d2`**. The NTP proof and timing window are **a single point in time**; they do not create a continuously owned original finance/Stop lease or guarantee future remote/public source availability.

## Honest remaining commissioning path
No original E1 source rights/budget/economic approval (0/3 genuine source acceptances), no two original incepted simulated USD/USDC accounts (0/2), no financial retained Windows Job/5+7 owner, no original initial two journals, no postinception `CONNECT_APPROVED_DATA`, no original source-publisher/127-epoch operational handoff, no accepted original actual <=8-sec native financial Stop/FLAT and no supervised one-hour Hyperliquid PAPER pilot. The **127 tests are source-level readiness, not finance-stage acceptance**. The selected R24 native release and all ten protected source pins remain unchanged. No automatic restart, C-drive Atlas storage/temp, VPS, paid data, wallet, credentials, provider trading API or live money.

**Outcome:** Original **flat-before-UTC-hour** method, strict genuine selected R24 Stop supervisor and run-loop contracts are source-test-qualified, real UTC readback worked, and the real preinception entry refusal passed. **Financial PAPER remains NO-GO; no claimed closure of E1, original Stop or financial owner gate.**

Planning estimate remains **roughly 8–15+ substantial verified execution batches** to a first truly supervised financial PAPER launch, assuming real source rights, budgets and account/native Stop protections can be accepted. This estimate is *not* a guaranteed countdown and may expand indefinitely when an external entitlement is unavailable. Months of subsequent PAPER soak happen after initial launch.
