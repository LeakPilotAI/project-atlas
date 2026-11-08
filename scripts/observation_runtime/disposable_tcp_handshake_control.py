"""Disposable loopback handshake and scoped native state evidence; never acceptance."""
import json
import os
import socket

from scripts.observation_runtime.socket_evidence import ip_helper


def _states(port, pid):
    native = ip_helper(port=port)
    return {'states': sorted({row['state'] for table in native['tables'] for row in table['rows']
                              if row['local_port'] == port and row['owner_pid'] == pid
                              and row['local_address'] == '127.0.0.1'}),
            'error': native['error']}


def inspect():
    if os.name != 'nt':
        raise OSError('WINDOWS_ONLY')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        pid = os.getpid()
        before = _states(port, pid)
        with socket.create_connection(('127.0.0.1', port), timeout=2) as client:
            client.settimeout(2)
            with listener.accept()[0] as peer:
                peer.settimeout(2)
                client.sendall(b'ATLAS-DIAGNOSTIC')
                exchanged = peer.recv(64) == b'ATLAS-DIAGNOSTIC'
                during = _states(port, pid)
        after = _states(port, pid)
        result = {'schema': 'ATLAS_TCP_HANDSHAKE_CONTROL_V1',
                  'before': before, 'during': during, 'after': after,
                  'loopback_payload_verified': exchanged,
                  'socket_accepting': bool(listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)),
                  'endpoints_redacted': True, 'operational_listener_accepted': False,
                  'financial_authorized': False}
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == '__main__':
    inspect()
