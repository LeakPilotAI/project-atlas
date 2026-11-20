# Operational PAPER readiness - actionable acceptance and activation

Base:f355a88f4e2db29a1efb8579e1e5e7e47bee82b3;branch chatgpt/atlas-rebuild-v1.
Assessment and source work only. No gate acceptance or operational activation.

## What changed in source

`scripts/volume_inspector/operational_autonomous_store.py` supplies an uninstalled
OperationalAutonomousStore using the existing FS2 append/replay/arithmetic/audit
engine and FS3 projection verification. There is no new financial engine.
The existing financial_record_store.py gains a small record-version dispatch;
its original default schema names and disposable provisioning are unchanged.

The new codec requires distinct QD_AUTO_OP_PIN_V1, INCEPTION_V1, INTENT_V1,
RECORD_V1, COMMIT_V1, ACK_V1 and PROJECTED_ACK_V1 versions. Old fixture/manual
pins or inception bytes refuse; no copying, renaming or migration API is supplied.
The operational inception binds accepted enrollment, SIMULATED execution and
explicit calculation parameters. The existing autonomous parameter schema is
used only as an arithmetic specification inside this new envelope: release and
provenance must match accepted enrollment and its inception digest. It is not a
historical fixture account relabeled operational. All actual test instances and
their authority proofs remain synthetic and confined to diagnostics directories.

Construction requires accepted enrollment, current custody, clock, projection and
an authenticated admission port. Root/pin/projection binding is checked before
financial access. Inception must already exist: this adapter cannot initialize
an account and its inherited provisioning entry explicitly refuses. No paths,
keys, credentials, issuer, service, API registration or launcher are installed.

Each write needs an authenticated PENDING reservation bound to the exact command,
current pin and enrollment before original FS2 intent/record/commit/FS3 projection
ACK publication. Custody CAS is retained. A separately verified reservation ACK
is required before returning success. Any uncertain result or post-write authority
loss poisons the instance and calls mark_unknown; unavailable custody cannot be
claimed to have durably recorded that marker. Recovery is not implemented as
automatic retry. Same operation retries are idempotent only with accepted custody.

This removes the **hardcoded test record/pin codec** dependency. It does not yet
install an operational authority or connect the new codec to an accepted runtime
reader/bootstrap. The V5 entry still enforces its disposable execution domain.
Completing that narrow composition/reader/publication handoff against accepted
operational bindings remains engineering; deleting V5's confinement is not a plan.
Existing FS3 reporting arithmetic is retained, not newly operationally enrolled.

## Acceptance checklist - nothing pre-approved

| Gate | Operator/reviewer decision (cannot be coded into acceptance) | Engineering or evidence needed | Condition for promotion |
|---|---|---|---|
| B1 | Operator confirms autonomous $1,000 hypothetical,eligible ranked stocks/ETFs,$100 entry,one position,long-only,no scale-in,2bps fee+2bps slippage per side,overnight allowed,Stop preserves holdings. Named scope reviewer accepts new epoch and exclusions. | Bind exact inception/policy/resource/release IDs;retain unresolved legacy obligations as excluded,not closed. No original archive was accessed in this task. | Authenticated,profile-scoped review accepts the isolated account and explicitly handles historical exclusions; no self-certification or silent waiver of historical B1. |
| C1 | Named ownership reviewer accepts actual process/resource/writer roster and legacy writer exclusions. Operator authorizes bounded native observations. | Observe actual owned parent/worker identities;verify all five roles and scanner/legacy paths cannot write selected roots;prove admission closure,pending/UNKNOWN drain,owned Stop and restart. Source roster exists;native fixtures do not accept actual writers. | Retained native evidence plus reviewer disposition covers every real writer/resource and failure condition. |
| D1 | Accept or reject proposed reduced single-user PAPER threat model;name issuer,clock,currentness/recovery custodians. Explicitly accept residual risks below. Historical strict decisions remain unchanged until formal disposition. | Implement/install accepted signing/session verification,durable PENDING/CAS/current/high-water/revocation,UTC anchor plus monotonic expiry,and backup/recovery adapter. Bind real native resource identities. New operational codec is source-implemented;these dependencies are not installed. | Independently authenticated acceptance and tested real mechanisms,or formal profile-scoped acceptance of specifically reduced assurances through existing governance;not local hashes alone. |
| E1 | Choose data feed and confirm authorized automated simulation/non-display and dashboard use. Separately authorize connection and supervised bounded autonomous session. | Provider entitlement evidence;authenticated bid/ask,size,timestamp,venue/session/calendar,halts,corporate-action/instrument mapping,freshness and reconnect;integration/failure/recovery trial. | Accepted rights and operational evidence plus explicit session release permission. No provider was contacted for market data. |

An operator's architecture/risk preference is not independent source authentication.
If a required reviewer or custody requirement cannot be met, record BLOCKED rather
than silently substituting Codex,ChatGPT,a fixture signer or an environment variable.
Actual identities/fingerprints and signatures belong in reviewed private enrollment,
not public Git. No approval box in this checklist constitutes acceptance.

## Same-user,D:-only limitations requiring an explicit disposition

- Owner/SYSTEM ACLs and native identities help against accidents and other users;
  they cannot exclude arbitrary code running as the same account or administrator.
- Same-user signatures do not create independent operator identity. Same-drive
  reservation/high-water files coordinate but do not prove anti-rollback if the
  entire drive is restored coherently or replaced. Local hashes cannot fix this.
- Active data,local custody and source on D: share disconnection/power/controller
  failure risks. No physical power-loss durability is established by process tests.
- A backup copy on the same D: is not an independent backup. Independent removable
  custody/backup needs separate approval and custody outside that shared failure
  domain;application deployment remains D:. If all copies must remain on the same
  physical drive,loss/rollback assurance remains explicitly reduced/unresolved.
- A stopped parent is not proof that child writers drained. Elapsed timers are
  not UTC authenticity. Reboot,clock discontinuity,missing pins,UNKNOWN effects
  or unexpected native identity must refuse resume. No automatic restart.

## Read-only local inventory actually observed

Verified branch/HEAD and clean tracked tree before work. Existing source/state
require injected issuer,current custody,clock and writer acceptance;no accepted
bundle is installed by this change. Credential stores/keys/private account records
were not inspected,so this is not a claim that no credentials exist anywhere.
The13 protected directories were not opened or reverified;their earlier retained
status is not fresh acceptance evidence.

Permitted Windows PowerShell5.1 observation:current token IsAuthenticated=True;
W32Time exists and is Stopped;Stopwatch.IsHighResolution=True. The sandbox's first
observation returned a filtered unauthenticated token and no visible service;that
was an observer restriction,not evidence that Windows lacked the service. No time
query,clock setting,service start,account/ACL change or process termination occurred.
High-resolution elapsed timing does not supply authenticated UTC. No real writer
process roster or independent custody was certified from these observations.

Source-only quote inventory includes investment/providers.py,quality_dip_quotes.py
and robinhood_equity_quotes.py. Display-price fallback to midpoint/one-sided/public
quotes is not accepted executable L1 evidence. Existing provider labels or presence
of a quote client prove neither entitlement nor authenticated displayed size.

## Authenticated L1 candidates - no subscription/account inspected

| Candidate | Documented capability | Required choice/evidence before use |
|---|---|---|
| Alpaca market-data-only SIP | Latest best bid/ask;real-time streaming.SIP is consolidated;IEX is one exchange and must not be represented as consolidated NBBO. | Verified SIP entitlement/API credentials,automated/non-display and local display rights,instrument coverage,quote sizes/timestamps and operational freshness. No broker order SDK or broker execution integration is needed. |
| Massive stocks NBBO quotes | Authenticated WebSocket NBBO quote channel. | A plan explicitly including real-time quote access,applicable exchange/user/non-display permissions and API entitlement;do not assume every WebSocket plan grants NBBO. |
| IBKR L1 data-only | API top-of-book subscriptions documented. | Applicable subscriptions/API permissions plus local session/client dependency. Not the shortest route if no such account/client already exists;no order-routing capability may be introduced. |

Primary documentation reviewed2026-10-25:
[Alpaca feed/entitlement FAQ](https://docs.alpaca.markets/us/docs/market-data-faq),
[Alpaca streaming quote fields](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data),
[Massive stocks WebSocket](https://www.massive.com/docs/websocket/stocks/overview),
[IBKR API L1 requirements](https://www.interactivebrokers.com/docs/general/market-data-subscriptions/introduction).
Public documentation review is not a feed connection or proof of this operator's
license. No purchase,subscription,credential installation or market-data request.

## Shortest supported activation sequence

1. **Decision:** operator and named reviewers dispose of the four checklist rows,
   especially the local PAPER threat model,legacy exclusion scope and custody limits.
   Keep all21 decisions unchanged until their required formal acceptance occurs.
2. **Source engineering:** wire the new operational codec into the existing
   publisher/read/V4-V5 composition under accepted operational resource/pin versions;
   implement only the selected real issuer,reservation/custody,clock and L1 adapters.
   No new engine,ledger,dashboard or speculative security layer is needed.
3. **Separate authorization:** inspect the exact existing resources and actual owned
   process/writer roster;install only reviewed dependencies/configuration after
   accepted evidence. Do not regenerate the epoch or alter the13 directories ad hoc.
4. **Separate authorization:** publish once-only real hypothetical inception with
   durable receipt;verify native source,projection,report,currentness and isolated
   backup/restore. Ambiguous publication stops for recovery review,not retry.
5. **Separate authorization:** install/start only the owned loopback read bridge;
   verify original Control Center/page,GET-only behavior,exact cash/account IDs,
   unavailable valuation,owned graceful Stop and restart refusal.
6. **Separate authorization:** connect the selected licensed L1 source and verify
   live quote quality/disconnections/session/halts before admitting any PAPER fill.
7. **Explicit session release:** issue one bounded autonomous PAPER grant;verify
   automatic risk-limited entry/management/exits,Pause/Stop,overnight continuity,
   daily reconciliation and failure recovery. Then seven authorized sessions and
   extended30-60session validation. No automatic promotion to real-money trading.

No supported launch date or readiness percentage follows from offline pass counts.
The next necessary operator input is the scoped acceptance/role/custody/provider
decision,not permission to place individual trades. Implementation/source permission
is distinct from actual dependency installation,inception,connection and startup.

## Validation

Final adapter/FS1/strict-contract/startup-lock selection:105passed,0failed,0skipped;
11new codec cases. Native FS2/FS3:120passed,1true-symlink case NOT EXECUTED due
to missing privilege. A restricted sandbox attempt failed at mutex reopening
(1pass/1fail);permitted native rerun retained the original assertions and passed.
Two V5 native financial regressions verify default-codec compatibility separately.
Total227passed,0finalfailed,1privilege-skip across three disjoint selections;
not one combined invocation. Ruff/compile passed for three changed Python files.
PAPER policy audit564runtime files plus targeted checks of the two native storage
files found zero issues. Exact roadmap backup/readback/history,state safety fields
and append-only queue preservation passed.
Earlier test setup used a nonexistent SQL column (1failure);corrected to the actual
body column. A later expected-empty-position assertion failed (6pass/1fail):the
canonical ledger intentionally retains closed history. Corrected to verify every
remaining quantity is zero while preserving the exact cash assertion. Failures
remain in private diagnostics;earlier overlapping passes are not added.

B1/C1/D1/E1BLOCKED;seven phases and all21decisions preserved.
PAPER startup NO. Production NO-GO. Genesis untouched;original UI unchanged.
