import os
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.services.paper_financial_replay import strict
from continuation_fixture import manifests, records
from native_continuation_session_fixture import (
    Authority,
    canonical_records,
    ledger,
)

from scripts.observation_runtime.native_fixture_budget import NativeFixtureBudget

root=Path(sys.argv[1]);p=Path(sys.argv[2]);phase=sys.argv[3]
b=NativeFixtureBudget(root);a=Authority(p/'custody'/'switch-status.json');m=manifests()['QUALITY_DIPS']
s=ledger(b,p,a,'QD',m)
row=canonical_records(m,[strict(records()['QUALITY_DIPS'][0]['command'])])[0]
s.append(row,fault=lambda stage:os._exit(73) if stage==phase else None)
s.close()

