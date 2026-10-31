# QD commissioning evidence investigation — October 30, 2026

Base `09c5e2dc99a1742e5a8c340363a76cfde547fd3c`. Personal sole-operator release authority remains in force. This investigation grants no provider, enrollment, promotion or financial execution authority. All 21 historical decisions and seven phases are preserved.

## Clock findings

Three genuine Windows status acquisitions completed within **67.578 seconds**, under a 100-second/three-acquisition ceiling. No service start/restart, resync, source/polling/registry change, manual time adjustment or diagnostic NTP traffic was performed. The first restricted attempt could not read the configuration registry; its refusal is retained. Normal local query access then succeeded. `w32tm /query /configuration` itself still returned Windows **0x80070005 Access denied**; no administrator elevation or access-control change was attempted.

At **02:16:38–02:17:43 Central**, W32Time was Running/Manual, configured NTP `time.windows.com,0x9`. Status retained Leap 0, Stratum 5 and Last Sync Error 0, but the last successful status synchronization was **02:08:29 Central**. Ages **491.4492 / 519.4663 / 554.8688 seconds** exceed Atlas's unchanged **120-second** limit. All three actual validator results were **CLOCK_STALE_OR_NEGATIVE_QUALITY**; they are not passing synchronization evidence.

| Component, milliseconds | First | Second | Third |
|---|---:|---:|---:|
| Root dispersion |8505.123|8505.123|8505.123|
| Half root delay |16.38805|16.38805|16.38805|
| Absolute phase offset |706.6123|706.6123|706.6123|
| Measured wall/QPC disagreement |0.0114|0.0003|0.0016|
| Fixed margin |1|1|1|
| 500ppm drift over sync age |245.72458045|259.73313185|277.43439405|
| 500ppm drift over 240-second validity |120|120|120|
| 500ppm drift during collection |1.3256935|0.3290902|0.56732785|
| Diagnostic sum, rounded up |9597|9610|9628|

These sums are **diagnostic arithmetic only**, not bounds issued by an accepted clock: freshness fails first. Collection durations were 2.6514 / 0.6582 / 1.1347 seconds, charged only for their conservative drift allowance; the whole query duration is not counted as an offset. Seconds-to-milliseconds conversion, absolute offset, half delay and ceiling rounding are consistent. No Atlas calculation or timestamp-interpretation defect was demonstrated. No conservative allowance or 1,000 ms threshold was removed. Dispersion alone exceeds the threshold, even if every other term were zero.

The System log records **Time-Service event 47 at 02:09:33 Central**: no valid response after eight attempts to the configured peer. The peer query shows one peer **Pending**, **Reachability 0**, **ValidDataCounter 0**, approximately 475 seconds remaining. Its separate last-success value is 02:01:02; it is retained as a different diagnostic field, not substituted for the status timestamp. Status reports poll interval 12 (4096 seconds). Read-only registry inspection still finds MinPollInterval 6, MaxPollInterval 15 and SpecialPollInterval 64; the earlier authorized settings are present. The effective configuration query was denied, so no claim is made that stored settings prove a particular effective policy or that the reported interval uniquely explains peer recovery behavior.

**Established cause of the current refusal:** stale Windows evidence following failed peer contact, with excessive reported dispersion and material phase offset. **Not established:** whether DNS, packet loss, firewall/NAT, upstream service behavior or oscillator behavior caused those failed contacts; whether another source agrees with UTC; or how much dispersion belongs to each remote/local contributor. Root delay is a Windows-reported cumulative path estimate, not a new measured end-to-end latency probe. VMICTimeProvider event 158 reports expected unsupported non-Hyper-V behavior, not proof of a competing active source. There was no source-disagreement measurement.

Normal peer recovery must produce fresh qualifying evidence. Waiting ages the same cut and cannot make it current. A separately authorized, bounded recovery of the unchanged source could be considered next; no guaranteed sub-second result or specific configuration fix is claimed. Do not lower `LocalClockDispersion` to manufacture acceptance. Current clock capability was not constructed; historical 915 ms acceptance and earlier 1,812–1,874 ms refusals remain historical.

Microsoft documents polling units/flags and Windows source selection separately from Atlas's conservative model: [Time Service tools and settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings), [Windows time accuracy](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/accurate-time). Those descriptions do not certify this PC's accuracy.

Private evidence: `logs/diagnostics/qd-evidence-clock-investigation-v1.json` (restricted refusal), `qd-evidence-clock-investigation-v2.json` (actual status/peer/event evidence), and `qd-evidence-clock-config-read-v1.json`. Machine-specific identifiers remain outside Git.

## Actual source correction: IEX clock admission

An adversarial execution-adapter test reproduced acceptance of physical uncertainty **1.001, 2 and 999 seconds**. `IEXPaperQuotes.quote` previously checked only the lower bound; its research-reference wrapper checked the upper bound separately. The canonical engine also checks quote age, but that is not a substitute for the adapter's physical clock contract.

The adapter now requires **0 <= physical uncertainty <= 1 second** before adding its existing one-second whole-timestamp encoding margin. The margin is not a relaxation of physical UTC quality. No validator, strategy, accounting, price, spread, liquidity, fee or risk limit changed. New tests exercise the exact boundary and refusal before entry frames, source sequence advancement or shutdown observations. No command or financial write is used to test this guard. Original red result: `qd-evidence-iex-clock-red-v1.txt` (**3 failed / 4 passed**), retained rather than overwritten.

## Current research custody: exact remaining facts

| Boundary | Existing implementation/evidence | Still required before operational consumption |
|---|---|---|
| Free research acquisition | `FreeResearchClient`: fixed TLS GET endpoints, no redirects, bounded/cache/rate controls; Alpaca Basic/IEX history/assets/calendar/actions and official SEC submissions/Company Facts/original documents. Historical genuine filing/valuation evidence preserved. | Authorized current scope, valid private Alpaca data credentials/Basic-IEX rights and permitted endpoint responses; real SEC application/contact header; accepted cache paths and request budget. Credentials/TLS success alone do not supply rights or ranking custody. No provider or private credential was inspected/connected here. Yahoo/FMP remain unused. |
| Valuation | Approved historical-earnings method, quarterly original filing/exhibit provenance, share/price basis and refusal tests retained. | Current admissible filings, corporate-action/share alignment, historical price coverage and accepted current reference; internally calculated values labelled non-analyst. Historical MSFT WATCH evidence is not a fresh current ranking. ETFs lacking qualifying fundamentals remain ineligible; do not invent an alternate model. |
| Original scanner | `InvestmentScanner(research_only=True)` with explicitly injected free providers/history/universe; isolated tests prove no legacy financial writes/background start. | Actual current scanner output plus exact six-field research envelope: `board`, `observations`, `instruments`, `quotes`, `publication`, `monitors`. Source revisions and original receipt/valuation/observation bindings must remain authentic and fresh. Do not use legacy `collect_board`, mutating GET or global scanner startup as a shortcut. |
| Source producer | `QualityDipsSourcePublication` plus existing `CandidateEvidenceAdapter`, current-publication reader and populated native fixture tests. | Operator-accepted `verify_components`, `verify_research`, `verify_head`, `verify_publication`, `verify_current` bindings to the actual research cut. These injected method names are interfaces, not installed authority. Maximum 16 instruments/bundles/monitors, 131072-byte packet; current QD cut <=30 seconds, read acquisition <=1 second; underlying candidate ranking rules still apply. |
| Native archive | `PERSONAL_QD_SOURCE_ARCHIVE_V1`, real creation-handle identities/ACL/predecessor/ACK, logical revision +1 native revision, CAS/UNKNOWN/refusal tested. | Explicit permission to create/enroll the proposed nonfinancial source child; real native root ID, account/epoch/source, verified native release digest/commit; accepted current-head custody and scoped publication lease. `verify_archive`, `verify_archive_head`, `lease_source_publication` must bind those actual facts. No root or authority was created. |
| Personal custody | Same-user reduced-assurance policy is approved; sole operator owns acceptance. | Retain actual accepted current cut/reservations, reconcile restart and refuse stale/conflicting/UNKNOWN state. Local hashes are consistency evidence, not independent coherent-rollback protection. No external reviewer is required. |

The archive has 128 native images including its initial image: at most **127 source publications**, potentially fewer by bytes. A 60-second plan must explicitly budget refreshes and reserve financial Stop capacity separately. Restart does not reset capacity. Existing financial continuation does not automatically enroll a research-source successor.

## IEX evidence classes and admission

| Evidence | Meaning | Executable now? |
|---|---|---|
| Injected synthetic WebSocket/authority fixtures | Parser, simulation, provenance and risk behavior under labelled test inputs | NO |
| Retained IEX daily bars/old quotes | Historical research with original event/receipt timestamps; close/reference is not a BID/ASK fill | NO |
| Current accepted IEX research ASK | Fresh cache quote plus accepted feed/instrument/calendar/clock lease, exact source sequence and provenance; `ASK_REFERENCE_NOT_FILL` | Research input only |
| Operational executable quote | Live permitted authenticated/subscribed IEX cache, actual fresh bid/ask/event/receipt cut and accepted execution/session authority | Only if every separate financial/session gate also passes |

`IEXFeed` requires a fresh, nonconflicting current-generation quote (default <=5 seconds), valid price/size/condition/venue/timestamp, and clears admission on disconnect. Subscription ACK with zero observations is insufficient. `IEXPaperQuotes` requires accepted instrument identity, stock/ETF USD shares, verified round-lot conversion, entitlement, TRADING status/open calendar and now the explicit <=1-second physical bound. `NativePersonalMarketInputs` binds it to the actual current source publication, enrolled session/operator and issued observation. The existing canonical engine additionally enforces its actual calendar, regular hours/halts/session, quote-age plus uncertainty, spread, displayed size/participation and instrument/risk limits. Entries use observed ASK, exits BID, both remain SIMULATED with modelled costs.

**Unmet actual conditions:** no current provider connection/quote, active entitlement/execution lease, accepted current native research cut, qualifying clock, operational resource/session/writer binding or real installed Control Center acceptance. No claim of market-open evidence is made from the 02:xx Central investigation. IEX remains single-exchange, not NBBO or guaranteed fill liquidity. No provider response was fabricated or requested in this execution.

## Installation and test disposition

The prior 638-file archive/manifest is retained as an immutable historical candidate. The IEX source correction changes one selected runtime file; therefore the old archive can remain internally consistent while no longer matching current reviewed runtime source. It must not be promoted as containing this correction. A new explicit-manifest source-only candidate is the next independently executable packaging step; it grants no installation or resource authority.

The separate [bounded promotion procedure](QD_COMMISSIONING_PROMOTION_PROCEDURE_V1_2026-10-30.md) records preservation, native identities/readback, exact owned Control Center acceptance, eight-second Stop, and rollback/refusal boundaries. Active installation and protected financial accounts were not read/mutated for this task; earlier installation/financial audits are historical, not silently refreshed.

Validation: **277 relevant clock/IEX/source/archive/packaging/restart cases passed**, zero final failures/skips, 21.74 seconds; **202 disjoint installation/valuation/original filing/research-only scanner/read-only dashboard cases passed**, zero failures/skips, 28.29 seconds. Total **479 distinct cases**, including **13 new cases**. Both runs report the same existing Starlette/httpx deprecation. Two restricted runs were interrupted while Windows Python's proactor loop blocked in its internal socket-pair accept; the retained stack identifies the environment boundary. Normal local execution passed with the original assertions and synthetic transports. This is not a provider test or new native publication acceptance. Prior 428/native/installed results remain separate preserved evidence.

## Refreshed immutable source handoff completed

After committing the validated correction at **`2c039af29dfefd1df77e0caa3db3fdf5ed188118`**, an explicit source-only package was built and independently verified. The [new candidate manifest](QD_COMMISSIONING_PROMOTION_CANDIDATE_V1_2026-10-30.json) has proposal revision 3 and all operational authorization flags false. The old revision-2 manifest and ZIP remain byte-identical; their previous acceptance is not rewritten.

- **638 source files / 7,720,188 bytes**; selected inventory SHA-256 `8a19ec246e3055c105a5b6a59523dba05dfad3d439bfaf3cceb892c831a384bd`.
- ZIP SHA-256 **`0e65fae1891fc8d406f086a6aa711781053aa7d9a6b3cf1c9c7963f709c87677`**.
- One selected-file delta from revision 2: `quality_dips_iex_input.py`, +164 bytes, SHA-256 `c5d502ee7d27fe702109e4d4ae7f141c032899638285f111740d839a61d902e3`. The other 637 selected files are unchanged. Two runtime deltas from the older genuinely tested installation: this correction and the native research archive.
- Proposed **uncreated** release: `D:\AtlasRuntime\releases\2c039af29dfefd1df77e0caa3db3fdf5ed188118`. Planned inventory: 10,204 files / 260,369,081 payload bytes with the unchanged 9,566-file dependency subset. New native IDs and native release digest remain **unavailable**, not copied from the old installation or ZIP digest.
- Source-package work consumed **5 entries / 4,133,284 bytes / 5.781 seconds**, within 180 seconds / 4,096 entries / 64 MiB. No native child, installation copy, active selector, provider or account was created. Private package receipt: `logs/diagnostics/qd-evidence-candidate-package-v1.json`.

Ruff and in-memory compilation passed. The static PAPER policy audit checked **640 files, zero issues**. Canonical archival updater preserved the full prior checkpoint and historical bytes; unrelated state and the preexisting research-test modification were preserved. Whitespace validation uses Git's `cr-at-eol` interpretation for the deliberately preserved Windows roadmap line endings; no historical line-ending rewrite was used to hide that distinction.

**Remaining boundary:** fresh qualifying clock, real current provider/research/execution evidence, operator-authorized operational installation/resource enrollment and actual installed Control Center acceptance. Financial activation/inception/PAPER pilot were not attempted. PAPER startup **NO**. Production **NO-GO**.
