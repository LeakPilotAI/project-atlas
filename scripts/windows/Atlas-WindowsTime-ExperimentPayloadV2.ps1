# Prepared source successor only. The prior one-run grant is consumed.
# Default invocation refuses before module, Windows, process or registry access.
param([switch]$ExecuteNewlyAuthorizedV2,
      [string]$root, [string]$nonce, [string]$expectedSid,
      [int]$parentPid, [long]$parentFileTime, [long]$deadlineQpc)
if(-not $ExecuteNewlyAuthorizedV2){throw 'NEW_EXPLICIT_OPERATOR_EXPERIMENT_AUTHORIZATION_REQUIRED'}
if(-not $root -or -not $nonce -or -not $expectedSid -or $parentPid -le 0 -or $parentFileTime -le 0 -or $deadlineQpc -le 0){throw 'EXACT_NEW_EXPERIMENT_BINDINGS_REQUIRED'}
# This switch/binding check is not an issuer or permission grant. A separately
# approved one-run launcher must pin this entire template and supply actual facts.
$guardPath=Join-Path $PSScriptRoot 'Atlas-WindowsTime-ExperimentGuard.psm1'
$guardBytes=[IO.File]::ReadAllBytes($guardPath)
if($guardBytes.Length -gt 65536){throw 'GUARD_SOURCE_CAPACITY'}
$guardText=([Text.UTF8Encoding]::new($false,$true)).GetString($guardBytes)
if($guardText.Length -gt 0 -and $guardText[0] -eq [char]0xfeff){$guardText=$guardText.Substring(1)}
# Pin canonical UTF8/LF text so a normal Windows Git checkout cannot silently
# make a reviewed script unusable solely by changing CRLF. Execute these exact
# verified characters; do not reopen a mutable path after the hash check.
$guardText=$guardText.Replace("`r`n","`n")
$guardHash=[BitConverter]::ToString(([Security.Cryptography.SHA256]::Create()).ComputeHash([Text.Encoding]::UTF8.GetBytes($guardText))).Replace('-','').ToLowerInvariant()
if($guardHash -cne 'a04829941bdddd59f8a5c9dd114e66cee60148448f4285fb1eece503335e4424'){throw 'EXACT_REVIEWED_GUARD_SOURCE_MISMATCH'}
New-Module -Name AtlasTimeExperimentGuardV2 -ScriptBlock ([scriptblock]::Create($guardText))|Import-Module -DisableNameChecking
$script:atlasOriginalEffectiveV2=$null
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$env:PSModulePath=Join-Path $PSHOME 'Modules'
$result=[ordered]@{schema='ATLAS_ONE_BOUNDED_W32TIME_EXPERIMENT_V2';started_utc=[datetime]::UtcNow.ToString('o');apply_reload_attempts=0;rollback_reload_attempts=0;mutation_started=$false;rollback_required=$false;rollback_verified=$false;commands=@();writes=@();status='PREFLIGHT'}
$key=$null;$before=$null;$successful=$false
$result['target_restore_readback_verified']=$false;$result['full_scope_verified']=$false
function Remaining-Seconds {($deadlineQpc-[Diagnostics.Stopwatch]::GetTimestamp())/[double][Diagnostics.Stopwatch]::Frequency}
function Write-NewJson($name,$value) {
 $path=Join-Path $root $name
 $bytes=[Text.Encoding]::UTF8.GetBytes(($value|ConvertTo-Json -Depth 15))
 $stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
 try{$stream.Write($bytes,0,$bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function Read-Snapshot {
 $base='HKLM:\SYSTEM\CurrentControlSet\Services\W32Time'
 $config=Get-Item -LiteralPath ($base+'\Config')
 $values=[ordered]@{}
 foreach($name in @($config.GetValueNames()|Sort-Object)){$values[$name]=@{kind=[string]$config.GetValueKind($name);value=$config.GetValue($name)}}
 $config.Close()
 $p=Get-ItemProperty -LiteralPath ($base+'\Parameters')
 $n=Get-ItemProperty -LiteralPath ($base+'\TimeProviders\NtpClient')
 $s=Get-Service -Name W32Time
 $snapshot=[ordered]@{configuration_values=$values;service=[string]$s.Status;startup=[string]$s.StartType;source=[string]$p.NtpServer;type=[string]$p.Type;SpecialPollInterval=$n.SpecialPollInterval;NtpClientEnabled=$n.Enabled}
 $s.Dispose()
 return $snapshot
}
function Invoke-Time($arguments,$label) {
 $info=New-Object Diagnostics.ProcessStartInfo
 $info.FileName=$tool;$info.Arguments=$arguments;$info.UseShellExecute=$false;$info.CreateNoWindow=$true
 $info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
 $process=New-Object Diagnostics.Process;$process.StartInfo=$info
 try {
  if(-not $process.Start()){throw 'OWNED_TIME_COMMAND_START_FAILED'}
  $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
  if(-not $process.WaitForExit(4000)){$process.Kill();$process.WaitForExit();throw 'EXACT_OWNED_TIME_COMMAND_TIMEOUT'}
  $row=@{label=$label;arguments=$arguments;exit_code=$process.ExitCode;stdout=$stdout.GetAwaiter().GetResult();stderr=$stderr.GetAwaiter().GetResult();observed_utc=[datetime]::UtcNow.ToString('o')}
  $result.commands+=$row
  if($row.exit_code -ne 0){throw ('TIME_COMMAND_REFUSED_'+$label)}
  return $row.stdout
 }finally{$process.Dispose()}
}
function Assert-Effective($text,$maximum,$update) {
 if($null -eq $script:atlasOriginalEffectiveV2){
  if($maximum -ne 15 -or $update -ne 360000){throw 'ORIGINAL_EFFECTIVE_CUT_REQUIRED'}
  $script:atlasOriginalEffectiveV2=$text
 }
 $null=Assert-AtlasTimeEffective -OriginalText $script:atlasOriginalEffectiveV2 -CurrentText $text -ExpectedMaximum $maximum -ExpectedUpdate $update
}
function Assert-Scope($snapshot,$maximum,$update) {
 $null=Assert-AtlasTimeScope -Original $before -Current $snapshot -ExpectedMaximum $maximum -ExpectedUpdate $update
}
function Assert-Qualification($decision,$evidenceHash,$nowQpc,$frequency) {
 $null=Assert-AtlasTimeQualification -Decision $decision -ExpectedNonce $nonce -EvidenceHash $evidenceHash -NowQpc $nowQpc -Frequency $frequency
}
function Assert-Parent {
 $parent=Get-Process -Id $parentPid -ErrorAction Stop
 try{if($parent.StartTime.ToUniversalTime().ToFileTimeUtc() -ne $parentFileTime){throw 'PARENT_IDENTITY_CHANGED'}}finally{$parent.Dispose()}
}
try {
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $principal=New-Object Security.Principal.WindowsPrincipal($identity)
 if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) -or $identity.User.Value -cne $expectedSid){throw 'APPROVED_SAME_OPERATOR_ELEVATION_UNAVAILABLE'}
 if((Remaining-Seconds) -lt 235){throw 'INSUFFICIENT_TOTAL_BOUND_BEFORE_EFFECTS'}
 Assert-Parent
 $tool=Join-Path ([Environment]::SystemDirectory) 'w32tm.exe'
 $signature=Get-AuthenticodeSignature -LiteralPath $tool
 if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)'){throw 'WINDOWS_TOOL_SIGNATURE_REFUSED'}
 $before=Read-Snapshot;Assert-Scope $before 15 360000
 $effective=Invoke-Time '/query /configuration /verbose' 'effective_before'
 Assert-Effective $effective 15 360000
 $status=Invoke-Time '/query /status /verbose' 'status_before'
 if($status -notmatch '(?m)^Leap Indicator:\s*0' -or $status -notmatch '(?m)^Last Sync Error:\s*0(?:\s|$)'){throw 'SOURCE_NOT_HEALTHY_BEFORE_EFFECTS'}
 $ageMatch=[regex]::Match($status,'(?m)^Time since Last Good Sync Time:\s*(\d+(?:\.\d+)?)s\r?$')
 if(-not $ageMatch.Success -or [decimal]$ageMatch.Groups[1].Value -gt 120){throw 'SOURCE_FRESHNESS_UNVERIFIED_BEFORE_EFFECTS'}

 $result['before']=$before;$result['effective_before']=$effective
 Write-NewJson 'admin-before.json' $result
 if((Remaining-Seconds) -lt 225){throw 'INSUFFICIENT_APPLY_OBSERVE_ROLLBACK_BUDGET'}
 $key=[Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SYSTEM\CurrentControlSet\Services\W32Time\Config',$true)
 if($null -eq $key){throw 'APPROVED_REGISTRY_KEY_UNAVAILABLE'}
 # Recheck the two exact values at the write boundary. No other name is writable.
 if($key.GetValue('MaxPollInterval') -ne 15 -or $key.GetValue('UpdateInterval') -ne 360000 -or [string]$key.GetValueKind('MaxPollInterval') -ne 'DWord' -or [string]$key.GetValueKind('UpdateInterval') -ne 'DWord'){throw 'ORIGINAL_VALUES_CHANGED_BEFORE_WRITE'}
 $result.mutation_started=$true
 $key.SetValue('MaxPollInterval',6,[Microsoft.Win32.RegistryValueKind]::DWord);$result.writes+=@{name='MaxPollInterval';value=6;stage='APPLY'}
 $key.SetValue('UpdateInterval',100,[Microsoft.Win32.RegistryValueKind]::DWord);$result.writes+=@{name='UpdateInterval';value=100;stage='APPLY'}
 $key.Flush()
 $result.apply_reload_attempts=1
 $null=Invoke-Time '/config /update' 'single_apply_reload'
 $effective=Invoke-Time '/query /configuration /verbose' 'effective_applied';Assert-Effective $effective 6 100
 $applied=Read-Snapshot;Assert-Scope $applied 6 100
 $observationStart=[Diagnostics.Stopwatch]::GetTimestamp()
 $observationEnd=$observationStart+[long](180*[Diagnostics.Stopwatch]::Frequency)
 $result['applied']=$applied;$result['effective_applied']=$effective
 Write-NewJson 'admin-applied.json' @{schema='ATLAS_W32TIME_APPLIED_V1';nonce=$nonce;observation_start_qpc=$observationStart;observation_end_qpc=$observationEnd;deadline_qpc=$deadlineQpc;applied=$applied;effective=$effective}
 while([Diagnostics.Stopwatch]::GetTimestamp() -lt $observationEnd -and (Remaining-Seconds) -gt 40) {
  Assert-Parent
  $now=Read-Snapshot;Assert-Scope $now 6 100
  if(Test-Path -LiteralPath (Join-Path $root 'abort.json')){throw 'PARENT_REFUSED_OR_ABORTED_EXPERIMENT'}
  $decisionPath=Join-Path $root 'clock-qualified.json'
  if(Test-Path -LiteralPath $decisionPath){
   $decision=Get-Content -LiteralPath $decisionPath -Raw|ConvertFrom-Json
   $evidence=Join-Path $root 'clock-binding.json'
   $evidenceHash=(Get-FileHash -LiteralPath $evidence -Algorithm SHA256).Hash.ToLowerInvariant()
   Assert-Qualification $decision $evidenceHash ([Diagnostics.Stopwatch]::GetTimestamp()) ([Diagnostics.Stopwatch]::Frequency)
   $effective=Invoke-Time '/query /configuration /verbose' 'effective_success';Assert-Effective $effective 6 100
   $result['after']=Read-Snapshot;Assert-Scope $result.after 6 100
   $result['full_scope_verified']=$true;$result['qualification']=$decision;$result['status']='SUCCESS_APPLIED_CLOCK_QUALIFIED_TEMPORARILY';$successful=$true
   break
  }
  Start-Sleep -Milliseconds 400
 }
 if(-not $successful){throw 'NO_QUALIFYING_CLOCK_WITHIN_OBSERVATION_BOUND'}
}catch{$result['failure']=$_.Exception.ToString();$result['status']='FAILED_REQUIRES_ROLLBACK_OR_NO_EFFECT'}
finally {
 if($successful){
  try{
   $result['remaining_seconds']=[math]::Round((Remaining-Seconds),3);$result['ended_utc']=[datetime]::UtcNow.ToString('o')
   Write-NewJson 'admin-final.json' $result
  }catch{$successful=$false;$result['failure']='SUCCESS_RECEIPT_UNVALIDATED_REQUIRES_ROLLBACK: '+$_.Exception.Message}
 }
 if($result.mutation_started -and -not $successful){
  $result.rollback_required=$true
  try {
   if((Remaining-Seconds) -lt 15){throw 'INSUFFICIENT_ROLLBACK_BOUND_UNRESOLVED'}
   if($null -eq $key){throw 'ROLLBACK_KEY_UNAVAILABLE'}
   $maximum=$key.GetValue('MaxPollInterval');$update=$key.GetValue('UpdateInterval')
   if($maximum -notin @(15,6) -or $update -notin @(360000,100) -or [string]$key.GetValueKind('MaxPollInterval') -ne 'DWord' -or [string]$key.GetValueKind('UpdateInterval') -ne 'DWord'){throw 'FOREIGN_CHANGE_NO_OVERWRITE_UNRESOLVED'}
   $key.SetValue('MaxPollInterval',[int]$before.configuration_values.MaxPollInterval.value,[Microsoft.Win32.RegistryValueKind]::DWord);$result.writes+=@{name='MaxPollInterval';value=15;stage='ROLLBACK'}
   $key.SetValue('UpdateInterval',[int]$before.configuration_values.UpdateInterval.value,[Microsoft.Win32.RegistryValueKind]::DWord);$result.writes+=@{name='UpdateInterval';value=360000;stage='ROLLBACK'}
   $key.Flush();$result.rollback_reload_attempts=1
   $null=Invoke-Time '/config /update' 'single_rollback_reload'
   $effective=Invoke-Time '/query /configuration /verbose' 'effective_rollback'
   $result['after']=Read-Snapshot
   $null=Assert-AtlasTimeTargetReadback -Current $result.after -EffectiveText $effective
   $result['target_restore_readback_verified']=$true
   Assert-Effective $effective 15 360000
   Assert-Scope $result.after 15 360000
   $result['full_scope_verified']=$true
   $result['effective_rollback']=$effective;$result.rollback_verified=$true;$result.status='FAILED_ROLLBACK_CONFIRMED'
  }catch{$result['rollback_error']=$_.Exception.ToString();$result.status='UNRESOLVED_ROLLBACK_NOT_CONFIRMED_STOP'}
 }elseif(-not $result.mutation_started){$result.status='REFUSED_BEFORE_CONFIGURATION_CHANGE'}
 if(-not $successful){
  $result['remaining_seconds']=[math]::Round((Remaining-Seconds),3);$result['ended_utc']=[datetime]::UtcNow.ToString('o')
  Write-NewJson 'admin-final.json' $result
 }
 if($null -ne $key){$key.Dispose()}
}
if($result.status -eq 'SUCCESS_APPLIED_CLOCK_QUALIFIED_TEMPORARILY'){exit 0}
if($result.status -eq 'FAILED_ROLLBACK_CONFIRMED'){exit 41}
if($result.status -eq 'REFUSED_BEFORE_CONFIGURATION_CHANGE'){exit 43}
exit 42
