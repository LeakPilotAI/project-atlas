# Project Atlas — post-production disk cleanup and bloat reduction

**Scheduled milestone:** Execute only **after full financial PAPER production is independently accepted** and a stable, restorable native release, one-click Start and Stop, flat/closed-position receipt, reporting and recovery baseline are verified. **This document does not authorize deleting anything now.**

## Scope and targets for the future read-only inventory

- `D:\Work\Project Atlas`: old isolated pytest basetemp folders, test output, logs/diagnostics, build artifacts, obsolete backups, copied source ZIPs, abandoned native-copy rehearsals, generated cache/bytecode, redundant virtual environments and archived fixtures.
- `D:\AtlasRuntime`: retired/unselected releases, old code-only installers and their receipts, duplicative quarantined copies; **never** assume a nonselected release is safe to delete because it may be needed for rollback, runtime dependencies, source proof or an active process.
- Atlas-created files under Windows user temp/cache locations such as `%TEMP%`, and any Atlas-owned shortcuts or generated logs. **Do not scan or bulk-clean Windows, Program Files, AppData, System32, registry, or third-party caches** just because the path has grown.
- Do not touch `D:\Work\Project-Genesis`, other projects, creative work, browser profiles, personal data, local secrets, unrelated caches, or active finance/PAPER ledgers.

## Proposed guarded one-time workflow

1. **Freeze a passing baseline.** Verify paper trading is stopped and actual USD/USDC PAPER positions are confirmed flat, all native writer leases closed, Stop journal finalized, no pending orders, and daily reports preserved. Record current selected native release, Git HEAD, and authoritative receipts. Take a verified rollback backup or reversible snapshot.
2. **Read-only manifest first.** Inventory exact paths, sizes, ages, owner/process references, hash where required, Git tracked/untracked membership, and cleanup class. Show total recoverable bytes by class before changing anything. Use one low-priority bounded enumerator with pauses, no uncontrolled recursive OS scan or editor-index storm.
3. **Classify explicitly.** (A) obviously disposable ignored test directories, old generated logs and caches *after provenance/use review*; (B) archive/quarantine candidates that might support rollback or financial audit; (C) protected active code, selected + immediate rollback releases, credentials, original evidence, accepted journals/receipts, account/report histories and Windows system files.
4. **Approval and quarantine.** Provide a concrete candidate list and size estimate for separate operator approval. Prefer move to a dedicated quarantine folder with retention window; never automatic recursive deletion. Do not follow reparse points, hard links, network mounts or unknown ownership. Preserve relevant financial and compliance evidence for the months-long PAPER evaluation.
5. **Prove no regression.** After approved removal or quarantine, verify native selection and hashes, test a clean one-click Start/read-only dashboard/Stop cycle (without real account mutations), verify settled PAPER records, log and notification retention, and measure freed space. Restore on any mismatch.
6. **Ongoing hygiene.** Only after acceptance, add bounded file/log rotation for *non-authoritative disposable* diagnostics; preserve complete financial journals and enough provenance for accounting and crash recovery. Clean up ad-hoc duplicate test roots, and keep bulk trial folders outside VS Code-watched workspaces whenever practical.

**Explicit vetoes:** No automated cleanup during active PAPER trading, no mass deletion of untracked files, no moving source/ledger/selector/receipt files on a hunch, no Windows Cleanup/registry commands without separate scoped approval, and no deletion of old releases before restart/rollback viability is proven.

**Current status (2026-11-09):** Deferred until full PAPER production. No inventory or cleanup run. Financial PAPER **NO-GO, 0/9 gates**. Next work remains R13 code-only installation/selection and subsequent source/finance commissioning.
