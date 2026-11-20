# Source-only, owner-mediated per-user Windows PAPER Stop request signal.
# No financial Start/Stop on import, no socket/token transfer, no disk secret.
# The only power a separate shortcut gets is requesting SHUTDOWN_FLATTEN.
# The owner must independently hold an accepted session and durable ledger.
function Get-AtlasPaperStopSignalIdentity {
    param([string]$OfflineTestId = '')
    if ($OfflineTestId -and $OfflineTestId -cnotmatch '^test-[a-f0-9]{32}$') {
        throw 'PAPER_STOP_SIGNAL_TEST_ID_INVALID'
    }
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    if ($null -eq $sid -or [string]::IsNullOrWhiteSpace($sid.Value)) {
        throw 'PAPER_STOP_SIGNAL_WINDOWS_PRINCIPAL_REQUIRED'
    }
    $desktopSession = [System.Diagnostics.Process]::GetCurrentProcess().SessionId
    if ($desktopSession -lt 0) { throw 'PAPER_STOP_SIGNAL_SESSION_UNAVAILABLE' }
    $suffix = if ($OfflineTestId) { '_' + $OfflineTestId } else { '' }
    $name = 'AtlasFinancialPaperStop_' + $sid.Value + '_' + $desktopSession + $suffix
    return @{ sid=$sid; event='Local\' + $name; mutex='Local\' + $name + '_Owner' }
}

function New-AtlasAcceptedPaperStopSignalOwner {
    param([object]$AcceptedSession = $null, [string]$OfflineTestId = '')
    # An arbitrary caller field saying ownership_verified is never authority.
    if ($null -eq $AcceptedSession -or
        $AcceptedSession.session_id -isnot [string] -or
        [string]::IsNullOrWhiteSpace($AcceptedSession.session_id) -or
        $AcceptedSession.session_id.Length -gt 128) {
        throw 'PAPER_STOP_SIGNAL_ACCEPTED_OWNER_REQUIRED'
    }
    $methods = @($AcceptedSession.PSObject.Methods.Name)
    if (-not ($methods -ccontains 'verify_session') -or
        -not ($methods -ccontains 'request_stop') -or
        -not ($methods -ccontains 'verify_durable_stop_receipt')) {
        throw 'PAPER_STOP_SIGNAL_ACCEPTED_OWNER_REQUIRED'
    }
    $pinnedSession = $AcceptedSession.session_id
    try { $verified = $AcceptedSession.verify_session() }
    catch { throw 'PAPER_STOP_SIGNAL_ACCEPTED_OWNER_REQUIRED' }
    if ($verified -isnot [bool] -or -not $verified -or
        $AcceptedSession.session_id -cne $pinnedSession) {
        throw 'PAPER_STOP_SIGNAL_ACCEPTED_OWNER_REQUIRED'
    }
    $id = Get-AtlasPaperStopSignalIdentity -OfflineTestId $OfflineTestId
    $mutexAcl = [System.Security.AccessControl.MutexSecurity]::new()
    $mutexAcl.AddAccessRule([System.Security.AccessControl.MutexAccessRule]::new(
        $id.sid, [System.Security.AccessControl.MutexRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow))
    $createdMutex = $false
    $mutex = [System.Threading.Mutex]::new($true, $id.mutex, [ref]$createdMutex, $mutexAcl)
    if (-not $createdMutex) {
        $mutex.Dispose()
        throw 'PAPER_STOP_SIGNAL_OTHER_OWNER_ACTIVE'
    }
    $event = $null
    try {
        $eventAcl = [System.Security.AccessControl.EventWaitHandleSecurity]::new()
        $eventAcl.AddAccessRule([System.Security.AccessControl.EventWaitHandleAccessRule]::new(
            $id.sid, [System.Security.AccessControl.EventWaitHandleRights]::FullControl,
            [System.Security.AccessControl.AccessControlType]::Allow))
        $createdEvent = $false
        $event = [System.Threading.EventWaitHandle]::new(
            $false, [System.Threading.EventResetMode]::AutoReset,
            $id.event, [ref]$createdEvent, $eventAcl)
        if (-not $createdEvent) { throw 'PAPER_STOP_SIGNAL_EXISTING_EVENT_REFUSED' }
        # Only the owner keeps the actual accepted session reference in memory.
        return [pscustomobject]@{ schema='ATLAS_PAPER_OWNED_STOP_SIGNAL_V1';
            session_id=$pinnedSession; owner=$AcceptedSession;
            mutex=$mutex; event=$event; name=$id.event; used=$false }
    } catch {
        if ($null -ne $event) { $event.Dispose() }
        try { $mutex.ReleaseMutex() } catch {}
        $mutex.Dispose()
        throw
    }
}

function Wait-AtlasOwnedPaperStopSignal {
    param([object]$Ownership = $null, [int]$TimeoutMilliseconds = 1000)
    if ($null -eq $Ownership -or
        $Ownership.schema -cne 'ATLAS_PAPER_OWNED_STOP_SIGNAL_V1' -or
        $null -eq $Ownership.owner -or $null -eq $Ownership.event -or
        $Ownership.used -ne $false -or
        $TimeoutMilliseconds -lt 0 -or $TimeoutMilliseconds -gt 30000) {
        throw 'PAPER_STOP_SIGNAL_OWNER_BINDING_REQUIRED'
    }
    if (-not $Ownership.event.WaitOne($TimeoutMilliseconds)) {
        return @{ status='NO_STOP_SIGNAL'; financial_flatness_verified=$false }
    }
    # Latch once even after uncertain/failed financial dispatch. A second
    # event must not trigger a second financial stop operation.
    $Ownership.used = $true
    $session = $Ownership.owner
    if ($session.session_id -cne $Ownership.session_id) {
        throw 'PAPER_STOP_SIGNAL_OWNER_IDENTITY_CHANGED'
    }
    try { $verified = $session.verify_session() }
    catch { throw 'PAPER_STOP_SIGNAL_OWNER_IDENTITY_CHANGED' }
    if ($verified -isnot [bool] -or -not $verified -or
        $session.session_id -cne $Ownership.session_id) {
        throw 'PAPER_STOP_SIGNAL_OWNER_IDENTITY_CHANGED'
    }
    Import-Module (Join-Path $PSScriptRoot 'Atlas-Paper-Stop-Handoff.psm1') -Force -ErrorAction Stop
    $handoff = @{schema='ATLAS_PAPER_STOP_HANDOFF_V1';session_id=$Ownership.session_id;
        mode='SHUTDOWN_FLATTEN';paper_only=$true;ownership_verified=$true}
    $result = Invoke-AtlasAcceptedPaperStopHandoff $handoff $session
    # The owner itself must independently read the matching native durable
    # Stop receipt. A finished in-memory handoff does NOT satisfy this.
    try { $durable = $session.verify_durable_stop_receipt('SHUTDOWN_FLATTEN', $result) }
    catch { throw 'PAPER_STOP_SIGNAL_DURABLE_RECEIPT_UNVERIFIED' }
    if ($durable -isnot [bool] -or -not $durable) {
        throw 'PAPER_STOP_SIGNAL_DURABLE_RECEIPT_UNVERIFIED'
    }
    return $result
}

function Request-AtlasPaperOwnedStopSignal {
    param([string]$OfflineTestId = '')
    $id = Get-AtlasPaperStopSignalIdentity -OfflineTestId $OfflineTestId
    try {
        # Modify-only access; no read/owner session/token acquisition.
        $event = [System.Threading.EventWaitHandle]::OpenExisting(
            $id.event, [System.Security.AccessControl.EventWaitHandleRights]::Modify)
    } catch [System.Threading.WaitHandleCannotBeOpenedException] {
        throw 'PAPER_STOP_SIGNAL_NO_OWNED_SESSION'
    }
    try {
        if ($event.Set() -ne $true) { throw 'PAPER_STOP_SIGNAL_SEND_UNVERIFIED' }
    } finally { $event.Dispose() }
    # A signal is not a durable receipt. Never report FLATTENED here.
    return @{schema='ATLAS_PAPER_STOP_SIGNAL_REQUEST_V1';
             status='REQUESTED_NOT_VERIFIED'; financial_flatness_verified=$false}
}

function Close-AtlasPaperStopSignalOwner {
    param([object]$Ownership = $null)
    if ($null -eq $Ownership -or
        $Ownership.schema -cne 'ATLAS_PAPER_OWNED_STOP_SIGNAL_V1') {
        throw 'PAPER_STOP_SIGNAL_OWNER_BINDING_REQUIRED'
    }
    if ($null -ne $Ownership.event) {
        $Ownership.event.Dispose(); $Ownership.event=$null
    }
    if ($null -ne $Ownership.mutex) {
        try { $Ownership.mutex.ReleaseMutex() } finally {
            $Ownership.mutex.Dispose(); $Ownership.mutex=$null
        }
    }
}
Export-ModuleMember -Function Get-AtlasPaperStopSignalIdentity, New-AtlasAcceptedPaperStopSignalOwner, Wait-AtlasOwnedPaperStopSignal, Request-AtlasPaperOwnedStopSignal, Close-AtlasPaperStopSignalOwner
