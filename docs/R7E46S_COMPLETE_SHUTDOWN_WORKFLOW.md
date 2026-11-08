# R7E46S - Complete Atlas Shutdown and restoration (OPT-IN, runtime NOT ACCEPTED)

New supported-source entry point: scripts/windows/Atlas-CompleteShutdown.ps1 -Complete. No real container or backend was started/stopped in S. No shortcut was changed or activated. Independent runtime acceptance and explicit operator approval are still required before using this new mode on real services.

## Current desktop finding

Read-only WScript.Shell shortcut inspection found:

- Stop Atlas.lnk -> D:\Work\Project Atlas\ATLAS-STOP.bat -> scripts/windows/Atlas-Stop.ps1. That legacy script throws ATLAS_LEGACY_LIFECYCLE_BLOCKED before its old unsafe shutdown body. The batch file ignores failure and still prints Atlas is stopped. It does NOT invoke the verified background manager. Do not treat that message as proof or use this shortcut as the verified workflow.
- Atlas Background.lnk -> Windows PowerShell 5.1 -> scripts/windows/Atlas-Background-Controls.ps1. Its Stop action invokes the verified manager and is BACKEND-ONLY.
- Project Atlas.lnk -> ATLAS.bat -> blocked legacy Atlas-Launch.ps1, with a legacy stop sweep afterward. No legacy path was re-enabled.

Targets, arguments and hashes are preserved in shortcuts-before.json and compared after. Existing legacy/install scripts and .lnk files remain unchanged. A shortcut migration requires a separate explicit approval; S does not redirect a shortcut behind the operator's back.

The verified backend-only Stop deliberately leaves database/cache containers running. That behavior and the misleading blocked legacy batch are separate explanations for the reported experience. Actual current container state is UNKNOWN: the exact-name Docker inspection failed because the dockerDesktopLinuxEngine pipe was unavailable. No engine restart or global container enumeration was attempted.

## Future operator workflow (not executed or authorized by S)

Backend-only maintenance:
1. Use Atlas Background / Atlas Status, or the supported manager Status -Json.
2. If verified running, request Atlas-Background.ps1 -Action Stop; then independently poll Status until STOPPED. A stopping acknowledgement is not completion. Ambiguity/timeout requires preserving records, not force termination.
3. Databases intentionally remain available. Use this mode for API development.

Complete shutdown, only after separate acceptance/approval:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Work\Project Atlas\scripts\windows\Atlas-CompleteShutdown.ps1" -Complete -Json
```

Use this explicit executable/file invocation, not an interactive dot-source or encoded wrapper: the stop-requesting controller is verified as that exact script/opt-in role. The process identity/creation-time/executable/run checks remain strict.

The command acquires the root-specific global lifecycle mutex. Normal manager Start/Stop requests share it; nested synchronous manager Stop is reentrant on the same controller thread, and other controllers are refused. Startup/stop workers still finish only their verified run; a starting/ambiguous session causes refusal, not a takeover. ExpectedRunId binds the manager request to the independently read run. No port-only proof or forced API termination is used.

Before stopping anything, validate BOTH dependency identities: exact names atlas-postgres/atlas-redis, full immutable IDs, permitted and consistent Compose project atlas/projectatlas, exact services/root and single docker-compose.yml label, non-oneoff flag, consistent boolean/status and safe stop signal (default/SIGTERM/SIGINT). Reject contradictory/foreign/missing evidence. Only explicit daemon no-such-container replies mean ABSENT; unavailable/permission errors never mean stopped.

Docker context is read locally and restricted to Docker Desktop local named pipes; remote/ambiguous/conflicting contexts are refused. Complete commands pin the selected pipe. New work never starts/stops Docker Desktop or the Engine. No global process/container list or name substring filters are used.

After the verified backend exits, revalidate the whole pair and each immutable ID, then request Docker stop only for a running, positively identified dependency. [Docker documents](https://docs.docker.com/reference/cli/docker/container/stop/) that timeout -1 waits without its forced-kill timeout. The mode uses that setting, observes the owned CLI for a bounded default 60 seconds, and NEVER kills the CLI or container. It then independently inspects the exact ID and backend state. Already-stopped/absent services are reported accurately. A partial failure can stop one verified dependency while leaving another running; the result is INCOMPLETE, never all stopped.

## Evidence, uncertainty and recovery

The active receipt is logs/runtime/atlas-complete-shutdown.json. Each operation has an independent logs/diagnostics/complete-shutdown/<UUID>/ audit directory with prior receipt, native-command outputs and receipt versions. Receipt bytes are flushed before atomic replacement; old versions are retained. Durable pending-ID intent precedes each stop request. No journal/database/container/image/network/volume is removed or reset.

An unsuccessful or timed-out stop CLI may already have reached the daemon. Preserve its pending ID and owned CLI identity; never blindly replay. A still-running prior CLI blocks reentry. PID reuse is checked using creation time only, without reading an unrelated replacement's command line. An exited CLI plus a still-running uncertain container remains blocked; the retry only observes that ID. Once the exact old IDs are independently stopped, re-running the explicitly approved Complete command can reconcile without a duplicate stop. Missing/malformed evidence or changed IDs require a separately approved forensic plan; never delete/reset the receipt or ownership locks to bypass the gate.

A failed backend drain leaves dependencies untouched. R's blocked provider or journal writer may prevent API exit; Complete Shutdown cannot turn that failure into success. If a controller or CLI is interrupted, preserve receipt, process identity and logs. A crash/power-loss guarantee beyond filesystem/daemon behavior is not claimed. There is no force-recovery shortcut.

Startup refuses incomplete/contradictory receipts. Completed receipts require stopped backend, two valid dependency records, no pending intents and no unconfirmed CLI. After a complete stop, a separately approved normal/Gaming launch validates the same retained container IDs, starts only those IDs, verifies both healthy, then launches the API. PostgreSQL and Redis are independent prerequisites; both must be healthy before backend startup. Existing first-install creation is limited to the two named Compose services and requires root.env; partial/missing previously recorded identities cannot be silently recreated. No data deletion, new risk authority or research opt-in occurs.

Normal startup now distinguishes confirmed absence from failed inspection, requires consistent project/IDs, pins/restores local Docker process environment and rechecks IDs through readiness. It never changes Docker Desktop settings. Complete shutdown does not alter persistent restart policies or credentials.

Rollback is restoration of the retained services, not deletion/recreation:

- First obtain a verified COMPLETE receipt and no pending CLI/API owner. If incomplete, keep backend stopped and resolve evidence with approval.
- After separate startup approval use Atlas-Background-Gaming.ps1 -Action Start (research remains masked false unless explicitly opted in), or the verified GUI Gaming start. The manager restores only Atlas prerequisites. Do not run legacy shortcuts or compose down.
- Verify actual Gaming environment, at least 180-second discovery, normal PAPER management cadence and PAPER_ONLY/MANUAL_ONLY in the future running process; source tests are not those observations.
- For extended-hours rollback use the previously documented disabled startup and O journal migration/recovery contract. Do not delete the journal/commitment pair. No automatic Discord or real-capital changes.

## Separate approval decisions

L1: approve independent real lifecycle validation after Docker is available, with exact Atlas labels/IDs/volumes and backups checked read-only first. Backend-running acceptance requires a separately approved permitted-provider Gaming startup; stopping already-stopped backend/dependencies does not certify that path.
L2: choose a truthful desktop default (verified backend-only Stop) and a separate explicitly selected Complete option, then approve a narrowly scoped shortcut/batch migration. Current links remain unchanged.
L3: accept failed-drain/uncertain-CLI recovery limits or authorize a separate improvement. Never approve broad termination or destructive Docker cleanup.

No production activation, migration, restart or shortcut installation is granted by this document.

Receipt service observations carry PREFLIGHT, POST_BACKEND or FINAL verification stages. A blocked result may retain earlier observations; it must not be represented as a verified final Docker state.
