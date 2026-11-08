"""Bounded read-only Windows listening inventory stability control."""
import json
import os
import time

from scripts.observation_runtime.disposable_repeated_native_listener_control import _cmdlet_listeners, _identity


def inspect(*, rounds=4):
    if os.name != 'nt':
        raise OSError('WINDOWS_ONLY')
    if type(rounds) is not int or not 2 <= rounds <= 6:
        raise ValueError('ROUNDS_OUT_OF_BOUNDS')
    inventories = []
    for iteration in range(rounds):
        rows = _cmdlet_listeners()
        inventories.append({_identity(row) for row in rows})
        if iteration + 1 < rounds:
            time.sleep(0.2)
    overlap = [len(inventories[i] & inventories[i + 1]) for i in range(rounds - 1)]
    result = {'schema': 'ATLAS_CMDLET_LISTENER_STABILITY_V1',
              'rounds': rounds, 'counts': [len(rows) for rows in inventories],
              'adjacent_identity_overlap': overlap,
              'all_round_identity_overlap': len(set.intersection(*inventories)),
              'endpoints_redacted': True, 'operational_listener_accepted': False,
              'financial_authorized': False}
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == '__main__':
    inspect()
