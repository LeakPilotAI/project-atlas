# Project Atlas — selected R23 Alpaca IEX data-only source-admission repair

**November 18, 2026 | MADDOG | Desktop Commander | SOURCE-ONLY PATCH — NOT INSTALLED IN R23**

## Result

**A real selected-release compatibility failure was reproduced and repaired in the workspace source, but NOT deployed into the selected immutable release.**

R23 remains genuinely installed and selected at original source commit `8463f1da3786647677629ae10da5e95c8940e688`, installed native artifact digest `b7b21a66cd6487f7f2e5de05b3135c47338186d3ae621e0ef2afc50a0c3d5766`, r0023 selector SHA-256 `28960b08a8cbca3d5ed8db37369c5aef5a234f45487e1379c67bba2bdc9d3abc`. No subsequent selector or financial operation was performed.

### Reproduced failure in ACTUAL installed R23

The **actual immutable installed R23** `scripts/observation_runtime/alpaca_iex_probe.py --inspect` returned **exit code 1**, sanitized `IEX_CONFIGURATION_OR_DATA_UNAVAILABLE`, without reading credentials or connecting Alpaca. Original selected revision has 23 records and new R23 source/artifact, while the installed original `_inspect_current_r22_source()` required **exactly 22** and original R22 artifact. The stale `alpaca_iex_rest_access_probe.py` original source likewise admitted only selected revisions 14 or 22, and the WebSocket CLI's data-only preauthorization whitelist also incorrectly excluded revision 22 itself. This is a real currently selected R23 adapter compatibility defect, independently of E1 source rights.

### Source-only repair

In the development checkout (NOT selected image):

1. `scripts/observation_runtime/alpaca_iex_probe.py`: introduced exact native R22 and R23 immutable source/artifact/head anchors, original known installed 10,773 versus 10,802-file counts, current store's 22/23 exact selection chain verification, original independent installed native-image verification, all 12 original distinct empty financial root checks, 13,487-symbol research-only roster and independent new native selection store readback. `--inspect` no longer mistakes surviving r0022 as current selection; unknown future or altered selection REFUSES rather than falling back.
2. The same CLI now allows *only* original selected 12/13/14 and exact verified R22/R23 `--execute-data-only` scope at the code compatibility layer. Existing private-credential and market-data reads still require the original user-specified exact `ALPACA_IEX_QUOTE_OBSERVATION_ONLY_NO_TRADING` scope and original bounded-transport checks. No session or provider call was performed in this execution.
3. `scripts/observation_runtime/alpaca_iex_rest_access_probe.py`: admits genuine selected 23 for its one GET, no redirect, no retry, data-only scope. Existing provider-rights and financial acceptance bits remain false. The preexisting stable `ValueError` credential-contract family is maintained with a scoped lint annotation.
4. Updated existing two source tests to recognize the **genuine current R23 native image** rather than erroneously assert revision 22, while preserving historical synthetic R12/R14/R15/R22 fixture behavior. Added 6 new source-only tests for R23 branch priority, forged selected source refusal before keys, fake data-only scope remaining nonfinancial, R23 REST preflight, unknown revision 24 refusal, and provider-rights forgery refusal.

### Actual verification and evidence

- **Installed R23 original --inspect before repair:** REFUSED exit 1, no credentials or provider connections.
- **Corrected workspace --inspect with selected R23 isolated interpreter**: PASS exit 0; `selected_revision=23`, `source_catalog_symbols=13487`, `provider_connected=false`, `private_credentials_accessed=false`, `current_executable_quotes_verified=false`, `trading_authorized=false`. Used explicit Python site-package paths because isolated `-S` imports cannot see FastAPI otherwise.
- **67 bounded original R23 Python regression tests passed, 1 full-native test deliberately separated** under original 2-CPU `NativeR17CpuBudget`, with strict no-cache, D-only basetemp.
- **1 independent real selected-R23 CLI-subprocess test passed**, using full original native-image verification outside nested 2-CPU pytest guard. Total **68 PASS / zero failed** across both runs. Initial one-shot test runner hit a diagnostic-only isolated import-path error, corrected before the passing test.
- **Scoped Ruff: PASS** on all four modified source/test files.
- Original 12 financial namespaces distinct and **EMPTY**; all 10 original protected initial recovery/selection/PIN SHA records matched, no revision24, selected R23 original installed source hash remained **`3a24cb4fbc04d85202345c19bf7b9a9f2b03a8c97b47b07806af6dce8ac934e8`**. **DO NOT edit the native installed image or silently reselect/deploy** this development patch.
- Independent strict read-only attestation `logs/diagnostics/atlas-r23-iex-source-compat-20261118-r01/final-independent-r23-iex-source-only-attestation.json`; SHA-256 `166a6d167e3f3eea4ceeada061bb192283accb6d6c6d1fd8fcbbe921b92b0517`.
- Focused passing 67-case JUnit `logs/diagnostics/atlas-r23-iex-source-compat-20261118-r01/focused-iex-r23-offline-junit.xml`; SHA `be2c7ad46ef183d01c08f383ea02270943fe77c88b861fe5bcb177df49b61ef5`. Independent 1-case real native subprocess JUnit in same folder, SHA recorded in the attestation.

### Original commissioning remains blocked

**Stage A original E1 acceptance is STILL 0/3**. Public Alpaca Basic IEX documentation does not by itself admit this account's applicable automated non-display/retention and derived-data rights, active source budget, continuously current prices or genuine original native financial source issuer; real Hyperliquid data/fee/funding provenance and Quality Dips upstream research/source rights still missing. No provider rights, private credentials, original financial account inception, trading or simulated fill were created. The original Stage B partial Job/clock tests and Stage J/K synthetic Stop/flat-first tests do not prove an actual 12-role retained owner or original financial Stop. Genuine account inception 0/2 and first supervised HL PAPER pilot not started.

**Decision:** important R23 IEX inspection defect fixed and tested **in development source only**, not installed, no trading, financial PAPER OFF and live-money OFF. Avoid another installation for this single compatibility fix alone unless independently qualifying a necessary successor release with the broader actual financial readiness tasks. No R23 install/selection approvals should be replayed.
