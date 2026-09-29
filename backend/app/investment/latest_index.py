"""Incremental current-state projection; immutable research journals stay intact."""
import json
import threading
import time
from collections import OrderedDict
from pathlib import Path


class LatestIndex:
    def __init__(self):
        self.lock = threading.RLock()
        self.files = OrderedDict()
        self.parsed_rows = 0

    def read(self, path):
        path = Path(path).resolve()
        with self.lock:
            if not path.exists():
                self.files.pop(path, None)
                return []
            stat = path.stat()
            state = self.files.get(path)
            if (state is None or state['inode'] != stat.st_ino
                    or stat.st_size < state['offset']
                    or (stat.st_size == state['size'] and stat.st_mtime_ns != state['mtime'])):
                state = {'inode': stat.st_ino, 'offset': 0, 'rows': {}}
            with path.open('rb') as stream:
                stream.seek(state['offset'])
                while True:
                    raw = stream.readline()
                    if not raw or not raw.endswith(b'\n'):
                        break  # an append in progress is incorporated next refresh
                    state['offset'] = stream.tell()
                    try:
                        row = json.loads(raw)
                    except (ValueError, UnicodeError):
                        continue
                    if not isinstance(row, dict):
                        continue
                    self.parsed_rows += 1
                    symbol = str(row.get('symbol') or '').strip().upper()
                    previous = state['rows'].get(symbol)
                    if symbol and (path.name == 'plans.jsonl' or previous is None
                                   or str(row.get('timestamp') or '') >= str(previous.get('timestamp') or '')):
                        state['rows'][symbol] = row
                    if self.parsed_rows % 256 == 0:
                        time.sleep(0)  # let HTTP/background coroutines acquire the GIL
            state.update(size=stat.st_size, mtime=stat.st_mtime_ns)
            self.files[path] = state
            self.files.move_to_end(path)
            while len(self.files) > 8:
                self.files.popitem(last=False)
            return list(state['rows'].values())


latest_index = LatestIndex()
