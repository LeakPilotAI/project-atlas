$ErrorActionPreference='Stop'
$out=Split-Path -Parent $MyInvocation.MyCommand.Path
$result=[ordered]@{utc=[DateTime]::UtcNow.ToString('o');accepted=$false;operational_mutations=0}
try {
    $service=Get-CimInstance Win32_Service -Filter "Name='W32Time'"
    $parameters=Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Services\W32Time\Parameters'
    $result.clock_configuration=@{service=$service.State;startup=$service.StartMode;source=$parameters.NtpServer;type=$parameters.Type}
    if($service.State -ne 'Running' -or $service.StartMode -ne 'Auto' -or $parameters.NtpServer -ne 'time.windows.com,0x9' -or $parameters.Type -ne 'NTP'){throw 'CLOCK_CONFIGURATION_OR_SERVICE_CHANGED'}
    $desktop=[Environment]::GetFolderPath('Desktop')
    $shell=New-Object -ComObject WScript.Shell
    $links=@()
    try {
        foreach($name in @('Project Atlas.lnk','Stop Atlas.lnk')) {
            $path=Join-Path $desktop $name
            if(-not (Test-Path -LiteralPath $path -PathType Leaf)){throw ('DESKTOP_REFERENCE_MISSING:'+ $name)}
            $before=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
            # Existing-file metadata only. Never call Save or execute a target.
            $link=$shell.CreateShortcut($path)
            try {$links+=@{name=$name;sha256=$before;target=$link.TargetPath;arguments=$link.Arguments;working_directory=$link.WorkingDirectory}}
            finally {[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($link)}
            if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $before){throw 'DESKTOP_REFERENCE_CHANGED_DURING_READ'}
        }
    } finally {[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)}
    $result.desktop_references=$links
    $baseline=Get-Content -LiteralPath 'D:\Work\Project Atlas\logs\diagnostics\qd-exact-promotion-preflight-v1-20261030\result.json' -Raw | ConvertFrom-Json
    foreach($reference in $links){
        $prior=@($baseline.desktop_references|Where-Object {$_.name -ceq $reference.name})
        if($prior.Count -ne 1 -or $reference.sha256 -ine $prior[0].sha256 -or $reference.target -ine $prior[0].target -or $reference.arguments -cne $prior[0].arguments -or $reference.working_directory -ine $prior[0].workingDirectory){throw 'DESKTOP_BASELINE_CHANGED_REVIEW_REQUIRED'}
    }
    $filter="ExecutablePath LIKE 'D:\\AtlasRuntime\\%' OR ExecutablePath LIKE 'D:\\Work\\Project Atlas\\%' OR (Name='python.exe' AND CommandLine LIKE '%D:\\Work\\Project Atlas%')"
    $rich=ConvertFrom-Json -InputObject $env:ATLAS_V5_RICH_CLAIMS
    if($rich -isnot [array] -or $rich.Count -lt 2 -or $rich.Count -gt 8){throw 'V5_RICH_RETAINED_CLAIMS_REQUIRED'}
    $seen=@{}
    foreach($v in $rich){
        if((($v.PSObject.Properties.Name|Sort-Object)-join ',') -cne 'command_line,created,image,parent_pid,pid' -or ($v.pid -isnot [int] -and $v.pid -isnot [long]) -or ($v.parent_pid -isnot [int] -and $v.parent_pid -isnot [long]) -or $v.pid -le 4 -or $v.parent_pid -le 0 -or $v.command_line -isnot [string] -or [string]::IsNullOrWhiteSpace($v.command_line) -or $seen.ContainsKey([string]$v.pid)){throw 'V5_RICH_CLAIM_SHAPE_OR_DUPLICATE'}
        $seen[[string]$v.pid]=$v
        $filter+=' OR ProcessId='+[string]$v.pid
    }
    $processes=@(Get-CimInstance Win32_Process -Filter $filter)
    foreach($v in $rich){if(@($processes|Where-Object {$_.ProcessId -eq $v.pid}).Count -ne 1){throw 'V5_REQUIRED_ROLE_NOT_OBSERVED'}}
    # Windows PowerShell 5.1 emits a JSON array as one pipeline object.
    # Deserialize first; enumerate the resulting array in a separate step.
    $parsedClaims=ConvertFrom-Json -InputObject $env:ATLAS_AUTH_HELPER_CLAIMS
    if($null -eq $parsedClaims -or $parsedClaims -isnot [System.Array]){throw 'DIAGNOSTIC_HELPER_CLAIMS_ARRAY_REQUIRED'}
    $claims=@($parsedClaims)
    if($claims.Count -ne $rich.Count){throw 'V5_CLASSIC_RICH_ROSTER_COUNT_MISMATCH'}
    $classicSeen=@{}
    foreach($v in $claims){
        $context=$seen[[string]$v.pid]
        if($null -eq $context -or $classicSeen.ContainsKey([string]$v.pid) -or $v.created -ne $context.created -or $v.image -ine $context.image){throw 'V5_CLASSIC_RICH_IDENTITY_MISMATCH'}
        $classicSeen[[string]$v.pid]=$true
    }
    if($claims.Count -eq 0){throw 'DIAGNOSTIC_HELPER_CLAIMS_EMPTY'}
    foreach($identity in $claims){
        if($null -eq $identity -or $identity -is [System.Array] -or
            (($identity.PSObject.Properties.Name|Sort-Object)-join ',') -cne 'created,image,pid' -or
            ($identity.pid -isnot [int] -and $identity.pid -isnot [long]) -or
            $identity.pid -le 0 -or $identity.pid -gt [uint32]::MaxValue -or
            ($identity.created -isnot [int] -and $identity.created -isnot [long]) -or
            $identity.created -le 0 -or $identity.image -isnot [string] -or
            [string]::IsNullOrWhiteSpace($identity.image)){throw 'DIAGNOSTIC_HELPER_CLAIM_FIELD_TYPE'}
    }
    $others=@()
    foreach($candidate in $processes){
        $claim=@($claims|Where-Object {$_.pid -eq $candidate.ProcessId})
        if($claim.Count -ge 1){
            $context=$seen[[string]$candidate.ProcessId]
            if($null -eq $context -or $candidate.CommandLine -cne $context.command_line -or $candidate.ParentProcessId -ne $context.parent_pid){throw 'V5_COMMAND_OR_PARENT_MISMATCH'}
            $live=[Diagnostics.Process]::GetProcessById($candidate.ProcessId)
            try {
                foreach($identity in $claim){
                    # Preserve scalar comparison evidence privately before any refusal.
                    $observedCreated=$live.StartTime.ToUniversalTime().ToFileTimeUtc()
                    $observedImage=$live.MainModule.FileName
                    if(-not $result.Contains('helper_identity_comparisons')){$result.helper_identity_comparisons=@()}
                    $result.helper_identity_comparisons+=@{expected_pid=$identity.pid;observed_pid=$live.Id;expected_created=$identity.created.ToString();observed_created=$observedCreated.ToString();expected_image=$identity.image;observed_image=$observedImage;pid_equal=($live.Id -eq $identity.pid);created_equal=($observedCreated -eq $identity.created);image_equal=($observedImage -ieq $identity.image)}
                    if($live.StartTime.ToUniversalTime().ToFileTimeUtc() -ne $identity.created -or $live.MainModule.FileName -ine $identity.image){throw 'DIAGNOSTIC_HELPER_OWNERSHIP_MISMATCH'}
                }
            } finally {$live.Dispose()}
        }else{$others+=,$candidate}
    }
    $result.verified_diagnostic_helper_claims=$claims
    $processes=$others
    $result.atlas_python_processes=@($processes|Select-Object ProcessId,ExecutablePath,CommandLine,CreationDate)
    if($processes.Count -ne 0){throw 'EXISTING_ATLAS_PROCESS_REQUIRES_OWNERSHIP_REVIEW'}
    $result.accepted=$true
} catch {$result.error=$_.Exception.ToString()}
$json=$result|ConvertTo-Json -Depth 8
[IO.File]::WriteAllText((Join-Path $out 'metadata-preflight-result.json'),$json,[Text.UTF8Encoding]::new($false))
[ordered]@{accepted=$result.accepted;clock_configuration=$result.clock_configuration;desktop_references_read=@($result.desktop_references).Count;atlas_processes=$(if($result.Contains('atlas_python_processes')){@($result.atlas_python_processes).Count}else{$null});error=$result.error}|ConvertTo-Json -Depth 4
if(-not $result.accepted){exit 2}
