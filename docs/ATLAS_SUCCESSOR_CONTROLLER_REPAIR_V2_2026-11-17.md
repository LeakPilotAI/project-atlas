# Successor support-controller V2 repair — 2026-11-17

**SOURCE-ONLY REPAIR AND OFFLINE QUALIFICATION COMPLETE. REPLACEMENT WINDOWS-LOCAL INSTALL REVIEW READY.** No installation, selection, local approval, one-shot attempt, financial record or provider request was performed. The application archive was not rebuilt. All original protections remain.

The user explicitly authorized the minimum support-only correction in the prior safety review. Starting checkpoint: `67282a436e8d1aa4b434d4ed634190f4b3cd3675`. Only `scripts/atlas_single_successor_control.py` and its necessary offline tests changed; original application modules, pacing library/constants and R23 PIN scripts did not. Source repair commit: `c6446aa98632a2a283b1d2cc7660522b9418fe9f`. This support commit is **not a new application release**.

## Exact replacement pins

| Item | Exact value |
|---|---|
| Corrected controller SHA-256 | `6389ebfd3c283fafdf449143410e5a4f81de0e7685642d94109da640ff4444cc` |
| Offline test source SHA-256 | `55b4365a066f2d4b2b8ec1d285ec7736f5a4993a959b6df383a13d78e849c8cd` |
| V2 proposal SHA-256 | `44026303465ddd24c34dbfe6ab3c11f2c9b8af1a297632f828eee8c903104df3` |
| Review command SHA-256 | `55342bfca46f58c636706933be762750924de90f669a5160260f0d5b93a69b74` |
| Unchanged application source commit | `2f0fcfd9741b8fd524f2e5921a79998373a689c9` |
| Unchanged application ZIP SHA-256 | `7036ba930870a58b1029091f3361a8b4b527a997ea9ff1597467fe6a2d2669f1` |
| Unchanged source inventory digest | `5799507de6cdd5ac2cdf030c938cbca479d79a32f7173cb79644545376a3f3ff` |
| Unchanged merged content inventory digest | `a578044b4fd62ab418ef8a8bfd75a9a35a82444611847c183581f4118e756620` |
| Unchanged dependency inventory digest | `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91` |
| Preserved unused original install decision SHA-256 | `c89bb83e24798750335b211134ce85fe0743ccf7a87d8a2b56de57895e4d475b` |

Exact replacement proposal: `D:\Work\Project Atlas\logs\diagnostics\atlas-single-successor-control-repair-20261117-r01\proposal.json`. Public source/test/evidence pins are in `docs/ATLAS_SUCCESSOR_CONTROLLER_REPAIR_V2_PINS_2026-11-17.json`. The old proposal remains byte-for-byte intact. Its decision binds the old controller/proposal and cannot authorize this code. The new proposal has schema `ATLAS_SINGLE_SUCCESSOR_CODE_ONLY_PROPOSAL_V2`, binds the corrected self-source and exact immutable timing policy, and points at the **same** existing archive/destination/receipt/dependencies. No replacement approval is pre-created or inferred from source-only permission.

## Corrected execution order and deadlines

1. Start one monotonic600-second budget at function entry, before imports, input preparation, CPU admission, predecessor readback or NTP qualification. Invalid/backward/nonfinite clock observations refuse. There is no600seconds-plus-preflight allowance.
2. Construct the **real** original `LowImpactEnvelope` with `check_every=32`, `pace_every=128`, `pause_seconds=0.06`, `max_seconds=500`. Validate those exact original constants and constructor **before any single-use attempt**. Original590-second constructor ceiling is unchanged. The500-second paced-I/O cap remains; the separate total600-second deadline can be stricter.
3. Under the unchanged two-processor CPU guard, validate source/dependency plan, original R23/native root/protected records, actual SID/proposal-bound decision and create-new target. Refuse an existing attempt before deep preflight. Retain the real predecessor release files and independently read back the predecessor using original interfaces. Measure this actual current preflight duration, not cumulative CPU or an old observation.
4. Qualify the existing180-second independent clock and perform original clock/source/host/decision/native-root checks. No new one-shot record exists yet. Failure or timeout leaves the local decision unused. The original NTP source/quality checks and host CPU/space guard remain.
5. Before native-copy admission, calculate the exact nominal pacing from the pinned file sizes/callback inventory. Reserve copy/internal readback as **max(150s, 3 × current predecessor-readback seconds + planned pacing +15s)**. Also reserve the full existing **180s independent installed readback plus30s terminal/cleanup**. A bad/missing current duration or insufficient total remaining time refuses before consumption. Recheck after priority/clock/host admission costs and immediately before consuming the attempt and creating the install intent.
6. Only then may a separately authorized execution create its new single-use attempt and installation journal. Every native-copy admission callback checks the shared total budget, leaves180+30seconds available, verifies the original pacing/CPU controls and periodically refreshes exact native root/selector/decision/clock/host evidence. The copier's start time is the same function-entry origin. A slow copy never steals the final readback reserve.
7. Independently installed readback still has its complete180-second timeout. The short40-second assumption was removed. Before/after it, native identity/hash/count/closed-handle checks remain mandatory. The original create-new receipt and durable ACK are preserved.
8. The total deadline is checked again after clock revocation, native predecessor handle closure, original priority restoration and CPU-affinity cleanup. No success result is returned when those steps fail or exceed the total deadline. A post-copy/ACK cleanup failure appends the original refusal stage, even if an ACK was already written; that journal then cannot satisfy the exact two-stage selection gate. Partial/unknown outcomes are never retried or overwritten. As with the existing native interfaces, deadline checks do not assert that Windows kernel calls can always be preempted; a delayed/failed close cannot be reported as success.

Selection retains its distinct exact local decision, genuine installed receipt/ACK/artifact, original selector lock/current head, clock, resource ownership and cleanup checks. It now also validates its configuration/preflight budget before consumption and checks the full deadline after cleanup. No select mode was invoked during this repair.

## Scheduling model and evidence limits

For this unchanged10773-file/915-directory/266189938-byte candidate, the pinned copier has92863 budget callbacks and43.50seconds of nominal sleeps under32/128/0.06 pacing. This is source-derived accounting, not an actual completed native copy. The3× measured readback multiplier,150-second copy minimum,15-second model margin, full180-second independent readback and30-second cleanup reserve are a conservative admission policy, not fabricated Windows throughput evidence.

For example, with16seconds measured predecessor readback and200seconds already elapsed in total preflight, the copy reserve is150seconds and required remaining work is360seconds;400seconds remain, so budget admission can pass. With the earlier73.906-second readback, the copy reservation alone is280.218seconds; after the180-second clock phase this cannot fit conservatively within600seconds, so the new controller refuses **without consuming approval**. There is no guaranteed installation success on a slow host and no automatic deadline enlargement or retry. An actual future native execution must pass its own fresh preflight and all original readbacks. This source-only repair does not claim native installation timing or financial acceptance.

## Actual validation

- Final broader profile: **171 distinct Python passed,0 failed,0 skipped,4 deselected,0 warnings** in9.13seconds pytest /12.094seconds guarded process /13.141seconds bounded parent. It includes all44 current controller cases,25 new versus the original19. Earlier36-focused and171-regression runs overlap and are not added.
- The real original envelope constructor, priority lifecycle, deadline and pacing methods participate in joined controller tests, with only Windows API/kernel and physical copy/readback/clock ports injected. Tests no longer replace the envelope with a permissive constructor. Coverage includes real600 rejection/original500 acceptance, original128 cadence, changed pacing constants, delayed inputs/predecessor/NTP, expired/missing clock, no attempt on priority/preflight failure, copy reservation exhaustion, late readback, final cleanup errors/timeouts, duplicate attempt, unchanged financial/no-selection flags, V2 schema/hash/policy refusal and old decision rejection.
- Broader source/archive/namespace/native-plan and original R13/R14 pacing/security tests passed. Four deliberately excluded cases were a native child-priority launch and three actual historical operational-plan inspections; no native acceptance or financial-child launch cases were collected. Exclusions are listed verbatim in the retained runner/results. No timeout or crash occurred.
- No-cache Ruff F passed the two changed Python files. No frontend files changed, so Node was not rerun; the previous80 passing Node tests remain history, not new results added here.
- Exact bounded command: selected R23 `python\python.exe -I -B -S logs/diagnostics/atlas-single-successor-control-repair-20261117-r01/bound.py regression-final`. The retained `validate.py` contains the complete seven-file profile, explicit four deselections, disabled pytest cache/plugin autoload, D:-only basetemp/XML and original two-processor guard. Outer deadline180seconds. No known crashing timed-tracing/audit-hook combination was enabled.
- Actual replacement default `review` passed against the real archive/dependency plan; the actual real envelope constructor accepted32/128/.06/500 without native entry. Read-only original selector/native metadata refresh passed: R23 revision21,12 distinct empty financial roots, ten protected file hashes unchanged and actual current SID matched the old unchanged decision. No successor target, receipt or installation journal exists; no old/new attempt or new local decision exists. This metadata observation is not a new full10763-file native scan.
- The future local command was parsed with Windows' real argument parser and its Python code compiled, without executing a local approval prompt. Exact source/evidence hashes are retained under `D:\Work\Project Atlas\logs\diagnostics\atlas-single-successor-control-repair-20261117-r01` and the public pins file. All new temporary work stayed on D:; intensive tests used at most two processors. Provider/NTP requests:0.

## Exact next Windows-local action

Open **`D:\Work\Project Atlas\logs\diagnostics\atlas-single-successor-control-repair-20261117-r01\Review-Successor-Install-V2.cmd`** in a genuine visible Windows-local console. Review the displayed new proposal/controller hashes, unchanged candidate/destination and timing policy. If approving, type the entire displayed scope:

`APPROVE_ONE_ATLAS_WRITER_RECOVERY_CODE_ONLY_INSTALL_NO_FINANCIAL_START`

This creates only **`D:\Work\Project Atlas\logs\diagnostics\atlas-single-successor-control-repair-20261117-r01\local-install-decision.json`** bound to the current SID and V2 proposal. It does **not** install or select. Do not use the old review command or copy/reuse the old decision. Hidden/piped/unsupported console input fails closed. No assistant-created decision exists.

After the genuine new decision exists, report its actual SHA-256 and separately authorize the exact bounded code-only installation. A native preflight may still refuse on current timing/clock/resource evidence while leaving that new decision unused. Only successful native create-new copy, full identity/ACL/hash readback, durable receipt/ACK and cleanup can make the later **distinct** local SELECT review available. R23 stays selected until that separately approved selection. Never run an old approval against changed support code.

**Current result:** repaired support source and replacement review ready; installation NOT attempted; native successor receipt/artifact digest NONE; selection pending. Original financial account roots remain uninitialized and the three legitimate PIN assignments are preserved unstaged. No account, provider, financial activation or PAPER grant exists. QD WATCH-only, provider hold, method-review-only status, B1/C1/D1/E1 and all21 historical decisions remain. **PAPER NOT RUNNING / production NO-GO.**
