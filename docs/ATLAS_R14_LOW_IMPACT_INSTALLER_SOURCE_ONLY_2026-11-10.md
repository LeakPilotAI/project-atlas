# Atlas R14 low-impact installer adapter — source-only implementation (2026-11-10)

## Terminal scope and outcome

**New R14-specific native code-only installer adapter implemented and tested; NOT INSTALLED OR APPROVED.** The prior R14 create-only source archive remains pinned to frozen commit `7ff9d3dba2eabe110f843c13efac49464805de2a`. This adapter is a new **workspace-side** coordinator written **after** the frozen source package, analogous to the previously reviewed R13 workspace-side adapter. It is *not* inside the frozen R14 ZIP and must be separately reviewed before any actual native code installation.

New tracked files: `scripts/atlas_r14_low_impact_installer.py` and `tests/test_atlas_r14_low_impact_installer.py`. The installer script exposes only `inspect()` from its CLI. There is **no executable install CLI**; direct `install(execute_approved=True, clock=...)` is also hard blocked by `APPROVAL_SHA256=None`. The old consumed R13 consent and its exact occupied target cannot be substituted for a new R14 grant.

## Exactly pinned source and native plan

- Frozen R14 source commit: `7ff9d3dba2eabe110f843c13efac49464805de2a`; ZIP at `logs/diagnostics/atlas-r14-source-only-20261110-r01/atlas-source.zip`, SHA-256 `22e4d00cb61c56d0b298c059e597937696df8deeca25c7ec6b38ec5ff01e192a`.
- 953 source tracked files, source inventory SHA-256 `bf7c37a4e424a7947b46636df06fc860253ee46abc038aa80b496e09b9d09367`; 9,566 native Python dependency files, dependency inventory SHA-256 `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91`, receipt SHA-256 `b1363f4514d3cdce4a1914e79d14842ece94136ed5d035ea195b4883da99a7a0`.
- Pinned R14 source-only preflight review `source-preflight-not-approval.json` SHA-256 `91c181a823c4dc20fd65067dce69356159c8beb202c4d416f68dd267c298f99d`. Exact status `SOURCE_ARCHIVE_AND_NATIVE_PLAN_VERIFIED_NOT_INSTALL_AUTHORIZATION`; zero activation/financial flags.
- New create-only proposed native location: `D:\AtlasRuntime\releases\7ff9d3dba2eabe110f843c13efac49464805de2a`; planned **10,519 files**, **912 directories including root**, **263,456,250 bytes**. Existence/selector checks run before source preflight, and again immediately before any future native copy.
- R12 remains selected with exact selector SHA-256 `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`. The previous R13 partial native tree remains preserved and unselected; its 427-byte refusal journal SHA-256 `6ab85e9feb4842ea80d26008165df7741497de248959488ce651e2f20a2992ec` is pinned and checked. The R13 final native acceptance receipt remains absent.

## R14 installation safety implementation (not execution)

- Enforces create-only new R14 release path and receipt/journal, refusal of occupied destinations, old R13 failed tree and exact terminal refusal journal intact, and prior R12 selection unchanged.
- Reuses tested `LowImpactEnvelope`: Windows `IDLE_PRIORITY_CLASS` before source/dependency hashing, CPU priority/selector checks at least every 32 native admissions, 60ms sleep every 128 admissions, same 500-second deadline, one owning process, priority restored after scope. Deliberate pacing does not guarantee future host responsiveness.
- Future `install` requires a **new** hash-pinned one-shot R14-specific consent bound to the exact operator SID, R14 archive/source/dependency values, and all-false selection, financial, provider and startup flags; rejects old R13 schema or any widened permission. The adapter cannot create that consent or self-authorize.
- Requires real independent two-public-peer NTP runtime identity and 180-second native qualification, then rechecks consent and create-only layout, uses historical creation-handle native copy, fixed-size identity/ACL/size/SHA-256 post-copy proof, isolated installed Python readback, terminal nonfinancial receipt; any failure preserves the partial and terminal refusal journal, no retry into occupied location.
- This source-only work did not run native copy/readback, select a release, change the Windows clock, connect providers, enroll financial accounts, or submit any PAPER/live trades.

## Verification

Single Windows **IDLE-priority** Python pytest runner invoked R14 + retained R13 narrow adapter suites: **45 passed, 0 failed/skipped in 4.67 seconds**, exit 0. Includes genuine read-only R14 archive/dependency plan validation, synthetic R14 consent and widened-privilege refusals, exact R13 terminal journal pin, occupied-target refusal, IDLE inheritance/restore and pacing safety. Earlier first run had one *test-only* expected-error-prefix mismatch (the shared R13 pinned-byte verifier raised its historical R13 prefix), corrected without bypassing the guard; subsequent R14-only 14/14 and combined 45/45 passed.

**No operational gate promoted.** Next step is a separately reviewed/authorized R14 exact one-time native installation (ideally a non-gaming idle-host session), original native creation-handle + fully completed readback, followed by separate release selection. This still does not accept Quality Dips, Hyperliquid or Kalshi financial PAPER operating gates: **0/9 independently accepted, NO-GO**. No Project Genesis work, GitHub push, file cleanup or paid services.

## 2026-11-10 additional completion-boundary review

A subsequent source-only review found the future R14 `admit()` callback called `IndependentNtpClock.require_operational()` on **every** native I/O admission. The pinned 10,519-file workload has a static model of roughly 91,327 admissions across copy and native readback; `require_operational()` issues and prunes a timestamp-cache entry on each call. This was a potentially avoidable CPU/cache amplification, **not** independently established as the cause of the prior R13 timeout.

R14 now uses a distinct `_native_admission()`: `LowImpactEnvelope.tick()` still checks the 500-second deadline **every admission**, with Windows IDLE priority and R12 selector readback every 32; the qualified two-peer NTP clock is re-attested **on the first admission, at least every 32 admissions, and at least once per second if native disk operations are slow**, plus again after source preflight, before child readback, and before the final nonfinancial receipt. It refuses immediately at the next bounded checkpoint on revoked/invalid NTP. This does not waive the initial 180-second independent-clock qualification.

The former installed child readback timeout used a 540-second origin despite the **500-second** outer deadline. New `_remaining_installed_readback_timeout()` uses the actual enclosing monotonic start/deadline, refuses to start a child with 35 seconds or less remaining, caps the readback timeout at 120 seconds or the actual remaining time minus five seconds, and requires terminal deadline/clock/selector/one-shot scope checks before any final receipt. Thus the verifier cannot be deliberately granted more time than the installation envelope permits.

Focused R14 + R13 IDLE-priority regression: **49 passed, 0 failed/skipped, 3.39 seconds**, including synthetic 32-call and one-second NTP admissions, clock refusal at checkpoint, backwards monotonic re-attestation, insufficient readback time refusal and legacy safety tests. No native installation or account/provider access. **R14 is still not installed and `APPROVAL_SHA256=None`; R12 remains selected; failed R13 remains preserved.** Separate source/authority review and explicit installation approval still needed before any native copy.
