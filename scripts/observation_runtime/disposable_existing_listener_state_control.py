"""Read-only Windows listener state comparison with redacted endpoint/process identities."""
import ipaddress
import json
import os
import subprocess

from scripts.observation_runtime.socket_evidence import ip_helper


def inspect():
    if os.name != 'nt':
        raise OSError('WINDOWS_ONLY')
    ps = ('$r=@(Get-NetTCPConnection -State Listen -ErrorAction Stop); '
          '$r | Select-Object LocalPort,LocalAddress,State,OwningProcess | ConvertTo-Json -Compress')
    completed = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ps],
                               capture_output=True, text=True, timeout=12, check=True)
    decoded = json.loads(completed.stdout) if completed.stdout.strip() else []
    rows = decoded if isinstance(decoded, list) else [decoded]
    address_classes = {'loopback': 0, 'wildcard': 0, 'interface': 0}
    owner_classes = {'pid_zero': 0, 'pid_nonzero': 0}

    def address_class(item):
        address = ipaddress.ip_address(item['LocalAddress'].split('%')[0])
        return 'loopback' if address.is_loopback else ('wildcard' if address.is_unspecified else 'interface')

    for item in rows:
        address_classes[address_class(item)] += 1
        owner_classes['pid_zero' if item['OwningProcess'] == 0 else 'pid_nonzero'] += 1

    ids = sorted(set(int(item['OwningProcess']) for item in rows[:10] if item['OwningProcess'] > 0))
    owner_map = {}
    if ids:
        owner_ps = ("$ids=@(" + ','.join(map(str, ids)) + "); "
                    "$ids | ForEach-Object { $proc=Get-Process -Id $_ -ErrorAction SilentlyContinue; "
                    "[pscustomobject]@{pid=$_;category=if($null -eq $proc){'unavailable'}"
                    "elseif($proc.ProcessName -match '^(python|powershell|pwsh)$'){'interpreter'}"
                    "else{'other'}} } | ConvertTo-Json -Compress")
        owner_result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', owner_ps],
                                      capture_output=True, text=True, timeout=10, check=True)
        owner_decoded = json.loads(owner_result.stdout) if owner_result.stdout.strip() else []
        owner_items = owner_decoded if isinstance(owner_decoded, list) else [owner_decoded]
        owner_map = {int(item['pid']): item['category'] for item in owner_items}

    sampled = []
    for item in rows[:10]:
        port = int(item['LocalPort'])
        native = ip_helper(port=port)
        matching = [r for table in native['tables'] for r in table['rows']
                    if r['local_port'] == port and r['local_address'] == item['LocalAddress']
                    and r['owner_pid'] == item['OwningProcess']]
        sampled.append({'address_class': address_class(item),
                        'owner_class': 'pid_zero' if item['OwningProcess'] == 0 else 'pid_nonzero',
                        'process_class': owner_map.get(item['OwningProcess'], 'pid_zero'),
                        'nettcp_state': item['State'],
                        'native_error': native['error'],
                        'native_states': sorted(set(r['state'] for r in matching)),
                        'owner_match': bool(matching)})
    result = {'schema': 'ATLAS_EXISTING_LISTENER_STATE_CONTROL_V1',
              'listener_count': len(rows), 'samples': sampled,
              'address_classes': address_classes, 'owner_classes': owner_classes,
              'endpoints_redacted': True, 'operational_listener_accepted': False,
              'financial_authorized': False}
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == '__main__':
    inspect()
