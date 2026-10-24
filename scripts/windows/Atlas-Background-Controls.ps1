# Manual Windows Forms controls for normal and opt-in gaming background mode.
#Requires -Version 5.1
param([object]$AcceptedSelectedReadBridge = $null)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Import-Module (Join-Path $PSScriptRoot "Atlas-Background-Ui.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "Atlas-ReadOnly-Dashboard.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "Atlas-Control-Center.psm1") -Force
Import-Module (Join-Path $PSScriptRoot "Atlas-SelectedPaper-ReadOnly.psm1") -Force

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Manager = Join-Path $PSScriptRoot "Atlas-Background.ps1"
$PowerShell = Join-Path $PSHOME "powershell.exe"

$form = New-Object System.Windows.Forms.Form
$form.Text = "Atlas Control Center"
$form.StartPosition = "CenterScreen"
$form.Size = New-Object System.Drawing.Size(500, 735)
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.MaximizeBox = $false
$form.MinimizeBox = $true

$status = New-Object System.Windows.Forms.Label
$status.Location = New-Object System.Drawing.Point(20, 18)
$status.Size = New-Object System.Drawing.Size(445, 48)
$status.AutoEllipsis = $true
$status.Text = "Status not checked - click Atlas Status."
$form.Controls.Add($status)
$statusTip = New-Object System.Windows.Forms.ToolTip
$statusTip.SetToolTip($status, $status.Text)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = "Run Full Atlas (startup gate checked)"
$startButton.Location = New-Object System.Drawing.Point(20, 72)
$startButton.Size = New-Object System.Drawing.Size(445, 34)
$startButton.Enabled = $false
$form.Controls.Add($startButton)

$gamingButton = New-Object System.Windows.Forms.Button
$gamingButton.Text = "Start Atlas Gaming Mode"
$gamingButton.Location = New-Object System.Drawing.Point(20, 116)
$gamingButton.Size = New-Object System.Drawing.Size(445, 34)
$gamingButton.Enabled = $false
$form.Controls.Add($gamingButton)

$statusButton = New-Object System.Windows.Forms.Button
$statusButton.Text = "Atlas Status"
$statusButton.Location = New-Object System.Drawing.Point(20, 160)
$statusButton.Size = New-Object System.Drawing.Size(445, 34)
$statusButton.Enabled = $true
$form.Controls.Add($statusButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = "Stop Atlas (verified backend only)"
$stopButton.Location = New-Object System.Drawing.Point(20, 204)
$stopButton.Size = New-Object System.Drawing.Size(445, 34)
$stopButton.Enabled = $false
$form.Controls.Add($stopButton)

$dashboardButton = New-Object System.Windows.Forms.Button
$dashboardButton.Text = 'Open Read-Only Dashboard'
$dashboardButton.Location = New-Object System.Drawing.Point(20, 248)
$dashboardButton.Size = New-Object System.Drawing.Size(445, 34)
$dashboardButton.Add_Click({
    $dashboardButton.Enabled = $false
    try {
        Open-AtlasReadOnlyDashboard $Root
        Set-StatusMessage 'Read-only dashboard ready; protected backend unavailable.' ([System.Drawing.Color]::DarkGreen)
    } catch {
        Set-StatusMessage "Read-only dashboard failed: $($_.Exception.Message)" ([System.Drawing.Color]::DarkRed)
    } finally { $dashboardButton.Enabled = $true }
})
$form.Controls.Add($dashboardButton)
$dashboardStop = New-Object System.Windows.Forms.Button
$dashboardStop.Text = 'Close Read-Only Dashboard Host'
$dashboardStop.Location = New-Object System.Drawing.Point(20, 292)
$dashboardStop.Size = New-Object System.Drawing.Size(445, 34)
$dashboardStop.Add_Click({
    try {
        Close-AtlasReadOnlyDashboard
        Set-StatusMessage 'Read-only host closed; browser tabs may remain open.' ([System.Drawing.Color]::DarkSlateGray)
    } catch {
        Set-StatusMessage $_.Exception.Message ([System.Drawing.Color]::DarkRed)
    }
})
$form.Controls.Add($dashboardStop)
$form.Add_FormClosing({
    param($sender, $eventArgs)
    try { Close-AtlasSelectedPaperDashboard; Close-AtlasReadOnlyDashboard } catch {
        $eventArgs.Cancel = $true
        Set-StatusMessage $_.Exception.Message ([System.Drawing.Color]::DarkRed)
    }
})

function Set-StatusMessage([string]$Message, [System.Drawing.Color]$Color) {
    Set-AtlasBackgroundStatusRendering $status $statusTip $Message $Color
}

function Start-BackgroundManager([string]$SelectedAction) {
    if ($SelectedAction -eq 'Start' -or $SelectedAction -eq 'GamingStart') {
        $blocked = Get-AtlasFullStartupGate $Root
        Set-StatusMessage $blocked ([System.Drawing.Color]::DarkRed)
        $diagnostics.Text = 'Last startup request: ' + (Get-Date).ToString('o') + "`r`n" + $blocked
        return
    }
    if ($script:activeManager) { return }
    try {
        $token = [guid]::NewGuid().ToString("N")
        $outputPath = Join-Path $env:TEMP "atlas-background-$token.out"
        $errorPath = Join-Path $env:TEMP "atlas-background-$token.err"
        $exitCodePath = Join-Path $env:TEMP "atlas-background-$token.exit"
        $managerLiteral = $Manager.Replace("'", "''")
        $exitCodeLiteral = $exitCodePath.Replace("'", "''")
        $managerAction = if ($SelectedAction -eq "GamingStart") { "Start" } else { $SelectedAction }
        $gamingSetup = if ($SelectedAction -eq "GamingStart") {
            '$env:ATLAS_GAMING_MODE = "true"'
        } else {
            ''
        }
        $childScript = @"
`$ErrorActionPreference = 'Stop'
`$ProgressPreference = 'SilentlyContinue'
`$exitCode = 1
try {
    $gamingSetup
    & '$managerLiteral' -Action '$managerAction' -Json
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
            action = $managerAction
            output_path = $outputPath
            error_path = $errorPath
            exit_code_path = $exitCodePath
            completion_deadline = $null
        }
        $startButton.Enabled = $false
        $statusButton.Enabled = $false
        $stopButton.Enabled = $false
        $gamingButton.Enabled = $false
        $caption = if ($SelectedAction -eq "Status") { "Checking Atlas status..." } else { "$SelectedAction request is running..." }
        $color = Get-AtlasBackgroundStatusColor "idle"
        Set-StatusMessage $caption $color
    } catch {
        $color = Get-AtlasBackgroundStatusColor "error"
        Set-StatusMessage "Atlas $SelectedAction failed: $($_.Exception.Message)" $color
        $startButton.Enabled = $false
        $statusButton.Enabled = $true
        $stopButton.Enabled = $false
        $gamingButton.Enabled = $false
    }
}

function Apply-AtlasStatus($Result) {
    $color = Get-AtlasBackgroundStatusColor ([string]$Result.state)
    Set-StatusMessage "$($Result.state): $($Result.message)" $color
    $startButton.Enabled = ($Result.state -eq "STOPPED")
    $stopButton.Enabled = ($Result.state -eq "running")
    $statusButton.Enabled = $true
    $gamingButton.Enabled = ($Result.state -eq "STOPPED")
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
        return
    }
    $active = $script:activeManager
    if (-not $active.process.HasExited) { return }

    if (-not $active.completion_deadline) {
        $active.completion_deadline = (Get-Date).AddSeconds(10)
    }
    $files = $null
    try {
        $files = Read-AtlasManagerCompletionFiles $active.output_path `
            $active.error_path $active.exit_code_path
        if ($files.state -eq "pending") {
            if ((Get-Date) -lt $active.completion_deadline) { return }
            $script:activeManager = $null
            $color = Get-AtlasBackgroundStatusColor "error"
            Set-StatusMessage "Atlas $($active.action) completion timed out waiting for file handles: $($files.reason) Temporary files were retained for inspection." $color
            $startButton.Enabled = $false
            $statusButton.Enabled = $true
            $stopButton.Enabled = $false
            $gamingButton.Enabled = $false
            try { $active.process.Dispose() } catch {
                [System.Diagnostics.Trace]::WriteLine("Atlas background process cleanup failed: $($_.Exception.Message)")
            }
            return
        }
        if ($files.state -eq "failed") {
            $script:activeManager = $null
            throw $files.reason
        }
        $completion = ConvertFrom-AtlasManagerCompletion $active.action `
            $files.output $files.error_output $files.exit_code
        if (-not $completion.success -and
            (Get-Date) -lt $active.completion_deadline -and
            $files.exit_code.Trim() -eq "0" -and
            (
                $completion.error -match "returned no JSON status" -or
                (
                    $completion.error -match "returned malformed JSON" -and
                    $files.output.TrimStart() -match '^[\{\[]'
                )
            )) {
            # Retry incomplete output until the existing completion deadline.
            return
        }
        $script:activeManager = $null
        if (-not $completion.success) {
            $color = Get-AtlasBackgroundStatusColor "error"
            Set-StatusMessage $completion.error $color
            $startButton.Enabled = $false
            $statusButton.Enabled = $true
            $stopButton.Enabled = $false
            $gamingButton.Enabled = $false
            return
        }
        $result = $completion.result
        if ($active.action -eq "Status") {
            Apply-AtlasStatus $result
        } else {
            $color = Get-AtlasBackgroundStatusColor "idle"
            Set-StatusMessage "$($result.state): $($result.message)" $color
            $startButton.Enabled = $false
            $stopButton.Enabled = $false
            $statusButton.Enabled = $true
            $gamingButton.Enabled = $false
        }
    } catch {
        try {
            $color = Get-AtlasBackgroundStatusColor "error"
            Set-StatusMessage "STATUS CHECK FAILED: $($_.Exception.Message)" $color
            $startButton.Enabled = $false
            $statusButton.Enabled = $true
            $stopButton.Enabled = $false
            $gamingButton.Enabled = $false
        } catch {
            [System.Diagnostics.Trace]::WriteLine("Atlas background UI callback failed: $($_.Exception.Message)")
        }
    } finally {
        if (-not $script:activeManager) {
            try { $active.process.Dispose() } catch {
                [System.Diagnostics.Trace]::WriteLine("Atlas background process cleanup failed: $($_.Exception.Message)")
            }
            if ($files -and $files.state -eq "ready") {
                try { Remove-ManagerOutput $active } catch {
                    [System.Diagnostics.Trace]::WriteLine("Atlas background output cleanup failed: $($_.Exception.Message)")
                }
            }
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
$gamingButton.Add_Click({
    Invoke-AtlasBackgroundUiCallback { Start-BackgroundManager "GamingStart" } {
        param($callbackError)
        $color = Get-AtlasBackgroundStatusColor "error"
        Set-StatusMessage "Atlas Gaming Start failed: $($callbackError.Exception.Message)" $color
    } | Out-Null
})
$statusButton.Add_Click({
    Invoke-AtlasBackgroundUiCallback {
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

$runtimeSummary = New-Object System.Windows.Forms.Label
$runtimeSummary.Location = New-Object System.Drawing.Point(20, 338)
$runtimeSummary.Size = New-Object System.Drawing.Size(445, 58)
$runtimeSummary.Text = "Backend / full frontend / Docker: NOT VERIFIED`r`nRead-only host: independent; verify with Open action`r`nStartup gate: BLOCKED; production NO-GO"
$form.Controls.Add($runtimeSummary)
$fullFrontend = New-Object System.Windows.Forms.Button
$fullFrontend.Text = 'Open Full Frontend (requires verified runtime)'
$fullFrontend.Location = New-Object System.Drawing.Point(20, 402)
$fullFrontend.Size = New-Object System.Drawing.Size(445, 32)
$fullFrontend.Add_Click({
    Set-StatusMessage (Get-AtlasFullFrontendDecision $Root) ([System.Drawing.Color]::DarkRed)
})
$form.Controls.Add($fullFrontend)
$diagnostics = New-Object System.Windows.Forms.TextBox
$diagnostics.Multiline = $true
$diagnostics.ReadOnly = $true
$diagnostics.ScrollBars = 'Vertical'
$diagnostics.Location = New-Object System.Drawing.Point(20, 482)
$diagnostics.Size = New-Object System.Drawing.Size(445, 105)
$diagnostics.Text = 'No startup attempt in this GUI. Process identity/readiness not verified. Use explicit Atlas Status only when recovery-capable manager inspection is intended.'
$form.Controls.Add($diagnostics)
$selectedPaper = New-Object System.Windows.Forms.Button
$selectedPaper.Text = 'Open Selected PAPER Account (read-only)'
$selectedPaper.Location = New-Object System.Drawing.Point(20, 596)
$selectedPaper.Size = New-Object System.Drawing.Size(445, 32)
$selectedPaper.Add_Click({
    try {
        Open-AtlasSelectedPaperDashboard -Root $Root -AcceptedBridge $AcceptedSelectedReadBridge
        Set-StatusMessage 'Selected PAPER Account read-only session verified.' ([System.Drawing.Color]::DarkGreen)
    } catch {
        Set-StatusMessage $_.Exception.Message ([System.Drawing.Color]::DarkRed)
    }
})
$form.Controls.Add($selectedPaper)
$selectedPaperClose = New-Object System.Windows.Forms.Button
$selectedPaperClose.Text = 'Close Selected Account Read-Only Host'
$selectedPaperClose.Location = New-Object System.Drawing.Point(20, 636)
$selectedPaperClose.Size = New-Object System.Drawing.Size(445, 32)
$selectedPaperClose.Add_Click({
    try { Close-AtlasSelectedPaperDashboard } catch {
        Set-StatusMessage $_.Exception.Message ([System.Drawing.Color]::DarkRed)
    }
})
$form.Controls.Add($selectedPaperClose)
$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Icon = [System.Drawing.SystemIcons]::Application
$tray.Text = 'Atlas Control Center'
$trayMenu = New-Object System.Windows.Forms.ContextMenuStrip
$showItem = $trayMenu.Items.Add('Show Control Center')
$showItem.Add_Click({ $form.Show(); $form.WindowState = 'Normal'; $form.Activate() })
$exitItem = $trayMenu.Items.Add('Exit GUI (close read-only host only)')
$exitItem.Add_Click({ $form.Close() })
$tray.ContextMenuStrip = $trayMenu
$tray.Add_DoubleClick({ $form.Show(); $form.WindowState = 'Normal'; $form.Activate() })
$minimize = New-Object System.Windows.Forms.Button
$minimize.Text = 'Minimize to Tray'
$minimize.Location = New-Object System.Drawing.Point(20, 440)
$minimize.Size = New-Object System.Drawing.Size(210, 32)
$minimize.Add_Click({
    try { $tray.Visible = $true; $form.Hide() } catch {
        $form.Show()
        Set-StatusMessage 'Tray unavailable; Control Center remains open.' ([System.Drawing.Color]::DarkRed)
    }
})
$form.Controls.Add($minimize)
$closeGui = New-Object System.Windows.Forms.Button
$closeGui.Text = 'Close GUI - Keep Atlas Running'
$closeGui.Location = New-Object System.Drawing.Point(238, 440)
$closeGui.Size = New-Object System.Drawing.Size(227, 32)
$closeGui.Add_Click({ $form.Close() })
$form.Controls.Add($closeGui)
# A request can always display the gate refusal without a recovery-capable Status call.
$startButton.Enabled = $true

$script:activeManager = $null
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
            $gamingButton.Enabled = $false
        } catch {
            [System.Diagnostics.Trace]::WriteLine("Atlas background timer callback failed: $($_.Exception.Message)")
        }
    } | Out-Null
})
$timer.Start()

[void]$form.ShowDialog()
$timer.Stop()
$tray.Visible = $false
$tray.Dispose()
if ($script:activeManager) {
    try { $script:activeManager.process.Dispose() } catch { }
}
