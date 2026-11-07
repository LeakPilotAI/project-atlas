"""Explicit test-owned subprocess; exits abruptly only itself, confined to supplied fixture root."""
import os
import sys
from pathlib import Path

from test_quality_dips_integration_v1 import system

root, boundary = Path(sys.argv[1]), sys.argv[2]
s = system(root)
request = s.approve(s.entry())
write = s.store.output.write_bound


def interrupted_write(leaf, raw):
    if boundary == "before-intent" and leaf.endswith("-intent.json"):
        os._exit(29)
    if boundary == "during-record" and leaf.endswith("-record.json"):
        with (s.store.output.root / leaf).open("xb") as stream:
            stream.write(raw[:len(raw) // 2])
            stream.flush()
            os.fsync(stream.fileno())
        os._exit(29)
    result = write(leaf, raw)
    if ((boundary == "after-commit" and leaf.endswith("-commit.json"))
            or (boundary == "after-ack" and leaf.endswith("-ack.json"))):
        os._exit(29)
    return result


s.store.output.write_bound = interrupted_write
if boundary == "after-pin":
    advance = s.store.trust.advance
    def interrupted_advance(old, new):
        advance(old, new)
        os._exit(29)
    s.store.trust.advance = interrupted_advance
s.service.execute(request)
raise AssertionError("Crash boundary not exercised")
