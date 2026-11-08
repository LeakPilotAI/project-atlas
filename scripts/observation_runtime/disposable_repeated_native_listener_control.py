"""Bounded, read-only repeated IP Helper queries for unchanged existing listeners."""
import json
import os
import subprocess
import time

from scripts.observation_runtime.socket_evidence import ip_helper


def inspect(*, rounds=3):
    if os.name != 'nt':
        raise OSError('WINDOWS_ONLY')
    if type(rounds) is not int or not 1 <= rounds <= 5:
        raise ValueError('ROUNDS_OUT_OF_BOUNDS')
    ps = ('$r=@(Get-NetTCPConnection -State Listen -ErrorAction Stop); '
          '$r | Select-Object -First 8 LocalPort,LocalAddress,State,OwningProcess | ConvertTo-Json -Compress')
    completed = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ps],
                               capture_output=True, text=True, timeout=12, check=True)
    decoded = json.loads(completed.stdout) if completed.stdout.strip() else []
    selected = decoded if isinstance(decoded, list) else [decoded]
    history = [[] for _ in selected]
    for iteration in range(rounds):
        for index, item in enumerate(selected):
            native = ip_helper(port=int(item['LocalPort']))
            matches = [row for table in native['tables'] for row in table['rows']
                       if row['local_port'] == item['LocalPort']
                       and row['local_address'] == item['LocalAddress']
                       and row['owner_pid'] == item['OwningProcess']]
            history[index].append({'states': sorted(set(row['state'] for row in matches)),
                                   'native_error': native['error']})
        if iteration + 1 < rounds:
            time.sleep(0.2)
    result = {'schema': 'ATLAS_REPEATED_NATIVE_LISTENER_CONTROL_V1',
              'sample_count': len(selected), 'rounds': rounds,
              'samples': [{'cmdlet_initial_state': item['State'], 'history': samples}
                          for item, samples in zip(selected, history)],
              'endpoints_redacted': True, 'operational_listener_accepted': False,
              'financial_authorized': False}
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == '__main__':
    inspect()
