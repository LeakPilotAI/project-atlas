# Successor installation safety review — stopped before approval consumption

**BLOCKED BEFORE INSTALLATION. The genuine local INSTALL decision remains unused.** No successor release directory, receipt, installation journal or one-shot attempt record was created. R23 remains selected at native revision21. There is no successor native receipt/artifact digest and no selection approval to request yet.

Starting checkpoint: `c44fedf6a1b39662aa59e5f126196db02b5929b3`. Candidate source remains `2f0fcfd9741b8fd524f2e5921a79998373a689c9`; no rebuild or new release was made.

## Independently verified current inputs

The bounded read-only check used the real proposal/decision validators, native current-SID reader, native selector and original root inspector. It ran under the unchanged original two-processor CPU guard and completed in4.125seconds. All temporary evidence stays under `D:\Work\Project Atlas\logs\diagnostics\atlas-successor-install-safety-20261117-r01`.

| Input or invariant | Result |
|---|---|
| Genuine local install decision SHA-256 | `c89bb83e24798750335b211134ce85fe0743ccf7a87d8a2b56de57895e4d475b` — exact match |
| Current operator SID / exact install scope / source / no-financial flags | Independently matched by original validator |
| Proposal SHA-256 | `28e22e70ea03c35724a4fad5229f7ea61f63343b14f6615002250a0cf73dc810` — exact match |
| Proposal-bound controller SHA-256 | `935afa325b47a8f2380443b83d90a98a42f59ad95f317f4d63fd15049edd333a` — unchanged |
| Candidate ZIP SHA-256 | `7036ba930870a58b1029091f3361a8b4b527a997ea9ff1597467fe6a2d2669f1` — exact match |
| Canonical source/dependency plan |1207 source +9566 dependencies =10773 files /915 directories /266189938 file bytes |
| Original native selected state | R23 source `96c6b85f76368a69bfd035cbcf3eb05776c21525`, revision21, exact approved artifact/head |
| Original financial roots | All12 native identities/ACL metadata matched, distinct and empty |
| Ten protected approval/recovery/receipt/PIN files | Original hashes unchanged |
| Legitimate R23 PIN edits | All3 preserved unstaged; no reset/stash/export/staging |
| Successor target, receipt and pending journal | Absent |
| Install attempt / selection decision / selection attempt | Absent |

This execution did not repeat the expensive full R23 native payload scan or9,566-file physical dependency scan. Those successful prior observations remain historical; current metadata/protected-record verification is not relabeled as a new full payload readback. No fresh NTP or provider request was made because installation was already blocked before either was necessary.

## Confirmed constructor and consumption-order defect

`scripts/atlas_single_successor_control.py::execute` writes the create-new `local-install-attempt.json` at source line181, then constructs `LowImpactEnvelope(max_seconds=600)` at line189. The real `scripts/atlas_r13_low_impact_installer.py::LowImpactEnvelope.__init__` permits only **30 through590 seconds** and rejects600 with `R13_BOUNDED_LOW_RESOURCE_POLICY_REQUIRED`.

Four actual constructor-only checks were performed without entering an envelope, making a priority change, launching a process, creating an attempt or copying files:

| Requested seconds | Real result |
|---|---|
|600 | Exact expected refusal |
|590 | Constructor accepted, not entered |
|500 | Constructor accepted, not entered |
|591 | Exact expected refusal |

Thus the unchanged approved controller would consume the decision's attempt and then deterministically refuse before clock qualification/copy. It must not be executed. The prior offline execution tests replaced this envelope with a double whose constructor accepted arbitrary parameters; they did not demonstrate compatibility with the real envelope. The earlier source qualification's installation-readiness assessment is superseded by this safety refusal. Its passing regression results, candidate content hashes and preserved native observations remain valid within their documented limits.

## Original R23 timing and current600-second review

Original R23 imports `CHECK_EVERY=32`, `PACE_EVERY=128`, `PAUSE_SECONDS=0.06`, `MAX_SECONDS=500` from the original R14 installer. Its180-second clock qualification occurs **before** its500-second paced copy/readback envelope. The successor's600-second total instead includes the predecessor deep readback,180-second clock qualification, paced copy/internal readback and independent final installed readback. The two phase arrangements are not equivalent.

Original R23's full copy actually reached `R13_LOW_IMPACT_INSTALL_DEADLINE_PRESERVE_PARTIAL`; its preserved audit found7910 of10763 files before separately authorized recovery completed the release. See the unchanged historical section in `docs/ATLAS_R23_NATIVE_RELEASE_SOURCE_PLAN_2026-11-13.md` and original protected refusal/recovery records. That failure is evidence against assuming a full copy is cheap; it does not establish the new controller's precise copy duration because its predecessor-readback behavior differs.

The current successor uses the envelope defaults, which pace every32 callbacks, not every128. Exact planned callback accounting from the real copier and pinned inventory gives92,863 budget callbacks:

| Nominal pacing | Planned sleep alone |
|---|---|
| Current successor defaults:0.06s every32 |174.06s |
| Original R23:0.06s every128 |43.50s |

This includes native-copy and internal readback budget calls, directory setup, dependency EOF checks and namespace traversal. It excludes real API/disk/ACL/hash time, host guard recovery waits, NTP overhead and independent final readback. It is a source-derived lower-bound estimate, not measured native-copy acceptance.

Using the prior73.906-second predecessor readback,180-second clock qualification, the existing maximum180-second final installed-readback reservation and15-second terminal reserve leaves **151.094seconds** for copy/internal readback. The current nominal pacing alone exceeds that conservative allowance. Historical timings do not guarantee present host throughput. The controller's existing minimum40-second final-readback admission check is not evidence that the full independent readback can finish in40seconds. No deadline has been increased or silently moved to exclude required work.

## Minimum separately reviewable correction — NOT IMPLEMENTED

Scope is the **excluded operator-support controller and its offline contract tests only**. Keep the exact application source, ZIP, inventory, destination, dependencies, R23 selection, three existing PIN scripts and all original financial records unchanged. No new application release or artifact is necessary for this support-only repair.

1. Validate the real pacing/envelope configuration before writing any single-use attempt. Reuse the original R23 **32/128/0.06** cadence and original **500-second paced-I/O cap**; do not broaden the envelope's590-second constructor limit or turn the total600-second limit into600seconds plus preflight.
2. Apply that paced-I/O envelope to copy/readback as in the original R23 phase arrangement, while a separate monotonic total deadline still covers all execution phases, including predecessor verification and180-second clock qualification. Preserve original current CPU, host, selector, root, decision and clock checks. Do not shorten or skip independent native verification.
3. Before consuming an attempt or creating the installation journal, require an explicit conservative budget for remaining full copy/internal readback, independent installed readback and terminal ACK/cleanup. Recheck it at native-copy admission boundaries. Reserve final readback explicitly rather than treating40seconds as sufficient. If supported timing evidence cannot justify the remaining budget, refuse before mutation; do not merely assume the faster cadence guarantees success.
4. Exercise the **real** envelope constructor/cadence in offline joined controller tests. Use injected clocks to prove total-deadline coverage, final-readback reservation, pre-consumption refusal, cancellation and complete cleanup. Cover the exact600-vs590 regression, delayed predecessor/NTP, slow copy/readback and no attempt on invalid configuration. No native copy is authorized as part of that source-only repair.
5. Pin the separately reviewed corrected support source and a replacement proposal. The exact original INSTALL decision binds the **old proposal**, which binds the **old support hash**. Preserve that decision as unused historical evidence; it **cannot authorize changed code**. A new genuine Windows-local decision and explicit execution authorization are necessary after corrected-source/timing qualification. No assistant-generated approval, changed PIN assignment, replay of the old decision or premature selection decision is permitted.

This is a proposed repair contract, not implemented code, a new proposal pin, a new financial grant or authority to rerun installation. A simple change from600 to590 alone is insufficient: it neither fixes phase budgeting nor the fourfold pacing difference or early approval consumption.

## Next human decision and current result

**Next decision:** authorize source-only implementation and offline qualification of the support-only timing/consumption-order correction above, preserving the exact candidate and existing unused decision. No terminal command or local approval review needs to be repeated now. After that repair is genuinely qualified and independently pinned, present one replacement Windows-local code-only INSTALL review. Prepare the separate SELECT review only after actual successful installation/receipt/ACK/readback.

No installation attempt occurred. Native successor receipt digest: **NONE**. Successor selection: **PENDING, NOT APPROVED**. Original R23 remains selected at revision21. Original simulated financial balances remain nonexistent; no accounts were initialized. Provider hold, QD WATCH-only, method-review-only status, B1/C1/D1/E1 and all21 historical commissioning decisions remain unchanged. **PAPER NOT RUNNING / production NO-GO.**
