# Stage 23 — Desktop launcher and runtime recovery

Decision: BLOCKED for real startup/browser acceptance. Phase 2 HOLD; Phase 3 BLOCKED; production NO-GO. All 21 release decisions unchanged.

The existing Project Atlas desktop shortcut targets Windows PowerShell with -NoProfile -ExecutionPolicy Bypass -STA -File scripts/windows/Atlas-Background-Controls.ps1, working directory D:\Work\Project Atlas. Its SHA256 is 52b027d49faaeae779e195df15ecae42ec0ff3c10384894354383582d471626e. Atlas Background uses the same launch chain. Neither shortcut was modified or executed. Stop Atlas still targets legacy ATLAS-STOP.bat; it was not executed.

The controls GUI is intentionally passive: Status must be selected before Start, and it does not open a browser. The manager launches app.main:app on 127.0.0.1:8000 after Docker dependency handling. Backend dashboard routes are served by that API. The separate frontend package defines Next dev/build/start but is not launched by this manager. No frontend readiness or browser acceptance was performed.

The API lifespan unconditionally calls require_startup_authorization(), which refuses startup. The separate observation entry reports capabilities or runs a synthetic operation; it does not serve the API. No safe permitted full dashboard startup path was established. Changing auto-start behavior would not resolve this restriction and could start dependencies before backend refusal. No launcher source or startup protections were changed.

Safety finding: Get-VerifiedState, invoked by manager Status, can acquire a recovery lock and archive stale-session metadata. Status was therefore not invoked as a read-only audit. No current runtime STOPPED assertion is made from historical evidence. No services, Docker operations, provider connections, protected journals or Genesis resources were accessed.

Journal diagnosis: bounded faulthandler attempt exited 1 after ten seconds without captured output. A plugin-disabled default-temp attempt produced one setup ERROR: pytest could not create its numbered temporary directory in the sandbox Temp root. A plugin-disabled workspace-basetemp attempt stalled beyond twenty seconds and was interrupted; no test pass was reported. These attempts do not establish the storage blocking point. Stage22 failure evidence retained. Next diagnosis should capture traceback directly to an exclusively created workspace file with capture disabled and a bounded deadline.

Validation: static source/shortcut review only; zero new passing test claims. One setup error; two interrupted/bounded incomplete attempts. No frontend build, browser exercise, or full regression acceptance claimed. Existing work preserved.

Next safe execution: implement and test a separately scoped offline dashboard host with explicit capability boundaries, or obtain explicit approval for the minimum existing runtime integration. Keep production lock intact. Then test ownership/readiness/browser behavior through mocks before any authorized runtime smoke test. Retain the journal stall as unresolved.

Seven phases and all AFI milestones remain as recorded in the master roadmap; AFI-1 through AFI-10 PENDING. External PIT data, provider rights, holdout acceptance, real backup/restoration, runtime/resource acceptance, consent and recovery gates remain open.
