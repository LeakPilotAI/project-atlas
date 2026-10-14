# Three-button Windows Forms control for the separate manual Atlas background mode.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Import-Module (Join-Path $PSScriptRoot "Atlas-Background-Ui.psm1") -Force

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Manager = Join-Path $PSScriptRoot "Atlas-Background.ps1"
$PowerShell = Join-Path $PSHOME "powershell.exe"

$form = New-Object System.Windows.Forms.Form
$form.Text = "Atlas Background"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(500, 270)
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.MaximizeBox = $false
$form.MinimizeBox = $true

$status = New-Object System.Windows.Forms.Label
$status.Location = New-Object System.Drawing.Point(20, 18)
$status.Size = New-Object System.Drawing.Size(445, 48)
$status.AutoEllipsis = $true
$status.Text = "Checking Atlas status..."
$form.Controls.Add($status)
$statusTip = New-Object System.Windows.Forms.ToolTip
$statusTip.SetToolTip($status, $status.Text)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = "Start Atlas Background"
$startButton.Location = New-Object System.Drawing.Point(20, 72)
$startButton.Size = New-Object System.Drawing.Size(445, 34)
$form.Controls.Add($startButton)

$statusButton = New-Object System.Windows.Forms.Button
$statusButton.Text = "Atlas Status"
$statusButton.Location = New-Object System.Drawing.Point(20, 116)
$statusButton.Size = New-Object System.Drawing.Size(445, 34)
$form.Controls.Add($statusButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = "Stop Atlas Background"
$stopButton.Location = New-Object System.Drawing.Point(20, 160)
$stopButton.Size = New-Object System.Drawing.Size(445, 34)
$form.Controls.Add($stopButton)

function Set-StatusMessage([string]$Message, [System.Drawing.Color]$Color) {
    Set-AtlasBackgroundStatusRendering $status $statusTip $Message $Color
}

function Start-BackgroundManager([string]$SelectedAction) {
    if ($script:activeManager) { return }
    try {
        $token = [guid]::NewGuid().ToString("N")
        $outputPath = Join-Path $env:TEMP "atlas-background-$token.out"
        $errorPath = Join-Path $env:TEMP "atlas-background-$token.err"
        $exitCodePath = Join-Path $env:TEMP "atlas-background-$token.exit"
        $managerLiteral = $Manager.Replace("'", "''")
        $exitCodeLiteral = $exitCodePath.Replace("'", "''")
        $childScript = @"
`$ErrorActionPreference = 'Stop'
`$ProgressPreference = 'SilentlyContinue'
`$exitCode = 1
try {
    & '$managerLiteral' -Action '$SelectedAction' -Json
    `$exitCode = 0
} catch {
    [Console]::Error.WriteLine(`$_.ToString())
} finally {
    [System.IO.File]::WriteAllText('$exitCodeLiteral', [string]`$exitCode)
}
exit `$exitCode
"@
        $encodedScript = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($childScript))
        $arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -EncodedCommand {0}' -f $encodedScript
        $process = Start-Process -FilePath $PowerShell -ArgumentList $arguments `
            -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $outputPath `
            -RedirectStandardError $errorPath -PassThru -ErrorAction Stop
        if (-not $process) { throw "Could not start the hidden Atlas background controller." }
        $script:activeManager = @{
            process = $process
            action = $SelectedAction
            output_path = $outputPath
            error_path = $errorPath
            exit_code_path = $exitCodePath
        }
        $startButton.Enabled = $false
        $statusButton.Enabled = $false
        $stopButton.Enabled = $false
        $caption = if ($SelectedAction -eq "Status") { "Checking Atlas status..." } else { "$SelectedAction request is running..." }
        $color = Get-AtlasBackgroundStatusColor "idle"
        Set-StatusMessage $caption $color
    } catch {
        $color = Get-AtlasBackgroundStatusColor "error"
        Set-StatusMessage "Atlas $SelectedAction failed: $($_.Exception.Message)" $color
        $startButton.Enabled = $false
        $statusButton.Enabled = $true
        $stopButton.Enabled = $false
    }
}

function Apply-AtlasStatus($Result) {
    $color = Get-AtlasBackgroundStatusColor ([string]$Result.state)
    Set-StatusMessage "$($Result.state): $($Result.message)" $color
    $startButton.Enabled = ($Result.state -eq "STOPPED")
    $stopButton.Enabled = ($Result.state -eq "running")
    $statusButton.Enabled = $true
}

function Remove-ManagerOutput($Active) {
    foreach ($path in @($Active.output_path, $Active.error_path, $Active.exit_code_path)) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            try { Remove-Item -LiteralPath $path -Force -ErrorAction Stop } catch { }
        }
    }
}

function Poll-BackgroundManager {
    if (-not $script:activeManager) {
        if ($script:refreshStatus -or (Get-Date) -ge $script:nextStatusCheck) {
            $script:refreshStatus = $false
            Start-BackgroundManager "Status"
        }
        return
    }
    if (-not $script:activeManager.process.HasExited) { return }

    $active = $script:activeManager
    $script:activeManager = $null
    try {
        $output = if (Test-Path -LiteralPath $active.output_path -PathType Leaf) {
            [System.IO.File]::ReadAllText($active.output_path).Trim()
        } else { "" }
        $errorOutput = if (Test-Path -LiteralPath $active.error_path -PathType Leaf) {
            [System.IO.File]::ReadAllText($active.error_path).Trim()
        } else { "" }
        $exitCodeData = if (Test-Path -LiteralPath $active.exit_code_path -PathType Leaf) {
            [System.IO.File]::ReadAllText($active.exit_code_path).Trim()
        } else {
            ""
        }
        $completion = ConvertFrom-AtlasManagerCompletion $active.action $output $errorOutput $exitCodeData
        if (-not $completion.success) {
            $color = Get-AtlasBackgroundStatusColor "error"
            Set-StatusMessage $completion.error $color
            $startButton.Enabled = $false
            $statusButton.Enabled = $true
            $stopButton.Enabled = $false
            return
        }
        $result = $completion.result
        if ($active.action -eq "Status") {
            Apply-AtlasStatus $result
            $script:nextStatusCheck = (Get-Date).AddSeconds(2)
        } else {
            $color = Get-AtlasBackgroundStatusColor "idle"
            Set-StatusMessage "$($result.state): $($result.message)" $color
            $script:refreshStatus = $true
        }
    } catch {
        try {
            $color = Get-AtlasBackgroundStatusColor "error"
            Set-StatusMessage "STATUS CHECK FAILED: $($_.Exception.Message)" $color
            $startButton.Enabled = $false
            $statusButton.Enabled = $true
            $stopButton.Enabled = $false
            $script:nextStatusCheck = (Get-Date).AddSeconds(2)
        } catch {
            [System.Diagnostics.Trace]::WriteLine("Atlas background UI callback failed: $($_.Exception.Message)")
        }
    } finally {
        try { $active.process.Dispose() } catch {
            [System.Diagnostics.Trace]::WriteLine("Atlas background process cleanup failed: $($_.Exception.Message)")
        }
        try { Remove-ManagerOutput $active } catch {
            [System.Diagnostics.Trace]::WriteLine("Atlas background output cleanup failed: $($_.Exception.Message)")
        }
    }
}

$startButton.Add_Click({
    Invoke-AtlasBackgroundUiCallback { Start-BackgroundManager "Start" } {
        param($callbackError)
        $color = Get-AtlasBackgroundStatusColor "error"
        Set-StatusMessage "Atlas Start failed: $($callbackError.Exception.Message)" $color
    } | Out-Null
})
$statusButton.Add_Click({
    Invoke-AtlasBackgroundUiCallback {
        $script:nextStatusCheck = [datetime]::MaxValue
        Start-BackgroundManager "Status"
    } {
        param($callbackError)
        $color = Get-AtlasBackgroundStatusColor "error"
        Set-StatusMessage "Atlas Status failed: $($callbackError.Exception.Message)" $color
    } | Out-Null
})
$stopButton.Add_Click({
    Invoke-AtlasBackgroundUiCallback { Start-BackgroundManager "Stop" } {
        param($callbackError)
        $color = Get-AtlasBackgroundStatusColor "error"
        Set-StatusMessage "Atlas Stop failed: $($callbackError.Exception.Message)" $color
    } | Out-Null
})

$script:activeManager = $null
$script:refreshStatus = $true
$script:nextStatusCheck = [datetime]::MinValue
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 250
$timer.Add_Tick({
    Invoke-AtlasBackgroundUiCallback { Poll-BackgroundManager } {
        param($callbackError)
        try {
            $color = Get-AtlasBackgroundStatusColor "error"
            Set-StatusMessage "STATUS CHECK FAILED: $($callbackError.Exception.Message)" $color
            $startButton.Enabled = $false
            $statusButton.Enabled = $true
            $stopButton.Enabled = $false
        } catch {
            [System.Diagnostics.Trace]::WriteLine("Atlas background timer callback failed: $($_.Exception.Message)")
        }
    } | Out-Null
})
$timer.Start()
$form.Add_Shown({ $script:refreshStatus = $true })
[void]$form.ShowDialog()
$timer.Stop()
if ($script:activeManager) {
    try { $script:activeManager.process.Dispose() } catch { }
}
