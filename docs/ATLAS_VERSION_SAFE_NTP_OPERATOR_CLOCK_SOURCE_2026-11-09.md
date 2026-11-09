# Atlas version-safe independent-NTP operator clock source — verified 2026-11-09

**Status: SOURCE-ONLY.** New `NativeVersionSafePaperOperatorClock` implemented in `scripts/observation_runtime/personal_version_safe_release_clock.py`. It is not deployed, installed, wired into the six PAPER authority modules, selected, commissioned, or authorized as a financial writer. This is a prerequisite to a NEW immutable release; existing V8 bytes and nonfinancial support are unchanged.

## Implementation

- The version-safe source binding is evaluated first against the candidate's own installed module location, exact V7 r11 native predecessor head, exactly one new r12 SELECT, the selected release root, and (on initial deep admission) the native installed-release verifier. A workspace or unselected native candidate refuses before constructing `IndependentNtpClock`.
- Only after selection/installation proof does the source-only operator clock construct the real `IndependentNtpClock` with Google/Cloudflare public UDP NTP. Each operation rechecks the same selection head, process ID, runtime ID, exact clock object, operational state, NTP source, unauthenticated two-peer domain, `financial_authority=False` and uncertainty bound. On failure it permanently revokes the original NTP capability.
- Source clock exposes `sample`, `verify`, `runtime_sample`, `verify_runtime_sample`, `runtime_clock`, and `revoke` to match the existing operator-clock interface. It does not make a financial decision, touch a provider, publish an activation, initialize PAPER balances, or authorize simulated/real orders.
- Public UDP NTP is **unauthenticated**, so this source integration and successful tests are not acceptance of operational financial-clock continuity.

## Tests and native readback

- New `tests/test_personal_version_safe_operator_clock.py` covers real workspace refusal before NTP, synthetic owned release/clock sample and verification, selector-change permanent revocation, wrong runtime/process/clock object, malformed source/bounds/evidence, and invalid startup ID without network access.
- Focused V8/version-safe release/clock regression: **52 passed, 0 failed**.
- Broad clock, activation, source, support and release-selection regression: **440 passed, 9 skipped, 0 failed**. Skipped cases do not count as financial acceptance.
- After minor import/docstring cleanup, dedicated version-safe release/clock graph tests reran: **34 passed, 0 failed**.
- Current real Windows native read-only selector: **V7 revision 11 selected**, native r11 head `933482b46a31af43270a193a94a83353e945fbecc4eb4661e8b7f8e9c8262997`; **r0012.json absent**.

## Critical path forward

1. Separately review and integrate a new explicit version-safe operator-clock profile across the six existing financial admission/commissioning interfaces, maintaining exact V7/V8 historical refusals.
2. Freeze a NEW immutable self-consistent release candidate that actually contains the version-safe clock and dependency inventory. Verify builder, manifest and new installation/selection design before any native mutation.
3. Independently review installation, nonfinancial support and native selection handoff with genuine fresh independent NTP preflight. Never patch previous V8 installed bytes or use existing V8 receipt for changed code.
4. Only after coherent installed/selected runtime: independently accept eligible Alpaca IEX data, Hyperliquid quotes/fees/funding, one-time simulated account inception, Start/Stop flatten/recovery, dashboard/Discord and supervised financial PAPER soak.

Full PAPER production **NO-GO, 0/9 formally accepted financial operating prerequisites**. No Genesis, private accounts, live trades, simulated account creation, Windows Time changes, desktop shortcuts, boot services, paid VPS or GitHub push.
