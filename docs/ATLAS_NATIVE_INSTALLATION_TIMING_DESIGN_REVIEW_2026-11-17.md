# Native installation timing investigation and recommended design

**READ-ONLY INVESTIGATION COMPLETE. Recommend one continuously owned two-phase installation contract; source-only implementation approval is required.** No proposal-bound code, application archive, decision, selected release, financial namespace or original PIN assignment changed. No native scan, installation attempt, NTP/provider request or account operation ran in this investigation.

Starting checkpoint: `59b6ff550ccef2017bb852090090bac31640d3a7`. Historical native result: `docs/ATLAS_V2_SUCCESSOR_INSTALLATION_RESULT_2026-11-17.md`. Concrete review-only proposal: `docs/ATLAS_PHASED_INSTALL_SOURCE_REPAIR_PROPOSAL_2026-11-17.json`, SHA-256 **`9662bbce9831754f1b3bcfa52cea9d186f7378452e161122c130529722d92eda`**. That JSON is deliberately not an executable installation proposal or approval record.

## What the78.375-second predecessor cost contains

`scripts/release_selection.py::NativeInstalledReleaseVerifier.open` validates the exact receipt/hash/ACK, constructs one parent `NativePersonalReleaseIdentity`, calls one original `installed_readback`, yields the verified receipt while retaining the parent owner, checks the retained root on exit and closes that owner. It is not a single content read.

| Component | Actual source work | Timing evidence |
|---|---|---|
| Receipt and journal admission | Exact spec/receipt hash, release/path/flags, original durable ACK | Included in78.375s; separate duration UNKNOWN |
| Retained parent scan |10763 files /915 directory outputs, native IDs, link counts, ACLs, sizes, full hashes and exact namespace walk; retains real handles | Included in78.375s; separate duration UNKNOWN |
| Installed child scan | Original `-I -B -S` R23 Python, exact executable PID/creation-time versus retained process handle, installed-only paths/layout/version/module origins, another full native identity/ACL/hash/namespace scan, proof and zero retained-handle counts | Included in78.375s; separate duration UNKNOWN |
| Process/IPC overhead | Child creation/imports, bounded stdin/stdout proof, parent comparison, native exit wait and process-handle close | Included in78.375s; separate duration UNKNOWN |
| Subsequent clock qualification | Original real two-peer protocol for at least180 monotonic seconds and37 continuity samples | Completed; exact separate phase duration was not logged. Last bound139ms/peer difference1ms, then revoked |
| Other preflight overhead | CPU admission, source plan, root/SID/decision/host checks, NTP initialization and any qualification overrun |263.219−78.375−180=4.844s unallocated residual; **not a separately measured overhead time** |

Source/receipt-derived counts per full predecessor scan are265991191 content bytes,23958 data-plus-EOF read calls,10763 file opens,915 directory-output constructions and at least11678 ACL validations. Directory outputs reopen their ancestor chains:8513 ancestor-handle acquisitions per scan are derived from the exact paths. Thus the two scans imply21526 file admissions and1830 directory-output constructions, not merely1830 total Windows directory handles. These are successful-path counts from source and the preserved receipt, **not newly instrumented native events or per-operation timings**. The two full content passes total531982382 hashed bytes. Do not assign half the78.375seconds to either process.

Actual new copy work differs:9566 dependency reads totaling252648893bytes,10773 create-only target writes totaling266189938bytes, then an internal full target readback. The three byte streams sum785028769bytes, followed by a separate installed child reading266189938bytes. It also performs per-file creation, ACL/identity checks, flushes and namespace checks. Write/flush/antivirus/cache costs are UNKNOWN. The unchanged43.5seconds of planned pacing is an exact source-derived nominal value;293.625seconds is a conservative forecast, not observed copy performance.

## Can retained proof safely remove work?

Retaining the already verified parent owner through qualification/copy is sound within the original contract and is **already what V2 does**. The file open uses read sharing (native share1), so ordinary conflicting writes/deletes are denied while the handles live. Ancestor/directory handles retain native path continuity. This is same-user Windows custody, not immunity to an administrator or hostile code in the verifier process.

It does not make the installed child redundant. A parent file hash cannot independently prove that the installed interpreter starts with isolated flags, uses only its installed module origins, returns the exact native image/process proof and exits/cleans up correctly. Directory handles use read/write sharing (share3) and do not freeze the entire namespace; the contract must retain exact namespace/reparse checks. A saved receipt or matching PID is not a retained live proof.

In principle, a new identity-only parent custody adapter followed by the child's full hashes could avoid the parent's duplicate **content hashing**, provided every relevant file handle is retained before child verification, identities/ACLs/single links/namespace agree, sharing prevents substitution and cleanup is independently proved. No existing qualified public adapter supplies that narrower proof here. Its savings are UNKNOWN and it would change a security-critical verifier contract. **Do not implement that optimization as this minimum correction. Keep both original checks unchanged.**

There is also no repeated full predecessor scan inside V2's copy heartbeat to remove: its current selector/root/decision/clock/host checks are lightweight admissions. Claiming another78.375seconds of savings there would be false.

## Why the current combined600-second model cannot admit this cut

Measured elapsed at admission was263.219seconds, leaving336.781. Even the immutable minimum copy forecast150 + full independent readback180 + cleanup30 requires360seconds: a23.219-second shortfall **before** the3× predecessor term matters. Lowering only that multiplier cannot solve the observed refusal.

Under the actual forecast, copy293.625 + readback180 + terminal30 =503.625seconds, producing the documented166.844-second deficit. Perfectly overlapping the whole78.375-second predecessor interval with NTP would still leave88.469seconds of deficit under that unchanged model; implementing concurrent clock/verification ownership would add complexity without resolving it alone.

| Option | Assessment |
|---|---|
| Identical V2 retry or warmer-cache assumption | No material new evidence; not recommended |
| Lower forecast or shorten readback reservation | Unsupported calibration/changed safety policy; not recommended |
| Delete either predecessor proof | Loses a required custody or independent installed-origin property; rejected |
| New custody adapter to remove one content pass | Possible future research, unqualified and unnecessary for the minimum path |
| **Explicit separately bounded preflight and mutation phases in one live session** | **Recommended. Preserves all verification and separates their budgets transparently** |

## One recommended implementation contract

This is a **NEW authorization design**, not an interpretation of V2. V2's original600-second total and all its bytes remain untouched. A future changed controller needs its own source pin, new exact proposal, one genuine Windows-local INSTALL decision and explicit native execution authorization.

| Phase | Hard contract limit | Work and proof |
|---|---|---|
| A — read-only qualification |600s | Source/dependency/SID/decision/root/host checks; both original predecessor scans (each underlying180s limit preserved); continuously retained parent context; original180s NTP qualification; fresh boundary checks and failure cleanup |
| B — one code-only installation |600s | New create-only copy, internal native readback, full separate installed readback/receipt/ACK, owner/clock/handle/process cleanup |
| Paced I/O inside B |500s | Original32/128/.06 policy; copy, readback and ACK remain subject to this unchanged ceiling |
| Independent installed readback |180s | Full reservation and original child timeout; no shorter surrogate |
| Terminal reserve inside B |30s | Include ACK and complete cleanup; reserve15s of that inside the paced-I/O window for ACK/publication |
| **Overall invocation** |**1200s maximum** | Both phases and their boundary, with no uncounted pause or arbitrary timer restart |

The new overall maximum is explicitly20minutes versus V2's10minutes and requires new approval. It is derived from two bounded phases, not a suggested silent `600→1200` edit. Phase A retains two180-second native component ceilings plus180-second qualification, leaving60seconds for admissions/IPC/failure cleanup under its600-second limit. Native calls remain bounded by their existing contracts; no assumption that kernel/DNS calls are perfectly preemptible is made. Every overrun must refuse success and complete/preserve cleanup. The implementer must keep both phase clocks and one overall monotonic clock from their actual origins; future native timing is still required to establish real behavior.

A and B are **not separate commands or processes**. Obtain the single new local code-only decision before A; do not wait for another human decision between phases. The same installer process/SID/native creation identity retains the same original predecessor-verifier context throughout A→B. No serialized phase-A report, exited PID, reconstructed handle or disk flag may authorize B. Phase-A diagnostic JSON is evidence only. No preflight lease is resumable after process exit, failure, clock revocation or resource release.

Before B: independently refresh the exact current selector21/head, protected records, original root identities/ACLs and emptiness, target/receipt/journal absence, decision/source pins and host capacity. Recheck exact predecessor namespace/reparse metadata against the retained receipt at this boundary, using the existing bounded namespace checker; this is not another full content-hash scan. Then require the same genuinely qualified clock to be operational again and recompute both B and500s-I/O admission budgets after those checks. The boundary belongs to A; B starts exactly once immediately before its final admission, never retrospectively. Both the phase-A deadline and global deadline still apply at that instant.

The NTP clock's lifetime stays240seconds, refresh interval45seconds and uncertainty limit1000ms. Its original live two-peer re-observations may maintain continuity as implemented; never set a later expiry or reuse old qualifications. Require genuine current samples at the boundary, original30-second heavy-admission heartbeats, before/after blocking independent readback and before receipt/ACK. A180-second blocking child plus prior anchor age/cleanup must remain within the actual live capability; if it expires, refresh fails or sources conflict, fail closed rather than extending it. No Windows Time configuration, service action or new market provider is part of this design.

At B admission require BOTH: remaining phase-B time > copy forecast+180+30 AND remaining paced-I/O time > copy forecast+180+15. Check before consumption, again after priority/host/clock checks, at bounded native-copy checkpoints, before/after independent readback and through final cleanup. Consume a NEW exact local attempt only after these conditions pass, immediately before the original durable install intent. Set the copier's start to the genuinely new B origin **only under the newly approved phased contract**; never reset V2's timer, the global invocation timer, a running B timer or the NTP clock.

With the measured78.375-second predecessor and unchanged forecast, B reserves503.625seconds, leaving96.375seconds under its600-second cap. Copy+full independent readback takes473.625 forecast seconds; adding15seconds ACK allowance gives488.625, leaving11.375seconds under the500-second I/O cap. The full example totals766.844seconds including observed preflight and all reserved terminal work, within1200. This is a **credible scheduling path with every existing proof retained**, not a guarantee: the I/O admission margin is narrow, real write/flush costs remain unknown, and a future slow native run must stop rather than weaken the500-second cap.

## Resource, failure and evidence boundaries

Reuse the exact existing target `D:\AtlasRuntime\releases\2f0fcfd9741b8fd524f2e5921a79998373a689c9` and original receipt path. No rebuild, new application release, shortcut or replacement installation. The same10773 files/915 directories/266189938file bytes remain planned. Preserve the existing aggregate40000-entry/1GiB accounted-storage limits, original two-logical-processor guard, IDLE/pacing protection for native copy/readback, host RAM/disk/process admission and one independent installed-readback child at a time. Do not add a process pool, browser, provider, financial worker or new native authority. Diagnostic output must be bounded on D: and counted in the approved envelope; avoid cumulative full-inventory dumps during copy.

Phase-A refusal: close original owned child/handles, revoke the clock, restore CPU/priority, preserve evidence and leave the local attempt unused. After B consumption: preserve any target/journal/receipt/ACK/unknown tail; close only owned resources; no delete, overwrite, retry, automatic recovery or selector mutation. R23 stays selected. If ACK/receipt exists but cleanup is incomplete/late, do not return success; preserve the original refusal marker and exact two-stage successor selection refusal. Only a genuinely complete installation enables a later, separately approved local SELECT review.

Future evidence must distinguish exact phase entry/exit/admission times, total elapsed, current owner/retained-context identity, original independent child proof/exit/handle closure, actual live clock samples/rechecks/revocation, forecast versus actual copy/internal readback, independent full installed readback, native file/directory IDs/ACLs/hashes, resource charge, durable original receipt/ACK and all cleanup. Log timing around existing original calls without replacing their authority objects. If a parent/child split cannot be safely instrumented without changing their verifier, retain the composite and mark the split UNKNOWN; do not delay the minimum scheduling correction for cosmetic profiling.

## Offline checks completed and limits

The analysis verified the pinned source call graph, exact protected/source/archive/decision hashes and prior receipt/content inventories. A pure, non-operative schedule model passed12 examples: fitting phased reservations; phase-A expiry; exited owner; lost retention; expired/unqualified clock; absent approval; insufficient500-second admission; slow copy; readback overrun including its180-second cap even with overall room; terminal overrun; and a slow-but-bounded A. These are12 analysis examples, **not production controller tests or native evidence**. No installed Python child or native scan ran. Previous171 unit passes remain historical; no Python/Node product suite needed rerunning for documentation-only work.

## Exact minimum approval requested

**Authorize source-only implementation and offline qualification of this two-phase design in `scripts/atlas_single_successor_control.py` and necessary `tests/test_single_successor_control.py`, plus replacement review/pin/documentation artifacts.** Keep both original predecessor verifications and all native copy/readback/clock helpers unchanged; reuse their existing interfaces. Add phase/global budget, same-live-context, fresh boundary, real-envelope, old-decision isolation, fault/cleanup and non-resumable-preflight tests. Prepare one new pinned proposal/local INSTALL review only after that source qualification. This approval would permit **no native scan/installation, no decision consumption/creation, no selection and no financial/provider/PAPER operation**. Any additional helper change must be identified and separately justified before expanding the scope.

The genuine V2 decision remains untouched/unused, not transferable to changed code. No new Windows-local review should be repeated before the corrected source is qualified and pinned. R23 remains at the last independently verified revision21 with all12 original roots empty; this analysis performed no new native identity scan. All ten protected file hashes and three legitimate PIN edits are unchanged. B1/C1/D1/E1, all21 historical decisions, QD WATCH-only, provider hold and methodology-review-only status remain. **PAPER OFF / production NO-GO.**
