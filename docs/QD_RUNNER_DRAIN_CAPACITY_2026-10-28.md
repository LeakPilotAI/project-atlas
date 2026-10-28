# Quality Dips bounded driver, native drain and Stop capacity

This increment continues commit `5467a349ff40708bc478c55b08ca41811f21e71a`. Source implementation and offline validation only. The existing QD-only commissioning grant remains unchanged; no inception or pilot was attempted. Production NO-GO.

## Implemented

`personal_writer_ownership.py` now implements the drain interface already required by the existing runtime and shutdown coordinator. Under the existing writer lease and read-only native coordination snapshot, it replays the ledger and refuses unacknowledged projections, PENDING/UNKNOWN sessions/publications, missing session reservations and foreign enrollment bindings. No acknowledgement is manufactured, repaired or cleared. The installed composition requires the writer and engine to share the identical native ledger.

`personal_coordination_store.py` can reserve cumulative commit and image-byte capacity for Stop. Normal publication refuses before writing an intent if it would consume the reserve. A one-way, same-thread Stop transition permits only the remaining bounded capacity. Restart does not reset the durable revision count; reservation cannot be repeated on the instance. Operation headroom checks precede dispatch. Existing 128-revision and 1-MiB-image limits are unchanged.

`personal_commissioning_runner.py` is a one-shot driver of the existing personal runtime, concrete operator/writer/native coordination objects, existing IEX input and existing publication reader. It creates no providers, credentials, account, authority or process. It verifies session binding, closes entries on Stop, rechecks authority after source reads, refuses changed source components and never dispatches after expiration. UI-thread `request_stop` closes admission; the driver thread performs existing financial Stop, avoiding a second financial dispatcher. Idle reads are paced. Repeated execution and Stop-before-Start refuse.

The existing native grant is at most 60 seconds, and all financial actions require an unexpired grant. Therefore this driver reserves the final **eight seconds inside that window** for Stop: ordinary observation dispatch ends by second 52. This is not 60 seconds of trading plus extra authority. A late/blocking source or expired grant yields SHUTDOWN_INCOMPLETE, closes dispatch and never fabricates liquidation or a clean restart. Missing accepted observations cannot be reported as a successful zero-trade pilot.

The driver reserves **32 coordination commits and 256 KiB of image headroom** for Stop and checks the same conservative per-operation allocation before dispatch. Source/report prechecks reserve one financial exit and three report slots. These are enforced bounds, **not proof that the complete real composition fits them**. Exact full-path write amplification, growth, financial report publication and drain latency must still be measured before installation acceptance. Any overrun refuses; no limit is enlarged.

## Validation

- Combined accounting, risk, custody, writer, clock, session, desktop/read-composition, synthetic IEX and new driver selection: **685 passed, 0 failed, 0 skipped, 21 deselected, one existing dependency warning, 27.90 seconds**.
- After the final idle-pacing change: **68 focused passed, 0 failed, 0 skipped, 6.15 seconds**, overlapping combined cases. Ruff passed for seven affected source/test modules. AST and Git whitespace checks also performed.
- Original combined attempt: **677 passed, six failed to execute because async plugin auto-loading was disabled**, 21 deselected. Explicitly enabling the already-installed pytest-asyncio plugin resolved those six without assertion changes or dependency installation. Output retained at `logs/diagnostics/qd-runner-combined-20261028.txt`; successful run at `qd-runner-combined-20261028-b.txt`.
- Original focused attempt: **64 passed, one temporary-directory setup error** under the environment's default C: test directory. A new explicit D: diagnostic test root resolved it. No permissions or existing files were altered. Original output retained at `qd-runner-focused-20261028.txt`.
- Tests use synthetic memory/native-I/O doubles. No new genuine Windows-native financial publication, actual HTTP/browser pilot, provider connection, operational ownership acceptance or power-loss test was performed.

Fresh read-only Windows clock evidence: UTC epoch `1793179376`, **370 ms PASS**, unchanged `time.windows.com,0x9`. Existing calendar returned **MARKET_CLOSED**. No resync, service change, credential access or provider connection occurred.

## What remains before operational installation

1. Complete actual runtime authority and source assembly around the existing components, including factual `PersonalOperatorInstallation.technical` checks, engine/session/observation proofs, current reader authority, existing publication reader binding and the accepted research producer. The new driver is not a dependency installer or a substitute for those missing real ports.
2. Supply genuinely current Quality Dips research provenance, instrument/lot/fractional/halt/calendar facts and permitted current IEX observations. Existing `QualityDipsSourcePublication`, `QualityDipsPublicationReader` and `IEXPaperQuotes` require these; no synthetic callbacks or empty-ranking shortcut may supply them. IEX alone does not provide fundamental/valuation evidence. Market opening alone will not complete this integration.
3. Validate the complete composition's exact capacity consumption, native drain proof and Stop timing. Wire the existing read-only dashboard/Control Center Stop request to the single driver thread and verify exact owned closure. This increment does not claim that GUI connection is installed or tested.
4. Only after those checks: use the retained create-only installer for a NEW immutable release, verify installed identity/ACL/inventory/default refusal and fresh clock, then the unchanged authorized once-only $1,000 simulated USD inception, ONE bounded pilot, reconciliation, owned Stop and read-only manual restart. Do not silently rebind a new process to immutable original writer enrollment.

The installed release remains `fca29cfe7760a28d2569b8b4b91ed1ea99804c3c`; historical verified digest `93e52e897fd2f2f3cc4b17bd3e804e8c598a1a3a8938c2b5c47d386890310c91`. It was not overwritten or reinstalled. No actual balance, position, order, fill or P&L is claimed. No additional administrative approval is requested for the existing commissioning scope. Hyperliquid inception, V5 containment, Genesis, real-money execution and expanded/unattended operation remain excluded. Original UI, historical evidence, seven phases, 21 decisions and unrelated work are preserved.
