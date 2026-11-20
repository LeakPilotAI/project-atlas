"""Read-only alternate Windows GetTcpTable2 comparison on an owned loopback socket."""
import ctypes
import json
import os
import socket
import struct

from scripts.observation_runtime.socket_evidence import ip_helper


def inspect():
    if os.name != 'nt':
        raise OSError('WINDOWS_ONLY')
    dll = ctypes.WinDLL('iphlpapi')
    get = dll.GetTcpTable2
    dword = ctypes.c_uint32
    get.argtypes = [ctypes.c_void_p, ctypes.POINTER(dword), ctypes.c_int]
    get.restype = dword
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        size = dword(0)
        first = get(None, ctypes.byref(size), False)
        if first != 122 or not 4 <= size.value <= 8 * 1024 * 1024:
            raise OSError(first, 'GET_TCP_TABLE2_SIZE')
        buffer = ctypes.create_string_buffer(size.value)
        code = get(buffer, ctypes.byref(size), False)
        if code:
            raise OSError(code, 'GET_TCP_TABLE2_ROWS')
        count = struct.unpack_from('<I', buffer.raw)[0]
        stride = 28  # MIB_TCPROW2: 7 DWORDs.
        if count > 65536 or 4 + count * stride > size.value:
            raise ValueError('GET_TCP_TABLE2_TRUNCATED')
        states = []
        for index in range(count):
            offset = 4 + index * stride
            state, local, lp, remote, rp, pid, offload = struct.unpack_from('<7I', buffer.raw, offset)
            if socket.ntohs(lp & 65535) == port and pid == os.getpid() and buffer.raw[offset+4:offset+8] == socket.inet_aton('127.0.0.1'):
                states.append(state)
        native = ip_helper(port=port)
        owner_states = [row['state'] for table in native['tables'] for row in table['rows']
                        if row['owner_pid'] == os.getpid() and row['local_port'] == port
                        and row['local_address'] == '127.0.0.1']
        result = {'schema': 'ATLAS_TCP_TABLE2_CONTROL_V1', 'table2_states': sorted(set(states)),
                  'owner_pid_states': sorted(set(owner_states)), 'table2_count': count,
                  'owner_pid_error': native['error'], 'socket_accepting': bool(listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)),
                  'endpoints_redacted': True, 'operational_listener_accepted': False, 'financial_authorized': False}
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == '__main__':
    inspect()
