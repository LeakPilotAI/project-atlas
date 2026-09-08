# Stop Atlas API + atlas postgres/redis containers. Never quits Docker Desktop.
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
$VenvPy = Join-Path $Root "backend\.venv\Scripts\python.exe"

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

function Stop-AtlasPython {
    $markers = @("uvicorn", "app.main", "Project Atlas", "project-atlas")
    try {
        Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
            $cl = [string]$_.CommandLine
            $exe = [string]$_.ExecutablePath
            $hit = $false
            foreach ($m in $markers) {
                if ($cl -like "*$m*" -or $exe -like "*$m*") { $hit = $true; break }
            }
            if ($VenvPy -and $exe -and ($exe -ieq $VenvPy)) { $hit = $true }
            if ($hit -and $_.ProcessId -gt 4) {
                Stop-Tree ([int]$_.ProcessId)
            }
        }
    } catch { }
}

Write-Host "[stop] Atlas processes..."
foreach ($p in $ChildPids) { Stop-Tree $p }
Stop-AtlasPython
Stop-ListenPort 8000
Stop-ListenPort 3000

Get-Process -Name "node" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        $cl = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
        if ($cl -match "next|frontend") { Stop-Tree $_.Id }
    } catch { }
}

Write-Host "[stop] atlas containers only (Docker Desktop stays up)..."
if (Get-Command docker -ErrorAction SilentlyContinue) {
    docker stop atlas-postgres atlas-redis 2>$null | Out-Null
}

Write-Host "[stop] done. Docker Desktop / other apps were not touched."
