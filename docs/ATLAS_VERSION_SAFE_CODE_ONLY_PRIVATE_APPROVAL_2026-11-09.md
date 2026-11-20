# Atlas scoped local code-only install decision and genuine NTP preflight — November 9, 2026

**Nonfinancial milestone only.** User-directed next-stage work created one exact local create-only operator decision for copying the frozen version-safe candidate, without authorizing release-selection, simulated account inception, private provider access, orders, service startup or live trading. The private native SID decision file resides only in ignored `logs/diagnostics/atlas-version-safe-code-install-approval-20261109.json`, **NOT in Git**. Its complete SHA-256 is `6e134be6fc9d1a1bc96bcfeb95440e9ffc89dac3286ab7b77713ec36f490bfec`; source requires that exact hash, the native current SID and exact `ONE_SHOT_UNSELECTED_CODE_COPY_ONLY` scope. The hash binds local file bytes but is NOT an independently signed operator credential. This authorizes no financial PAPER operation.

## Genuine independent NTP verification

- Actual Windows read-only `python -B -m scripts.observation_runtime.atlas_independent_ntp_clock_preflight` completed **successfully** with Google + Cloudflare UDP NTP, **180.0 actual monotonic seconds**, **37** operational samples, initial bound **141 ms**, final bound **139 ms**. The clock was revoked at exit; Windows Time service was not used, and no code/native account/selection/provider/order mutation occurred.
- This standalone run proves nonfinancial clock connectivity/continuity **at its observed time**; it does NOT reuse its expired lease to authorize later installation. Every future native code installation must independently initiate a fresh 180-second check on the same owned clock immediately before a one-time copy.
- Corrected `scripts/install_version_safe_candidate.py` so the `prepare_reviewed_code()` call resets the install/copy deadline **after** the 180-second NTP preflight; the full 600-second native copy/readback budget is no longer reduced by the mandatory preflight. The code rereads the exact source/dependency/target pins and native selector after preflight. Tests now assert the correct ordering.

## Scoped local operator decision

- Exact `ATLAS_VERSION_SAFE_CODE_INSTALL_APPROVAL_V1` approval was created atomically with a native Windows SID read and a create-only file operation in ignored local diagnostics. It is pinned in the separate new installer, not the immutable historical V7/V8 installer. The approval contents and native SID are not committed or printed.
- Native read-only `require_separate_operator_approval()` passed with the current Windows SID and pinned SHA. Selection and financial-action fields are false; one-shot is true; target remains a new 10,574-file/265,175,432-byte nonfinancial release directory.
- Regression suite for version-safe, V8, source-dependency plan and NTP adapters: **129 passed, 8 skipped, zero failed**; skipped tests are not operational evidence. Existing selected V7r11 head remains fixed and `r0012.json` remains absent.

**Next exact action:** invoke the separate CLI's `--execute-reviewed-code-only --confirm-scope NO_PAPER_START_NO_FINANCIAL_ACCESS_NO_SELECTION` once. This will perform its OWN fresh 180-second dual-peer NTP qualification and, only if all immutable/native/source/operator requirements remain true, create only the new unselected runtime and its nonfinancial receipt. Preserve any failed partial attempt without retry or promotion. Existing V8 bytes and selected V7 remain unchanged.

**Full PAPER financial production: NO-GO, 0/9 formally accepted operational prerequisites.**
