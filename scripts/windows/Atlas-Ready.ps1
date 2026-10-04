# Operator startup gate. Warm-up is never reported as a steady-state pass.
param([string]$Root, [int]$TimeoutSeconds = 180)
$ErrorActionPreference = 'Stop'
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$result = @{ green=$false; checks=0; failed_checks=0; consecutive_green=0; required=3 }
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
    $result.checks++
    if ($allHealthy) { $result.consecutive_green++ }
    else { $result.failed_checks++; $result.consecutive_green=0; $result.last_failure=$checks }
    Write-Host "Startup stabilization: $($result.consecutive_green)/3 healthy checks"
    if ($result.consecutive_green -ge 3) { $result.green=$true; break }
    Start-Sleep -Seconds 5
} while ((Get-Date) -lt $deadline)
$directory = Join-Path $Root 'logs\diagnostics'
New-Item -ItemType Directory -Force $directory | Out-Null
$result | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $directory 'launcher-ready.json') -Encoding UTF8
if (-not $result.green) { Write-Host 'Atlas startup did not stabilize; inspect logs\diagnostics\launcher-ready.json'; exit 2 }
