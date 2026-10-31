# D: Windows storage readiness assessment - 2026-10-24

## Disposition

NTFS capability compatible in principle; NOT ACCEPTED for protected PAPER financial storage. Read-only assessment only. B1/C1/D1/E1 remain BLOCKED;PAPER startup NO;production NO-GO. No financial sources,Genesis,providers,services,containers or operational records accessed. No mount/format/encryption/partition/ACL/power changes. Only authorized documentation/state/checkpoint publication writes performed.

## Observed evidence, not assumptions

| Item | Read-only observation |
|---|---|
| Repository | chatgpt/atlas-rebuild-v1;expected f95db6cccdac32f556dbce55fbbadd5bbcb12735 matched;tracked tree initially clean |
| Filesystem/volume | Get-Volume D: NTFS,Fixed,Healthy,OK;1024191361024bytes capacity,800131936256bytes free at observation (about953.85/745.18GiB). A volume GUID access path was observed. Exact GUID/serial/PNP IDs and user SIDs withheld from public documentation. |
| Physical mapping | Get-Partition maps D: to disk1,partition2,GPT;disk size1024209543168bytes,INTEL SSDPEKNW010T9,SSD;Get-Disk reportsNVMe,Healthy,Online,notread-only/notoffline. Stable disk unique identity and serial were observed,not published. |
| Connection ambiguity | Operator confirms external physical drive. Windows reportsNVMe/fixed;Win32_DiskDrive reportsSCSI interface withNVMe model,PCI parent,removal-policy numeric1. These do not prove the physical enclosure,cable or actual transport. Do not override operator statement or assert USB/Thunderbolt identity. Exact physical connection remains UNVERIFIED. |
| Project ancestry | D:/,D:/Work,D:/Work/Project Atlas exist,not reported as links/reparse points by Get-Item;no recursive financial inventory. Metadata observation alone is not a held native namespace guarantee. |
| Permissions | All three inspected ACLs have AreAccessRulesProtected=False;Authenticated Users hasModify;project includes additional Modify ACEs. Root ownerAdministrators,Work/project current-user principal. Exact two-ACE protected owner/SYSTEM policy is NOT met. Broadly inherited project storage must not be adopted as protected financial root. |
| Proposed paths | D:/AtlasRuntime,D:/AtlasPaper,D:/AtlasPaper/QualityDips absent. No directories created,permissions inferred or native enrollment claimed. |
| Power | Highperformance scheme;diskidle1200seconds AC/DC;standby14400seconds AC,0DC;USBselectivesuspend enabled AC/DC. Policy values do not prove this NVMe device obeys diskidle or usesUSB. No setting changed. |
| Health limits | Storage statusHealthy/OK is coarse,not integrity/power-loss proof. Get-StorageReliabilityCounter deniedCIMaccess;wear,temperature,errorcounts and poweronhours UNVERIFIED. fsutil volumeinfo/ntfsinfo deniedaccess;detailed feature flags/NTFS version not verified. Initial sandbox CIM denial resolved only for approved read-only queries outside sandbox;no administrator privilege or security bypass requested. |

An initial SUB_USB alias query was unsupported;read-only explicit GUID query returned selective-suspend policy. No failed command counted as successful evidence. No write,flush,ACL attack,disconnect,reconnect,sleep,SMART selftest,drive-letter change or power interruption was performed. No tests of application financial behavior were needed or run.

## Actual native-reader compatibility

windows_output.py opens existing roots with retained ancestor handles and relative opens,requiresNTFS,validates exact protected owner/SYSTEM ACL,checks reparse/link conditions. shared_fence.file_identity returns volume serial plus file-index high/low from a native handle. snapshot_store.read_bound verifies identity/ACL/link before ReadFile and rechecks identity after read. operational_financial_read.py compares resource-root identities and canonical immutable bytes with independently authenticated source/projection/report pins;replays arithmetic and rejects missing/extra records. No source changes or imported financial initialization were used for this assessment.

NTFS supports ACLs/file IDs/hardlinks and the relevant Windows primitives conceptually. NTFS does not enforce application immutability against all privileged or same-user code. Existing DACL observations prove incompatibility with the selected policy,not successful enrollment. Physical reliability,actual protected-root native identity and whole namespace/exclusion still require independently accepted observations/tests. Current reader takes drive-letter local paths;do not feed a volume-GUID path and claim compatibility without source review and bounded tests. GUID discovery is identity evidence,not mount permission or startup authority.

Drive-letter reassignment must refuse if D: resolves to foreign volume/file identities;never follow a same-named path and repin automatically. Reformat/copy/restore creates a new identity and needs accepted recovery mapping. A reconnect may preserve file IDs but invalidates assumptions about uninterrupted handles/leases/current custody:close and independently reverify after explicit recovery,never auto-clearUNKNOWN. No reconnect recovery behavior was tested here.

## Failure domains and least privilege

External disconnect,cable/enclosure loss or power interruption can invalidate handles,interrupt publication,lose volatile write caches and leaveUNKNOWN. FlushFileBuffers is not evidence of SSD/enclosure power-loss protection or physical media persistence. Laptop/host sleep and selective suspend may stall I/O;the measured power plan does not eliminate that risk. No hardware power-loss protection,UPS,write-cache policy or enclosure flush guarantees were verified. Do not change settings based on this report alone.

NTFS allows useful Windows-principal separation with separately accepted protected roots,ancestor handling and least privilege. Current broad inherited ACLs do not provide it. Existing exact owner/SYSTEM implementation is tied to current caller SID;multiple writer/reader/custodian principals require an explicitly reviewed compatible design,not silently adding read ACEs that the current reader rejects. Owner/admin/SYSTEM and arbitrary same-user code remain threat-model limitations. No user/group membership or authority credentials were provisioned or audited beyond current-user identity query.

High-water custody cannot be independent if its sole state andfinancial data share the same rollbackable D: drive,even in different directories. Keep independently authenticated CAS/high-water/issuer/recovery custody separately protected and outside that failure domain;another local disk alone is not independent administrative authority. Trusted clock needs accepted authenticity/monotonic discontinuity/outage policy;NTFS time and Windows wall clock are not sufficient. A backup elsewhere on D: is not an independent copy. Offline backup needs a separate physical device/failure domain,authenticated source-cut manifests and separately authorized isolated restoration;no other volume,backup or key was inspected.

## Recommended first operational layout - proposal only

1. Retain source/development on D:/Work/Project Atlas. Never co-locate canonicalfinancial records under the mutable project tree or source-control paths.
2. Prefer an independently assessed internal system NTFS volume for immutable reviewed runtime release and new protected account roots outside the repository. Example locations C:/AtlasRuntime/releases/<accepted-sha> and C:/AtlasPaper/QualityDips/<accepted-epoch>/{source,projection,report,control} are UNINSPECTED,UNAPPROVED and NOT CREATED;C: suitability is not asserted.
3. Keep issuer/current/high-water/recovery custody under independently accepted principal/control and distinct rollback/failure domain. Keep at least one authenticated offline backup on a separate physical device. Single-user Windows-local architecture remains;no VPS/cloud requirement.
4. If operator elects D: financial storage instead,first resolve physical connection/enclosure/flush/power evidence,accept external-disconnect recovery risk,approve exact protected namespace/principals and independent custody/backup,then perform separately authorized confined native acceptance. Do not reuse project ACLs or treatHealthy as acceptance.

## Exact next permissions and blockers

B1:independent fresh-epoch/policy/legacy-exclusion review still needed;no historical records revisited. C1:exact actual resource/principal/writer roster and retainedprocess/drain acceptance absent. D1:issuer,clock,high-water,recovery custodians/protected roots,namespace/rollback/backup acceptance absent. E1:provider rights,accepted executableprice/ranking evidence and supervised release absent. All21decisions unchanged.

Next bounded request: operator identifies the physical connection/enclosure and chooses preferred internal-versusD: storage location;authorize READ-ONLY assessment of the named alternative volume and proposed parent paths if internal storage is selected. Name independent B1/C1/D1reviewers/custodians and threat model. Separately authorize any administrator-only health/feature query only if necessary;current denials remain limitations. Later provisioning must explicitly name paths/principals/ACLs/credentials/issuer mechanism and allowed actions;native disconnect/power/restore tests need their own confined scope. No such permissions inferred. Actual bridge installation,read-only launch,providers and PAPER commands remain separately gated.

## Validation and preservation

Documentation-only milestone;no Python/JSbehavior tests rerun or counted. Read-only storage/ACL/power/source checks above executed with failures reported. Approved roadmap updater verifies backup/readback;additional raw-byte comparison preserves outside-managed bytes and prior managed history. State/queue retain prior outcomes andB1/C1/D1/E1blocked. Seven phases and21decisions unchanged;originalUI,productionlock,native reader and PAPERfirstpolicy hashes checked unchanged. Existing untracked evidence retained. Reviewed documentation only published;raw serials,volumeGUID,SIDs,financial evidence and logs excluded.
