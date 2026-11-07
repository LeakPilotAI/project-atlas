# Opt-in only. No shortcut installation, engine management, removals or force kills.
#Requires -Version 5.1
[CmdletBinding()]
param([switch]$Complete, [switch]$Json,
      [ValidateRange(1,300)][int]$BackendTimeoutSeconds=45,
      [ValidateRange(1,300)][int]$DockerTimeoutSeconds=60)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
if (-not $Complete) { throw 'Explicit -Complete is required. Backend-only stop remains Atlas-Background.ps1 -Action Stop.' }
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Manager=Join-Path $PSScriptRoot 'Atlas-Background.ps1'
Import-Module (Join-Path $PSScriptRoot 'Atlas-CompleteShutdown.psm1') -Force
$gate=Enter-AtlasLifecycleGate $Root
$receiptPath=Join-Path $Root 'logs\runtime\atlas-complete-shutdown.json'
$operation=[guid]::NewGuid().ToString()
$audit=Join-Path $Root "logs\diagnostics\complete-shutdown\$operation"
$script:commandNumber=0
$script:ownedCli=@()
$script:DockerEndpoint=''

function Save-CompleteReceipt($Value) {
    $record=@{schema_version=1;operation=$operation;root=$Root;at_utc=[datetime]::UtcNow.ToString('o');
              state=$Value.state;backend_state=$Value.backend_state;services=@($Value.services);
              errors=@($Value.errors);pending_ids=@($Value.pending_ids);owned_cli=@($script:ownedCli)}
    $text=$record|ConvertTo-Json -Depth 9
    $version=[guid]::NewGuid().ToString('N')
    $temp="$receiptPath.$operation.$version.tmp"
    $bytes=(New-Object Text.UTF8Encoding($false)).GetBytes($text)
    $stream=[IO.File]::Open($temp,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try { $stream.Write($bytes,0,$bytes.Length);$stream.Flush($true) } finally { $stream.Dispose() }
    if (Test-Path -LiteralPath $receiptPath) {
        [IO.File]::Replace($temp,$receiptPath,(Join-Path $audit "receipt-before-$version.json"))
    } else { [IO.File]::Move($temp,$receiptPath) }
    [IO.File]::WriteAllText((Join-Path $audit 'receipt.json'),$text,(New-Object Text.UTF8Encoding($false)))
}

function Invoke-AtlasDockerCommand([string[]]$Arguments) {
    if ($script:DockerEndpoint) { $Arguments=@('--host',$script:DockerEndpoint)+$Arguments }
    $script:commandNumber++
    $out=Join-Path $audit "$($script:commandNumber).out"
    $err=Join-Path $audit "$($script:commandNumber).err"
    $process=Start-Process -FilePath $script:DockerPath -ArgumentList $Arguments -WindowStyle Hidden `
        -RedirectStandardOutput $out -RedirectStandardError $err -PassThru
    # Windows PowerShell's returned Process must retain its native handle before
    # a quick child exits; otherwise ExitCode may be unavailable after waiting.
    $null=$process.Handle
    $identity=@{pid=$process.Id;created_utc=$process.StartTime.ToUniversalTime().ToString('o');
                executable=$script:DockerPath;arguments=$Arguments;output=$out;error=$err;exited=$false;command_line=''}
    $script:ownedCli += $identity
    if (-not $process.WaitForExit($DockerTimeoutSeconds*1000)) {
        # Never kill a CLI or a container. Durable intent and this exact CLI
        # identity remain in the receipt; startup stays blocked until reconciled.
        $current=Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)" -ErrorAction Stop
        if ($current -and -not $process.HasExited) {
            $identity.created_utc=([datetime]$current.CreationDate).ToUniversalTime().ToString('o')
            $identity.executable=[string]$current.ExecutablePath
            $identity.command_line=[string]$current.CommandLine
        } else { $identity.exited=$true }
        return @{ok=$false;pending=$true;output='';error='Owned Docker CLI deadline exceeded';exit_code=$null}
    }
    $identity.exited=$true
    $process.WaitForExit()
    $exitCode=$process.ExitCode
    if ($null -eq $exitCode) { throw 'Owned Docker CLI exited without a trustworthy exit code.' }
    return @{ok=($exitCode -eq 0);pending=$false;
             output=([IO.File]::ReadAllText($out));error=([IO.File]::ReadAllText($err));exit_code=$exitCode}
}

function Get-CompleteContainer([string]$Target) {
    if ($Target -cnotin @('atlas-postgres','atlas-redis') -and $Target -cnotmatch '^[0-9a-f]{64}$') {
        throw 'Docker inspection target is not an exact Atlas name or full ID.'
    }
    # Only allowlisted metadata, never Config.Env, secrets or global inventories.
    $format='{"Id":{{json .Id}},"Name":{{json .Name}},"Config":{"StopSignal":{{json (index .Config "StopSignal")}},"Labels":{"com.docker.compose.project":{{json (index .Config.Labels "com.docker.compose.project")}},"com.docker.compose.service":{{json (index .Config.Labels "com.docker.compose.service")}},"com.docker.compose.project.working_dir":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},"com.docker.compose.project.config_files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},"com.docker.compose.oneoff":{{json (index .Config.Labels "com.docker.compose.oneoff")}}}},"State":{"Running":{{json .State.Running}},"Status":{{json .State.Status}}}}'
    # ProcessStartInfo on Windows PowerShell joins native arguments. Encode the
    # fixed format's quotes for the native CLI, never interpolate shell code.
    $nativeFormat='"'+$format.Replace('"','\"')+'"'
    $reply=Invoke-AtlasDockerCommand @('inspect','--type','container','--format',$nativeFormat,$Target)
    if (-not $reply.ok) {
        if (-not $reply.pending -and
            ($reply.error.Trim() -ceq "Error: No such object: $Target" -or
             $reply.error.Trim() -ceq "Error response from daemon: No such container: $Target")) { return $null }
        throw 'Docker ownership inspection unavailable; no stopped/absent state can be inferred.'
    }
    return ($reply.output|ConvertFrom-Json -ErrorAction Stop)
}

try {
    $prior=$null
    if (Test-Path -LiteralPath $receiptPath) {
        $prior=Get-Content -LiteralPath $receiptPath -Raw|ConvertFrom-Json -ErrorAction Stop
        if ($prior.schema_version -ne 1 -or $prior.root -ine $Root -or
            $prior.state -cnotin @('COMPLETE','BLOCKED','INCOMPLETE','IN_PROGRESS')) { throw 'Invalid existing complete-shutdown receipt; preserved without overwrite.' }
        if ($prior.state -ceq 'COMPLETE') { Assert-AtlasCompleteReceipt $Root }
        Assert-AtlasPriorCliExited $prior
    }
    New-Item -ItemType Directory -Force $audit | Out-Null
    New-Item -ItemType Directory -Force (Split-Path $receiptPath -Parent) | Out-Null
    if ($prior) { Copy-Item -LiteralPath $receiptPath -Destination (Join-Path $audit 'prior-receipt.json') }
    $script:DockerPath=(Get-Command docker.exe -CommandType Application -ErrorAction Stop).Source
    $context=Invoke-AtlasDockerCommand @('context','inspect','--format','{{.Endpoints.docker.Host}}')
    if (-not $context.ok) { throw 'Docker local context could not be independently verified.' }
    $script:DockerEndpoint=Confirm-AtlasLocalDockerEndpoint $context.output
    $backendStatus={ (& $Manager -Action Status -Json)|ConvertFrom-Json -ErrorAction Stop }
    $backendStop={param($Expected) (& $Manager -Action Stop -ExpectedRunId $Expected -Json)|ConvertFrom-Json -ErrorAction Stop }
    $inspect={param($Target) Get-CompleteContainer $Target}
    $stop={param($Id)
        $reply=Invoke-AtlasDockerCommand @('stop','--time','-1',$Id)
        # An unsuccessful stop CLI does not prove the daemon ignored its request.
        if (-not $reply.ok) { $reply.pending=$true }
        return $reply
    }
    $result=Invoke-AtlasCompleteShutdownPolicy -Root $Root -BackendStatus $backendStatus -BackendStop $backendStop `
        -Inspect $inspect -ContainerStop $stop -BackendTimeoutSeconds $BackendTimeoutSeconds -PriorReceipt $prior `
        -Observe {param($Value) Save-CompleteReceipt $Value}
    if ($Json) { $result|ConvertTo-Json -Depth 8 -Compress }
    else { Write-Output ("{0}: backend={1}; dependency states in {2}" -f $result.state,$result.backend_state,$receiptPath) }
    if ($result.state -cne 'COMPLETE') { throw "Complete Atlas Shutdown is $($result.state); inspect the preserved receipt. No force termination was attempted." }
} catch {
    if ((Test-Path -LiteralPath $audit) -and -not (Get-Variable result -Scope Script -ErrorAction SilentlyContinue)) {
        $fallback=@{state='BLOCKED';backend_state='UNKNOWN';services=@();pending_ids=@();errors=@($_.Exception.Message)}
        if ($prior) { $fallback.services=@($prior.services);$fallback.pending_ids=@($prior.pending_ids) }
        Save-CompleteReceipt $fallback
    }
    throw
} finally { Exit-AtlasLifecycleGate $gate }
