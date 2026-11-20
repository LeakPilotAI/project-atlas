# R7E46S - provider acceptance decision package

Reviewed 2026-10-17; no market API calls or load tests. Evidence: logs/diagnostics/r7e46s-20261017/primary-source-review.json, dependencies.json and final isolated tests. Facts below distinguish documentation, installed source and unverified operational requirements. This is not a legal opinion or permission to activate.

## Verified primary documentation

The [official RHJ stock-token API page](https://docs.robinhood.com/chain/stock-token-apis/) specifies 60 requests/second and 15-second caching for prices. It describes the raw underlying-equity bid/ask and generation time. R's 5 logical starts/second ceiling is below that published ceiling; its default 15-second quote cache aligns nominally. This does not prove an account-wide rate allowance, applicability to the classic /quotes fallback, actual coverage or executable liquidity.

[Robinhood Chain terms](https://docs.robinhood.com/chain/terms-of-service/) describe limited use and redistribution restrictions. Exact Atlas research/commercial data rights and applicability must be resolved rather than inferred from public reachability. The official crypto trading API is a different product and supplies no equity-endpoint approval here.

[Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html?ncid=mbr_idnedulnk00000001) restrict automated data collection without prior permission. Reviewed Atlas release evidence supplies no such permission record. [The yfinance maintainer](https://github.com/ranaroussi/yfinance) also distinguishes library availability from Yahoo data rights and highlights personal-use/research limitations. No authoritative numeric Yahoo Finance request entitlement was established. Software licensing is not a market-data license. Commercial/SaaS redistribution cannot be accepted by merely baselining this code.

## Verified installed implementation

Installed yfinance 1.7.0 source in backend/.venv/Lib/site-packages/yfinance/data.py has cookie/crumb acquisition, cookie-strategy fallback and configured transient retries with backoff inside a logical call. 429 during crumb acquisition may be followed by a target request; HTTP>=400 can trigger a cookie-strategy retry before 429 raises. These internals are beyond R's logical-operation limiter. Source was read without running requests or modifying the environment; packages/versions are inventoried. Broad dependency lower bounds do not freeze these behaviors.

R quote defaults: 3 owned workers/provider, 6 combined, 64 queued calls/provider, 64 pending symbols, 6 quote coroutines, 30-second whole-quote deadline. 0.2-second minimum logical start spacing; zero Atlas automatic retries. Existing RH endpoint/Yahoo source fallbacks remain bounded. Shared 429/503/RATE_LIMIT cooldown uses at least 5 seconds or greater numeric Retry-After plus bounded jitter. Unsupported Retry-After closes admission for review. FIFO applies to admitted jobs, not weighted consumer reservations; capacity rejects are observable. Separate processes, custom clients and standalone cash-client transports are not globally covered.

Caller timeout/cancellation does not terminate a blocking library operation. Unstarted work is removed; started work stays owned, provider admission is quarantined, late results discarded, and shutdown fails explicitly if real thread exit cannot be confirmed. No worker force-kill is supported. This prevents false successful drain, but a permanently blocked non-daemon worker can keep the API process alive and trigger the manager timeout. Existing manager 30-second stop wait, research 20-second drain and quote 20-second drain are not a proven whole-lifecycle deadline. No real shutdown or load was run in S.

## Decisions / remaining gates

| Gate | Status | Required decision/remediation |
|---|---|---|
| RHJ documented ceiling/cache | PASS documentation; NOT TESTED actual traffic | Keep conservative ceiling; verify every caller cache policy and aggregate independent consumers during later approved observation |
| Classic RH /quotes fallback numeric allowance | BLOCKED / undocumented in reviewed sources | Obtain an authoritative allowance or separately scope its removal/replacement; no silent provider change in S |
| Yahoo automated-access permission and SaaS use | BLOCKED | Provide applicable permission/licensed alternative; operator approval alone cannot establish vendor rights |
| Yahoo internal HTTP pacing/retries/deadlines | BLOCKED | Pin/review installed transport and scope an isolated licensed-provider/transport contract before claiming a global HTTP limit |
| FIFO/queue/cancellation/drain mechanics | PASS only to final isolated suite evidence | Retain rejection metrics and fault regressions; no hard thread-termination claim |
| Stuck-worker operational recovery | BLOCKED | Explicitly accept fail-closed timeout/manual recovery limits or approve a separately isolated cancellable transport/process design; no force recovery now |
| Live coverage/latency/401/429/Gaming/PAPER cadence | NOT TESTED | Separate approved bounded acceptance after rights/scope gates; no load increase now |

Proposed future internal acceptance thresholds retained from P: 37-symbol sweep p95<=60s,p99<=120s,degraded<=180s;>=34/37LIVE/FRESH in 3 eligible cycles; nonfuture accepted timestamps<=900s,LIVE<=120s; no unexpected 401/429 or growing queues; API health p95<=1s and normal 8s PAPER management p95 interval<=10s/max<=16s. These are proposed internal targets, not vendor entitlements, measured results or approvals. No actual current market freshness can be asserted while Atlas is stopped.
