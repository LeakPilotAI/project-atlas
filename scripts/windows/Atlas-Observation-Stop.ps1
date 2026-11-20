# Observation-only Stop request. NEVER a financial flatten or trade receipt.
# Does not launch applications, kill processes, touch Docker, Genesis, or accounts.
#Requires -Version 5.1
param([string]$OfflineTestId = '')
$ErrorActionPreference = 'Stop'

if($OfflineTestId -ne '' -and $OfflineTestId -cnotmatch '^test-[a-f0-9]{32}$'){
    throw 'ATLAS_OBSERVATION_STOP_TEST_NAMESPACE_REFUSED'
}
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$mutexName = "Local\AtlasObservationOwner_$sid"
$eventName = "Local\AtlasObservationStop_$sid"
if($OfflineTestId){
    $mutexName = "Local\AtlasObservationOwnerTest_${sid}_$OfflineTestId"
    $eventName = "Local\AtlasObservationStopTest_${sid}_$OfflineTestId"
}

$mutex=$null
$event=$null
$held=$false
try {
    try {
        $mutex = [System.Threading.Mutex]::OpenExisting($mutexName)
    } catch [System.Threading.WaitHandleCannotBeOpenedException] {
        throw 'ATLAS_OBSERVATION_STOP_NO_OWNED_SESSION'
    }
    # A released or abandoned named mutex does not certify a live owner. We
    # may only signal an event while another process actually holds ownership.
    try {
        $held = [bool]$mutex.WaitOne(0)
    } catch [System.Threading.AbandonedMutexException] {
        $held=$true
    }
    if($held){
        try {$mutex.ReleaseMutex()} catch {}
        $held=$false
        throw 'ATLAS_OBSERVATION_STOP_NO_OWNED_SESSION'
    }
    try {
        $event=[System.Threading.EventWaitHandle]::OpenExisting($eventName)
    } catch [System.Threading.WaitHandleCannotBeOpenedException] {
        throw 'ATLAS_OBSERVATION_STOP_NO_OWNED_SESSION'
    }
    if(-not $event.Set()){
        throw 'ATLAS_OBSERVATION_STOP_EVENT_NOT_SIGNALED'
    }
    Write-Output 'ATLAS_OBSERVATION_STOP_REQUESTED_NOT_CONFIRMED'
    Write-Output 'OBSERVATION_ONLY_NO_FINANCIAL_FLATNESS_CLAIM'
} finally {
    if($null -ne $event){$event.Dispose()}
    if($null -ne $mutex){$mutex.Dispose()}
}
