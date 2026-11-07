# Shared coordination and pure shutdown policy. Importing performs no lifecycle action.
#Requires -Version 5.1
Set-StrictMode -Version Latest

function Enter-AtlasLifecycleGate([string]$Root) {
    $canonical = [IO.Path]::GetFullPath($Root).TrimEnd('\').ToLowerInvariant()
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $key = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonical)))).Replace('-','') }
    finally { $sha.Dispose() }
    $mutex = New-Object Threading.Mutex($false, "Global\Atlas-Lifecycle-$key")
    try {
        try { $owned = $mutex.WaitOne(0) }
        catch [Threading.AbandonedMutexException] {
            $mutex.ReleaseMutex()
            throw 'Abandoned Atlas lifecycle gate; verify ownership and receipts before retrying.'
        }
        if (-not $owned) { throw 'Another Atlas lifecycle controller owns the exclusive gate.' }
        return $mutex
    } catch { $mutex.Dispose(); throw }
}

function Exit-AtlasLifecycleGate($Gate) {
    if ($null -ne $Gate) {
        try { $Gate.ReleaseMutex() } finally { $Gate.Dispose() }
    }
}

function Confirm-AtlasLocalDockerEndpoint([string]$Endpoint) {
    $endpointValue=$Endpoint.Trim()
    if ($endpointValue -cnotin @('npipe:////./pipe/dockerDesktopLinuxEngine','npipe:////./pipe/docker_engine')) {
        throw 'Only a verified local Docker Desktop named-pipe endpoint is allowed; remote/ambiguous contexts are refused.'
    }
    if ($env:DOCKER_HOST -and $env:DOCKER_HOST -cne $endpointValue) {
        throw 'DOCKER_HOST conflicts with the selected local context; no Docker operation is authorized.'
    }
    return $endpointValue
}

function Get-AtlasLocalDockerEndpoint {
    $endpoint=& docker context inspect --format '{{.Endpoints.docker.Host}}' 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Docker context endpoint could not be verified.' }
    return Confirm-AtlasLocalDockerEndpoint ([string]$endpoint)
}

function Assert-AtlasCompleteReceipt([string]$Root) {
    $path = Join-Path $Root 'logs\runtime\atlas-complete-shutdown.json'
    if (Test-Path -LiteralPath $path) {
        $receipt = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json -ErrorAction Stop
        if ($receipt.schema_version -ne 1 -or $receipt.root -ine $Root -or
            $receipt.state -cne 'COMPLETE' -or $receipt.backend_state -cne 'STOPPED' -or
            $receipt.pending_ids.Count -ne 0 -or $receipt.services.Count -ne 2) {
            throw 'An incomplete/ambiguous Complete Shutdown receipt blocks startup; inspect and reconcile it without deletion.'
        }
        $names=@($receipt.services|ForEach-Object {$_.name}|Sort-Object -Unique)
        if ($names.Count -ne 2 -or 'atlas-postgres' -cnotin $names -or 'atlas-redis' -cnotin $names) { throw 'Invalid dependency receipt.' }
        foreach ($row in @($receipt.services)) {
            if ($row.state -cnotin @('ABSENT','exited','created') -or
                ($row.state -ceq 'ABSENT' -and $row.id) -or
                ($row.state -cne 'ABSENT' -and $row.id -cnotmatch '^[0-9a-f]{64}$')) { throw 'Contradictory dependency receipt.' }
        }
        foreach ($cli in @($receipt.owned_cli)) {
            if ($cli.exited -isnot [bool] -or $cli.exited -ne $true) { throw 'Receipt retains malformed or unconfirmed Docker CLI evidence.' }
        }
    }
}

function Assert-AtlasPriorCliExited($Receipt, [scriptblock]$Lookup = {
    param($Id)
    $process=Get-CimInstance Win32_Process -Filter "ProcessId=$Id" -Property ProcessId,CreationDate -ErrorAction Stop
    if ($process) { return @{created_utc=([datetime]$process.CreationDate).ToUniversalTime().ToString('o')} }
}) {
    if (-not $Receipt -or $Receipt.state -ceq 'COMPLETE') { return }
    foreach ($cli in @($Receipt.owned_cli)) {
        if ($cli.exited -isnot [bool]) { throw 'Prior Docker CLI exit evidence is malformed.' }
        if ($cli.exited -eq $true) { continue }
        if ([int]$cli.pid -le 4 -or -not $cli.created_utc -or -not $cli.executable -or -not $cli.command_line) {
            throw 'Prior Docker CLI identity is incomplete; operator reconciliation required.'
        }
        $current=& $Lookup ([int]$cli.pid)
        if ($current -and $current.created_utc -ceq $cli.created_utc) {
            throw 'A prior Docker CLI remains active or ambiguous; no stop replay or startup is allowed.'
        }
    }
}

function ConvertTo-AtlasShutdownIdentity($Container, [string]$Name, [string]$Service, [string]$Root) {
    if ($null -eq $Container) { return $null }
    $labels = $Container.Config.Labels
    $project = [string]$labels.'com.docker.compose.project'
    $directory = [string]$labels.'com.docker.compose.project.working_dir'
    $config = [string]$labels.'com.docker.compose.project.config_files'
    $oneoff = [string]$labels.'com.docker.compose.oneoff'
    $hasStopSignal = if ($Container.Config -is [System.Collections.IDictionary]) {
        $Container.Config.Contains('StopSignal')
    } else { $null -ne $Container.Config.PSObject.Properties['StopSignal'] }
    $rawStopSignal = $null
    if ($hasStopSignal) { $rawStopSignal = $Container.Config.StopSignal }
    if ($null -ne $rawStopSignal -and $rawStopSignal -isnot [string]) {
        throw "Malformed optional Docker StopSignal for $Name; refusing dependency ownership."
    }
    $stopSignal = [string]$rawStopSignal
    if ($Name -cnotin @('atlas-postgres','atlas-redis') -or
        $Service -cnotin @('postgres','redis') -or
        [string]$Container.Name -cne "/$Name" -or
        [string]$Container.Id -cnotmatch '^[0-9a-f]{64}$' -or
        $project -cnotin @('atlas','projectatlas') -or
        [string]$labels.'com.docker.compose.service' -cne $Service -or
        $directory -ine $Root -or $config -ine (Join-Path $Root 'docker-compose.yml') -or
        $oneoff -ine 'False' -or $Container.State.Running -isnot [bool] -or
        $stopSignal -cnotin @('','SIGTERM','SIGINT','15','2') -or
        [string]$Container.State.Status -cnotin @('running','exited','created') -or
        ([bool]$Container.State.Running -ne ([string]$Container.State.Status -ceq 'running'))) {
        throw "Ambiguous/non-Atlas Compose identity for $Name; no dependency stop is authorized."
    }
    return @{name=$Name; service=$Service; id=[string]$Container.Id; project=$project;
             running=[bool]$Container.State.Running; status=[string]$Container.State.Status}
}

function Get-AtlasShutdownInventory([scriptblock]$Inspect, [string]$Root) {
    $items = @()
    foreach ($pair in @(@('atlas-postgres','postgres'),@('atlas-redis','redis'))) {
        $raw = & $Inspect $pair[0]
        $item = ConvertTo-AtlasShutdownIdentity $raw $pair[0] $pair[1] $Root
        $items += ,@{name=$pair[0]; service=$pair[1]; identity=$item}
    }
    $projects = @($items | Where-Object {$null -ne $_.identity} | ForEach-Object {$_.identity.project} | Sort-Object -Unique)
    if ($projects.Count -gt 1) { throw 'Atlas dependency Compose projects conflict; refusing all dependency stops.' }
    return ,$items
}

function Invoke-AtlasCompleteShutdownPolicy(
    [string]$Root, [scriptblock]$BackendStatus, [scriptblock]$BackendStop,
    [scriptblock]$Inspect, [scriptblock]$ContainerStop,
    [scriptblock]$Pause = { Start-Sleep -Milliseconds 500 },
    [scriptblock]$Clock = { [Diagnostics.Stopwatch]::GetTimestamp() / [double][Diagnostics.Stopwatch]::Frequency },
    [double]$BackendTimeoutSeconds = 45, $PriorReceipt = $null,
    [scriptblock]$Observe = { param($Value) }
) {
    $result = @{state='BLOCKED'; backend_state='UNKNOWN'; services=@(); errors=@(); pending_ids=@()}
    try {
        $state = & $BackendStatus
        $result.backend_state = [string]$state.state
        if ($state.state -cnotin @('running','stopping','STOPPED')) {
            throw 'Backend ownership is ambiguous before dependency inspection.'
        }
        $initialBackendState=[string]$state.state
        $initialRun=if ($initialBackendState -ceq 'STOPPED') { '' } else { [string]$state.run_id }
        if ($initialBackendState -cne 'STOPPED') {
            $initialGuid=[guid]::Empty
            if (-not [guid]::TryParse($initialRun,[ref]$initialGuid)) { throw 'Initial backend run identity is missing.' }
        }
        if ($PriorReceipt -and $PriorReceipt.state -cne 'COMPLETE') {
            $result.pending_ids = @($PriorReceipt.pending_ids)
            $result.services = @($PriorReceipt.services)
            foreach ($pending in $result.pending_ids) {
                if ([string]$pending -cnotmatch '^[0-9a-f]{64}$' -or
                    $pending -cnotin @($PriorReceipt.services | ForEach-Object {$_.id})) {
                    throw 'Prior uncertain stop intent has no trustworthy dependency identity.'
                }
            }
        }
        # Validate the entire pair before requesting even a backend stop.
        $inventory = Get-AtlasShutdownInventory $Inspect $Root
        if ($PriorReceipt) {
            if ($PriorReceipt.root -ine $Root) { throw 'Prior receipt root conflicts.' }
            foreach ($old in @($PriorReceipt.services)) {
                if ($old.id) {
                    $now = @($inventory | Where-Object {$_.name -ceq $old.name})
                    if ($now.Count -ne 1 -or $null -eq $now[0].identity -or $now[0].identity.id -cne $old.id) {
                        throw 'A prior dependency identity changed; operator reconciliation required.'
                    }
                }
            }
        }
        $result.services = @($inventory | ForEach-Object {
            if ($null -eq $_.identity) { @{name=$_.name;id='';state='ABSENT';verification='PREFLIGHT'} }
            else { @{name=$_.name;id=$_.identity.id;state=$_.identity.status;verification='PREFLIGHT'} }
        })
        & $Observe $result
        $state = & $BackendStatus
        $result.backend_state = [string]$state.state
        if ($state.state -cne 'STOPPED' -and
            ($initialBackendState -ceq 'STOPPED' -or [string]$state.run_id -cne $initialRun)) {
            throw 'Backend session changed during dependency preflight; refusing stop.'
        }
        $expectedRun = ''
        if ($state.state -cin @('running','stopping')) {
            $expectedRun = [string]$state.run_id
            $guid = [guid]::Empty
            if (-not [guid]::TryParse($expectedRun,[ref]$guid)) { throw 'Backend run identity is missing.' }
            if ($state.state -ceq 'running') {
                $ack = & $BackendStop $expectedRun
                if ($ack.state -cne 'stopping' -or [string]$ack.run_id -cne $expectedRun) {
                    throw 'Backend stop acknowledgement does not match the verified run.'
                }
            }
        } elseif ($state.state -cne 'STOPPED') { throw 'Backend state is ambiguous; dependency stop refused.' }
        $deadline = (& $Clock) + $BackendTimeoutSeconds
        while ($state.state -cne 'STOPPED') {
            if ((& $Clock) -ge $deadline) { throw 'Backend stop deadline exceeded; dependencies left untouched.' }
            & $Pause
            $state = & $BackendStatus
            $result.backend_state = [string]$state.state
            if ($state.state -cne 'STOPPED' -and
                ($state.state -cne 'stopping' -or [string]$state.run_id -cne $expectedRun)) {
                throw 'Backend ownership changed or became ambiguous; dependency stop refused.'
            }
        }
        $result.backend_state = 'STOPPED'
        # Revalidate all identities after backend exit, then by immutable ID before each stop.
        $fresh = Get-AtlasShutdownInventory $Inspect $Root
        for ($i=0; $i -lt $inventory.Count; $i++) {
            $before = $inventory[$i].identity; $after = $fresh[$i].identity
            if (($null -eq $before) -ne ($null -eq $after) -or
                ($before -and $before.id -cne $after.id)) { throw 'Dependency identity changed during backend drain.' }
        }
        foreach ($entry in $fresh) {
            if ($null -eq $entry.identity) {
                foreach ($row in $result.services) { if ($row.name -ceq $entry.name) { $row.verification='POST_BACKEND' } }
                continue
            }
            if ((& $BackendStatus).state -cne 'STOPPED') { throw 'Backend is no longer verified stopped.' }
            $current = ConvertTo-AtlasShutdownIdentity (& $Inspect $entry.identity.id) $entry.name $entry.service $Root
            if (-not $current -or $current.id -cne $entry.identity.id) { throw 'Dependency ID changed before stop.' }
            $outcome = @{ok=$true;pending=$false}
            if ($current.running) {
                if ($PriorReceipt -and $current.id -cin @($PriorReceipt.pending_ids)) {
                    $outcome = @{ok=$false;pending=$true}
                } else {
                    # Durable intent precedes the Docker request; an interrupted
                    # controller must not automatically replay an uncertain stop.
                    $result.pending_ids += $current.id
                    & $Observe $result
                    $outcome = & $ContainerStop $current.id
                    # A CLI acknowledgement alone is not final container-exit
                    # evidence. Keep the intent until exact-ID inspection proves exit.
                }
            }
            $final = ConvertTo-AtlasShutdownIdentity (& $Inspect $current.id) $entry.name $entry.service $Root
            if (-not $final -or $final.id -cne $current.id) { throw 'Final dependency identity could not be verified.' }
            foreach ($row in $result.services) { if ($row.name -ceq $entry.name) { $row.state=$final.status;$row.verification='FINAL' } }
            if (-not $outcome.ok -or $final.running) { $result.errors += "Dependency $($entry.name) is not confirmed stopped." }
            if ($outcome.pending -and $final.running -and $current.id -cnotin $result.pending_ids) { $result.pending_ids += $current.id }
            if (-not $final.running) { $result.pending_ids = @($result.pending_ids | Where-Object {$_ -cne $current.id}) }
            & $Observe $result
        }
        # Earlier observations can become stale while the second service drains.
        # Reinspect the entire pair and reject additions/replacements/restarts.
        $finalInventory = Get-AtlasShutdownInventory $Inspect $Root
        for ($i=0; $i -lt $fresh.Count; $i++) {
            $before=$fresh[$i].identity; $after=$finalInventory[$i].identity
            if (($null -eq $before) -ne ($null -eq $after) -or
                ($before -and $before.id -cne $after.id)) { throw 'Dependency identity changed during final verification.' }
            foreach ($row in $result.services) {
                if ($row.name -ceq $finalInventory[$i].name) {
                    $row.state=if ($after) { $after.status } else { 'ABSENT' }
                    $row.verification='FINAL'
                }
            }
            if ($after -and $after.running) { $result.errors += "Dependency $($after.name) is running at final verification." }
        }
        $finalBackend=& $BackendStatus
        $result.backend_state=[string]$finalBackend.state
        if ($finalBackend.state -cne 'STOPPED') { throw 'Final backend stop verification failed.' }
        if (-not $result.errors.Count -and -not $result.pending_ids.Count) { $result.state='COMPLETE' }
        else { $result.state='INCOMPLETE' }
    } catch { $result.errors += $_.Exception.Message; $result.state='BLOCKED' }
    & $Observe $result
    return $result
}

Export-ModuleMember -Function Enter-AtlasLifecycleGate,Exit-AtlasLifecycleGate,Confirm-AtlasLocalDockerEndpoint,Get-AtlasLocalDockerEndpoint,Assert-AtlasCompleteReceipt,Assert-AtlasPriorCliExited,ConvertTo-AtlasShutdownIdentity,Get-AtlasShutdownInventory,Invoke-AtlasCompleteShutdownPolicy
