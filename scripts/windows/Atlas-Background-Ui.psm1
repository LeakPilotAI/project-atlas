function Get-AtlasBackgroundStatusColor([string]$State) {
    switch ($State) {
        "running" { return [System.Drawing.Color]::DarkGreen }
        "STOPPED" { return [System.Drawing.Color]::DarkSlateGray }
        { $_ -eq "starting" -or $_ -eq "stopping" } { return [System.Drawing.Color]::DarkOrange }
        default { return [System.Drawing.Color]::DarkRed }
    }
}

function Set-AtlasBackgroundStatusRendering(
    [System.Windows.Forms.Label]$Label,
    [System.Windows.Forms.ToolTip]$ToolTip,
    [string]$Message,
    [System.Drawing.Color]$Color
) {
    $Label.Text = $Message
    $Label.ForeColor = $Color
    $ToolTip.SetToolTip($Label, $Message)
}

function ConvertFrom-AtlasManagerCompletion(
    [string]$Action,
    [string]$Output,
    [string]$ErrorOutput,
    [string]$ExitCodeData
) {
    $exitCode = 0
    if ([string]::IsNullOrWhiteSpace($ExitCodeData) -or
        -not [int]::TryParse($ExitCodeData.Trim(), [ref]$exitCode)) {
        $detail = if ([string]::IsNullOrWhiteSpace($ErrorOutput)) {
            "No exit status was reported and no stderr was captured."
        } else {
            "No exit status was reported. stderr: $($ErrorOutput.Trim())"
        }
        return [pscustomobject]@{ success=$false; result=$null; error="Atlas $Action failed: $detail" }
    }
    if ($exitCode -ne 0) {
        $detail = if ([string]::IsNullOrWhiteSpace($ErrorOutput)) {
            "exit code $exitCode; no stderr was captured."
        } else {
            "exit code $exitCode. stderr: $($ErrorOutput.Trim())"
        }
        return [pscustomobject]@{ success=$false; result=$null; error="Atlas $Action failed: $detail" }
    }
    if ([string]::IsNullOrWhiteSpace($Output)) {
        return [pscustomobject]@{
            success=$false; result=$null
            error="Atlas $Action exited with code 0 but returned no JSON status."
        }
    }

    try {
        $result = $Output | ConvertFrom-Json -ErrorAction Stop
    } catch {
        return [pscustomobject]@{
            success=$false; result=$null
            error="Atlas $Action exited with code 0 but returned malformed JSON: $($_.Exception.Message)"
        }
    }
    $validStates = @("STOPPED", "running", "starting", "stopping", "AMBIGUOUS", "stop_timeout")
    if (-not $result -or [string]$result.state -cnotin $validStates -or
        [string]::IsNullOrWhiteSpace([string]$result.message)) {
        return [pscustomobject]@{
            success=$false; result=$null
            error="Atlas $Action exited with code 0 but returned an invalid status payload."
        }
    }
    return [pscustomobject]@{ success=$true; result=$result; error="" }
}

function Invoke-AtlasBackgroundUiCallback(
    [scriptblock]$Callback,
    [scriptblock]$OnError
) {
    try {
        & $Callback
        return $true
    } catch {
        $callbackError = $_
        try {
            & $OnError $callbackError
        } catch {
            [System.Diagnostics.Trace]::WriteLine(
                "Atlas background UI error handler failed: $($_.Exception.Message)"
            )
        }
        return $false
    }
}

Export-ModuleMember -Function Get-AtlasBackgroundStatusColor, Set-AtlasBackgroundStatusRendering, `
    ConvertFrom-AtlasManagerCompletion, Invoke-AtlasBackgroundUiCallback
