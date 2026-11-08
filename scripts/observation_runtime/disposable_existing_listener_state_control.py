"""Read-only state comparison of existing Windows TCP listeners, without endpoint disclosure."""
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
    for item in rows:
        address = ipaddress.ip_address(item['LocalAddress'].split('%')[0])
        category = 'loopback' if address.is_loopback else ('wildcard' if address.is_unspecified else 'interface')
        address_classes[category] += 1
        owner_classes['pid_zero' if item['OwningProcess'] == 0 else 'pid_nonzero'] += 1
    sampled = []
    for item in rows[:10]:
        port = int(item['LocalPort'])
        native = ip_helper(port=port)
        matching = [r for t in native['tables'] for r in t['rows']
                    if r['local_port'] == port and r['local_address'] == item['LocalAddress']
                    and r['owner_pid'] == item['OwningProcess']]
        sampled.append({'address_class': ('loopback' if ipaddress.ip_address(item['LocalAddress'].split('%')[0]).is_loopback else ('wildcard' if ipaddress.ip_address(item['LocalAddress'].split('%')[0]).is_unspecified else 'interface')),
                        'owner_class': 'pid_zero' if item['OwningProcess'] == 0 else 'pid_nonzero',
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
