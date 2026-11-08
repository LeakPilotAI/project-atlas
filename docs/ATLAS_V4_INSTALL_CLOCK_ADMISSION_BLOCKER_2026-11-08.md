# V4 create-only code installation: verified Windows clock admission blocker — 2026-11-08

**Outcome: REFUSED BEFORE ANY CODE COPY.** The user explicitly requested execution of the reviewed V4 unselected code installation. Atlas's existing verified installer was invoked with the exact reviewed proposal and its SHA-256, but the operational Windows clock constructor refused `CLOCK_STALE_OR_NEGATIVE_QUALITY` before writing the native release directory, installation receipt, or journal. This is not a failure in the code archive or native copy plan, and is **not** permission to relax financial/time gates.

## Fixed reviewed inputs (remain valid, not installed)

- Proposal: `docs/QD_UNSELECTED_CODE_INSTALL_PROPOSAL_V4_2026-11-08.json`.
- Proposal SHA-256: `43623d87993478fa89fb0ebfac5be3e2bd761f9cfe1185bab5139d17d0305869`.
- Source commit: `fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`.
- Source archive SHA-256: `3f366b14f85d6dfce990ff98ca2b573176e1a838b3054b957894b04a060f2855`.
- Target remains absent: `D:\AtlasRuntime\releases\fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed`. Exact `logs/diagnostics/qd-unselected-release-fc07ba532f9b88a2b6d281a4f5c60ef2b72deaed.json` and adjacent `.pending.jsonl` remain absent.
- Selected immutable release stays `de437abe888a2d20746762a39402ae421417c1f6`, selection revision 8. No provider connection, financial account mutation, PAPER start/stop, or desktop shortcut modification was performed.

## Native clock findings

- The pinned Windows Time peer configuration still matches the reviewed `time.cloudflare.com,0x8 time.google.com,0x8`; last effective source was `time.google.com,0x8`. W32Time was running with zero Last Sync Error and NTP stratum 2.
- At refused admission, the last Windows Time sync was approximately 15 minutes old. The quality verifier `scripts/observation_runtime/personal_windows_clock.py` requires `MAX_AGE=120` seconds, with a fresh status recheck approximately every five seconds. Refusal was therefore correct.
- A standard `w32tm /resync /rediscover` request was attempted. Windows refused it with `Access is denied (0x80070005)` from the non-elevated desktop session. No service configuration, NTP peers, clock thresholds or privileges were altered. Windows later synced automatically (observed 06:03:30 local), but the peer polling cadence was of the order of many minutes; it is not a guarantee of a fresh update throughout installation.
- The prior fully verified native release copier's durable journal records **152.922 seconds** to copy and independently read back ~10,455 files. The new V4 install plan has 10,482 files. A single fresh Windows Time sync (and no further automatic sync) is **not sufficient** to guarantee all clock admission checks remain within 120 seconds throughout the real create-only copy. Launching the installer at the next favorable window would risk an irrevocable, partial native installation, so no retry was attempted.

## Safest next dependency

- First obtain genuine operator-authorized **elevated Windows Time service maintenance** and independent native proof that the reviewed NTP roster can maintain a sufficiently fresh, quality-verified time source across a full native release copy. Do not replace the trusted clock with synthetic evidence, forge a status, disable the admission check, weaken `MAX_AGE`, alter the pinned NTP peer trust silently, or allow automatic privileged escalation.
- Once the clock service behavior is genuinely corrected and verified, independently reconfirm the empty create-only target and pinned proposal, then execute exactly one new unselected installation. Any partial record must be preserved for manual reconciliation, never overwritten/retried under the same release path.
- **66 existing Windows-clock and V4 proposal regressions passed, zero failed** after the refusal. Formal financial PAPER acceptance remains 0/9; real session Start/Stop, flatten, restart, browser/listener and elapsed soak remain grouped for FINAL LAUNCH CERTIFICATION.
