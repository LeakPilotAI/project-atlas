"""Bounded read-only listener stability inside one PowerShell process."""
import json
import os
import subprocess


def inspect(*, rounds=4):
    if os.name != 'nt':
        raise OSError('WINDOWS_ONLY')
    if type(rounds) is not int or not 2 <= rounds <= 6:
        raise ValueError('ROUNDS_OUT_OF_BOUNDS')
    ps = ("$snapshots=@(); for($i=0;$i -lt " + str(rounds) + ";$i++){ "
          "$rows=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | ForEach-Object { "
          "('{0}|{1}|{2}' -f $_.LocalPort,$_.LocalAddress,$_.OwningProcess) }); "
          "$snapshots+=,[pscustomobject]@{identities=@($rows)}; "
          "if($i -lt " + str(rounds - 1) + "){Start-Sleep -Milliseconds 200} }; "
          "$snapshots | ConvertTo-Json -Depth 5 -Compress")
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ps],
                            capture_output=True, text=True, timeout=18, check=True)
    decoded = json.loads(result.stdout)
    if not isinstance(decoded, list) or len(decoded) != rounds:
        raise ValueError('INVALID_SNAPSHOT_COUNT')
    inventories = [set(snapshot['identities']) for snapshot in decoded]
    report = {'schema': 'ATLAS_SINGLE_SHELL_LISTENER_STABILITY_V1',
              'rounds': rounds, 'counts': [len(rows) for rows in inventories],
              'adjacent_identity_overlap': [len(inventories[i] & inventories[i+1]) for i in range(rounds-1)],
              'all_round_identity_overlap': len(set.intersection(*inventories)),
              'endpoints_redacted': True, 'operational_listener_accepted': False,
              'financial_authorized': False}
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == '__main__':
    inspect()
