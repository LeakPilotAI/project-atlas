# Atlas R15 source-only successor candidate — verified freeze (2026-11-10)

## Outcome: source package verified; R14 remains selected and financial PAPER is NO-GO

A **complete, bounded successor SOURCE candidate** has been frozen with Atlas's existing deterministic `scripts.build_release_candidate.build_selected()` packager, without reinstalling any native runtime. It contains the reviewed R14 source baseline plus every subsequently tracked new *runtime* module, including the corrected writer-custody/clock/data preflight changes already committed in the workspace.

**Do not confuse "R15" in the candidate directory name with a released/installed version.** There is no new native R15 installation, selection, operating activation, account inception or PAPER trade. The candidate is identified by source commit `2c79a8d846d6b33669008114732ae5896153812a`, not a new immutable installed-release ID.

## Exact immutable source-candidate evidence

| Item | Verified |
|---|---|
| Frozen Git source commit | `2c79a8d846d6b33669008114732ae5896153812a` (clean tracked Git checkpoint at freeze) |
| Existing verified R14 source baseline | `logs/diagnostics/atlas-r14-source-only-20261110-r01/release-manifest.json`; SHA-256 `c01d65cd3491d6e03c713daf81a88d8a1410b3aa1a06b4f7d0586184ee77cc13` |
| Original R14 source zip SHA-256 | `22e4d00cb61c56d0b298c059e597937696df8deeca25c7ec6b38ec5ff01e192a` |
| Source files retained from original R14 package | **953**, SHA-bound from the old source baseline and freshly read from committed workspace sources |
| Additional reviewed, tracked new runtime files | **7**: three legacy R14 code-install/selection support scripts (currently consumed/disabled), three R14 public-data/readiness diagnostics, and native host resource admission |
| New total source inventory | **960 tracked files**; no untracked files, private credentials, or native Python dependencies copied |
| Canonical file-list inventory SHA-256 | `31df928fd182f4508ff84d4342eff5dc4ce6acb5cea68adc9f20265b23a8bb82` |
| Verified source-only zip SHA-256 | `f6cb597a53373efee929c306ae42537e16abcbcf6e57f7bd23ee92e8570160c0` |
| Source-only zip size | **4,887,669 bytes**, no native 263 MB copy |
| Source selection | `logs/diagnostics/atlas-r15-source-only-20261110-r01/source-selection.json` |
| Archive | `logs/diagnostics/atlas-r15-source-only-20261110-r01/package/atlas-source.zip` |
| Create-only nonfinancial freeze receipt | `logs/diagnostics/atlas-r15-source-only-20261110-r01/source-freeze-readonly-result.json` |
| Current genuine native selected version | **R14, revision 13**, selected envelope SHA-256 `6b1e04b8f733d46421c81a5d158dbafbecf052e6f3a8e8289d175caca96d4e31` |

The freeze required a clean Git HEAD, original R14 manifest + archive pins, replay of the genuine 13-record native selection store under its identity-bound lock, exactly the seven additional tracked runtime paths and no other new runtime additions, hashed bytes of each of the **960** tracked source files, and `build_selected` archive/manifest/ZIP verification. The output directory, explicit source-selection and freeze receipt were **create-only**, so any failure would have left evidence rather than overwritten a previous candidate.

Important corrected source SHA-256 values included in the new zip:

- `backend/app/services/unified_writer_roster.py`: `d26f821afee33855c8543f649f40f9f2fe25529043770dce59ecb8105945f697` (final-success lease/owner verification)
- `scripts/observation_runtime/personal_version_safe_release_clock.py`: `7357b0d537a2e4b7728b896337bfee48f8856ced5b6e2410c56c623191ea17c5` (real R14 13-record and future exact forward-chain compatibility)
- `scripts/observation_runtime/alpaca_iex_probe.py`: `6d3756c6307ca2b980968791c7f45288cb2cd41acac98f63c751340b2eccf33d` (R14 offline source admission)
- `scripts/observation_runtime/atlas_r14_hyperliquid_public_book_probe.py`: `51b1b0738e5fe3f7a31e9193a569da11aaad28b9a58a91e75e191c01d3bece26` (bounded data-only book diagnostics; existing public budget not replenished)

The package verifier returned `ATLAS_SOURCE_CANDIDATE_VERIFICATION_V1`, `supplied_bytes_consistent=true`, **`source_authenticated=false`**, **`installation_verified=false`**, **`activation_approved=false`**. These latter three are NOT test failures: they correctly describe the source-only scope. Separately reviewed native-dependency layout, host resources, external time, installation operator authorization, one-shot install receipt, and future native revision-14 selection would be required before the archive could serve an installed release. **None of those actions have been performed or authorized by this candidate.**

## Tests and resource safety

The new `tests/test_atlas_r15_frozen_source_archive.py` performs independent archive-bound source/ZIP checks, exact 960-member inventory and critical source-hash verification, tamper refusal, and checks all installed/financial/selection flags remain false. The frozen artifact is local and ignored in Git; when not present elsewhere, these artifact-dependent tests skip rather than fabricate it.

Focused existing candidate-selected inventory, candidate verifier, Windows namespace, R14 release-clock and financial-writer roster tests plus the new candidate test: **106 passed, 0 failed in 9.04 seconds**, using Atlas's Windows IDLE-priority single-test runner. No broad interpreter spawning, Docker or VS Code fanout, new native installation, 263 MB native dependency copy or API request was used.

## Next meaningful acceptance steps

1. Review the 960-file committed source candidate against retained dependency receipt, then prepare an **R15 code-only native installation proposal** with a unique unopened installation target. Independent operator approval is separate from this source packaging step. Never reuse R14's consumed installation/selection consent or partially failed R13 target.
2. Independently verify R15 installed release identity and original native file/ACL handles; separately approve one-time **code-only native selection** after any installation passes. There is no authority to do these actions yet.
3. Continue financial commissioning independently: existing PersonalPaper parent currently has **zero** activation children; confirm actual Quality Dips and Hyperliquid writer/source custody, approved free market-data freshness and rights, continuous financial UTC and ledger/Stop reconciliation. Only then run a supervised real PAPER-only two-lane session and enable the safe manually operated Start/Stop desktop shortcuts. Kalshi brand-new YES/NO contracts remain a separate unaccepted venue.

**Formal financial PAPER acceptance stays NO-GO, 0 of 9 operating gates accepted.** This release candidate is a reproducible code-delivery milestone, not a paper-trading milestone or evidence of profitability. No live trading, private account access, paid data/VPS, auto-start or Project Genesis edits occurred.
