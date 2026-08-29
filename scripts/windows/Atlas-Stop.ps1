# Stop Atlas API, frontend, compose stack, and (by default) Docker Desktop.
param(
    [string]$Root = "",
    [int[]]$ChildPids = @(),
    [switch]$KeepDockerDesktop
)

$ErrorActionPreference = "Continue"
if (-not $Root) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}
Set-Location $Root

function Stop-Tree([int]$ProcessId) {
    if ($ProcessId -le 0) { return }
    & taskkill.exe /F /PID $ProcessId /T 2>$null | Out-Null
}

function Stop-ListenPort([int]$Port) {
    $out = & netstat.exe -ano 2>$null | Select-String ":$Port\s+.*LISTENING"
    foreach ($line in $out) {
        $procId = ($line.ToString().Trim() -split "\s+")[-1]
        if ($procId -match "^\d+$" -and [int]$procId -gt 4) {
            Stop-Tree ([int]$procId)
        }
    }
}

Write-Host "[stop] Atlas processes..."
foreach ($p in $ChildPids) { Stop-Tree $p }
Stop-ListenPort 8000
Stop-ListenPort 3000

# Named windows from Start-Process -WindowStyle Minimized / titles
Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object {
    try { $_.Path -like "*\\nodejs\\*" -or $_.ProcessName -eq "node" } catch { $true }
} | ForEach-Object {
    # only kill node whose command line looks like next/atlas frontend
    try {
        $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
        if ($cl -match "next|frontend") { Stop-Tree $_.Id }
    } catch { }
}

Write-Host "[stop] docker compose down..."
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $job = Start-Job -ScriptBlock {
        param($r) Set-Location $r; docker compose down --remove-orphans
    } -ArgumentList $Root
    $null = Wait-Job $job -Timeout 25
    if ($job.State -eq "Running") {
        Stop-Job $job -ErrorAction SilentlyContinue
        Write-Host "[stop] compose down timed out - continuing"
    }
    Remove-Job $job -Force -ErrorAction SilentlyContinue
}

if (-not $KeepDockerDesktop) {
    Write-Host "[stop] quitting Docker Desktop..."
    $quit = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
    if (Test-Path $quit) {
        Start-Process $quit -ArgumentList "-Quit" -ErrorAction SilentlyContinue | Out-Null
        Start-Sleep -Seconds 3
    }
    @(
        "Docker Desktop",
        "com.docker.backend",
        "com.docker.build",
        "com.docker.dev-envs",
        "com.docker.proxy",
        "Docker Desktop Backend",
        "docker"
    ) | ForEach-Object {
        Get-Process -Name $_ -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "[stop] done."
