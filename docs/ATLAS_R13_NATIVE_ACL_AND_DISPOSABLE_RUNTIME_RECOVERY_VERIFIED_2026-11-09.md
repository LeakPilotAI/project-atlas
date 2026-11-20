# Atlas R13 disposable recovery — native ACL and copied-runtime smoke passed (2026-11-09)

**Result: native file owner/SYSTEM ACL + exact file-identity + SHA-256 verification completed, and the copied Windows Python interpreter imported current modules. Disposable rehearsal only. NO installed/selected R13, no financial PAPER.**

## Root cause and resource correction

The user's Windows PC became unresponsive while VS Code was open during the prior R13 10,518-file native-copy campaign. The preexisting copier has a size/time bound and native file checks but did **not** set Windows IDLE process priority, deliberately pace I/O, or avoid repeated deep cumulative file-list serialization when an observer was supplied. The exact relative contribution of VS Code extensions and other processes is unknown; this is **not** evidence of malware or proof that Atlas alone caused every process. The earlier long installer was interrupted before final native ACL/readback completion.

Commit `08ef289c` introduced `scripts/atlas_r13_low_impact_installer.py`: a separate R13 installer adapter using IDLE_PRIORITY_CLASS, bounded pacing, deadline, original-priority restoration, no giant cumulative observer callbacks, and strict create-only destination checks. Its existing 55 focused source-only tests passed. The actual R13 install method remains hard-blocked (`APPROVAL_SHA256=None` and no install CLI). **It does not repair or resume an original partial native copier; never use the interrupted tree as an operational release.**

## Current execution: independent native ACL and identity readback (completed)

Used the *already copied, isolated* disposable folder:
`logs/diagnostics/qd-native-install-r13-20261109-r01/candidate`.

Executed one Windows IDLE_PRIORITY_CLASS read-only process using the existing native WindowsOutput Win32/NTFS primitives. Verified the exact pinned `c7dfb85665bbcd5ba4494c33365d4dff8ea92b12` source archive, retained native Python dependency receipt and unchanged R12 selector before opening any native files. Held verified native relative directory handles, independently checked exact protected owner/SYSTEM DACL and directory identity on **912 directories** (including root), then verified each file through the native handle: owner/SYSTEM ACL, single-link identity, expected size, unchanged pre/post native identity, full SHA256 and contents.

Results: **10,518/10,518 native file handles; 912/912 native directories; 263,440,156 bytes; zero ACL, native identity or SHA256 errors; 23.7 seconds**. Windows IDLE process priority, 60ms pauses every 32 file checks, and no new file copies, ACL repairs, provider requests or installed native selection.

Create-once ignored diagnostics receipt:
`logs/diagnostics/qd-native-install-r13-20261109-r01/native-handle-readback-r1.json`
with status `NATIVE_OWNER_ACL_IDENTITY_AND_SHA_READBACK_PASS_UNSELECTED`.

**Evidence boundary:** This is independently sufficient to verify the copied *disposable* tree's native owner/ACL and actual file contents **at readback time**. The original creation handles and their exact native original identities are unavailable because the first copier exited. Thus **do not retroactively mark its uninterrupted original install receipt as completed**, or treat this file set as a new operational R13 native release.

## Next actionable proof: copied interpreter imports (completed)

Executed one small copied-Python subprocess with Windows IDLE_PRIORITY_CLASS and a 25-second deadline. It used exactly the copied interpreter `candidate/python/python.exe` with `-I -B -S`, clean environment without account secrets, explicit isolated source/stdlib/site-packages paths, and socket connection calls replaced with refusal. Checked that the executed Python 3.12.10 executable and prefixes really belong to the **disposable candidate**, then imported eight relevant updated modules from that copy:
`app.services.hyperliquid_consensus_settlement`, `app.services.paper_perp_transition`, `app.services.paper_source_publication`, `app.services.perp_source_planner`, `app.investment.alpaca_iex`, `app.services.quality_dips_current_producer`, `scripts.observation_runtime.atlas_qd_scored_research_intake`, and `scripts.observation_runtime.atlas_qd_native_iex_readonly_pairing`.

Result **8/8 imports passed**, no network or service initiation, no account access, no trading, no new installation, selected native R12 SHA unchanged.

Create-once ignored diagnostics receipt:
`logs/diagnostics/qd-native-install-r13-20261109-r01/copied-interpreter-import-smoke-r1.json`.

## Where this moves real PAPER production

We now have (1) pinned source ZIP, (2) retained Python dependency file/metadata checks, (3) a complete disposable native ACL/identity/SHA readback, (4) an actual copied Python smoke test, and (5) a separate source-coded low-impact future installer with all new release permission gates closed.

This is the strongest available **nonoperational R13 copy evidence** without running another full installer. The next legitimate operational step is a separately approved, independently reviewed **new code-only native install** to an empty create-only native release path, followed by a *distinct* code-only release selection. The disposable copy cannot be promoted in place. Additional source acceptance, financial clock/custody, independent PAPER USD/USDC accounts, owned Start/Stop flatten and supervised forward soak remain pending. **Formal financial PAPER: NO-GO, 0/9 financial workstreams accepted.**

No Project Genesis modifications, live/PAPER orders, brokerage accounts, paid providers, Windows time/boot/shortcut change, native R12 selection, or remote GitHub push.
