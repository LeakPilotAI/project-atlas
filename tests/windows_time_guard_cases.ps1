param([Parameter(Mandatory=$true)][string]$ModulePath,
      [Parameter(Mandatory=$true)][string]$PayloadPath,
      [Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference='Stop'
Set-StrictMode -Version 2.0
Import-Module -Name $ModulePath -Force -DisableNameChecking

function New-Fixture([string]$fault) {
    $snapshot=@{service='Running';startup='Manual';source='time.windows.com,0x9';type='NTP';SpecialPollInterval=64;NtpClientEnabled=1;
        configuration_values=@{MaxPollInterval=@{kind='DWord';value=15};UpdateInterval=@{kind='DWord';value=360000};
            MinPollInterval=@{kind='DWord';value=6};PhaseCorrectRate=@{kind='DWord';value=1};
            LastKnownGoodTime=@{kind='QWord';value=134000000000000000L};OtherProtected=@{kind='DWord';value=10}}}
    $state=@{snapshot=$snapshot;fault=$fault;writes=@();reloads=@();records=@();queries=0;remaining=300;
             observed=$false;peer_revision=8;peer_last_sync=1700000000;verify_calls=0;ports=$null}
    if($fault -eq 'preflight_wrong_value'){$snapshot.configuration_values.MaxPollInterval.value=7}
    if($fault -eq 'preflight_service_stopped'){$snapshot.service='Stopped'}
    if($fault -eq 'preflight_budget'){$state.remaining=200}
    $ports=@{}
    $ports.ReadSnapshot={
        if($state.fault -eq 'rollback_snapshot_missing' -and $state.reloads -contains 'rollback'){throw 'FIXTURE_MISSING_ROLLBACK_SNAPSHOT'}
        return $state.snapshot
    }.GetNewClosure()
    $ports.QueryEffective={
        $state.queries++
        if($state.fault -eq 'applied_readback_missing' -and $state.queries -eq 2){throw 'FIXTURE_MISSING_APPLIED_QUERY'}
        if($state.fault -eq 'rollback_query_missing' -and $state.reloads -contains 'rollback'){throw 'FIXTURE_MISSING_ROLLBACK_QUERY'}
        $policy=if($state.fault -eq 'preflight_policy'){'Policy'}else{'Local'}
        $s=$state.snapshot
        $text="MaxPollInterval: $($s.configuration_values.MaxPollInterval.value) ($policy)`nUpdateInterval: $($s.configuration_values.UpdateInterval.value) (Local)`nMinPollInterval: $($s.configuration_values.MinPollInterval.value) (Local)`nPhaseCorrectRate: 1 (Local)`nSpecialPollInterval: $($s.SpecialPollInterval) (Local)`nType: $($s.type) (Local)`nNtpServer: $($s.source) (Local)`nOtherProtected: 10 (Local)"
        if($state.fault -eq 'effective_duplicate' -and $state.queries -eq 2){$text+="`nMaxPollInterval: 6 (Local)"}
        if($state.fault -eq 'rollback_incomplete_effective' -and $state.reloads -contains 'rollback'){$text=$text.Replace('UpdateInterval: 360000 (Local)','')}
        if($state.fault -eq 'effective_foreign_only' -and $state.observed){$text=$text.Replace('OtherProtected: 10','OtherProtected: 11')}
        return $text
    }.GetNewClosure()
    $ports.WriteSetting={param($name,$value)
        if($name -cnotin @('MaxPollInterval','UpdateInterval')){throw 'FIXTURE_UNAPPROVED_WRITE_NAME'}
        if($state.fault -eq 'rollback_write_failure' -and $name -ceq 'MaxPollInterval' -and $value -eq 15){throw 'FIXTURE_ROLLBACK_WRITE_FAILED'}
        $state.writes+=@{name=$name;value=$value}
        $state.snapshot.configuration_values[$name].value=$value
        if($state.fault -eq 'interrupted_first_write' -and $name -ceq 'MaxPollInterval' -and $value -eq 6){throw 'FIXTURE_INTERRUPTED_AFTER_FIRST_EFFECT'}
        if($state.fault -eq 'interrupted_second_write' -and $name -ceq 'UpdateInterval' -and $value -eq 100){throw 'FIXTURE_INTERRUPTED_AFTER_SECOND_EFFECT'}
    }.GetNewClosure()
    $ports.Reload={param($phase)
        $state.reloads+=$phase
        if($state.fault -eq 'apply_reload_failure' -and $phase -ceq 'apply'){return [int]5}
        if($state.fault -eq 'rollback_reload_failure' -and $phase -ceq 'rollback'){return [int]5}
        return [int]0
    }.GetNewClosure()
    $ports.ObserveClock={param($seconds)
        if($seconds -ne 180){throw 'FIXTURE_UNBOUNDED_OBSERVATION'}
        $state.observed=$true;$state.remaining=80
        $state.snapshot.configuration_values.LastKnownGoodTime.value+=645331075L
        $state.peer_revision++;$state.peer_last_sync+=64
        $e=@{qualified=$true;complete=$true;bound_ms=900;age_seconds=1;domain='DISPOSABLE_SYNTHETIC';source='time.windows.com,0x9'}
        switch($state.fault){
            'runtime_same' {$state.snapshot.configuration_values.LastKnownGoodTime.value-=645331075L}
            'runtime_regression' {$state.snapshot.configuration_values.LastKnownGoodTime.value-=645331076L}
            'runtime_bad_kind' {$state.snapshot.configuration_values.LastKnownGoodTime.kind='String'}
            'runtime_bool' {$state.snapshot.configuration_values.LastKnownGoodTime.value=$true}
            'runtime_string' {$state.snapshot.configuration_values.LastKnownGoodTime.value='134000000645331075'}
            'runtime_range' {$state.snapshot.configuration_values.LastKnownGoodTime.value=[long]::MaxValue}
            'runtime_large_jump' {$state.snapshot.configuration_values.LastKnownGoodTime.value+=4200000000L}
            'runtime_unknown_key' {$state.snapshot.configuration_values['LastUnexpected']=@{kind='QWord';value=1L}}
            'runtime_removed_key' {$state.snapshot.configuration_values.Remove('LastKnownGoodTime')}
            'static_row_extra' {$state.snapshot.configuration_values.OtherProtected.extra='foreign'}
            'static_kind_change' {$state.snapshot.configuration_values.OtherProtected.kind='QWord'}
            'namespace_replaced' {$state.snapshot.configuration_values.Remove('OtherProtected');$state.snapshot.configuration_values['LastOtherProtected']=@{kind='DWord';value=10}}
            'snapshot_extra' {$state.snapshot.extra='foreign'}
            'foreign_poll' {$state.snapshot.configuration_values.MaxPollInterval.value=7}
            'foreign_update' {$state.snapshot.configuration_values.UpdateInterval.value=101}
            'foreign_target_type' {$state.snapshot.configuration_values.MaxPollInterval.value='6'}
            'foreign_minimum' {$state.snapshot.configuration_values.MinPollInterval.value=7}
            'foreign_unknown' {$state.snapshot.configuration_values.OtherProtected.value=11}
            'foreign_source' {$state.snapshot.source='foreign.invalid,0x9'}
            'source_array' {$state.snapshot.source=@('time.windows.com,0x9','time.windows.com,0x9')}
            'service_array' {$state.snapshot.service=@('Running','Running')}
            'startup_array' {$state.snapshot.startup=@('Manual','Manual')}
            'type_array' {$state.snapshot.type=@('NTP','NTP')}
            'foreign_service' {$state.snapshot.service='Stopped'}
            'foreign_startup' {$state.snapshot.startup='Automatic'}
            'foreign_type' {$state.snapshot.type='NoSync'}
            'foreign_special' {$state.snapshot.SpecialPollInterval=128}
            'foreign_client' {$state.snapshot.NtpClientEnabled=0}
            'clock_incomplete' {$e.complete=$false}
            'clock_1000' {$e.bound_ms=1000}
            'clock_1001' {$e.bound_ms=1001}
            'clock_bool' {$e.bound_ms=$true}
            'clock_wrong_domain' {$e.domain='LOCAL_WINDOWS'}
            'clock_wrong_source' {$e.source='foreign.invalid'}
            'clock_stale' {$e.age_seconds=121}
            'clock_negative_age' {$e.age_seconds=-1}
            'clock_nan' {$e.age_seconds=[double]::NaN}
            'deadline_exhausted' {$state.remaining=10}
            'budget_nan' {$state.remaining=[double]::NaN}
            'budget_string' {$state.remaining='forever'}
            'budget_increase' {$state.remaining=301}
        }
        if($state.fault -match '^rollback_' -or $state.fault -eq 'clock_unqualified'){$e.qualified=$false}
        return $e
    }.GetNewClosure()
    $ports.VerifyClock={param($value)
        $state.verify_calls++
        if($state.fault -eq 'clock_verifier_object'){return @{verified=$true}}
        return [bool]($state.fault -ne 'clock_unverified' -and $value.domain -ceq 'DISPOSABLE_SYNTHETIC')
    }.GetNewClosure()
    $ports.Record={param($phase,$value)
        $state.records+=$phase
        if($state.fault -eq 'record_before_false' -and $phase -ceq 'before'){return $false}
        if($state.fault -eq 'record_before_object' -and $phase -ceq 'before'){return @{ok=$true}}
        if($state.fault -eq 'record_intent_false' -and $phase -ceq 'intent'){return $false}
        if($state.fault -eq 'record_applied_false' -and $phase -ceq 'applied'){return $false}
        if($state.fault -eq 'record_qualified_false' -and $phase -ceq 'qualified'){return $false}
        if($state.fault -eq 'record_qualified_object' -and $phase -ceq 'qualified'){return @{verified=$true}}
        if($state.fault -eq 'rollback_record_false' -and $phase -ceq 'rollback'){return $false}
        if($state.fault -eq 'rollback_record_object' -and $phase -ceq 'rollback'){return @{verified=$true}}
        if($state.fault -eq 'caller_mutates_record' -and $phase -ceq 'before'){$value.snapshot.configuration_values.MinPollInterval.value=99}
        if($state.fault -eq 'caller_mutates_ports' -and $phase -ceq 'before'){$state.ports.ReadSnapshot={throw 'FOREIGN_REBOUND_PORT'}}
        return $true
    }.GetNewClosure()
    $ports.RemainingSeconds={return $state.remaining}.GetNewClosure()
    $state.ports=$ports
    return @{state=$state;ports=$ports}
}

$names=@('sync_advance','runtime_same','caller_mutates_record','caller_mutates_ports',
    'runtime_regression','runtime_bad_kind','runtime_bool','runtime_string','runtime_range','runtime_large_jump','runtime_unknown_key','runtime_removed_key',
    'static_row_extra','static_kind_change','namespace_replaced','snapshot_extra',
    'foreign_poll','foreign_update','foreign_target_type','foreign_minimum','foreign_unknown','foreign_source',
    'source_array','service_array','startup_array','type_array',
    'foreign_service','foreign_startup','foreign_type','foreign_special','foreign_client','effective_foreign_only',
    'interrupted_first_write','interrupted_second_write','apply_reload_failure','applied_readback_missing','effective_duplicate',
    'rollback_write_failure','rollback_reload_failure','rollback_query_missing','rollback_incomplete_effective',
    'rollback_snapshot_missing','rollback_record_false','rollback_record_object','record_qualified_false','record_qualified_object','record_applied_false',
    'clock_unqualified','clock_unverified','clock_incomplete','clock_1000','clock_1001','clock_bool','clock_wrong_domain',
    'clock_wrong_source','clock_stale','clock_negative_age','clock_nan','clock_verifier_object','deadline_exhausted','budget_nan','budget_string','budget_increase',
    'preflight_wrong_value','preflight_service_stopped','preflight_budget','preflight_policy',
    'record_before_false','record_before_object','record_intent_false')
$rows=@()
foreach($name in $names){
    $fixture=New-Fixture $name
    $result=Invoke-AtlasTimeGuardedExperiment -Ports $fixture.ports
    $rows+=@{name=$name;result=$result;writes=$fixture.state.writes;reloads=$fixture.state.reloads;
             records=$fixture.state.records;after=$fixture.state.snapshot;peer_revision=$fixture.state.peer_revision;
             verify_calls=$fixture.state.verify_calls}
}
$refused=$false
try{Invoke-AtlasTimeGuardedExperiment|Out-Null}catch{$refused=$_.Exception.Message -eq 'TIME_GUARD_EXPLICIT_PORTS_REQUIRED'}
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($PayloadPath,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'SOURCE_SUCCESSOR_PARSE_FAILED'}
foreach($name in @('Assert-Effective','Assert-Scope','Assert-Qualification')){
    $functions=$ast.FindAll({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name},$true)
    if($functions.Count -ne 1){throw 'EXACT_SUCCESSOR_WRAPPER_NOT_FOUND'}
    . ([scriptblock]::Create($functions[0].Extent.Text))
}
$script:atlasOriginalEffectiveV2=$null
$fixture=New-Fixture 'sync_advance'
$before=$fixture.state.snapshot|ConvertTo-Json -Depth 16|ConvertFrom-Json
$original=& $fixture.ports.QueryEffective
Assert-Effective $original 15 360000
& $fixture.ports.WriteSetting 'MaxPollInterval' 6
& $fixture.ports.WriteSetting 'UpdateInterval' 100
$null=& $fixture.ports.ObserveClock 180
Assert-Scope $fixture.state.snapshot 6 100
Assert-Effective (& $fixture.ports.QueryEffective) 6 100
& $fixture.ports.WriteSetting 'MaxPollInterval' 15
& $fixture.ports.WriteSetting 'UpdateInterval' 360000
$fixture.state.snapshot.configuration_values.LastKnownGoodTime.value+=640000000L
$null=Assert-AtlasTimeTargetReadback $fixture.state.snapshot (& $fixture.ports.QueryEffective)
Assert-Scope $fixture.state.snapshot 15 360000
Assert-Effective (& $fixture.ports.QueryEffective) 15 360000
$nonce='0123456789abcdef0123456789abcdef';$hash=('ab'*32)
$qualificationRows=@()
$qualificationCases=@('valid','zero_bound','bound_999','ack_false','ack_string_false','ack_integer',
 'missing_bound','extra_field','bound_boolean','bound_string','bound_float','bound_negative','bound_1000',
 'domain_fixture','domain_array','source_changed','source_array','nonce_wrong','nonce_array','hash_wrong','hash_array',
 'qpc_future','qpc_stale','qpc_boundary','qpc_string','qpc_boolean','qpc_zero','frequency_zero','frequency_float','now_nan')
foreach($fault in $qualificationCases){
 $decision=@{nonce=$nonce;binding_verified=$true;bound_ms=900;clock_domain='LOCAL_WINDOWS';source='time.windows.com,0x9';observed_qpc=9999000L;evidence_sha256=$hash}
 $now=10000000L;$frequency=1000L
 switch($fault){
  'zero_bound'{$decision.bound_ms=0}
  'bound_999'{$decision.bound_ms=999}
  'ack_false'{$decision.binding_verified=$false}
  'ack_string_false'{$decision.binding_verified='false'}
  'ack_integer'{$decision.binding_verified=1}
  'missing_bound'{$decision.Remove('bound_ms')}
  'extra_field'{$decision.extra='foreign'}
  'bound_boolean'{$decision.bound_ms=$true}
  'bound_string'{$decision.bound_ms='900'}
  'bound_float'{$decision.bound_ms=900.0}
  'bound_negative'{$decision.bound_ms=-1}
  'bound_1000'{$decision.bound_ms=1000}
  'domain_fixture'{$decision.clock_domain='DISPOSABLE_SYNTHETIC'}
  'domain_array'{$decision.clock_domain=@('LOCAL_WINDOWS','LOCAL_WINDOWS')}
  'source_changed'{$decision.source='foreign.invalid'}
  'source_array'{$decision.source=@('time.windows.com,0x9','time.windows.com,0x9')}
  'nonce_wrong'{$decision.nonce=('a'*32)}
  'nonce_array'{$decision.nonce=@($nonce,$nonce)}
  'hash_wrong'{$decision.evidence_sha256=('c'*64)}
  'hash_array'{$decision.evidence_sha256=@($hash,$hash)}
  'qpc_future'{$decision.observed_qpc=$now+1}
  'qpc_stale'{$decision.observed_qpc=9994999L}
  'qpc_boundary'{$decision.observed_qpc=9995000L}
  'qpc_string'{$decision.observed_qpc='9999000'}
  'qpc_boolean'{$decision.observed_qpc=$true}
  'qpc_zero'{$decision.observed_qpc=0L}
  'frequency_zero'{$frequency=0L}
  'frequency_float'{$frequency=1000.0}
  'now_nan'{$now=[double]::NaN}
 }
 $accepted=$false;$errorText=$null
 try{Assert-Qualification $decision $hash $now $frequency;$accepted=$true}catch{$errorText=$_.Exception.Message}
 $qualificationRows+=@{name=$fault;accepted=$accepted;error=$errorText}
}
@{cases=$rows;qualification_cases=$qualificationRows;default_refused=$refused;successor_wrappers_verified=$true;windows_calls=0;administrator_elevations=0;domain='DISPOSABLE_SYNTHETIC'}|
    ConvertTo-Json -Depth 32|Set-Content -LiteralPath $OutputPath -Encoding UTF8
