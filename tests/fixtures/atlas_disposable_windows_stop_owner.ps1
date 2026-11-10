# Native Windows event round-trip fixture. Disposable, NO Atlas financial owner.
# The native event uses an explicitly isolated test-<32hex> namespace.
param([Parameter(Mandatory=$true)][string]$OfflineTestId,
      [Parameter(Mandatory=$true)][string]$ReceiptPath,
      [string]$SelectedR14StopModule = '',
      [string]$SelectedR15StopModule = '')
$ErrorActionPreference='Stop'
if($OfflineTestId -cnotmatch '^test-[a-f0-9]{32}$') {throw 'TEST_ISOLATED_NAMESPACE_REQUIRED'}
if(Test-Path -LiteralPath $ReceiptPath){throw 'TEST_RECEIPT_MUST_NOT_EXIST'}
$ledger=Join-Path (Split-Path -Parent $ReceiptPath) 'disposable-stop-ledger.sqlite'
$fixture=Join-Path $PSScriptRoot 'atlas_disposable_stop_sqlite.py'
$python=Join-Path $PSScriptRoot '..\..\backend\.venv\Scripts\python.exe'
function Invoke-DisposableLedger([string]$Action){
    & $python -B $fixture $Action $ledger $ReceiptPath 2>$null
    if($LASTEXITCODE -ne 0){throw ('DISPOSABLE_STOP_SQLITE_'+$Action+'_REFUSED')}
}
Invoke-DisposableLedger 'reserve'
$stopModule = Join-Path $PSScriptRoot '..\..\scripts\windows\Atlas-Paper-Owned-Stop-Signal.psm1'
if($SelectedR14StopModule -and $SelectedR15StopModule){throw 'DISPOSABLE_NATIVE_STOP_RELEASE_AMBIGUOUS'}
if($SelectedR14StopModule){
    $expected = 'D:\AtlasRuntime\releases\7ff9d3dba2eabe110f843c13efac49464805de2a\scripts\windows\Atlas-Paper-Owned-Stop-Signal.psm1'
    $expectedSha = '893a81bf11f7849f8ba20b31bb9e96b45e30ed09e35485ad018e1d7a21d1e9dc'
    if($SelectedR14StopModule -cne $expected -or -not (Test-Path -LiteralPath $expected -PathType Leaf) -or
        (Get-FileHash -LiteralPath $expected -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expectedSha){
        throw 'DISPOSABLE_SELECTED_R14_NATIVE_STOP_SOURCE_REFUSED'
    }
    $stopModule = $expected
}
if($SelectedR15StopModule){
    $expected = 'D:\AtlasRuntime\releases\2c79a8d846d6b33669008114732ae5896153812a\scripts\windows\Atlas-Paper-Owned-Stop-Signal.psm1'
    $expectedSha = '893a81bf11f7849f8ba20b31bb9e96b45e30ed09e35485ad018e1d7a21d1e9dc'
    if($SelectedR15StopModule -cne $expected -or -not (Test-Path -LiteralPath $expected -PathType Leaf) -or
        (Get-FileHash -LiteralPath $expected -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expectedSha){
        throw 'DISPOSABLE_SELECTED_R15_NATIVE_STOP_SOURCE_REFUSED'
    }
    $stopModule = $expected
}
Import-Module -Name $stopModule -Force -ErrorAction Stop
$session=[pscustomobject]@{session_id='test-disposable-two-lane-session';path=$ReceiptPath;stops=0;
    python=$python;fixture=$fixture;ledger=$ledger;
    positions=@{QUALITY_DIPS=5;HYPERLIQUID=3}}
$session | Add-Member -MemberType ScriptMethod -Name verify_session -Value {
    return $this.session_id -ceq 'test-disposable-two-lane-session'
}
$session | Add-Member -MemberType ScriptMethod -Name request_stop -Value {
    param($mode)
    if($mode -cne 'SHUTDOWN_FLATTEN' -or $this.stops -ne 0){throw 'TEST_STOP_NOT_ONCE'}
    $before=@{QUALITY_DIPS=[int]$this.positions.QUALITY_DIPS;HYPERLIQUID=[int]$this.positions.HYPERLIQUID}
    if($before.QUALITY_DIPS -le 0 -or $before.HYPERLIQUID -le 0){throw 'TEST_EXPECTED_OPEN_PAPER_POSITIONS'}
    $this.stops++
    $this.positions.QUALITY_DIPS=0
    $this.positions.HYPERLIQUID=0
    $outcome=@{
        schema='QD_AUTO_SHUTDOWN_V1';mode=$mode;status='FLATTENED';
        position_state='FLAT';process_shutdown='VERIFIED_EXIT';
        lanes=@{
            QUALITY_DIPS=@{state='ACKNOWLEDGED_FLAT_AND_DRAINED'};
            HYPERLIQUID=@{state='ACKNOWLEDGED_FLAT_AND_DRAINED'}
        }
    }
    $receipt=@{schema='QD_CONTROL_STOP_V1';phase='FINISHED';outcome=$outcome;
      disposable_positions_before=$before;
      disposable_positions_after=@{QUALITY_DIPS=[int]$this.positions.QUALITY_DIPS;
                                   HYPERLIQUID=[int]$this.positions.HYPERLIQUID}}
    $bytes=[System.Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $receipt -Depth 12 -Compress))
    $s=[System.IO.File]::Open($this.path,[System.IO.FileMode]::CreateNew,[System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
    try { $s.Write($bytes,0,$bytes.Length); $s.Flush($true) } finally {$s.Dispose()}
    & $this.python -B $this.fixture finish $this.ledger $this.path 2>$null
    if($LASTEXITCODE -ne 0){throw 'DISPOSABLE_SQLITE_STOP_FINISH_REFUSED'}
    return $receipt
}
$session | Add-Member -MemberType ScriptMethod -Name verify_durable_stop_receipt -Value {
    param($mode,$result)
    if($mode -cne 'SHUTDOWN_FLATTEN' -or $this.stops -ne 1){return $false}
    & $this.python -B $this.fixture verify $this.ledger $this.path 2>$null
    if($LASTEXITCODE -ne 0){return $false}
    $persisted=(Get-Content -LiteralPath $this.path -Raw | ConvertFrom-Json)
    return ($persisted.schema -ceq 'QD_CONTROL_STOP_V1' -and
      $persisted.phase -ceq 'FINISHED' -and
      $persisted.outcome.mode -ceq $mode -and
      $persisted.outcome.lanes.QUALITY_DIPS.state -ceq 'ACKNOWLEDGED_FLAT_AND_DRAINED' -and
      $persisted.outcome.lanes.HYPERLIQUID.state -ceq 'ACKNOWLEDGED_FLAT_AND_DRAINED' -and
      $persisted.disposable_positions_before.QUALITY_DIPS -eq 5 -and
      $persisted.disposable_positions_before.HYPERLIQUID -eq 3 -and
      $persisted.disposable_positions_after.QUALITY_DIPS -eq 0 -and
      $persisted.disposable_positions_after.HYPERLIQUID -eq 0 -and
      $this.positions.QUALITY_DIPS -eq 0 -and $this.positions.HYPERLIQUID -eq 0 -and
      $result.outcome.status -ceq 'FLATTENED')
}
$ownership=$null
try {
    $ownership=New-AtlasAcceptedPaperStopSignalOwner -AcceptedSession $session -OfflineTestId $OfflineTestId
    Write-Output 'DISPOSABLE_NATIVE_OWNER_READY'
    [Console]::Out.Flush()
    $final=$null
    for($i=0;$i -lt 100;$i++){
        $response=Wait-AtlasOwnedPaperStopSignal -Ownership $ownership -TimeoutMilliseconds 100
        if($response.status -eq 'NO_STOP_SIGNAL'){continue}
        $final=$response
        break
    }
    if($null -eq $final){throw 'DISPOSABLE_NATIVE_OWNER_NOT_SIGNALED'}
    if($final.outcome.status -cne 'FLATTENED' -or $session.stops -ne 1){throw 'DISPOSABLE_FLATTEN_UNVERIFIED'}
    Write-Output 'DISPOSABLE_TWO_LANE_DURABLE_FLATTEN_VERIFIED'
}finally {
    if($null -ne $ownership){Close-AtlasPaperStopSignalOwner -Ownership $ownership}
}
