"""Daily bridge imports and reviews synthetic data from a clean source archive."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from test_offline_candidate_packaging import candidate, fixture_root


def test_clean_candidate_daily_bridge_has_its_pure_transitive_dependencies(tmp_path, monkeypatch):
    source, _ = fixture_root(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[1]
    files = ['scripts/observation_runtime/daily_afi_bridge.py', 'backend/app/__init__.py',
             'backend/app/backtest/__init__.py', 'backend/app/backtest/historical.py',
             'backend/app/backtest/forecast_dataset.py', 'backend/app/backtest/forecast_evaluation.py',
             'backend/app/investment/__init__.py', 'backend/app/investment/market_hours.py',
             'backend/app/investment/offline_research.py', 'backend/app/core/__init__.py',
             'backend/app/core/durable_io.py', 'backend/app/services/__init__.py',
             'backend/app/services/paper_execution_model.py']
    for name in files:
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repo/name).read_bytes())
    previous = candidate.git
    monkeypatch.setattr(candidate, 'git', lambda *args: previous(*args)+files if '--others' in args else previous(*args))
    candidate.build(tmp_path/'candidate')
    clean = tmp_path/'clean'
    with zipfile.ZipFile(tmp_path/'candidate/atlas-source.zip') as archive:
        archive.extractall(clean)
    payload = {'chart': {'error': None, 'result': [{'meta': {'symbol': 'SPY', 'currency': 'USD', 'dataGranularity': '1d',
                                                          'exchangeTimezoneName': 'America/New_York', 'instrumentType': 'ETF'},
                                               'timestamp': [1792071000, 1792157400],
                                               'indicators': {'quote': [{'open': [100, 101], 'high': [101, 102], 'low': [99, 100], 'close': [100, 101], 'volume': [1000, 1000]}]}}]}}
    (clean/'synthetic-source.json').write_text(json.dumps(payload), encoding='utf8')
    code = """import sys,pathlib,hashlib,json
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root/'backend'));sys.path.insert(1,str(root))
def guard(event,args):
 if event=='socket.connect':raise PermissionError('offline packaging test')
sys.addaudithook(guard)
import app
assert pathlib.Path(app.__file__).resolve().is_relative_to(root)
from scripts.observation_runtime.daily_afi_bridge import build_daily_dataset
raw=(root/'synthetic-source.json').read_bytes();stamp='2026-10-16T20:01:00+00:00'
universe={'asset_id':'ETF:SPY','listed_at':'2026-01-01T00:00:00+00:00','listing_available_at':'2026-01-01T00:00:00+00:00','delisted_at':None,'delisting_available_at':None}
r=build_daily_dataset([{'payload_bytes':raw,'sha256':hashlib.sha256(raw).hexdigest(),'received_at':stamp}],symbol='SPY',asset_class='US_ETF',universe=universe,dataset_id='packaging-fixture',version='v1',asof=stamp,fixture_mode='SYNTHETIC_REPLAY',price_policy='UNADJUSTED',session_scope='REGULAR_ONLY')
assert r.review.status=='ACCEPTED_SYNTHETIC' and len(r.review.observations)==2
assert json.loads(r.audit_bytes)['production_approved'] is False
print('PASS')"""
    result = subprocess.run([sys.executable, '-c', code, str(clean)], cwd=clean, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    assert result.stdout.strip() == 'PASS'
