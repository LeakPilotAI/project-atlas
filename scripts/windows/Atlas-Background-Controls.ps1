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
$form.Size = New-Object System.Drawing.Size(420, 245)
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.MaximizeBox = $false
$form.MinimizeBox = $true

$status = New-Object System.Windows.Forms.Label
$status.Location = New-Object System.Drawing.Point(20, 18)
$status.Size = New-Object System.Drawing.Size(365, 42)
$status.Text = "Checking Atlas status..."
$form.Controls.Add($status)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Text = "Start Atlas Background"
$startButton.Location = New-Object System.Drawing.Point(20, 72)
$startButton.Size = New-Object System.Drawing.Size(365, 34)
$form.Controls.Add($startButton)

$statusButton = New-Object System.Windows.Forms.Button
$statusButton.Text = "Atlas Status"
$statusButton.Location = New-Object System.Drawing.Point(20, 116)
$statusButton.Size = New-Object System.Drawing.Size(365, 34)
$form.Controls.Add($statusButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = "Stop Atlas Background"
$stopButton.Location = New-Object System.Drawing.Point(20, 160)
$stopButton.Size = New-Object System.Drawing.Size(365, 34)
$form.Controls.Add($stopButton)

function Invoke-BackgroundManager([string]$SelectedAction) {
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $PowerShell
    $startInfo.Arguments = ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}" -Action {1} -Json' -f $Manager, $SelectedAction)
    $startInfo.WorkingDirectory = $Root
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { throw "Could not start the hidden Atlas background controller." }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $output = $stdoutTask.Result.Trim()
    $errorOutput = $stderrTask.Result.Trim()
    if ($process.ExitCode -ne 0) {
        if ($errorOutput) { throw $errorOutput }
        throw "Atlas background $SelectedAction failed with exit code $($process.ExitCode)."
    }
    if (-not $output) { throw "Atlas background $SelectedAction returned no status." }
    return ($output | ConvertFrom-Json -ErrorAction Stop)
}

function Get-AtlasStatus {
    return (Invoke-BackgroundManager "Status")
}

function Update-Status {
    try {
        $current = Get-AtlasStatus
        $status.Text = "$($current.state): $($current.message)"
        $status.ForeColor = if ($current.state -eq "running") {
            [System.Drawing.Color]::DarkGreen
        } elseif ($current.state -eq "STOPPED") {
            [System.Drawing.Color]::DarkSlateGray
        } else {
            [System.Drawing.Color]::DarkOrange
        }
        $startButton.Enabled = ($current.state -eq "STOPPED")
        $stopButton.Enabled = ($current.state -eq "running")
    } catch {
        $status.Text = "STATUS CHECK FAILED: $($_.Exception.Message)"
        $status.ForeColor = [System.Drawing.Color]::DarkRed
        $startButton.Enabled = $false
        $stopButton.Enabled = $false
    }
}

function Invoke-AtlasControl([string]$SelectedAction) {
    $result = Invoke-BackgroundManager $SelectedAction
    $status.Text = "$($result.state): $($result.message)"
    Update-Status
}

$startButton.Add_Click({
    try { Invoke-AtlasControl "Start" }
    catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "Atlas Background") | Out-Null }
})
$statusButton.Add_Click({ Update-Status })
$stopButton.Add_Click({
    try { Invoke-AtlasControl "Stop" }
    catch { [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "Atlas Background") | Out-Null }
})

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 2000
$timer.Add_Tick({ Update-Status })
$timer.Start()
$form.Add_Shown({ Update-Status })
[void]$form.ShowDialog()
$timer.Stop()
