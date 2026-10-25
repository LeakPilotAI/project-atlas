# Windows-local financial storage selection - 2026-10-24

## Recommendation and authority

Recommend C: as the proposed volume for a NEW isolated Quality Dips PAPER financial account and reviewed runtime release, separate from development on D:. This selects a practical location, not an enrolled resource or security acceptance. No existing account root is presently approved. No existing permissions changed. B1/C1/D1/E1BLOCKED;PAPERstartupNO;productionNO-GO. Windows-local/noVPS/no live-money implementation preserved.

## Observed storage evidence

| Observation | C: | D: |
|---|---|---|
| Filesystem/type | NTFS,Fixed | NTFS,Fixed |
| Windows mapping | Disk0,partition3,GPT | Disk1,partition2,GPT |
| Device model | T-CREATE TM8FPE001T | INTEL SSDPEKNW010T9 |
| Windows bus | NVMe | NVMe |
| Volume capacity bytes |1022982692864 |1024191361024 |
| Free bytes at observation |305065586688 (about284GiB) |800129904640 (about745GiB) |
| Disk capacity bytes |1024209543168 |1024209543168 |
| Coarse health |Healthy/Online,volumeOK |Healthy/Online,volumeOK |
| Read-only/offline flags |False/False |False/False |
| Proposed financial/runtime parents |C:/AtlasPaper,C:/AtlasPaper/QualityDips,C:/AtlasRuntime,C:/AtlasCustody absent |D:/AtlasPaper,D:/AtlasRuntime absent |

Get-Volume/Get-Partition/Get-Disk supplied distinct volume GUIDs and disk unique identities. Exact serial/GUID/PNP/SID values were observed locally but excluded from Git publication. Win32_DiskDrive separately enumerated the two models at indices0and1 withStatusOK;SCSI interface presentation does not contradict NVMe bus abstraction. No other disk,Genesis path or financial records inspected.

Conclusion: C: andD: are NOT partitions on the same Windows-enumerated physical disk. Distinct device models/unique IDs support device-level separation;this does not prove complete hardware independence or exclude controller/firmware virtualization. They share the same workstation,OS,privileged administrators,malware exposure and possibly power/controller infrastructure. The operator's confirmed externalD: remains a physical-topology fact not independently resolved by NVMe/fixed metadata;do not claim C: enclosure/internal placement was physically inspected. C: recommendation relies on system-volume/localdevice separation and existing Windows metadata,not hardware teardown.

## Permissions and capabilities - observed versus unverified

C:/ ownerTrustedInstaller;AreAccessRulesProtected=False. Authenticated Users canCreateDirectories,UsersReadAndExecute,SYSTEM/AdministratorsFullControl,additional capabilityACE. D:/ownerAdministrators and broadAuthenticatedUsersModify. Existing D:/Work/Project Atlas has inherited broadModify permissions and additionalModifyACEs. No reported reparse/link attributes on inspected existing roots/project. Get-Item metadata is not held native ancestor identity proof. Parent ACL observations are NOT permission to change volume-root ACLs or adopt them as financial root policy.

NTFS supports native file IDs,security descriptors and relevant handle primitives. Existing windows_output.py explicitly requiresNTFS and exact protected owner/SYSTEM DACL at the resource root;shared_fence.file_identity binds volume serial/file index;native reader compares actual roots and immutable current/source/projection/report identities. Snapshot reader validates identity/ACL/link before reading. No reader or writer imported/executed for this assessment.

Both existing volume-root ACLs differ from the financial-root policy,which is expected:do NOT modify C:/ or D:/ ACLs to make them match. A separately provisioned protected child namespace is required,with independently accepted ancestor handling and exact native identities. No existing financial root was located or tested,and no claim of C: being immediately operationally ready is made.

Get-StorageReliabilityCounter was attempted once for each mapped physical disk and deniedCIMaccess. Temperature,wear,poweronhours and uncorrectederrors remain UNVERIFIED. Prior D:fsutil detailed filesystem queries were denied;not repeated or treated as passed. These may require an administrator-authorized read-only session/provider permissions;administrator access is not guaranteed to expose counters the hardware/driver does not provide. No elevation of account privileges,SMART selftest,disk scan,write test,flush test,power interruption,backup or restore performed. Healthy/OK is not power-loss protection,integrity or media-lifetime proof.

## Exact proposed resource layout - NOT CREATED

- Source/development remains D:/Work/Project Atlas.
- Reviewed immutable runtime release: C:/AtlasRuntime/releases/<accepted-release-sha>.
- Account namespace: C:/AtlasPaper/QualityDips/<independently-accepted-epoch>.
- Resource roles below that namespace: source,projection,report,control.
- Local custody-service/configuration namespace,if independently approved: C:/AtlasCustody/QualityDips/<accepted-epoch>.

Placeholders are intentional:account/epoch/release names must be accepted before provisioning;no synthetic fixture identity is promoted. No directories above were created. No legacy record copying,migration,reset or adoption. Keep source/projection/report/control physically distinct within the accepted namespace and bind exact creation-handle identities. Paths alone are not resource identity. Current reader consumes drive-letter paths;pin volume/file identities and refuse reassignment,substitution or reconnect uncertainty rather than automatically repinning.

C:/AtlasCustody is a proposed LOCAL coordination/configuration location ONLY. It is NOT independent rollback authority if its only evidence shares the same rollbackable C:volume,account orsystem backup. A different directory or Windows account alone cannot establish independent currentness.

## Minimum practical Windows identity/ACL model

1. Use a standard nonadministrator identity as the accepted Atlas resource owner/reader. Keep elevated maintenance separate;do not routinely runAtlas elevated. Independently review exact principalSID and threatmodel before enrollment.
2. For compatibility with current native code,the financial root/file policy is exactly protected DACL,owner matching executing AtlasSID,and exactly ownerFullControl plusSYSTEMFullControl;no broad/inherited/Everyone/Users/AuthenticatedUsers permissions. Do not insert extra reader/custodianACEs and claim the existing validator accepts them.
3. A dedicated standard Atlas account separate from the development identity gives useful separation from unrelated ordinary-user/dev processes. This is a PROPOSAL requiring new account/credential/session approval and native acceptance;none exists here. Reader and one-time publisher must use a compatible owner context;different principals need explicit source/security review,not an ACL workaround.
4. Running Atlas and development under the same standard identity offers protection from other unprivileged identities but cannot exclude arbitrary same-user code. Owner can rewrite itsDACL;SYSTEM/admin can take control. Exact writer roster,accepted publisher/current custody and deployment isolation still required. Do not claim all-writer exclusion from ACL alone.
5. Operational read-only capability means no application mutation paths;the current ownerFullControl filesystem policy is NOT an OS-enforced read-only reader identity. A split low-privilege reader requires a separately reviewed versioned policy/reader change before provisioning.
6. Protect the reviewed runtime against development writes according to independently accepted release policy. No runtime ACL scheme or service installed by this assessment. No change to volume root,other users,Genesis or unrelated resources.

## Custody and offline backup placement

Accepted high-water must survive rollback of financial resources and not be reconstructible solely from local hashes. Name an independent custodian/mechanism with authenticated monotonic compare-and-swap/source-cut/acknowledgement evidence. A separately held signed/witnessed high-water record outside rollbackable C: and routine workstation administration is needed under the current acceptance model. D: is a different disk but is not automatically trusted independent custody:it remains connected/development-controlled and shares host compromise. No cloud/VPS is required;an independently controlled offline local mechanism may be proposed and reviewed,not manufactured here.

Keep authenticated offline backups on a separately identified physical device,disconnected when not used,with accepted manifest/source-cut/receipt custody and retention. Do not call another folder on C: a backup failure domain. D: can at most be a separately approved additional connected copy/staging location;it does not by itself satisfy OFFLINE backup or independent authority. No backup-device letter/path assigned because none was authorized/observed. Backup target must be named by verified volume identity before later permission,not inferred from a free drive letter. Restore remains separately authorized into isolated new identities;never copy pins into authority or overwrite originals.

Issuer and trusted clock need independently accepted identity/authenticity,expiry,revocation,monotonic discontinuity and outage policies. Disk selection cannot supply them. No keys,credentials,Windows accounts or custodyservices provisioned.

## Bounded future provisioning checklist - permission still required

1. Operator selects the proposed C:layout and exact account/epoch/release names. B1reviewer accepts1000USD hypothetical inception,eligibleQualityDipsstocks/ETFs,100entry/oneposition/manual/long/fractional/no-scale/overnight/syntheticcosts and complete legacy exclusions. Existing financial discrepancies stay unresolved/excluded,not silently closed.
2. Name C1ownership reviewer,D1issuer/high-water/clock/recoverycustodians and approve principal/threatmodel. Authorize only necessary administrator read-only health/feature checks if desired;retain unsupported results honestly.
3. Issue explicit permission naming new paths,ownerSID,SYSTEMpolicy,ancestor plan and approved provisioner,with no volume-root/legacy/Genesis modifications. Resolve account/credential needs separately. No writable account publication is implied by directory approval.
4. Review and separately authorize the actual one-time operational publisher/issuer/current-custody implementation. Existing bootstrap only verifies intent/acknowledgedgenesis;it does not publish or create authority.
5. Provision only accepted new namespaces under retained native creation handles,verify protectedACLs,reparse/hardlink/namespace identities and resource roster. Stop on preexisting/conflicting/ambiguous resources;no repair/delete/reset fallback. Independently record andaccept evidence.
6. Separately authorize immutable inception/projection/report publication with durable intent/commit/ack evidence and externally accepted currentpin. Failed/UNKNOWN work blocks retry/re-enrollment;no fixture-record conversion.
7. Separately accept backup/isolatedrestore and actual process/ownership/drain evidence,install reviewed bridge only with explicit permission. Then explicitly authorize a supervised read-only launch;financialPOSTs remain disabled. Provider/PAPERrouting needs later E1 and runtime permission.

B1/C1/D1/E1 remainBLOCKED;all21decisions unchanged. Selecting C:does not bypass them. No startup granted.

## Validation and continuity

Read-only storage/permission/source assessment;no application-code changes or behavior tests run/recounted. Repository branch/expectedHEAD matched,tracked tree initiallyclean. Documentation-only diff/secret review,approved master-roadmap updater withbyte-equalbackup/exactreadback/outside-managedbytes/prior-managed preservation,queueprefix/stateblockedtask preservation and protectedUI/startuplock/nativecode/policy/gatematrixhashchecks performed. All seven phases unchanged;Phase2HOLD/Phase3BLOCKED. No directories/accounts/ACLs/keys/services/financial records provisioned;only authorized documentation/checkpoint writes. Existing untracked work preserved. PAPERstartupNO;productionNO-GO.
