"""Actual subprocess source interruption; all financial evidence remains unchanged."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import test_source_bound_two_lane_native as fixtures
from source_publication_native_fixture import DurableArchive

system=fixtures.system


@pytest.mark.parametrize('phase',['before','record','pin','ack'])
def test_source_crash_restart_does_not_adopt_tail_or_duplicate_financial_effect(system,phase):
    s,pub=system
    root=s.root/'crash-archive';archive=DurableArchive(root)
    packet=pub.qpub.read_current();(s.root/'packet.json').write_text(json.dumps(packet))
    before=(s.q.writer._cut(),s.p.writer._cut(),s.journal.snapshot())
    env=dict(os.environ);env['PYTHONPATH']=os.pathsep.join([str(Path(sys.prefix)/'Lib/site-packages'),str(Path.cwd()/'backend'),str(Path.cwd()/'tests')])
    child=subprocess.Popen([sys._base_executable,'-B',str(Path(__file__).with_name('source_publication_crash_child.py')),
        '--root',str(root),'--phase',phase],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    out,err=child.communicate(timeout=12)
    assert child.returncode==71,(out,err)
    assert (s.q.writer._cut(),s.p.writer._cut(),s.journal.snapshot())==before
    if phase in ('record','pin'):
        with pytest.raises(ValueError):archive.current()
    elif phase=='before':assert archive.current()=={'revision':0}
    else:assert archive.read(archive.current())==packet
