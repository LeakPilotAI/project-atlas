# R7E46S - Ruff disposition (NO BASELINE APPROVED)

The inherited 3,997 findings are inventoried without fixes or policy waivers. Evidence: logs/diagnostics/r7e46s-20261017/lint-final/ (final) and lint-c/ (earlier preserved snapshot). scripts/audit_release_lint.py emits raw diagnostics, normalized findings, by-file/rule CSV, summary counts, exact command, Ruff version and resolved settings into a fresh output directory.

Reproduce against a clean extracted candidate using the repository venv Python:

```text
python scripts/audit_release_lint.py <extracted-root> <new-output-directory> --head-baseline logs/diagnostics/r7e46p-20261016/ruff-whole-HEAD.json --previous-baseline logs/diagnostics/r7e46r-20261017/ruff-final.json
```

Use backend/.venv/Scripts/python.exe for the recorded environment. Ruff 0.16.5 and resolved settings are captured; no auto-fix, rule disable or baseline file is installed. Counts are by file/rule/message multiset, not a claim about individual changed-line ancestry. Line moves and duplicate diagnostics can shift attribution. Final inventory totals are recorded in result.json; earlier C snapshot has 3,997 findings: 3,972 HEAD-inherited and 25 pre-S-inherited, with 0 new/0 resolved versus R.

## Proposed review disposition

All findings remain UNADJUDICATED and the release-quality gate remains BLOCKED until an explicit decision. Inheritance does not waive a diagnostic. The review labels are audit triage, not official severity or confirmed bugs. Final grouping distinguishes numeric S security rules from SIM simplifications and I001 imports from ISC string-concatenation diagnostics; earlier C coarse-prefix group totals are preserved as preliminary evidence:

- 3,028 style/baseline candidates: mostly typing/import modernization. This is a proposed review group, not automatic acceptance. Even an I/UP finding can need semantic review.
- 480 security/exception-policy reviews: includes 399 BLE001 and silent exception patterns. Justify intended fallback boundaries individually; never bulk-disable them.
- 489 correctness reviews: duplicates/redefinitions/default calls, control-flow and test-related rules. Examine runtime versus intentional test cases before declaring a release defect.

Representative source review, no waiver:

| Finding | Observed context | Required disposition |
|---|---|---|
| PLR0124 eight self-comparisons | Several `x==x` checks intentionally reject NaN, including quote-price validation | Preserve behavior; separately approve finite-check rewrite or documented narrow baseline after tests |
| F601 one duplicate dictionary key | Same ACCUMULATION value repeated in tests/test_validation_proof_v4.py, not a production position mutation | Safe cleanup candidate under separate scope; do not describe as proven P&L corruption |
| ASYNC251 one blocking sleep | tests/test_runtime_watchdog.py deliberately stalls its isolated event loop to test lag capture | Intentional fixture candidate requiring a narrow documented disposition, not broad rule removal |
| B023 three loop captures | hyperliquid_cache.py local helper consumes current ctx synchronously inside the loop | Review synchronous lifetime; no demonstrated deferred wrong-symbol result from this inspection |
| B008 two default calls | Frozen backtest assumption/threshold dataclasses | Review immutability and APIs before remediation/baseline |
| F811 fifty-five redefinitions | Full file/line inventory retained | Individual review required; neither intentionality nor defect is inferred from the count |

Operator quality options: authorize targeted correctness/policy remediation; or approve an exact scoped inherited baseline with hash/rule/file limits and a no-new-findings gate, after review. No option is selected by S. Existing E136expected failures are separate unresolved functional gates, not lint findings.

## Complete rule breakdown for the inherited3997

| Rule | Count |
|---|---:|
| ASYNC251 | 1 |
| B008 | 2 |
| B009 | 1 |
| B023 | 3 |
| BLE001 | 399 |
| C405 | 1 |
| C408 | 14 |
| DTZ004 | 1 |
| F401 | 116 |
| F541 | 5 |
| F601 | 1 |
| F811 | 55 |
| F841 | 16 |
| FLY002 | 1 |
| FURB105 | 1 |
| FURB157 | 57 |
| FURB162 | 73 |
| G201 | 1 |
| I001 | 409 |
| ISC004 | 5 |
| PERF402 | 1 |
| PIE807 | 5 |
| PLC3002 | 1 |
| PLR0124 | 8 |
| PLR0402 | 6 |
| PLR1730 | 3 |
| PLW0602 | 2 |
| PLW1510 | 12 |
| RET501 | 1 |
| RUF007 | 14 |
| RUF010 | 1 |
| RUF012 | 2 |
| RUF015 | 1 |
| RUF022 | 4 |
| RUF046 | 13 |
| RUF059 | 7 |
| RUF100 | 23 |
| S110 | 54 |
| S112 | 27 |
| SIM102 | 11 |
| SIM103 | 2 |
| SIM114 | 2 |
| SIM117 | 4 |
| SIM210 | 1 |
| TRY004 | 11 |
| UP006 | 1296 |
| UP017 | 265 |
| UP034 | 3 |
| UP035 | 309 |
| UP037 | 10 |
| UP041 | 8 |
| UP045 | 728 |

Complete file totals and every file/rule cell are in summary.json and by-file-rule.csv; all3997individual locations/messages are in findings.json. Those files are the reproducible breakdown, not a sample or hand-written shortlist.
