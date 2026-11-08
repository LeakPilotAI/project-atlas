# QD V5 source-bound preview and pre-effect guard

Base: 2aff87593e93ab0ff959d3fb4173df2fb7e645b0, chatgpt/atlas-rebuild-v1.
UNIFIED_PERP_FINANCIAL_COMPLETENESS remains ACTIVE and incomplete.

## Implemented and verified

The actual AutonomousPaper decision preparation is shared by preview and commit.
Preview checks the coordination database against the acknowledged native cut,
uses the existing decision and FS1 transition, and returns the exact command
digest and projected receipt. It publishes no intent, diagnostic, financial,
report or control record and does not acquire the native writer mutex or latch.
Missing acknowledgements refuse rather than replay a financial callback.

Actual V5 preview retains existing enrollment, source, session, observation,
clock and writer-ownership verification. Accept can require the exact expected
command digest. Re-evaluation refuses a changed command before financial effects.
Cached acknowledged frames cannot accept another expected command. Standalone
and strict/manual behavior remain supported; no parallel native dispatch exists.

The operational QD store now supplies explicitly authenticated read-only cut,
preview and receipt inspection through its existing operational admission.
The base disposable store's operational-domain refusal remains unchanged.
No test pin is converted into operational evidence.

## Validation actually executed

Four disjoint final Python selections: **735 passed, 0 failed, 1 skipped**.
There are **17 new cases**; intermediate overlapping runs are not added.

| Selection | Passed | Failed | Skipped |
|---|---:|---:|---:|
| 25-file financial/perp/unified/FS1-FS3/policy/startup/archive-updater suite | 595 | 0 | 1 |
| Actual V3/V5, native preview, Stop and genuine HTTP suite | 78 | 0 | 0 |
| Operational QD codec and actual runtime factory | 32 | 0 | 0 |
| Operational perp codec compatibility | 30 | 0 | 0 |

The skipped true-symlink probe lacks Windows privilege (1314): NOT EXECUTED.
Native resources and genuine owned subprocess HTTP hosts were disposable.
The HTTP suite checks graceful host shutdown and port release; it is not a new
real browser, WinForms Control Center or full two-lane acceptance run.

New cases cover unchanged preview bytes, guarded receipt/state equality,
quote/clock changes before effect, revoked/expired/stale/closed evidence,
acknowledged and unacknowledged retries, concurrent previews/commits, changed
writer roster, stopped runtime and the actual operational factory guarded path.

Retained original failures: sandbox default temporary-directory access;
an initial assertion compared presentation fields to raw canonical state and
was corrected to inspect raw state; an initial HTTP selection omitted its
required confined-root variable (three skips). Final selections above resolve
those setup/assertion issues. Logs remain private under logs/diagnostics.
No power-loss durability, external custody or operational acceptance is claimed.

Targeted Ruff and in-memory compilation passed for all seven changed/new Python
files. The PAPER release audit inspected 580 source files with zero issues.
The approved archival updater succeeded; separate readback verified the exact
old master prefix/suffix, verbatim prior body retained in the same master,
byte-identical backup and one bounded current checkpoint. Original QD HTML/JS,
Python startup lock and FS1 legacy golden are byte-identical to base HEAD.

## Remaining engineering, not an external-only wait

1. Bind the real QD lane to unified custody using V5 preview then V5 guarded
   accept after durable reservation. Never dispatch store.execute alongside it.
   Verify both native financial and coordination acknowledgements before global
   ACK. Authenticate exact observation/frame/planner/component identities.
2. Bind existing perpetual discovery, plan and exit logic to accepted executable
   book/queue evidence and separate USDC risk. A manual resting-order plan is
   neither autonomous authority nor evidence of a taker fill.
3. Route QD shutdown financial effects through global reservation; connect the
   existing PerpShutdownCoordinator to accepted book-cache and actual writer
   roster/drain/owned-close composition. Do not infer ownership from PID alone.
4. Execute complete real-interface two-lane continuous, cross-process crash and
   Control Center lifecycle acceptance. Current counterpart-lane fixtures do
   not establish that assembly.

Command timestamps are re-evaluated: a clock tick between preview and commit
can conservatively refuse the expected digest. Do not weaken freshness or clear
an uncertain global reservation blindly to force progress.

## Minimum remaining operational actions

Finish the four engineering items above; obtain scoped B1 account/source and
epoch acceptance, C1 complete writer/ownership/drain acceptance, D1 accepted
local issuer/custody/clock/resource/recovery installation evidence and E1 provider
rights/executable data plus supervised release acceptance. Separately authorize
and verify inception of each isolated account ($1,000 USD QD and $1,000 simulated
USDC perp, no assumed FX consolidation), dependency installation and bounded
launch. Then run the authorized seven-day stability trial with daily financial,
data, restart and owned-shutdown evidence. The trial has not begun.

All 21 decisions/seven phases, original UI, startup lock and protected accounts
remain unchanged. No providers, operational services or Genesis were touched.
PAPER startup NO. Production NO-GO. Source work is not exhausted.
