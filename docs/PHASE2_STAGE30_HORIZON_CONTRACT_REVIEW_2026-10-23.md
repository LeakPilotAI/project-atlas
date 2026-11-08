# Stage 30 - AFI-1 Horizon Contract Review

Status: PROPOSED / NOT INDEPENDENTLY ACCEPTED

Phase 2: HOLD
Phase 3: BLOCKED
Production: NO-GO
AFI-1 through AFI-10: PENDING

## Existing verified behavior

- Dataset-bound synthetic forecasts support 1D and 5D.
- 1D means first eligible close strictly after issuance.
- 5D means fifth eligible close strictly after issuance.
- 5D is not equivalent to one calendar week.
- Unsupported horizon conventions refuse.
- US equity/ETF sessions use the bounded 2026-2028 cash calendar.
- Crypto uses separate UTC 24/7 close conventions.
- No real-data skill, independent custody, or production acceptance is established.

## Proposed longer-horizon semantics

These definitions are candidates for review, not approved implementation.

### One calendar week

Target anchor: issuance plus seven calendar days.
Proposed target: first eligible asset-calendar close on or after
the anchor, subject to an approved roll-forward policy.

### Calendar months

1M, 3M and 6M use calendar-month anniversary anchors.
End-of-month and missing-day rules require explicit approval.
Target selection must use the asset-specific calendar.

### Calendar years

1Y and 5Y use calendar-year anniversary anchors.
Leap-day treatment and nontrading-day roll-forward require
explicit approval.

### Long-horizon scenarios

2030, 2040 and 2050 remain conditional scenario research.
Require explicit assumptions, uncertainty, structural-break
sensitivity and refusal of unsupported precision.

## Mandatory refusal boundaries

- Unknown or unsupported target calendar
- Target beyond verified calendar coverage
- Ambiguous session or close convention
- Unsupported corporate-action adjustment
- Missing source availability or point-in-time provenance
- Incompatible horizon/model/dataset cohort
- Attempt to relabel 5D as 1W
- Attempt to treat scenario assumptions as calibrated forecasts

## Required adversarial review cases

1. Friday issuance and following-week target
2. Holiday and weekend roll-forward
3. Early close and daylight-saving transition
4. Month-end and leap-day anniversaries
5. Unsupported equity calendar year
6. Crypto UTC daily-close boundaries
7. Delisting before proposed target
8. Corporate action crossing target interval
9. Missing or revised outcome availability
10. Scenario horizon without accepted assumptions

## Independent review questions

- Are anchor and roll-forward semantics appropriate by asset?
- Are calendars and source revisions independently verifiable?
- Are issue/target/outcome timestamps unambiguous?
- Are corporate actions and delistings handled consistently?
- Are model training and evaluation horizons reproducible?
- Are unsupported states refused rather than inferred?

## Acceptance disposition

This document is an offline proposal only.
No evaluator behavior changes are authorized by this document.
No additional AFI milestone is accepted.
No release gate or trading authority changes.
