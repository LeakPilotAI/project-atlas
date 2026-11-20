# R13 500-second timeout: offline admission-cost analysis and bounded pacing fix (2026-11-10)

**Disposition:** Source-only R13 installer efficiency repair and deterministic tests. No install, partial reuse, operational promotion, financial PAPER order, provider call, or bulk filesystem read. The operator was playing NBA 2K27 during this diagnostic, so only lightweight metadata/scripts/synthetic checks ran.

## Reconstructed observed failure

The **previous one-time approved** R13 code-only installation created `D:\AtlasRuntime\releases\c7dfb85665bbcd5ba4494c33365d4dff8ea92b12`, finished the native creation loop, and entered post-copy native readback. The Windows IDLE installer refused with `R13_LOW_IMPACT_INSTALL_DEADLINE_PRESERVE_PARTIAL` before final installed proof; the terminal journal reads `REFUSED_PRESERVE_PARTIAL_NO_RETRY`, final install receipt is absent, R12 remains selected and the one-time approval has been consumed (`APPROVAL_SHA256=None`). Details are in `docs/ATLAS_R13_ONE_SHOT_CODE_INSTALL_REFUSAL_2026-11-09.md`.

## Lightweight offline cost result

Using ONLY the preexisting 2.97 MB native Python dependency receipt and 4.85 MB source ZIP manifest, without touching native installed-file contents, `logs/diagnostics/atlas_r13_static_admission_cost_20261110.py` calculated the per-phase admission count directly from the pinned `scripts/native_install_candidate.py::_copy_prepared_code` loops and file sizes:

| Model input/output | Value |
|---|---:|
| Source files / native Python dependency files | 952 / 9,566 |
| Total planned files / bytes | 10,518 / 263,440,156 |
| Estimated copy-stage admissions | 56,429 |
| Estimated post-copy readback + namespace admissions | 34,898 |
| Estimated full workload admissions | 91,327 |
| Old 60ms pauses every 32 admissions | 2,853 sleeps, **171.18 seconds** |
| New 60ms pauses every 128 admissions | 713 sleeps, **42.78 seconds** |
| **Potential intentional-wait reduction** | **128.40 seconds** |

These are **static estimates, not measured sleep durations or an identified sole cause**. They exclude native Windows handle and ACL costs, disk scheduling, antivirus, independent NTP refreshes, selector digest reads, Python overhead, installed child proof and game contention. The prior timeout remains a genuine refusal. Playing NBA 2K27 is **not demonstrated to have caused it**.

## Source-only correction

In `scripts/atlas_r13_low_impact_installer.py`, `LowImpactEnvelope` accepts an independently validated `pace_every` parameter. The **future** install path uses `check_every=32, pace_every=128, pause_seconds=.06`, retaining:
- Windows IDLE CPU class and readback before native I/O, priority verification and R12 selector pin every **32** admissions
- the same **500-second** work deadline and deadline checks after pauses and on each admission
- 60 ms bounded pauses every **128** admissions, with no subprocess pool or unbounded I/O loops
- create-only destination/receipt and independent NTP, approval and native copy/readback requirements, all unmodified

Synthetic regressions cover 256 admissions with 8 selector/priority checkpoints but 2 pauses, lost IDLE priority refusal at the 32nd admission **before** any pause, invalid cadences, and the unchanged one-time-permission/preflight refusal. The genuine inspector test is now state-aware: it must refuse if the earlier used R13 destination/journal is present, rather than bypass create-only safety.

**Test result:** single idle-priority targeted R13 suite **31 passed, 0 failed/skipped in 1.02 seconds**, with no native installation/scan. Source and tests alone do **not** demonstrate a future install will complete within the deadline or remain imperceptible to a running game.

## Recovery boundary / next production work

The existing R13 destination is occupied with a failed, unaccepted installation. **Do not retry into it, remove it, convert it to an accepted release, recycle the one-time approval, or adjust the 500-second deadline without separate technical review.** Actual operational recovery requires a **new, empty, create-only native release-generation namespace**, updated version-safe installation and selection pins, a fresh explicit one-shot approval for that specific target, independently qualifying NTP, complete original native creation-handle/readback acceptance, and a deliberate idle-host installation window. During gaming, limit development to lightweight offline work.

Formal financial PAPER remains **NO-GO 0/9**, selected R12 unchanged; no Project Genesis or deferred cleanup changes, Windows boot/time alteration, provider/account access, PAPER/live order or GitHub push.
