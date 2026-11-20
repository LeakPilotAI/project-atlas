# Windows Time source diagnosis — October 30, 2026

Base `01ec959486cf272db93d6728237d92d289b9c237`, branch `chatgpt/atlas-rebuild-v1`. **Read-only diagnosis complete; system correction not authorized or executed.** No financial, provider, installation, startup or Genesis activity. Sole operator remains release authority; B1/C1/D1/E1 and all 21 historical decisions remain unchanged.

## Confirmed result: peer contact recovered; Atlas clock still refuses

The previous failure is historical, not an ongoing total outage. Time-Service event 47 records eight unanswered peer attempts at **02:09:33 Central**. A later **event 37 at 02:24:33 Central** records valid time data from the unchanged configured peer. This recovery preceded this investigation and was not caused by an Atlas resync.

At **05:46:06–05:46:15 Central**, W32Time was **Running / Manual / NTP / `time.windows.com,0x9`**, Leap 0, Stratum 5, Last Sync Error 0. The single peer was **Active, client mode, Reachability 255, ValidDataCounter 8**, rather than the previous Pending/zero-reachability state. A normal synchronization advanced during the diagnostic: status last-success **05:45:10 → 05:46:14**, with age **57.4358640 → 0.3489746 seconds**. No forced synchronization occurred.

Actual unchanged Atlas validator results: **1,803 ms and 1,736 ms — REFUSED** against **1,000 ms**. These two observations satisfy the 120-second age check but fail uncertainty. No clock capability, financial release or commissioning acceptance was issued.

| Actual acquisition term, ms | Before | After normal synchronization |
|---|---:|---:|
| Windows root dispersion |856.5827|832.7089|
| Half root delay |16.1529|16.1529|
| Absolute phase offset |779.2555|765.4049|
| Wall/QPC disagreement |0.0270|0.0119|
| Fixed margin |1|1|
| Drift over synchronization age |28.717932|0.1744873|
| Drift over 240-second validity |120|120|
| Drift during collection |0.41022085|0.2012921|
| Rounded bound / actual refusal |1803|1736|

The final dispersion plus absolute offset alone is **1,598.1138 ms**. Query timing, a shorter invented lifetime or an offset-only declaration cannot legitimately pass this sample. Existing arithmetic, absolute-value handling, units, ceiling, provenance and refusal behavior were not changed. These are dated observations, not permanent current-clock clearance.

## Network and source evidence

| Question | Confirmed evidence | Limit of the conclusion |
|---|---|---|
| DNS failing now? | Configured name resolves through its normal CNAME chain to an IPv4 address. The AAAA query returns no usable IPv6 address; IPv4 works. | Does not reconstruct DNS at 02:09 or prove UDP reachability. No resolver setting or cache was flushed. |
| UDP 123 reachable now? | Three Windows stripchart samples all received NTP replies; round-trip delays **30.7902 / 29.0143 / 29.4452 ms**, offsets **+787.6222 / +787.5139 / +786.7397 ms**. | These are real NTP replies, not ping/TCP/DNS inference. Diagnostic source ports differ from W32Time's service source port. |
| Actual service UDP path? | Service peer Active/reachability 255, normal last-sync advance during collection and two W32Time-owned UDP-123 endpoints. | Current service success does not identify where the eight earlier attempts were lost. No source-port-123 socket was stolen/shared or service interrupted. |
| Upstream server dispersion? | Two additional one-packet diagnostics: current DNS-selected server and the exact peer IP already reported by Windows. Both Leap 0 / server mode / Stratum 4. Advertised root dispersion **10.1318 / 10.1776 ms**, root delay **0.0610 ms**, measured round trips **30.0124 / 31.5881 ms**, offsets **+785.2165 / +791.3675 ms**. | Not independent UTC authentication. The roughly 6 ms difference is between sequential same-provider samples, not proof of source disagreement or an alternate trusted clock. Do not substitute packet dispersion for Windows aggregate dispersion in Atlas. |
| Different DNS and service IP? | Both addresses belong to this configured-name diagnostic path and answered. Windows retained its existing peer while a fresh DNS query selected another answer. | A changed DNS answer is not proof of corruption, invalid peer configuration or permission to pin/change peers. Exact addresses remain in private evidence. |
| Network/router restrictions? | Successful diagnostic replies and actual service sync establish working paths during collection. | Historical transient loss, asymmetric paths, NAT/router/ISP filtering or server loss remain hypotheses; no packet capture exists for the earlier failure. No router/firewall/VPN changes or new tracing were performed. |

Microsoft documents that the Windows Time client uses source UDP 123, while stripchart uses an ephemeral source port. Consequently stripchart alone cannot prove the service's path; the separate fresh service evidence above matters. [Windows Time tools and settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings)

## Local firewall findings

Read existing firewall policy only: active profile **Public**, firewall enabled; default outbound **Allow**, default inbound **Block**, block-all-inbound false. The inventory examined 952 rule metadata objects and retained only named time rules or enabled UDP/Any block candidates. There was no named W32Time/NTP rule among those candidates. Two tool-containment outbound block rules have local-user security filters; their names or apparent program `Any` do not prove they block the Windows service. An unrelated application-specific inbound UDP block is not an NTP service block. These rules were not changed or bypassed to alter Windows Time behavior.

The initial exact-name CIM lookup found no objects because display names are not rule instance IDs. The corrected display-name read succeeded; original lookup errors are not evidence of missing rules. Current service synchronization and all diagnostic replies succeeded despite those existing policies. **No confirmed local firewall cause and no justification for a firewall exception/reset.** This inspection does not certify the complete effective WFP/third-party/network policy at the earlier failure time.

## Windows behavior and remaining causal uncertainty

Stored settings remain **MinPollInterval 6 / MaxPollInterval 15 / SpecialPollInterval 64 / PhaseCorrectRate 1 / UpdateInterval 360000 / LocalClockDispersion 10**, NtpClient enabled/input provider. Before/after configuration values and service state/startup matched exactly. The peer displays HostPoll/PeerPoll 13 (8192 seconds), yet actual successive synchronizations and the remaining-time reset show approximately **64-second** scheduling. Do not misread the displayed logarithmic interval as proof that SpecialPollInterval is ignored or that no current sampling occurs.

The local Windows status dispersion is much larger than the dispersion advertised by either responding server. A material local residual offset is also corroborated by the independent diagnostic exchanges. **Current acceptance failure is dominated by Windows/client quality and residual clock error, not current total NTP unreachability or query latency.** Exact local filter/discipline contributions cannot be decomposed from these snapshots. Network asymmetry and oscillator/power behavior are not ruled out. No confirmed Atlas calculation defect or timestamp interpretation defect was found.

The effective `w32tm /query /configuration` operation still returns **0x80070005 Access denied**. Registry reads are observations, not proof of effective policy origin. No Windows administrator elevation was requested/executed in this diagnosis. User-level permission to run diagnostics is distinct from Windows administrator rights. The documented Windows phase-correction algorithm uses polling and correction settings; the stored values are a supported tuning hypothesis, **not a proven explanation of the earlier packet loss**. [Windows Time correction settings](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings)

## Safest correction and exact decision

**Do not change peers, DNS, firewall, service startup, system time manually or Atlas limits.** Current reachability recovered. Repeated resyncs or firewall resets are not supported by this evidence.

The least invasive next step is an administrator **read-only effective-configuration check**. If the operator wants an active corrective experiment rather than additional normal observation, the separately reviewable [bounded proposal](QD_WINDOWS_TIME_CORRECTION_PROPOSAL_V1_2026-10-30.json) requests that check followed, **only if applicability is confirmed**, by two targeted Windows discipline settings:

- `HKLM\SYSTEM\CurrentControlSet\Services\W32Time\Config\MaxPollInterval`: **15 → 6**.
- Same key, `UpdateInterval`: **360000 → 100**.

These are documented high-accuracy configuration values. Existing MinPoll 6 / SpecialPoll 64 are retained; this is **not** authorization or a claim to implement the full Microsoft high-accuracy profile. No change to FrequencyCorrectRate, Secure Time Seeding, LocalClockDispersion, source, Manual startup or clock validators. The proposed changes target local discipline behavior; success is not guaranteed. [Microsoft high-accuracy configuration](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/configuring-systems-for-high-accuracy)

**Proposed scope, not executed:** one administrator execution, read/record effective configuration and original typed values; stop on ambiguity/foreign policy; apply only the two exact values; one configuration reload, **no resync or service restart**; observe ordinary synchronization for <=180 seconds; run the unchanged Atlas check. Total correction/verification/possible rollback <=300 seconds. On error or failure to demonstrate fresh <=1,000 ms evidence, restore only the two original values if they still equal this experiment's values, then one rollback reload. Never overwrite a concurrent foreign change. Preserve diagnostics and refusal regardless of outcome.

Risks: changes affect this PC's Windows clock discipline, may increase correction activity and expose clock discontinuities to other applications; unrelated software must not be restarted. Rollback restores configuration, not past elapsed time; it does not undo ordinary OS time discipline. No guarantee against source/network faults. Application startup and financial authority remain excluded even if clock acceptance passes.

**Approval requested:** either authorize only the administrator read-only effective-configuration check, or explicitly approve the complete conditional two-setting experiment and its rollback scope above. No such approval is inferred from this diagnostic directive. No administrator or configuration operation beyond read-only current-permission queries was performed.

## Validation, preservation and checkpoint

- Existing clock and IEX boundary tests: **62 passed, 0 failed, 0 skipped**, **1.97 seconds**. No production source changed; prior 479/428/native/installed evidence preserved separately, not summed as new coverage.
- Main diagnosis **9.312 seconds**, within 150 seconds; packet follow-up **3.172 seconds**, within 40 seconds. **Five total diagnostic NTP replies** across two bounded stripchart invocations plus the single observed-peer invocation; no synchronization request. There are two full validator acquisitions and one additional raw native source observation used to bind the peer-packet target.
- Private evidence: `logs/diagnostics/qd-windows-time-source-diagnosis-v1.json`, `qd-windows-time-upstream-packets-v1.json`, `qd-windows-time-firewall-scope-v1.json`, `qd-windows-time-source-tests-v1.txt`. Original failures and prior evidence retained. Six initial diagnostic/script/test-log files total **39,776 bytes**; later checkpoint/documentation artifacts are additional. No cleanup/deletion; **0 bytes recovered**.
- All owned diagnostic commands self-exited. No listener/HTTP host, native publication child, financial writer, provider, installation or operational account was started. No unrelated process or Genesis interaction. The unrelated research-test edit remains unchanged.
- Full canonical roadmap is updated through its tested archival updater; autonomous state, execution queue and recovery checkpoint preserve previous evidence and seven-phase history. Source promotion manifest and active installation remain unchanged.

**Clock: REFUSED. PAPER startup: NO. Production: NO-GO. Stop at the administrator/Windows-configuration authorization boundary.**
