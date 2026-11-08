"""Compare read-only Windows OWNER_PID table classes on an owned loopback socket."""
import ctypes
import json
import os
import socket

from scripts.observation_runtime.socket_evidence import native_table


def inspect():
    if os.name != 'nt':
        raise OSError('WINDOWS_ONLY')
    get = ctypes.WinDLL('iphlpapi').GetExtendedTcpTable
    dword = ctypes.c_uint32
    get.argtypes = [ctypes.c_void_p, ctypes.POINTER(dword), ctypes.c_int,
                    dword, ctypes.c_int, dword]
    get.restype = dword
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        tables = {}
        for table_class in (3, 4, 5):  # OWNER_PID_LISTENER, CONNECTIONS, ALL
            size = dword()
            first = get(None, ctypes.byref(size), False, socket.AF_INET, table_class, 0)
            if first != 122 or not 4 <= size.value <= 8 * 1024**2:
                tables[str(table_class)] = {'first_code': first, 'size': size.value}
                continue
            buffer = ctypes.create_string_buffer(size.value)
            code = get(buffer, ctypes.byref(size), False, socket.AF_INET, table_class, 0)
            tables[str(table_class)] = {'code': code, 'rows': native_table(buffer.raw[:size.value], family=4, port=port)['rows'] if code == 0 else None}
        result = {'schema': 'ATLAS_DISPOSABLE_IPHELPER_TABLE_CLASS_V1',
                  'port': port, 'expected_pid': os.getpid(), 'tables': tables,
                  'operational_listener_accepted': False, 'financial_authorized': False}
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == '__main__':
    inspect()
