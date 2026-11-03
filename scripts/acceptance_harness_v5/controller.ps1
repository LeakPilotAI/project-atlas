$ErrorActionPreference='Stop'
$out=Split-Path -Parent $MyInvocation.MyCommand.Path
$binding=Get-Content -LiteralPath (Join-Path $out 'binding.json') -Raw|ConvertFrom-Json
Import-Module (Join-Path ('D:\AtlasRuntime\launchers\'+$binding.support_sha256) 'scripts\windows\Atlas-Installed-Nonfinancial.psm1') -Force
function Timing([string]$Event,[int]$Cycle,[object]$Details=$null){
    [ordered]@{event=$Event;cycle=$Cycle;utc=[DateTime]::UtcNow.ToString('o');qpc=[Diagnostics.Stopwatch]::GetTimestamp();frequency=[Diagnostics.Stopwatch]::Frequency;details=$Details}|ConvertTo-Json -Depth 5 -Compress|Add-Content -LiteralPath (Join-Path $out 'controller-timing.jsonl') -Encoding UTF8
}
try {
    foreach($cycle in 1..2){
        Timing 'open_call_started' $cycle
        $ready=Open-AtlasInstalledNonfinancialDashboard -Binding $binding -Approved
        $owner= & (Get-Module Atlas-Installed-Nonfinancial) { $script:installedNonfinancialOwner }
        Timing 'actual_process_launch' $cycle @{created_filetime=$owner.Created;process_start_utc=$owner.Process.StartTime.ToUniversalTime().ToString('o')}
        Timing 'application_ready_returned' $cycle
        $native=[ordered]@{pid=$owner.Pid;created=$owner.Created;image=$owner.Image;original_handle=$owner.Process.Handle.ToInt64()}
        $path=Join-Path $out ('cycle-'+$cycle+'-controller-native.json')
        $body=[Text.UTF8Encoding]::new($false).GetBytes(($native|ConvertTo-Json -Compress))
        $f=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try{$f.Write($body,0,$body.Length);$f.Flush($true)}finally{$f.Dispose()}
        $ready|ConvertTo-Json -Compress
        if([Console]::ReadLine() -cne ('STOP '+$ready.host_id)){throw 'OWNED_STOP_COMMAND_MISMATCH'}
        Timing 'stop_requested' $cycle
        $closed=Close-AtlasInstalledNonfinancialDashboard
        Timing 'stop_completed' $cycle $closed
        $closed|ConvertTo-Json -Compress
        if($cycle -eq 1 -and [Console]::ReadLine() -cne 'NEXT'){break}
    }
} finally {Close-AtlasInstalledNonfinancialDashboard|Out-Null}
