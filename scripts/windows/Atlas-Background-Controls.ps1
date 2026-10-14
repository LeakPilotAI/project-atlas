# Three-button Windows Forms control for the separate manual Atlas background mode.
#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

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
    $status.Text = $Message
    $status.ForeColor = $Color
    $statusTip.SetToolTip($status, $Message)
}

function Start-BackgroundManager([string]$SelectedAction) {
    if ($script:activeManager) { return }
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $PowerShell
    $startInfo.Arguments = ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Action {1} -Json' -f $Manager, $SelectedAction)
    $startInfo.WorkingDirectory = $Root
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    try {
        $token = [guid]::NewGuid().ToString("N")
        $outputPath = Join-Path $env:TEMP "atlas-background-$token.out"
        $errorPath = Join-Path $env:TEMP "atlas-background-$token.err"
        $process = Start-Process -FilePath $PowerShell -ArgumentList $startInfo.Arguments `
            -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput $outputPath `
            -RedirectStandardError $errorPath -PassThru -ErrorAction Stop
        if (-not $process) { throw "Could not start the hidden Atlas background controller." }
        $script:activeManager = @{
            process = $process
            action = $SelectedAction
            output_path = $outputPath
            error_path = $errorPath
        }
        $startButton.Enabled = $false
        $statusButton.Enabled = $false
        $stopButton.Enabled = $false
        $caption = if ($SelectedAction -eq "Status") { "Checking Atlas status..." } else { "$SelectedAction request is running..." }
        Set-StatusMessage $caption [System.Drawing.Color]::DarkSlateGray
    } catch {
        Set-StatusMessage "Atlas $SelectedAction failed: $($_.Exception.Message)" [System.Drawing.Color]::DarkRed
        $startButton.Enabled = $false
        $statusButton.Enabled = $true
        $stopButton.Enabled = $false
    }
}

function Apply-AtlasStatus($Result) {
    $color = if ($Result.state -eq "running") {
        [System.Drawing.Color]::DarkGreen
    } elseif ($Result.state -eq "STOPPED") {
        [System.Drawing.Color]::DarkSlateGray
    } elseif ($Result.state -eq "starting" -or $Result.state -eq "stopping") {
        [System.Drawing.Color]::DarkOrange
    } else {
        [System.Drawing.Color]::DarkRed
    }
    Set-StatusMessage "$($Result.state): $($Result.message)" $color
    $startButton.Enabled = ($Result.state -eq "STOPPED")
    $stopButton.Enabled = ($Result.state -eq "running")
    $statusButton.Enabled = $true
}

function Remove-ManagerOutput($Active) {
    foreach ($path in @($Active.output_path, $Active.error_path)) {
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
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
        if ($active.process.ExitCode -ne 0) {
            $detail = if ($errorOutput) { $errorOutput } else { "exit code $($active.process.ExitCode)" }
            Set-StatusMessage "Atlas $($active.action) failed: $detail" [System.Drawing.Color]::DarkRed
            $startButton.Enabled = $false
            $statusButton.Enabled = $true
            $stopButton.Enabled = $false
        } elseif (-not $output) {
            throw "Atlas background $($active.action) returned no status."
        } else {
            $result = $output | ConvertFrom-Json -ErrorAction Stop
            if ($active.action -eq "Status") {
                Apply-AtlasStatus $result
                $script:nextStatusCheck = (Get-Date).AddSeconds(2)
            } else {
                Set-StatusMessage "$($result.state): $($result.message)" [System.Drawing.Color]::DarkSlateGray
                $script:refreshStatus = $true
            }
        }
    } catch {
        Set-StatusMessage "STATUS CHECK FAILED: $($_.Exception.Message)" [System.Drawing.Color]::DarkRed
        $startButton.Enabled = $false
        $statusButton.Enabled = $true
        $stopButton.Enabled = $false
        $script:nextStatusCheck = (Get-Date).AddSeconds(2)
    } finally {
        $active.process.Dispose()
        Remove-ManagerOutput $active
    }
}

$startButton.Add_Click({
    Start-BackgroundManager "Start"
})
$statusButton.Add_Click({
    $script:nextStatusCheck = [datetime]::MaxValue
    Start-BackgroundManager "Status"
})
$stopButton.Add_Click({
    Start-BackgroundManager "Stop"
})

$script:activeManager = $null
$script:refreshStatus = $true
$script:nextStatusCheck = [datetime]::MinValue
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 250
$timer.Add_Tick({ Poll-BackgroundManager })
$timer.Start()
$form.Add_Shown({ $script:refreshStatus = $true })
[void]$form.ShowDialog()
$timer.Stop()
if ($script:activeManager) {
    $script:activeManager.process.Dispose()
}
