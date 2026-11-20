# R7E44F — market-readiness preflight

**Source audit complete. Overall market readiness: AMBER. Unattended external alert delivery: BLOCKED by intentional policy.**

2026-10-16, America/Chicago (CDT, UTC−05:00). Passive file observation:
09:15:52 UTC / 04:15:52 CDT. Branch `chatgpt/atlas-rebuild-v1`, HEAD
`f9df47b4cd80dd647d85043aba617cf00c4e6dc0`, unchanged.

This execution made no live API/provider calls and invoked no lifecycle commands,
including manager Status. It did not start/stop Atlas or Docker. The last conclusive
process-level STOPPED verification is R7E44E; passive lifecycle files remain absent
in this audit. File absence alone is not a fresh process-ownership proof. Today's
regular-session feed freshness, detection latency and real notification receipt
have **not** been accepted by this source audit.

## Monitoring services and prerequisites

| Domain | Existing services and feeds | Coverage / dependency limits |
|---|---|---|
| Common runtime | Windows background manager, API/desktop control, Postgres, Redis, runtime watchdog; backend venv and existing environment file | Manager verifies root/run/PID/creation/executable/command/parent ownership and owns lifecycle locks. Normal dependency launcher must verify Atlas-specific containers; no global Docker action is needed. Database initialization retries up to 15 times at 2-second intervals. Redis startup ping failure is logged; `/health` only reports configuration. |
| Stocks / equity research | Investment scanner → YFinanceClient prices, bars, fundamentals/valuation → investment stores/tape → Quality Dips consumer and ladder monitor; Robinhood universe research and morning brief | Quality Dips quote overlay prefers public Robinhood RHJ underlying bid/ask; classic public Robinhood quote fallback, then Yahoo 1-minute pre/post-market and quote-field fallback. No brokerage account/order access. Research/history and public quote coverage are not a guaranteed consolidated real-time U.S. stock tape. Legacy equity day trading is explicitly inactive. |
| Crypto / perpetuals | Hyperliquid registered adapter; REST `meta`, `metaAndAssetCtxs`, candles/funding data; allMids WebSocket; general scanner, opportunity/PAPER trackers, manual-perp service, micro discovery/management, PAPER mirror/delivery loop | Live registered exchange is Hyperliquid. Crypto monitoring here principally uses its perpetual-market universe. Liquid allowlists and discovery filters limit coverage; count actual runtime markets rather than claiming every crypto or spot venue is monitored. BTC accumulation reuses existing research/adapter paths. |
| Crypto Quality Dips research | `/api/investments/crypto-quality-dips/status` and evidence store | Explicit `MANUAL_OPERATOR_ONLY` ingestion, autonomous collection false, external feeds not connected; not a second active crypto collector. |
| Alerts | Candidate generation, E48 typed delivery/dedup contracts, Discord client/subscriber store, investment notifier, PAPER reconciliation/evidence alert services | Bot connectivity and subscriber persistence do not grant outbound authority. Both central automated senders currently return false before transport. E133–E136 production lifecycle activation gates remain closed. |

Dependencies also include usable outbound provider connectivity, correct local time,
writable Atlas logs/data, valid existing Discord configuration for bot connectivity,
and applicable provider packages. Configuration presence is not a connectivity test.
No credential values, subscriber IDs or account data are included in this audit.

## Current configuration and desktop workflow

An allowlisted read of `backend/.env`, source defaults and this audit process's
environment is saved in `allowlisted-config.json`. It is configuration evidence,
not a substitute for querying a future API process.

| Setting / loop | Current configured behavior |
|---|---|
| Gaming opt-in | Default false; supported Gaming Mode launch injects true into its child environment |
| Micro discovery | Normal 60 seconds; Gaming Mode `max(normal,180)` = 180 seconds |
| Micro PAPER management | Enabled, independent normal 8-second sleep interval |
| General market scanner | 15 seconds, unchanged by Gaming Mode |
| Manual-perp refresh | 20-second sleep, unchanged by Gaming Mode |
| Manual-perp delivery / PAPER mirror | Default 10-second sleep, unchanged by Gaming Mode |
| Investment research scanner | Enabled; open interval 900 seconds, closed interval 21,600 seconds; price refresh 900 seconds |
| Quality Dips consumer | Enabled; configured 60 minutes |
| Accumulation ladder monitor | Separate 30-second loop; fresh-quote fetch for existing ACCUMULATE candidates, with cache age requested at 20 seconds |
| Robinhood universe research | Source defaults: four names per batch / six hours, universe sync daily, first pass after 90 seconds; independently clamped and not slowed by Gaming Mode |
| Morning brief | Enabled; configured 08:00 ET, weekday-only narrow send window; not continuous quote monitoring |
| Discord | Token and owner-list presence confirmed as booleans only; automated send paths intentionally denied regardless of enabled notification flags |

Intervals are sleeps after work, not guaranteed wall-clock service deadlines.
Provider retries, cycle duration, thread backlog and event-loop stalls can lengthen
the actual time between observations. No cadence configuration was changed.

The existing Atlas Background GUI is passive on opening: it displays "Status not
checked" and starts no service. Click **Atlas Status**, then choose **Start Atlas
Background** or **Start Atlas Gaming Mode** only after a conclusive STOPPED result.
Both Start buttons are disabled otherwise; Stop is enabled for a verified running
session. It launches hidden controller processes and polls completion asynchronously.
Closing the GUI does not issue a service stop. The dedicated Gaming launcher uses
the same ownership manager and restores its caller's environment afterward.
Normal Start does not explicitly clear a pre-existing inherited gaming variable;
verify the actual API mode rather than relying solely on the button caption.
No GUI or shortcut was opened or modified in this audit.

## Freshness, recovery and status indicators

| Layer | Implemented rule | Important interpretation |
|---|---|---|
| Startup readiness | HTTP 200 from health, research, command summary, PAPER reconciliation, plus healthy Atlas Postgres/Redis; three consecutive green checks, normally 5 seconds apart | Does not inspect provider ages, market coverage, reconciliation body eligibility, or successful notification receipt. HTTP 200 can represent warming/cached research. |
| Equity quote overlay | Cache 15s; LIVE ≤120s, FRESH ≤900s, REFERENCE ≤96h, then STALE; missing/reference values cannot trigger a ladder | LIVE/FRESH are actionable for existing ladder rules. The 15-minute allowance suits research context but is not a near-real-time opening alert SLA. Provider/effective timestamp must be checked, not file modification/retrieval time. |
| Investment fields | Price 15m; daily bars 36h; fundamentals 45d; valuation/macro 7d | Per-kind freshness. Future timestamps classify UNKNOWN. Long-lived fundamentals are not stale just because they are not intraday. |
| Hyperliquid shared ticker cache | TTL 25s; serialized refresh; rate-limit wait/backoff paths at 30/45s; failed fetch can return prior cached data | No hard maximum stale-cache age is enforced here. Cache expiry is not evidence a new provider quote arrived. |
| Hyperliquid REST | 30s total / 10s connect timeout; installed hardener allows three attempts, 0.4s then 0.8s sleeps for transport/timeouts/5xx | Client 4xx, including 429, are not retried by that hardener; shared cache has separate 429 handling. Registry logs a hardening-install failure instead of aborting boot. |
| Hyperliquid WebSocket | 20s ping/ping timeout; reconnect backoff starts 2s, multiplies 1.5 to 60s; cancellation exits | No per-symbol receipt timestamp/age accompanies `_mids`, and retained mids are not cleared on disconnect. |
| Manual-perp refresh failure | Installed hardener locks retained setups WAIT/STALE, clears alert candidates and persists the lock on exception | Success means refresh returned, not independent provider-origin timestamp attestation. A service-running flag alone is insufficient. |
| PAPER mark helper | Nominal 30s age limit; six-hour pending order age limit | **Fixture-confirmed gap:** missing timestamp returns true; future timestamp also passes the one-sided age comparison. |
| PAPER micro management | Missing/nonpositive mark can become MARKET_DATA_UNAVAILABLE for an evaluated position | Retained numeric prices are not rejected on provider age here; an entirely empty price map skips `_manage_open`. An active 8s task is not proof of fresh marks. |
| Equity network recovery | RH request bounded at 5s plus async allowance, fallback surfaces; Yahoo async timeouts and scanner retry settings | Canceling an await does not forcibly terminate a blocking worker thread; sustained timeout/backlog behavior needs observation. |
| Equity session clock | Weekday 09:30–16:00 ET | Source clock has no exchange holiday/early-close calendar. Independently verify today's exchange calendar before a market-open acceptance; this audit did not verify an external calendar. |
| Investment market-open transition | After a closed-session cycle, sleeps the configured 21,600 seconds | No opening-bell wakeup interrupts that sleep. A pre-open launch can miss the opening scan even though its task remains running. |

Dashboard strengths: Quality Dips exposes source/session/age/quality and distinguishes
live-supported versus last-supported prices; the health page shows observed request
latency and refuses to invent host resource telemetry. Shared polling has timeouts,
one in-flight refresh and skips hidden tabs, which helps gaming resource use.

Dashboard limits: `/diagnostics/discord` derives `can_send_dm` from connection and
recipient presence even though the central sender is denied; it is not delivery
permission or receipt evidence. System Health labels Hyperliquid/Quality Dips ONLINE largely from
running flags; investment scanner staleness uses six hours, much looser than its
15-minute price policy. The shared runtime chip says "Live data ready" after a
successful JSON response without checking provider timestamps. Hidden-tab polling
stops, so a minimized page cannot be relied on as an active observer or alert channel.

### Verified provenance defect, not an observed live market incident

The adapter prefers any stored WebSocket mid over the newly fetched REST mark and
stamps the resulting ticker with local retrieval time. A pure fixture with retained
WS price 100 and new REST mark 200 returned price **100**, raw mark **200**. There is
no stored per-mid age to decide if the WS value is still current. Consequently a
successful REST request or newly refreshed setup timestamp does not establish that
the chosen price is fresh. No fabricated production price was used and no live
market incident is alleged. This gap should be repaired in separately authorized
source work before certifying unattended data integrity.

## Safeguards and unattended gaming verdict

PAPER_ONLY / MANUAL_ONLY remain unchanged: the Perp board declares manual execution,
risk endpoints forbid live capital/automatic real-money execution, and equity boards
carry manual-only/no-broker-execution restrictions. PAPER simulation can still open,
mark and close records during approved normal runtime; manual-only does not mean
PAPER journaling is disabled. Risk limits must be observed without changing them.

**Suitable for a bounded, operator-observed Gaming Mode data check after approval;
not yet certified for dependable unattended opening alerts while gaming.** R7E44E
proved startup/ownership/shutdown and actual 180s/8s settings. Its brief 675MiB API
working-set observation is not a gaming performance guarantee. Other loops, equity
research and watchdog work remain active. Automated external alerts are intentionally
unavailable, and stale-price provenance/health indicators need attention. Windows
power/sleep/network availability and actual foreground-game impact were not tested;
no power policy or resource optimization was changed.

## Evidence and isolated validation

**117 passed, 0 failed, 66.12s**, across 20 selected files covering transport retries,
equity quotes/provider errors/freshness, PAPER stale-data protection and risk API,
fake alert delivery/deduplication, health UI/operator readiness, gaming discovery,
GUI behavior/profile/inheritance/passive opening, and actual-API diagnostic contracts.
Two dependency deprecation warnings were reported (audioop and TestClient/httpx).
The complete selection is in `test-selection.json`; production data and external
connections were blocked by the isolated runner. No real Discord sender was used.

**Four additional audit-only probes passed**: retained WS-mid preference, missing/
future mark timestamp acceptance, intentional early-false production senders, and
the six-hour closed-session sleep without an opening-bell wakeup.
Passing these assertions **confirms gaps/policy**, not market readiness. Probe runs
and the later scheduling probe are preserved separately. The initial Ruff finding
is retained separately; final probe Ruff passed. Six lifecycle/UI/readiness files
parsed successfully; ten selected Python copies compiled. Git diff integrity passed.
No full-suite or full production-code Ruff claim is made.

Persisted prior-run evidence: last successful investment cycle ended
**09:00:43.197368 UTC**, before regular U.S. hours according to the source clock.
The provider-health file contains cumulative 322,317 requests / 321,217 successes,
340 timeouts, 452 empty and 308 other failures, zero recorded 401/429; about 99.659%
aggregate success. These are accumulated counters without a session denominator,
not today's uptime or live feed reliability. They do not prove that every watched
stock had a current usable quote. The API was not contacted during this preflight.

Evidence directory: `logs/diagnostics/r7e44f-20261016/`, including protected/source
hash baselines, worktree listings, allowlisted configuration, exact source references,
passive record metadata, test selection/logs, fixture probes, parser/Ruff/compilation
results, roadmap before-copy and final integrity result. No production code was
modified. Existing source and protected PAPER/configuration evidence remain intact.

## Highest-priority readiness gaps

1. **External alerts intentionally blocked.** Both `send_discord_alert` and
   `deliver_investment_alert` return false before transport. A connected bot and
   passing fake-sender tests cannot prove notification receipt. Preserve the policy;
   reactivation requires its own approval and consent/outbox activation acceptance.
2. **Perp price provenance not fail closed at every boundary.** Untimestamped retained
   WS mids override newer REST prices; stale-cache retention and missing/future mark
   acceptance can hide age. A narrow separately approved timestamp/expiry repair
   with regression tests is preferable to declaring unattended readiness.
3. **Readiness and health can overstate data health.** Enforce/observe per-feed
   source ages and cycle success rather than HTTP/running flags. Holiday/early-close
   handling and market-open transition remain unverified.
4. **Equity coverage and latency need market-open evidence.** A closed-session
   scanner pass sleeps six hours with no opening-bell wakeup (fixture confirmed).
   Thus an early pre-open startup can miss the opening scan. A 15-minute research
   scan, one-hour consumer and candidate-only 30s ladder monitor serve different
   purposes; they do not imply continuous all-watchlist stock anomaly alerts.
   Reference quotes must remain context-only. Report monitored versus unmonitored names.
5. **Unattended gaming longevity remains unmeasured.** Preserve current independent
   PAPER cadence; observe provider timeouts/thread backlog and responsiveness in a
   bounded live check. Extended benchmarks/optimization remain separate R7E45/R7E46 work.

## Separately approvable live-data acceptance plan — not executed

Suggested name: **R7E44G bounded market-open data acceptance**, with alert transport
activation explicitly excluded. Approval should state one Gaming Mode startup, a
maximum **10-minute** live observation after normal readiness, and one graceful
owned shutdown. This is a short functional check, not extended gaming benchmarking.

1. Before the planned window, independently confirm today's exchange calendar and
   regular/extended session boundaries. Schedule the single start **during the
   verified regular session**, so the initial equity cycle does not enter the
   closed-session six-hour sleep. This bounded plan does not repair pre-open
   scheduling. Repeat branch/HEAD/worktree preservation and
   conclusive ownership/process/port/lock preflight. Abort if ownership is ambiguous;
   do not stop an existing user session. Retain the existing Discord denial and all
   production lifecycle/no-backfill gates. Do not change subscriptions or authority.
2. Start once through the supported Gaming Mode launcher. Permit only its normal
   Atlas-owned dependencies and ordinary PAPER/background evidence writes. Verify
   actual process identities, sole listener, manager running, API/dashboard HTTP,
   three readiness greens, `ATLAS_GAMING_MODE=true`, 180s discovery and active normal
   8s PAPER management. If startup fails, clean up only through conclusively verified
   owned controls; no force/recovery or second start.
3. Use observational reads: `/health`, `/diagnostics/gaming-runtime`,
   `/diagnostics/runtime-latency`, `/diagnostics/paper-reconciliation`, and
   `/api/perps/paper-risk`. These route names were verified from source. Manual
   snapshot/board GETs invoke observability code that can create a missing/invalid
   cohort marker: before using `/api/perps/manual` or
   `/api/perps/manual/board?limit=1`, confirm the existing marker is valid, or omit
   those reads and report the observability limit. Do not silently initialize it.
   Use static dashboard page loads only if JavaScript is not automatically fetching
   additional mutable surfaces. Capture response bodies/ages, not just status codes.
4. Select at least BTC and ETH plus one verified in-universe liquid perp, and three
   actual configured liquid equity symbols. Record universe/allowlist inclusion and
   exclusions. Use a small number of unauthenticated read-only provider requests for
   underlying RH/Yahoo quote timestamps and Hyperliquid REST marks/candles; no account
   endpoints, trading endpoints, synthetic signals or production test notifications.
   Keep requests serial/bounded and within existing provider limits.
5. Observe two or more advancing provider-time observations after market open.
   For equities, require genuine source timestamps ≤120s old to claim opening LIVE
   acceptance; 120–900s is only FRESH research context, older/reference/missing fails
   the live criterion. Inspect source/session and independent quote agreement without
   assuming identical bid/ask/mid semantics. For perps, require positive finite prices,
   advancing actual provider observations, plausible OHLC and nonnegative volume/OI;
   funding may be zero/negative. Inspect three micro discovery passes if completed
   within the cap, manual refresh progression, management activity and no new stalls.
   No candidates or no price change is not automatically a failure; missing advancing
   timestamps/coverage evidence is INSUFFICIENT EVIDENCE.
6. Do not treat the known untimestamped WS-mid path as proven fresh by REST comparison
   alone. If provider-origin age is not observable, mark that lane BLOCKED/UNVERIFIED.
   Do not add diagnostic code, trigger refresh mutations, force reconnects or repair
   the source under this runtime-only approval. Reconnect failure injection stays
   in isolated fixtures; live recovery can be observed only if naturally encountered.
7. Treat Discord connection/subscriber-store reliability and local candidate/dedup
   logic as separate checks. Fake senders validate contracts; production automated
   transport must still return false. Real end-to-end notification receipt remains
   BLOCKED until separately approved policy/consent/recipient-specific delivery work.
   Do not generate trades, fake opportunities, test DMs or historical event backfill.
   If `/diagnostics/discord` is read, preserve only allowlisted connection/reliability
   booleans and subscriber count; discard owner IDs and do not treat `can_send_dm`
   as transport authority. No subscription command is needed.
8. Do **not** call `/investments/quality-dips` merely as a "read-only" health check:
   its GET path can refresh providers, persist forward/state/ladder records, invoke
   gated notification logic, and mark/terminal-close equity PAPER records. Its normal
   UI observation requires explicit acceptance of those documented side effects in
   a separate scope. Read existing equity provenance files/provider snapshots instead;
   a missing safe observable is a reported limitation, not permission to mutate.
9. At the first confirmed ownership/safeguard failure, or at the observation cap,
   reverify the exact run and gracefully stop once. Preserve all evidence; verify
   owned API/launcher/workers exited, no listener or lifecycle/lock remnants, prior
   journal prefixes preserved and post-stop reconciliation/risk reliability. Normal
   Atlas dependencies may remain running per manager policy; no global Docker action.
10. Report per-domain PASS/BLOCKED/INSUFFICIENT EVIDENCE, actual timestamps and gaps.
    One completed fresh equity cycle is required to claim scanner coverage; if none
    finishes within the cap, report incomplete rather than extending the run. No
    unattended full-session operation, R7E45/R7E46, alert enablement or publishing is
    authorized by approving this bounded plan.

Before executing this plan, decide whether to separately repair the identified
provenance gaps first. Nothing
in this preflight changes startup authority. Atlas/Genesis separation, permanent
gaming objective and the complete Prediction Market Intelligence V2 roadmap remain
in force.
