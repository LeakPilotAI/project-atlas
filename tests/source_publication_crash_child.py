"""Self-exiting source archive fixture; no financial operation or live source."""
import argparse
import json
import os
from pathlib import Path

from source_publication_native_fixture import DurableArchive


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--phase',required=True)
    a=p.parse_args();root=Path(a.root).absolute();conf=Path(os.environ['ATLAS_PERP_ORDER_TEST_ROOT']).absolute()
    if (not root.is_relative_to(conf) or not conf.name.startswith('perp-order-custody-')
            or any(x.is_symlink() or x.is_junction() for x in (root,*root.parents))):
        raise ValueError('CONFINED_SOURCE_CRASH_ONLY')
    archive=DurableArchive(root)
    def fault(phase):
        if phase==a.phase:os._exit(71)
    archive.fault=fault
    packet=json.loads((root.parent/'packet.json').read_text())
    archive.publish(expected=archive.current(),packet=packet,sources={'fixture':'EXPLICIT_SYNTHETIC'})


if __name__=='__main__':main()
