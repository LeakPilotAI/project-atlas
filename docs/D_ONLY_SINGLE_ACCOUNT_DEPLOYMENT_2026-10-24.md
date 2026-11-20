# Final D:-only, existing-account PAPER deployment - 2026-10-24

## Permanent operator decision

Atlas runtime,source,financial storage,control and local coordination deploy entirely on D:under the EXISTING Windows account. NoC:deployment,noadditionalWindowsaccounts,noVPS/cloud,no live-money implementation,noGenesisaccess. Preserve originalalienUI. This supersedes the prior C:recommendation as a current plan;LOCAL_FINANCIAL_STORAGE_SELECTION_2026-10-24.md and its evidence remain unchanged history. Device observations are not rewritten.

ATLAS_DEPLOYMENT_POLICY.json local_layout ATLAS_D_ONLY_SINGLE_ACCOUNT_V1 is canonical;PAPER release policy references that layout. New static checks reject C:roots,newWindowsaccounts,changed paths,root/projectACLpermission,provisioning flags or fabricated custody/backup independence. They are development regression checks,not operational enforcement or enrollment authority. All21decisions unchanged;B1/C1/D1/E1BLOCKED;PAPERstartupNO;productionNO-GO.

## Smallest compatible proposed layout - not provisioned

| Role | Exact proposed path |
|---|---|
| Development |D:/Work/Project Atlas (existing,unchanged) |
| Reviewed fixed runtime |D:/AtlasRuntime/releases/<accepted-release-sha> |
| New account |D:/AtlasPaper/QualityDips/<accepted-epoch> |
| Canonical financial source |D:/AtlasPaper/QualityDips/<accepted-epoch>/source |
| Immutable projections |D:/AtlasPaper/QualityDips/<accepted-epoch>/projection |
| Historical reports |D:/AtlasPaper/QualityDips/<accepted-epoch>/report |
| Enrollment/lifecycle control |D:/AtlasPaper/QualityDips/<accepted-epoch>/control |
| Local custody coordination only |D:/AtlasCustody/QualityDips/<accepted-epoch> |

Release/epoch placeholders need explicit accepted values,not synthetic fixture IDs. Prior read-only evidence foundD:NTFS,about745GiBfree,coarseHealthy,Windowsdisk1NVMe;operator identifiesexternalphysicaldrive,topology/flush/powerlossdetailsunverified. Proposed parent roots were absent at assessment;no freshprovisioning or newfilesystem observation in this milestone. No legacy adoption or copying. Do not create redundantstores oranotheraccountingengine.

Only NEW Atlas-owned child directories/files may receive their reviewed protectedDACL under a later permission. Do NOT changeD:/permissions,D:/Work,D:/Work/Project Atlas,existingfinancialsources or unrelatednamespace. Reader already opens retained ancestors,uses relativeopens and validates resource identity;new parent/root ownership/namespace handling still needs native acceptance. RootACLchanges are not required or authorized by this plan.

## Existing-account/native-reader reconciliation

windows_output.current_sid() obtains the executingWindowsidentity;validate_acl requires resource owner exactly thatSID,protectedDACL and exactly twoFullControlallowACEs:thatSID andSYSTEM. It does NOT require a newWindowsaccount. The observed operator principal was the existingrenalaccount;accept exact currentSID at actual enrollment,never trust a displayname/callerJSON as proof. No SID or credentials published.

Run accepted reader and separately approved one-timepublisher under the existingaccount to preserve currentpolicy compatibility. Do not adddifferentreader/custodianACEs or broadUsers/AuthenticatedUsers grants:thecurrentvalidator rejects them. Do not edit nativecode to make broadexistingprojectpermissions pass. Publisher is still unimplemented;the existingbootstrap only prepares/verifies authenticatedintent/genesisACK.

App read-only does not mean OSfilesystemreadonly:the currentowner hasFullControl. Keeping nofinancialPOSTs/providers/writers in the readservice limits its ownbehavior,but arbitrary same-accountcode can access/replacecontents or changeDACLs when not protected by livehandles. No claim that policyhashes or localapprovalJSON prevents that.

## Explicit limitations under this architecture

- Same-accountdevelopment,otherprocesses andoperatorcode cannot be durably excluded by owner/SYSTEMDACL alone;owner can changepermissions. Handleboundshare/identitychecks provide bounded refusal,detection and concurrenthandleprotection,not perpetual same-user immutability or independentwriterownership.
- SYSTEM/admin remain privileged. No protectedcredential/key/issuer boundary is created by anotherD:folder. Locallygeneratedhashes andcopiedpins are not independentapproval/currentness.
- Source,financialstate,control,localhigh-water andlocalbackups onD:share device-loss/disconnection/coherentrollback exposure. Separatefolders,manifesthashes or a secondpartition onthedevice cannot solve it. A D:-only backup is not independentphysicalbackup or provableofflinecustody whilethatdeviceisoperating.
- Trustedclock cannot come fromfilesystemtimestamps or unacceptedwallclockalone. Authenticatedissuer,clock,current/high-waterandrecoveryauthority remainmissing. Singleaccountdoes not authenticate them.
- Fixedruntimecopy onD:separatesnormaldevelopmentpaths,but same-accountmutation remainspossible;reviewedreleasebinding and startupchecks mustrefuse changedcode,not imply writeexclusion.
- External-drivepowerloss,cacheflush,enclosure/sleep/reconnect remainunaccepted. Never promise physicaldurability fromfsync/FlushFileBuffers or Healthy status. Never auto-repin a reconnect/changeddriveletter or clearUNKNOWN.

These are unresolvedD1/C1requirements,not inconveniences to silentlywaive. If requiredindependentcustody/offlinebackup cannot be supplied within permanentD:-only/singleaccount scope,the applicablegate remainsBLOCKED and launchcannotproceed. A reviewer may propose a disposition,but operatorpreference is not independentacceptance or a change to any21decision. No newaccount,C:deployment,cloudscheme or speculativeframework proposed as a workaround.

## Minimal executable deployment sequence - gated runbook, NOT executed

| Step | Action using existingcomponents | Required permission/evidence and stopcondition |
|---|---|---|
|1.scope |Fixacceptedepoch/release and1000USDhypotheticalinception;eligible rankedstocks/ETFs,100USDentry,oneposition,long/manual,noscale,fractionalwhere supported,overnightallowed,synthetic2bpsfee+2bpsslippage |IndependentB1scope/legacyexclusionacceptance;no legacy obligations declaredclosed. Stopwithoutdecision. |
|2.trust |Bind actualexistingSID/resources,acceptedissuer,current/high-water,clock,recovery/readservice acceptance |NamedC1/D1reviewers/custodians mustaccept real evidence and explicitly addresssame-account/sharedD:limits. No defaultissuer,testpins or fakecredentials. Stopwhenunavailable. |
|3.publisher |Implement smallestaccepted one-timepublisher/custodyintegration aroundexistingFS1-FS3/QD_OPcontracts |Separatesourceimplementationpermission andacceptedinterfaces. Reuseaccounting;no newfinancialengine. CurrentEnrollmentBootstrap hasnopublishmethod. |
|4.provision |CreateonlyapprovedNEW D:Atlasparent/accountrolepaths withretainedcreationhandles;applyexactcurrentowner/SYSTEMDACL;recordnativeidentities |Explicitnamedpath/SID/ACL/provisioningpermissionfirst. Nevermodifydrive/projectACLs;preexisting/foreign/ambiguousresource meansSTOP,norepair/deletefallback. |
|5.inception |Reserve durableaccount/epochoperation,intent;publish immutableQD_OPinception,projection,V2report;verifyrevision0/cash1000;acceptedcustodianACK/currentpin |Distinctfinancialpublicationpermission. KeepPENDING/UNKNOWN;never replayuncertainfinancialeffects or usefixturebuilder. No runtimefinancialwriteractivation. |
|6.readonly |EnrollmentBootstrap.verify_publication/launch_plan plusNew-AtlasEnrolledReadBridge withindependentlyaccepteddependencies;existingControlCenterselectedview |Actualresource/process/retainedchild/readserviceacceptance,explicitbridgeinstall andsupervisedreadonlylaunchpermission. LoopbackGETonly,POSTrefused,legacyresearchGETunavailable;verifyreadinessbeforebrowser andownedgracefulclose. Productionlockunchanged. |
|7.data |Existingmarketdata/rankadapter withlicensedstock/ETF/session/corporateaction/freshness/budget evidence |Provider-specificrightsandexplicitconnectionpermission,E1acceptance. Rankingalonecannotauthorizeentry;stale/missingpricesrefuse. Noprovidercallsnow. |
|8.manualPAPER |Narrowselectedaccountcommandrouting withmanualentry/partial/fullconfirmation,durableACK,policy/cash/revisionchecks |Separateruntimefinancialroutingapproval andacceptedB1/C1/D1/E1. Allwriteradmission/UNKNOWNdrain/reports/restartmustpassrealacceptance. Overnightpositionsstayopen;cleanreadonlyexitdoesnotmeanliquidation. |
|9.trial |Sevendesignatedauthorizedsessiondays,thenreviewbefore30-60sessions |Acceptedcountingrule;recordallattempts/failures,incompleteandUNKNOWN;dailycash/quantity/cost/reportreconciliation,ownedstop/restartandbackup/recoveryevidence. Pauseonunexplainedstate;no automaticpromotion. |

Shortest next step is acceptance of the existing-account/D:threatmodel and actualissuer/current/clock/recoverymechanisms,followed by separatelyauthorized minimalpublisher/provisioning. No startupbutton or additionaldemo solves those missingfacts. No servicesorproviderintegration runnow. Trialcountsremain0of7 and0of30-60.

## Validation and preservation

117combinedtests passed,0failed,0skipped:68policycases(15new),46enrollmentbootstrap/retainedchildcases,3productionlockcases. Singlecombinedrun;nooverlapdoublecounting. Purepolicychecks plusisolatedtestownedprocesses/controlreceipts only;nooperationalfinancialrecordcreation. Ruff2files/compilation2files andPAPERstatic558runtimefiles0issues pass. No newnativefinancialACL/browser/provideracceptance claimed;retainedsymlinkprivilegelimitation unchanged.

Approvedmasterupdaterbackup/readback/prior-managed/outsidebytesverified. Sevenphases/21decisions/startuplock/originalfrontend/native-readerbytes unchanged. StatecurrentlayoutsupersedespriorC:proposal,whichisretainedashistory. Policyaccount/risk/cost/gatestatusvaluesunchanged. No protecteddirectories/ACLs/keys/services/records provisioned;noGenesisaccess. Reviewedsourcepolicy/tests/docs only published. PAPERstartupNO;productionNO-GO.
