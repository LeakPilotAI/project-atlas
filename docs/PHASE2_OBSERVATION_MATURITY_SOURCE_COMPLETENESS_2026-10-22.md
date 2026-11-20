# Phase 2 offline observation maturity and source completeness

Status: scoped synthetic acceptance only. Phase 2 HOLD, Phase 3 blocked, production NO-GO. No provider or trading authority is established.

`forecast_observation_maturity.py` checks the exact session-close path for the implemented dataset horizons: **1D = next daily close** and **5D = fifth daily close**, using the existing U.S. cash calendar or crypto daily grid. A 1W target is deliberately distinct and remains unsupported for this dataset scorer. The verifier binds forecast issue, target, input price and availability, asset, source, dataset version and hashes. It checks that every required close was available by the evaluation cutoff; a target price alone cannot make a 5D path complete. It never substitutes a present-day price for a missing historical close. Revisions and immutable IDs remain governed by the underlying dataset review, while the window check also refuses regressed source publication order.

Window states are:

| State | Meaning |
|---|---|
| COMPLETE | Every required session close is present and available by the cutoff in an accepted **synthetic** dataset. This is structural completeness only. |
| IMMATURE | The forecast's target session has not ended at the evaluation cutoff. |
| PARTIAL | The target has ended and some, but not all, required closes were available. |
| MISSING | The target has ended and none of the required closes was available. |
| CONTRADICTORY | The retained window shows conflicting source identity, ambiguous same-time revision or regressed publication order. |
| UNVERIFIED | The dataset review lacks accepted source rights or independently authenticated historical publication. |

Malformed, substituted or leaking input is refused with an exception before classification. The summary keeps source, asset, horizon, dataset and manifest cohorts separate and reports **zero authoritative scored cases and no authoritative performance** for these offline results, including structurally COMPLETE synthetic windows. `score_complete_synthetic_windows` provides a separate diagnostic that excludes PARTIAL/MISSING/IMMATURE/CONTRADICTORY/UNVERIFIED cases before invoking the existing synthetic scorer. A retained target price with a missing interior close therefore yields zero scored cases in this strict path. Existing legacy synthetic diagnostics remain diagnostic only; this new contract does not convert them into market evidence.

Point-in-time limitations: `available_at` is a dataset declaration, not independently authenticated publication time. The manifest and receipt hashes demonstrate internal byte consistency, not provider rights, historic receipt custody or whole-history completeness. Local file timestamps and retrospective reconstruction are not publication witnesses. Longer AFI horizons require separately reviewed calendar, interval, corporate-action and source-coverage conventions. Authorized, independently witnessed archives and held-out outcomes remain external acceptance gates.

The historical receipt parser retains strict duplicate-key and nonfinite refusal. Mechanical lint cleanup removed import-order, unused-import and nested-condition findings. Four findings remain (`TRY004` twice, `FURB162`, `UP017`); changing exception semantics or timestamp normalization is deferred rather than assumed behavior-preserving.
