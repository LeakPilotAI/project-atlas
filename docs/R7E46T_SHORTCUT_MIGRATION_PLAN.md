# R7E46T — desktop shortcut migration proposal (APPROVAL REQUIRED)

No .lnk, desktop shortcut, installer, legacy script or batch was changed or executed. Read-only WScript.Shell metadata/hashes are recorded in logs/diagnostics/r7e46t-20261017/shortcuts-before.json. Actual existing labels are Atlas Background, Project Atlas and Stop Atlas; no existing link literally named Start Atlas was identified in the current Atlas-only Desktop shortcut inventory.

| Existing item | Verified target | Proposed disposition |
|---|---|---|
| Atlas Background.lnk | Windows PS5.1 -STA -File scripts/windows/Atlas-Background-Controls.ps1 | Retain verified GUI; distinguish normal/Gaming start and backend-only Stop labels explicitly in any separately approved UI revision |
| Project Atlas.lnk | ATLAS.bat -> blocked Atlas-Launch.ps1; then legacy stop sweep | With approval replace target with the verified background GUI, or add an explicitly named Start Atlas Gaming shortcut using supported Gaming launcher; remove no evidence and execute no legacy batch |
| Stop Atlas.lnk | ATLAS-STOP.bat -> blocked Atlas-Stop.ps1; batch prints success regardless | Prefer rename/replace as Stop Atlas Backend, targeting verified manager Stop with honest asynchronous stopping/final-status reporting |
| New separate option | None installed | After real-container acceptance, add Complete Atlas Shutdown using the explicit -Complete entry point and visible result/receipt; never silently turn backend-only Stop into complete stop |

Proposed targets, all relative scripts resolved from D:\Work\Project Atlas:

```text
GUI: powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background-Controls.ps1"
Gaming start: powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background-Gaming.ps1" -Action Start
Backend-only stop: powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Work\Project Atlas\scripts\windows\Atlas-Background.ps1" -Action Stop -Json
Complete: powershell.exe -NoProfile -ExecutionPolicy Bypass -File "D:\Work\Project Atlas\scripts\windows\Atlas-CompleteShutdown.ps1" -Complete -Json
```

These are proposal strings, not executed commands or installed shortcuts. The executable must be the verified absolute Windows PowerShell5.1 path; working directory is the Atlas root. No extended-hours opt-in or trading/Discord authority is added. The current manager Stop acknowledgement is not final shutdown: the migration must retain a visible failure/status workflow or use the verified GUI and independent Status polling. Do not install a console shortcut that vanishes while reporting ambiguous success.

Separate approval must choose names, default normal versus Gaming start, replacement versus additional links, exact paths, and whether batch files/GUI labeling may be changed. Complete shortcut installation also requires independent real-container acceptance. Scope approval does not waive cash/provider/lint or production gates.

Migration procedure after approval: hash and copy each exact existing .lnk into a new Atlas evidence directory; record target/arguments/workdir; create candidate links in an isolated repo directory; verify their metadata without launching; show the exact delta for review; install only the approved exact links. Never run legacy launch/stop scripts. Do not modify unrelated shortcuts or use broad desktop cleanup.

Rollback: restore original bytes from the verified per-link backup, without launching the restored legacy links. Record that original legacy paths remain blocked/unreliable. No container/backend action accompanies shortcut rollback. Missing backups/changed desktop paths require operator review; do not overwrite unknown links.
