# Atlas two-account offline commissioning sequence — 2026-11-08

Status: PREPARATION ONLY. No financial PAPER Start/Stop, provider calls, activation or accepted gate implied.

## Verified host facts
- Native selected code release: `de437abe888a2d20746762a39402ae421417c1f6`, selection revision 8, independent readback.
- Release receipt: `logs/diagnostics/qd-unselected-release-de437abe888a2d20746762a39402ae421417c1f6.json`, stage `D_RUNTIME_LAYOUT_VERIFIED`.
- `D:\AtlasPaper` currently lists `QualityDips`; a Hyperliquid account root has not been evidenced by this inventory.
- The native `validate_personal_inception` function supports both `QUALITY_DIPS` and `HYPERLIQUID`, with exact manifest, enrollment, release and policy digest binding.

## Offline-first dependency order
1. Inventory both account storage/custody roots, permissions and immutable native identities without creating financial state.
2. Prepare QD $1,000 USD and Hyperliquid $1,000 USDC inception manifests and separate native enrollment documents; validate the two schemas and exact selected-release bindings. Never infer enrollment from an existing folder.
3. Prepare and review missing native account namespaces only with create-only, nonfinancial authority and an exact destination/identity plan. Preserve existing roots; do not adopt or reset them silently.
4. Validate both account policy/risk limits, reporting scopes, source rights assumptions, fee/slippage and initial balance evidence offline. No provider checks until separately authorized.
5. Prepare activation, ownership/Stop, dashboard/Discord, readback and recovery packets without publishing activation or issuing a financial runtime Start.
6. Run isolated unit/contract tests and final static checks, record any remaining runtime-only acceptance as FINAL-LAUNCH DEFERRED, not passed.

## Final launch certification — deferred until offline work is complete
- Confirm provider rights and current sources only after explicit provider-check permission.
- Requalify operational clock, code authority, both accounts and owner lease; then explicitly authorize and supervise PAPER launch.
- Perform actual desktop Start, live PAPER session, position flatten/Stop, cold restart/reconciliation, browser/listener acceptance, and elapsed soak in dependency order.
- Never enable live orders, modify Genesis, or automatically start on Windows boot.

Canonical gate status: 0/9 accepted as of this preparation. Runtime-only gate tests are deferred, never waived.
