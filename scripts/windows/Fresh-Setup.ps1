# After a clean git clone: venv, npm, one desktop shortcut.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$VenvPy = Join-Path $Backend ".venv\Scripts\python.exe"

Set-Location $Root
Write-Host "Project Atlas setup in $Root"

function Find-Python {
    $cmds = @(
        @{ File = "py"; Args = @("-3.12") },
        @{ File = "py"; Args = @("-3") },
        @{ File = "python"; Args = @() }
    )
    foreach ($c in $cmds) {
        $cmd = Get-Command $c.File -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        try {
            $ver = & $c.File @($c.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")) 2>$null
            if ($ver -match "^3\.(1[2-9]|[2-9]\d)") {
                return @{ File = $c.File; Args = $c.Args }
            }
        } catch { }
    }
    return $null
}

Write-Host "==> Python venv"
if (-not (Test-Path $VenvPy)) {
    $py = Find-Python
    if (-not $py) {
        Write-Host "[ERROR] Python 3.12+ not found. Install python.org 3.12 and retry." -ForegroundColor Red
        exit 1
    }
    & $py.File @($py.Args + @("-m", "venv", (Join-Path $Backend ".venv")))
}
& $VenvPy -m pip install -U pip
Push-Location $Backend
& $VenvPy -m pip install -e ".[dev]"
Pop-Location

Write-Host "==> Frontend npm install"
$npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npm) {
    Write-Host "[ERROR] Node.js/npm not found. Install Node.js LTS from nodejs.org." -ForegroundColor Red
    exit 1
}
Push-Location $Frontend
& npm.cmd install
Pop-Location

Write-Host "==> .env"
$beEnv = Join-Path $Backend ".env"
$rootEnv = Join-Path $Root ".env"
if (-not (Test-Path $beEnv) -and -not (Test-Path $rootEnv)) {
    Copy-Item (Join-Path $Root ".env.example") $beEnv
    Copy-Item (Join-Path $Root ".env.example") $rootEnv
    Write-Host "[WARN] Created backend\.env from example. Put your Discord token and secrets in it before starting." -ForegroundColor Yellow
} else {
    Write-Host "    .env already present"
    if ((Test-Path $beEnv) -and -not (Test-Path $rootEnv)) {
        Copy-Item $beEnv $rootEnv
        Write-Host "    copied backend\.env to repo root for docker compose"
    }
}

Write-Host "==> Desktop shortcut"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "Install-DesktopShortcut.ps1")

Write-Host ""
Write-Host "Setup complete. Double-click 'Project Atlas' on the desktop."
Write-Host "If you have not copied your real .env yet, edit backend\.env first."
