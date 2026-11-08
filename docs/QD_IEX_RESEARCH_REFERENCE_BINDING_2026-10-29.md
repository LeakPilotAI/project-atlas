# Authenticated IEX reference-price handoff and local readiness checkpoint

Base `d7ad0402724e3a43f9a755b6e512af22308cf1ef`. PERSONAL sole-operator, D-local, PAPER-only. Source and isolated tests only; no provider activation or financial publication.

## Implemented next milestone

`backend/app/services/quality_dips_iex_input.py::IEXPaperQuotes.research_reference_price` supplies the existing `FreeResearchBundle.reference_price` callback. It reuses the original IEX research screen's **ASK reference** convention, accepted instrument/entitlement/calendar/clock lease and current authenticated cache. No second data/scoring/financial engine or new default authority.

The caller supplies the exact accepted stock/ETF instrument mapping. The method refuses wrong symbol/identity/USD/share units, absent authority, disconnected/stale/absent quotes, closed calendar, revoked/changed acceptance or feed/authority replacement. Source nanoseconds and exact ASK remain in provenance; the existing measured-value boundary supplies UTC timestamps and a display float. The underlying physical clock allowance stays<=1second; the existing execution packet's additional1second of timestamp-quantization allowance is not misread as physical uncertainty. Financial command/entry checks remain unchanged.

Two stable accepted quote cuts are required. The result is labelled **ASK_REFERENCE_NOT_FILL**, single-exchange IEX/not NBBO, `financial_execution_authorized:false`. It cannot create a decision frame/session/position, clear UNKNOWN, start a socket/provider/worker or publish a ranking. No API endpoint or original UI file changed. A configured stale source refuses; it cannot silently fall back to a historical close.

Existing composition can explicitly bind:

```python
FreeResearchBundle(
    client=accepted_data_client,
    now=accepted_utc,
    reference_price=lambda symbol: accepted_iex.research_reference_price(
        symbol, instrument=accepted_instruments[symbol]),
)
```

These names denote required actual accepted dependencies, not installed defaults or fabricated live evidence. The original scanner and explicit historical-earnings method still perform scoring/valuation; the existing native source publisher/reader still require their real enrolled resource/current-custody/issuer binding. A research reference is not an executable fill or financial grant.

## Exact validation and preparation

- Final consolidated relevant suite: **325passed/0failed/0skipped**,20.37seconds, one existing Starlette/httpx deprecation warning. Covers both changes from this execution:17new installed-module tests and17new reference-price tests, **34new distinct cases**. Includes original IEX parser/runtime, free-source bundle, once-only publisher-memory, interrupted publication/restart, native coordination-memory, current custody, commissioning/Stop runner, source publication and read-only ASGI dashboard contracts.
- Reference-specific intermediate15pass and158pass/1warning runs overlap the final325. The prior release-binding221 and original research406 are preserved evidence, not additive test totals. An explicit synthetic free-bundle case obtains supported ratios from the accepted current ASK, leaves analyst targets unavailable and refuses after disconnection without new fetches or financial effects.
- Ruff passes changed source/tests. Static PAPER audit:639runtime files/0issues. No dependencies installed to suppress the existing warning.
- Refreshed complete source candidate: **637files/7,711,519bytes**, zero new dependencies, digest `4ed3ac5fc286e560e8208ce812ed44d73d23da853fdfc88e34356d579f3e3dfd`. All57actual loaded Atlas module origins in the explicit preparation set match that source inventory; Python/base runtime are D-resident. Private manifest: `logs/diagnostics/qd-iex-reference-installation-preparation-20261029.json`. Only the reviewed IEX input source differs from the previous candidate. This is source preparation, not installed ACL/native identity evidence.

No real market-data connection/request was made during these tests. All quotes, authorities and account transitions are explicit synthetic fixtures; no test evidence is relabelled operational. No native financial publication child, account/inception, installed process/HTTP host or Windows financial lifecycle was executed. ASGI compatibility is not a real-browser claim. Unrelated test formatting/untracked work remains preserved.

## Current factual gates and stop reason

`QD_BOUNDED_W32TIME_RESULT_2026-10-29.md` records the separately approved elevated W32Time start and171.801second observation. At postflight W32Time was **Running/Manual**, source `time.windows.com,0x9` unchanged. Windows reports Leap0/Stratum5/error0. The separate unchanged Atlas preflight at20:10:11Central refused **2551ms>1000ms**. No further polling loop, service start, resync, source/settings or manual clock change followed. Running is not full clock acceptance or independent UTC certification. Later quality is unasserted.

The U.S. regular session is closed. No current executable IEX evidence or accepted native current ranking is asserted. Previous genuine SEC/Alpaca research remains intact: quarterly-EPS proxy19.16,20anchors, non-analyst scenarios518.99/613.17/668.19; actual original-board result WATCH with unchanged risk/evidence/margin filters. No trades are forced.

### Minimum remaining actual work

1. Obtain genuinely qualifying current clock evidence under the existing unchanged contract and an appropriate bounded observation/runtime-preflight scope. Do not restart/resync/change configuration under consumed service grants or infer accuracy from offset alone.
2. During an eligible regular session, connect only previously authorized QD/IEX inputs within their existing bounds; use the implemented accepted-reference handoff for original scoring, verify actual instrument/calendar/action/halt/size/spread/participation facts, and bind genuine source provenance to actual native current-publication custody/local operator authority. That real publication/archive enrollment and operational assembly/readback are **not** completed by these fixture tests. No blanket-True verifier or invented native identity.
3. Install only the full reviewed immutable release through the existing authorized mechanism when prerequisites pass, preserving prior releases. Verify actual native identities, ACLs, hashes, accepted module origins, D-runtime and complete writer/session/current custody. Existing installed release remains **fca29cfe7760a28d2569b8b4b91ed1ea99804c3c**; new fixes are not installed.
4. Execute actual installed financial Stop/report/ACK/drain/owned exit/final readback<=8seconds, original dashboard/manual controls and restart reconciliation using the permitted exact resources/processes. Prior disposable5.823/4.881/5.763second timings remain disposable evidence. New module-parent checks must be included in actual timing; no reserve was weakened.
5. Only after every actual mandatory condition passes, continue the **already-approved, UNUSED once-only1000simulatedUSD/ONEtotal60secondQDcommissioning grant**. No routine repeat financial approval within that scope. Longer trials require separate approval. No Hyperliquid inception or live order path.

These clock/current-input/actual native installed prerequisites are the genuine execution boundary. No additional unbounded diagnostics or speculative security framework is started. There is no new external reviewer/enterprise chain. Source implementation/preparation has advanced; **operational source/current-custody installation, installed acceptance and pilot remain incomplete**.

All21historical decisions/sevenphases, original alien UI/Control Center, Genesis isolation, protected accounts/history, separate simulated USD/USDC scopes and D-only/PAPER-only policy preserved. No operational balance or positions asserted. **Account inception:NO. Pilot:NOT EXECUTED. PAPERstartup:NO. Production:NO-GO.**
