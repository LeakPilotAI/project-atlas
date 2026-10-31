"""Generate/check inert browser calendar constants from the existing pure policy."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'backend/app/investment/market_hours.py'
TARGET = ROOT / 'frontend/offline/market-replay/view.cjs'
START = '// BEGIN GENERATED BOUNDED EXCHANGE CALENDAR\n'
END = '// END GENERATED BOUNDED EXCHANGE CALENDAR\n'


def block():
    spec = importlib.util.spec_from_file_location('atlas_calendar_policy', SOURCE)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    data = {'years': sorted(policy.CALENDAR_YEARS),
            'holidays': sorted(d.isoformat() for d in policy.HOLIDAYS),
            'early_closes': sorted(d.isoformat() for d in policy.EARLY_CLOSES)}
    return (START + '// Source SHA256: ' + hashlib.sha256(SOURCE.read_bytes()).hexdigest() + '\n'
            + 'const exchangeCalendar = ' + json.dumps(data, separators=(',', ':')) + ';\n' + END)


def main():
    raw = TARGET.read_bytes()
    text = raw.decode('utf8').replace('\r\n', '\n')
    expected = block()
    if '--check' in sys.argv:
        assert text[text.index(START):text.index(END) + len(END)] == expected, 'Calendar source drift'
    else:
        if START in text:
            a, b = text.index(START), text.index(END) + len(END)
            text = text[:a] + expected + text[b:]
        else:
            text = text.replace('function decode(text)', expected + 'function decode(text)', 1)
        TARGET.write_bytes(text.replace('\n', '\r\n').encode('utf8'))


if __name__ == '__main__':
    main()
