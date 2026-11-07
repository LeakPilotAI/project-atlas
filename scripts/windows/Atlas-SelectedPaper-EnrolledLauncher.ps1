# Explicitly loaded source interface only. No default child/issuer/enrollment.
param([switch]$SourceLoadOnly)

function New-AtlasEnrolledReadBridge {
    param([object]$AcceptedPlan=$null,[scriptblock]$Authorize=$null,
          [scriptblock]$TrustedClock=$null,[scriptblock]$AcceptedChildFactory=$null)
    if($null -eq $AcceptedPlan -or $null -eq $Authorize -or $null -eq $TrustedClock -or $null -eq $AcceptedChildFactory){
        throw 'ENROLLED_LAUNCH_DEPENDENCIES_REQUIRED'
    }
    $plan=$AcceptedPlan | ConvertTo-Json -Depth 12 -Compress | ConvertFrom-Json
    $keys=@('schema','operation_id','account_id','epoch','enrollment_digest','policy_digest','release_digest','executable','publication_digest','issued_at','expires_at','capabilities')
    if((($plan.PSObject.Properties.Name|Sort-Object)-join ',') -cne (($keys|Sort-Object)-join ',') -or
        $plan.schema -cne 'QD_OP_ENROLLED_LAUNCH_PLAN_V1' -or
        ($plan.capabilities -join ',') -cne 'READ_ONLY') {throw 'ENROLLED_PLAN_SCHEMA_REFUSED'}
    foreach($key in @('enrollment_digest','policy_digest','release_digest','publication_digest')){
        if($plan.$key -cnotmatch '^[a-f0-9]{64}$'){throw 'ENROLLED_PLAN_BINDING_REFUSED'}
    }
    if($plan.operation_id -cnotmatch '^qd-enrollment:[a-f0-9]{64}$' -or
        $plan.account_id -isnot [string] -or [string]::IsNullOrWhiteSpace($plan.account_id) -or
        $plan.epoch -isnot [string] -or [string]::IsNullOrWhiteSpace($plan.epoch) -or
        $plan.executable -isnot [string] -or $plan.executable -cnotmatch '^[A-Za-z]:\\[^%\x00]*\.exe$' -or
        $plan.executable.Substring(2).Contains(':') -or $plan.executable.Split('\').Contains('..')){
        throw 'ENROLLED_PLAN_IDENTITY_REFUSED'
    }
    $check = {
        param([string]$Phase,$Context)
        $now=& $TrustedClock
        if(($now -isnot [int] -and $now -isnot [long]) -or
            ($plan.issued_at -isnot [int] -and $plan.issued_at -isnot [long]) -or
            ($plan.expires_at -isnot [int] -and $plan.expires_at -isnot [long]) -or
            $now -le 0 -or $plan.issued_at -le 0 -or $now -lt $plan.issued_at -or $now -gt $plan.expires_at -or $plan.expires_at -gt ($plan.issued_at+30)){
            throw 'ENROLLED_PLAN_CLOCK_OR_FRESHNESS_REFUSED'
        }
        $copy=$plan | ConvertTo-Json -Depth 12 -Compress | ConvertFrom-Json
        $allowed=& $Authorize $Phase $copy $Context $now
        if($allowed -isnot [bool] -or -not $allowed){throw 'INDEPENDENT_ENROLLED_LAUNCH_AUTHORITY_REQUIRED'}
    }.GetNewClosure()
    & $check 'PREPARE' $null  # Before importing bridge or invoking child factory.
    Import-Module (Join-Path $PSScriptRoot 'Atlas-SelectedPaper-Bridge.psm1') -Force
    $owned=$null;$nativeVerified=$false
    try {
        # Factory is explicitly trusted/injected; no default Start-Process,
        # executable/env/file resolution, provider or protected worker exists.
        $copy=$plan | ConvertTo-Json -Depth 12 -Compress | ConvertFrom-Json
        $child=& $AcceptedChildFactory $copy
        $owned=$child.Process;$context=$child.Context
        if($owned -isnot [System.Diagnostics.Process] -or $owned.HasExited -or
            $context.schema -cne 'QD_OP_BRIDGE_CONTEXT_V1' -or
            $context.account_id -cne $plan.account_id -or $context.epoch -cne $plan.epoch -or
            $context.enrollment_digest -cne $plan.enrollment_digest -or
            $context.process.pid -ne $owned.Id -or
            $context.process.creation_filetime -ne $owned.StartTime.ToUniversalTime().ToFileTimeUtc() -or
            $context.process.image -cne $owned.MainModule.FileName -or
            $context.process.image -cne $plan.executable){throw 'ENROLLED_CHILD_IDENTITY_OR_SCOPE_REFUSED'}
        $nativeVerified=$true
        & $check 'RETAIN' $context
        $authorizeRead = {param($candidate) & $check 'READ' $candidate;return $true}.GetNewClosure()
        return New-AtlasSelectedReadBridge -OwnedProcess $owned -ExpectedContext $context -Authorize $authorizeRead
    } catch {
        $failure=$_
        # Only a verified exact owned child may receive graceful EOF. Ambiguous
        # identity is retained on the error for the accepted owner to reconcile.
        if($nativeVerified -and -not $owned.HasExited){
            try {
                $owned.StandardInput.Close()
                if(-not $owned.WaitForExit(12000)){throw 'ENROLLED_CHILD_EXIT_UNCONFIRMED_NO_FORCED_TERMINATION'}
            } catch {
                $failure.Exception.Data['RetainedOwnedProcess']=$owned
                $failure.Exception.Data['ShutdownFailure']=$_.Exception.Message
            }
        } elseif($null -ne $owned){$failure.Exception.Data['RetainedUnverifiedProcess']=$owned}
        throw $failure
    }
}

if(-not $SourceLoadOnly){
    throw 'REFUSED: enrolled launcher is not installed. Explicit accepted dependencies and separate launch permission required.'
}
