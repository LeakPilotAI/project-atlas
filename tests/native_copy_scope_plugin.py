"""Opt-in declaration before the existing negative hardlink test executes."""
import os

from scripts.native_copy_test_scope import PROBE_OWNER, declare_probe


def pytest_runtest_call(item):
    root=os.environ.get('ATLAS_NEGATIVE_PROBE_ROOT')
    if root and item.nodeid.replace('\\','/').endswith(PROBE_OWNER):
        declare_probe(root,item.funcargs['tmp_path'])
