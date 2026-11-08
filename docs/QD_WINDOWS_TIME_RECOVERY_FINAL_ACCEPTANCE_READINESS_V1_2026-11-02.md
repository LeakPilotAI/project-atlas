# Windows Time recovery and final acceptance readiness

Starting checkpoint **68b2356245e2684bb65cd8ebc1afb8801078f01b**, branch `chatgpt/atlas-rebuild-v1`.

**READY FOR FRESH ACCEPTANCE AUTHORIZATION — against the separately prepared V2 package.** This was a read-only installation/Windows review, not installed acceptance. No application launch, selection, rollback, support reinstall, journal reset, provider/financial action, Windows setting/service action, or new acceptance grant occurred. Previous grants remain consumed. **PAPER NO; production NO-GO.**

## New clock evidence and actual configuration

Independently confirmed **W32Time Running / Automatic (`StartMode Auto`, registry Start 2)**, configured source **time.windows.com,0x9**, type NTP. Automatic startup was the operator's change; Atlas did not apply it. Automatic Windows Time does not enable automatic Atlas startup. Both installed-clock checks used normal process permissions, the exact D:-resident interpreter and actual installed clock module. Critical interpreter/module hashes matched the original pinned application receipt; no fixture evidence was injected.

| Installed clock observation | Uncertainty | Source evidence age | Result |
|---|---:|---:|---|
| Initial recovery check | **397 ms** | **6.1697438 s** | ACCEPTED, capability revoked |
| Final read-only readiness check | **301 ms** | **49.9393380 s** | ACCEPTED, capability revoked |

Final sample collected **2026-11-03T04:28:45.884988+00:00**, with Leap **0**, Stratum **5**, last sync error **0**, last successful synchronization **11/2/2026 10:27:55 PM** as reported by Windows. Root dispersion **0.0873845 s**, root delay **0.0309070 s**, phase offset **+0.0512677 s**. The unchanged bound includes dispersion, half-delay, absolute offset, measured wall/QPC skew, 1-ms margin and 500-ppm holdover over source age, capability lifetime and collection duration. Offset alone is not an uncertainty claim. Threshold remains **1,000 ms** and evidence age **120 seconds**.

Both capabilities were explicitly revoked and their processes exited. These are genuine samples from this review, not permanent clearance. A future acceptance run must acquire its own new evidence; no current capability is handed forward. No forced synchronization or time/service/source/registry/network change occurred. No synchronization or clock-authority error appeared in these accepted samples.

## Native application and support review

The actual installed application **2c039af29dfefd1df77e0caa3db3fdf5ed188118**, artifact **94ec8b392dd9d0db13e01a8180dd7574baeb468b5e7bd9f3c209af05df048867**, passed complete native inventory: **10,204 files / 903 directories / 260,369,081 bytes**, in **67.0569699 seconds**. Exact native identities, protected owner/SYSTEM ACLs, namespace, hashes, 638-source archive parity and **15 required installed dependencies** passed. The older preserved **fca29cfe7760a28d2569b8b4b91ed1ea99804c3c** inventory also passed: **10,182 files / 903 directories**; its handles closed. The first seven native groups took **126.8190144 seconds**; these completed inventories were not repeated after a supplemental diagnostic-collector error.

Existing support **5b027d7dc0853975ee751c2c83145a9820a95da28041263b3585b56a4312eccc**, deployment **7947f54e82d74079b378ad14c238dadb4259671ee7ed5c9d03e952d5d8327cd3**, receipt **01bb0f6efb04c706e594acb8c63759ee682e4bce2f2062882015edff36d6ce91**, intent and ACK passed native identities/ACL/namespace and pinned-hash checks. All nine frozen support source pins match. Application receipt SHA-256 **c12ae55c8e31be813c1b3c1b7da87785c89af0945f73efa89621d5d846210915** and installation journal SHA-256 **27940d77ef60d5389581213f6334910fdc84677c85639aeb20c50bc10d644f13** match. Journal: **44 records / 45,786,085 bytes**, preserved unchanged.

On-disk installed dependencies/origins and the actual imported installed clock module were verified. READY/image/creation/runtime module-origin claims for a launched application are **not** newly demonstrated: application launch is forbidden in this task. Those remain required during the future genuine installed run.

## Current operational baseline and cleanup readiness

Fresh native selector readbacks confirmed **UNSELECTED / revision 4**, head **bdfe3b9a58605667dbf3a1b74b035236c196445697759cc82cd9124e22f7a419**, four complete immutable records/eight aliases. The unchanged canonical native two-link pair reader verified identity, ACLs, exact alias pairing, bounded canonical bytes and repeated record equality. Selector file/mutex handles closed; no publication or rollback method was called. Existing known-head rollback target is valid, but no new rollback was executed.

The corrected strict scalar process checker found **zero unexplained Atlas processes** after excluding only genuine native PID/creation/image-bound diagnostic ownership. Desktop shortcut bytes/targets were read only and match the prior preserved references; no shortcut was launched or saved. Provider/writer/trading/automatic-Atlas-startup flags remain disabled; no financial state was enrolled or accessed.

The retained last installed endpoint **TCP / IPv4 / 127.0.0.1:60840** came from the actual earlier installed worker's READY evidence, not a guessed port. IP Helper, raw CIM and netstat each returned a complete fresh **empty scoped result**. Strict CIM/process cut followed LAST and passed. Snapshot age **20.649 ms** (<2,000 ms), oldest corroborating view **1,834.4611 ms** (<10,000 ms). All **four baseline query processes/handles** closed normally; read-only inventory/selector contexts closed and diagnostic processes exited. No forced termination or listener creation occurred.

This is current readiness evidence at that retained endpoint and for the scoped Atlas process roster. It is not a claim that every system TCP endpoint is absent, an explanation of historical State 0/PID-0 LISTENING, or a substitute for each future newly allocated port's post-Stop proof. Historical unexplained behavior remains preserved and must refuse if encountered. Future Open #2 still requires the actual unchanged gate, not this report or process count alone.

## Read-only diagnostic failures preserved and corrected

Three initial diagnostic refusals remain in their original result/source files; none was reclassified as successful:

1. An added preservation collector used an 8-MiB read bound on the 45.8-MB installation journal, after the original journal verifier and seven native groups had already passed. The narrow finish used the original **128-MiB installation-journal bound**; other single-link reads remain 8 MiB. No journal or financial capacity was expanded and the completed native inventories were not repeated.
2. That finish initially passed selector aliases to a single-link source helper, which correctly refused **Unsafe source identity: r0001.json**. The correction kept the single-link guard unchanged and used the existing **NativeSelectionStore.records** two-link/canonical/identity reader for selector records. Installation receipt/ACK/journal bytes and native selector record equality were then independently verified.
3. The first metadata diagnostic inherited a PowerShell-7 module path, so Windows PowerShell 5.1 could not resolve Get-FileHash. The diagnostic child environment was corrected to the **same system-only module path already used by the reviewed acceptance harness**. No Windows/system module installation, policy or machine environment change occurred. Corrected metadata and socket/process checks passed.

These were supplemental read-only wrapper defects, not permission to bypass underlying guards or evidence of installed financial corruption. Raw failures, initial sources and corrected results are retained under `logs/diagnostics/qd-w32time-recovery-final-acceptance-readiness-v1-20261102`.

## Exact future acceptance package and resource review

The old V1 package cannot be replayed: its single-use claim/result/temp are consumed and its metadata condition still requires Manual startup. Both old source and failure artifacts remain untouched. A separate **V2 review copy** was prepared with only the correct expected Automatic startup, versioned scope, fresh diagnostic destination and source/hash pins. It does not change installed support or relax ownership/clock/socket checks.

- Proposal: **docs/QD_FINAL_INSTALLED_NONFINANCIAL_ACCEPTANCE_PROPOSAL_V2_2026-11-02.md**.
- Fresh future evidence root: **D:\Work\Project Atlas\logs\diagnostics\qd-final-installed-nonfinancial-acceptance-v2-20261102**. No live claim, supervisor result or execution temp exists.
- Canonical scope SHA-256: **1dd87321626baae143a2f797dc26b48e206304df13d44146dcbda50f6817cacc**.
- Exact source manifest: **100 files**, raw SHA-256 **bec6af1bd1383746bc929b5e63ac8f6ebbb2fd00d5ba6e1fa3aa690b1d68b0cf**.
- Limits unchanged: **600 seconds / 8,192 entries / 64 MiB accounted storage**; only the reviewed r5 selection/r6 known-head rollback, two installed provider-disabled cycles, browser <=45 s, complete Stop <=8 s. Per-host 120 s / 96 total attempted requests; fresh preflight and cleanup reserves unchanged.
- Free D:-resource capacity and the existing alias-publication budget passed. Only four new selector alias entries are proposed; future evidence/temp/log growth remains guarded by the original conservative accountant and reserve. This review does not guarantee future timing or storage usage; the future guard must refuse before mutation if insufficient.

The new V2 files are review material only. No acceptance authorization was assumed, received or consumed by this readiness review. The source package must be explicitly reviewed/authorized at the resulting Git checkpoint before any operational action.

## Validation, preservation and next decision

**15 focused offline V2 tests passed / 0 failed / 0 skipped, 3.60 seconds**: default no-grant refusals, exact source/path pinning, parsing, Auto/Manual/Disabled/state/source/type condition fixtures, and byte-for-byte preservation of controller/worker/clock/native/rollback/browser/capture guards. The earlier seven-package-only run passed in 1.98 seconds and overlaps this final 15; it is not an additional test count. PowerShell parser, source-pin checks and static release-policy audit passed. Prior **301-pass** offline evidence remains intact and was not broadly repeated; it is not current installed acceptance.

Readiness evidence directory at accounting measurement: **56 entries / 1,886,059 logical bytes / 2,115,435 conservative accounted bytes**, excluding later report/index/checkpoint writes and the separately prepared V2 root. No existing data was deleted; space reclaimed **0**. The 600-second/8,192-entry/64-MiB budget belongs to the proposed future acceptance run and was neither consumed nor enlarged here. No retained historical/financial journal, account or Genesis resource was accessed or changed. Existing installation journal inspection was explicitly authorized and read-only.

Canonical roadmap uses the tested archival mechanism; recovery state, previous failures, all 21 release decisions, seven phases, B1/C1/D1/E1, original UI and unrelated research-test changes are preserved. No installed Open/Stop/browser acceptance has newly passed; both genuine cycles remain outstanding. Financial activation, current accepted research/executable IEX evidence, account inception and PAPER pilot remain separate unauthorized commissioning gates.

**Exact next authorization:** ONE fresh bounded **installed nonfinancial acceptance-only** run under the V2 proposal/scope/hash and reviewed Git checkpoint. It may temporarily select only the verified 2c039 release, perform the two genuine provider-disabled cycles with all original timing/identity/socket gates, and execute the reviewed r6 rollback to UNSELECTED. Acquire genuinely new clock/native/ownership evidence again immediately before mutation. No launch, selection or acceptance retry is authorized by this readiness directive. Stop here after checkpoint/push/remote verification.

**PAPER NO. Production NO-GO.**
