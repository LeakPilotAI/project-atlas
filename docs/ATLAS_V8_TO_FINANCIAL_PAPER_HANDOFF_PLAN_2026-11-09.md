# Atlas V8 to financial PAPER handoff — read-only dependency decision (2026-11-09)

Status: DESIGN / READ-ONLY. No selection, installed image mutation, provider commissioning, simulated balance inception or financial authority is granted by this file.

## Verified current checkpoint

- Source head `5466a5d0` adds the exact V8-native NTP operator-clock contract and six financial admission interfaces.
- Existing V8 native application `c8cc4846508b29483d10a0b4c4353f8a26f1fc9c` and independently verified V8 nonfinancial support remain installed but unselected.
- Native release selection remains V7 revision 11; V8 revision 12 is absent and intentionally refused. Preserve that historical chain.
- Focused read-only release/clock regression on Nov 9: 20 passed, 8 skipped, 0 failures. Skips do not imply commissioning acceptance.
- Full financial PAPER remains NO-GO, 0/9 accepted prerequisites.

## Root dependency

The immutable V8 installation was created before the new `NativeV8PaperOperatorClock` source contract was added. The workspace clock hardcodes that existing V8 installed application's receipt, artifact, and anticipated V7-r11-to-V8-r12 native selection. Merely selecting the old installed V8 cannot make its immutable application contain the later source. Patching installed bytes would invalidate verified receipts, so it is prohibited.

## Next implementation sequence (no version selection yet)

1. Design a new immutable release candidate with its own self-consistent native operator-clock identity and exact source/dependency inventory; do not reuse V8's installation receipt for changed application bytes.
2. Pin all application, support, selector, clock and activation adapters to that candidate. Validate that no source profile depends on a different release's hardcoded selected identity.
3. Add negative tests for absent selection, wrong receipt, altered selected head, stale/invalid NTP, unsupported installed image, and unchanged historical V7 selection. Include real native read-only verification.
4. Build and review candidate manifest/installer without financial effects. Require exact independent NTP preflight and separate authorization before any create-only native code installation.
5. Independently verify native application/support receipt and readback before reviewing a new append-only selector handoff. Keep selection refused until candidate clock is truly present in the installed image.
6. Only after coherent selection: separately commission Alpaca IEX equity executable data/rights, Hyperliquid book/funding/fees, QD USD and HL USDC once-only simulated accounts, operator financial clock/Stop and recovery, manual desktop Start/Stop, dashboard/Discord, and supervised soak.

## Boundaries

This note deliberately does not authorize any V8 r12 SELECT, simulated order, writer, live trade, account access, GitHub push, Genesis modification, Windows Time change, startup service, or shortcut rewiring. Neither passing code tests nor verifying an installed nonfinancial image closes any of the nine financial PAPER prerequisites.
