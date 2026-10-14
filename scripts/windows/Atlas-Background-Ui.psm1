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

Export-ModuleMember -Function Get-AtlasBackgroundStatusColor, Set-AtlasBackgroundStatusRendering
