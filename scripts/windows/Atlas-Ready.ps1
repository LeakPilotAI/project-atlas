# Operator startup gate. Warm-up is never reported as a steady-state pass.
# Read-only readiness verification: never starts/stops/removes containers or processes.
param([string]$Root, [int]$TimeoutSeconds = 180)
$ErrorActionPreference = 'Stop'
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$result = @{
    green=$false
    checks=0
    failed_checks=0
    consecutive_green=0
    required=3
    recovery='Run ATLAS-STOP.bat, inspect logs and Docker Desktop, then relaunch Project Atlas. This readiness check does not mutate runtime state.'
}

function Get-AtlasContainerHealth {
    $states = @{}
    foreach ($name in @('atlas-postgres', 'atlas-redis')) {
        try {
            $raw = & docker inspect -f '{{.State.Running}}|{{.State.Health.Status}}' $name 2>$null
            if ($LASTEXITCODE -eq 0 -and $raw) {
                $parts = ([string]$raw).Trim().Split('|')
                $states[$name] = @{
                    running = ($parts.Count -ge 1 -and $parts[0] -eq 'true')
                    health = if ($parts.Count -ge 2) { $parts[1] } else { 'unknown' }
                }
            } else {
                $states[$name] = @{ running=$false; health='missing' }
            }
        } catch {
            $states[$name] = @{ running=$false; health='unavailable' }
        }
    }
    return $states
}

do {
    $allHealthy = $true
    $checks = @{}
    foreach ($path in @('/health', '/api/research', '/api/command-center/summary', '/diagnostics/paper-reconciliation')) {
        try {
            $response = Invoke-WebRequest ("http://127.0.0.1:8000" + $path) -UseBasicParsing -TimeoutSec 5
            $checks[$path] = ($response.StatusCode -eq 200)
        } catch { $checks[$path] = $false }
        $allHealthy = $allHealthy -and $checks[$path]
    }
    $containers = Get-AtlasContainerHealth
    $checks['atlas-postgres'] = [bool]($containers['atlas-postgres'].running -and $containers['atlas-postgres'].health -eq 'healthy')
    $checks['atlas-redis'] = [bool]($containers['atlas-redis'].running -and $containers['atlas-redis'].health -eq 'healthy')
    $allHealthy = $allHealthy -and $checks['atlas-postgres'] -and $checks['atlas-redis']
    $result.checks++
    $result.last_checks = $checks
    $result.container_health = $containers
    if ($allHealthy) { $result.consecutive_green++ }
    else { $result.failed_checks++; $result.consecutive_green=0; $result.last_failure=$checks }
    Write-Host "Startup stabilization: $($result.consecutive_green)/3 healthy checks"
    if ($result.consecutive_green -ge 3) { $result.green=$true; break }
    Start-Sleep -Seconds 5
} while ((Get-Date) -lt $deadline)

$directory = Join-Path $Root 'logs\diagnostics'
New-Item -ItemType Directory -Force $directory | Out-Null
$artifact = Join-Path $directory 'launcher-ready.json'
$result | ConvertTo-Json -Depth 6 | Set-Content $artifact -Encoding UTF8
if (-not $result.green) {
    Write-Host "Atlas startup did not stabilize; inspect $artifact" -ForegroundColor Red
    Write-Host $result.recovery -ForegroundColor Yellow
    exit 2
}
