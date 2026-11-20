"""Read-only process self-binding evidence for installed PAPER writer candidates.

No writer roster issuance, financial permissions, or process termination.
"""
import json
import ntpath
from pathlib import Path


def inspect(*, expected_executable):
    from scripts.observation_runtime.quality_dips_read_service import observe_self
    raw = observe_self()
    path = str(Path(expected_executable))
    matched = (ntpath.normcase(raw['image']) == ntpath.normcase(path)
               and path.startswith('D:\\')
               and type(raw['pid']) is int and raw['pid'] > 0
               and type(raw['creation_filetime']) is int and raw['creation_filetime'] > 0)
    return {'schema': 'ATLAS_PERSONAL_WRITER_SELF_BINDING_PROBE_V1',
            'expected_executable': path, 'observed_process': raw,
            'installed_executable_matched': matched,
            'enrolled_writer_verified': False,
            'ownership_lease_issued': False,
            'paper_start_authorized': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-executable', required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(expected_executable=args.expected_executable), sort_keys=True))
