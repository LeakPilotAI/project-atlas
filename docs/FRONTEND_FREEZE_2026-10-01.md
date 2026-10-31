# Project Atlas Frontend Freeze Candidate — 2026-10-01

This document marks the current frontend as the **freeze candidate** for full regression.

## Freeze scope

The following surfaces are included:

- Perp Day Trade / Live Board
- Quality Dips
- Investment / Accumulation Plan
- Archive / Investment History
- Archive / Export
- Archive / Paper Trades
- Archive / Research Archive
- Archive / Snapshots
- Command Center / Overview
- Command Center / System Health
- Command Center / Risk Controls
- Future / Expanded Atlas Overview
- Global dashboard shell

## Shared shell / runtime pass

The freeze candidate includes:

- lazy workspace iframe loading
- shell-level loading state
- shell-level iframe error state with retry
- shared runtime loading / ready / degraded / error status chip
- hidden-workspace polling suppression
- one-refresh-at-a-time polling
- fetch timeout handling
- responsive viewport contracts
- narrow-screen shell navigation scrolling
- focus-visible keyboard affordances
- reduced-motion support

## Truth and safety

- Live-capital automatic execution remains disabled.
- PAPER and research surfaces retain their existing domain contracts.
- Perp, Investment, Archive, and Command Center data ownership remains isolated.
- Future / Prediction Markets UI is roadmap-only; no provider is connected.
- No fake portfolio, prediction-market, uptime, correlation, VaR, margin, or provider telemetry is introduced.
- Risk Controls exposes the existing PAPER-only kill switch; it does not enable real-money execution.

## Freeze rule

After this freeze candidate is validated, frontend feature work pauses.

Only the following changes are allowed before the freeze is released:

1. regression fixes,
2. truth/data-integrity fixes,
3. accessibility/responsive defects,
4. loading/error-state defects,
5. safety defects,
6. test-only corrections.

No new feature panels, styling redesigns, strategy changes, or execution capabilities should be added during the regression window.

## Validation gates

The freeze candidate must pass:

1. frontend freeze contract tests,
2. existing frontend/runtime targeted tests,
3. full repository pytest regression,
4. restart acceptance,
5. runtime soak.

The final frozen checkpoint is the branch HEAD that passes the full repository regression.
