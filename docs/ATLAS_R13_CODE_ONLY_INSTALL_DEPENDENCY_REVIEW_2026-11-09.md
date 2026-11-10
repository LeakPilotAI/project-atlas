# Atlas R13 — pinned code-only installation dependency review (2026-11-09)

**Disposition:** APPROPRIATE FOR REVIEW ONLY. This is **not** authority to install, select, start, connect to any provider, or place real/simulated financial orders.

## Exact source candidate being reviewed

The previously verified source-only archive remains at `logs/diagnostics/atlas-r13-source-only-20261109-r01/atlas-source.zip`, pinned to **commit `c7dfb85665bbcd5ba4494c33365d4dff8ea92b12`**. SHA-256: `20167da274294223333ea4668d288514176a675e9308a298786abd0b46b8f39c`. It contains **952 tracked runtime source files, 10,791,263 raw bytes**. Canonical selected-file inventory SHA-256: `c070130867636c27ae3ca31f01921a186445e7f4bc8b7ea2e9b14900893680e4`. Source selection and archive verification are separate from installed application verification, which has **not** happened for this candidate.

## Existing native dependency source: inspected, not copied or mutated

The `scripts.native_install_plan.prepare_install_inputs` source planner independently accepted the above archive plus the previously installed `D:\AtlasRuntime\releases\fca29cfe7760a28d2569b8b4b91ed1ea99804c3c` Python 3.12 runtime receipt. Dependency receipt:
`logs/diagnostics/qd-d-runtime-coordination-installation-20261028.json`, exact receipt SHA-256 `b1363f4514d3cdce4a1914e79d14842ece94136ed5d035ea195b4883da99a7a0`; canonical files-inventory SHA-256 `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91`.

A separate fresh read-only physical file walk opened each of **9,566** native Python dependency files, rechecked regular-file type, size, opened-file identity, pre/post modification metadata, and SHA-256 against that original receipt. **All 9,566 passed**, reading **252,648,893 bytes**, with **882 parent directories** checked for ordinary-directory type/reparse status. **Zero mismatches detected.** This is file-byte/type integrity *at observation time*; it is **not** a native ACL/custody attestation, clean dependency entitlement audit, cryptographic independent software-signature validation or guarantee that a later install cannot race with an attacker.

A separate semantic check inspected **88 installed Python distribution `METADATA` files** and verified their contents against the old receipt; every metadata hash matched. The pinned source commit's `backend/pyproject.toml`, SHA-256 `8ef76e01de46ac4192efaca89fcdea0b77bb31825b565b053babe7615fed8a54`, declares **21 runtime requirements**. The installed Windows-local Python **3.12.10** satisfies the `>=3.12` constraint. **106 dependency declarations** were evaluated (including relevant extras/transitive metadata); **no missing or version-incompatible requirements were detected**. This evaluates declared package metadata under the local platform, not all possible dynamic imports, provider rights, license terms or upstream security advisories.

The strict planner's complete collision/path/capacity check accepted **10,518 target files in 911 directories, 263,440,156 total bytes**. No destination directory was chosen or created; no files were copied or installed.

## Regression evidence

The unmodified source-only native installation and release-selection tests:
`tests/test_native_install_plan.py`, `tests/test_native_install_candidate.py`, and `tests/test_release_selection.py` passed **93 tests, zero failures or skips**. The earlier cross-strategy SOURCE/PAPER safety regression on the same c7df source returned **138 passing tests, zero failures** (one unrelated dependency deprecation warning). No guarded native acceptance suite was bypassed.

## Review record and controls

Pinned machine-readable record: `docs/ATLAS_R13_CODE_ONLY_INSTALL_DEPENDENCY_REVIEW_R1_2026-11-09.json` (review-only, all installation/selection/financial permission flags **false**).

**The selected native release is still R12**; native selection file `D:\AtlasRuntime\selection\r0012.json` remained SHA-256 `f685ff5c5d55ab87c4ee47b651afb823faa8d3696da4db120624bfac67c7c0c7`. No R13 native install, release selection, startup shortcut, operating source grant, paper account/writer or simulated/live order occurred. Project Genesis, paid feeds, existing provider budgets and credentials are untouched. GitHub remote has not been pushed.

## Exact next actionable step

The next milestone is to implement and independently qualify a **new code-only installer adapter** for precisely this pinned source and the independently revalidated dependency receipt. It must use native identity/ACL and create-only readback at a *new* destination, forbid overwriting installed R12 or copying data/secrets, require genuine independent time/custody and a **new exact operator approval**. An installer must never infer authorization from this review or reuse the old one-shot R12/V8 pins. A subsequent native code-only selection needs its **own** reviewed single-use approval.

Even after a code-only installation, **financial PAPER remains NO-GO, 0/9 accepted workstreams**: original QD issuer and valuation evidence, Hyperliquid funding/oracle source rights, financial independent clock, separate USD/USDC PAPER accounts, owned financial source writers and proven one-click Stop/flatten are still uncommissioned. Nothing in this report grants an exception.
