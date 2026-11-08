"""Disposable read-only comparison of three Windows TCP readers; never acceptance."""
import json
import os
import socket
import subprocess
import time

from scripts.observation_runtime.socket_evidence import ip_helper, netstat_rows


def inspect(*, connected=False):
    if os.name != 'nt':
        raise OSError('WINDOWS_ONLY')
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        pid = os.getpid()
        socket_acceptconn = listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)
        client = None
        peer = None
        try:
            if connected:
                client = socket.create_connection(('127.0.0.1', port), timeout=2)
                peer, _ = listener.accept()
            ps = ("$rows=@(Get-CimInstance -Namespace root/StandardCimv2 "
              "-ClassName MSFT_NetTCPConnection -Filter 'LocalPort=" + str(port) + "'); "
              "$rows | ForEach-Object { [pscustomobject]@{"
              "local=$_.LocalAddress;port=$_.LocalPort;pid=$_.OwningProcess;"
              "state_direct=$_.State;state_string=$_.State.ToString();"
              "state_type=$_.State.GetType().FullName;"
              "state_property=$_.PSObject.Properties['State'].Value}} | ConvertTo-Json -Compress")
            cim = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', ps],
                             capture_output=True, text=True, timeout=8)
            net = subprocess.run(['netstat.exe', '-ano', '-p', 'tcp'],
                             capture_output=True, text=True, timeout=8)
            native = ip_helper(port=port)
            net_lines = [line.strip() for line in net.stdout.splitlines()
                     if str(port) in line]
            cmd = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                              'Get-NetTCPConnection -LocalPort ' + str(port) +
                              ' -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,State,OwningProcess | ConvertTo-Json -Compress'],
                             capture_output=True, text=True, timeout=8)
            result = {'schema': 'ATLAS_DISPOSABLE_LISTENER_READERS_V1',
                  'port': port, 'connected': connected, 'expected_pid': pid, 'so_acceptconn': socket_acceptconn,
                  'netstat_exit': net.returncode, 'netstat_scoped_raw': net_lines,
                  'netstat_stderr': net.stderr.strip()[:200],
                  'nettcp_exit': cmd.returncode, 'nettcp': cmd.stdout.strip(),
                  'cim_exit': cim.returncode, 'cim': cim.stdout.strip(),
                  'cim_error': cim.stderr.strip()[:500],
                  'netstat': netstat_rows(net.stdout, port=port)['rows'] if net.returncode == 0 else None,
                  'ip_helper_error': native['error'],
                  'ip_helper_rows': [row for table in native['tables'] for row in table['rows']],
                  'operational_listener_accepted': False, 'financial_authorized': False}
        finally:
            if peer is not None:
                peer.close()
            if client is not None:
                client.close()
    print(json.dumps(result, sort_keys=True), flush=True)
    return result


if __name__ == '__main__':
    inspect()
