"""Run the actual daily export CLI from a clean, hash-checked source archive."""
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from test_daily_afi_export import bundle
from test_daily_forecast_batch import inputs as forecast_inputs
from test_daily_probability_protocol import _freeze_request, _holdout_request
from test_daily_probability_replay import inputs as replay_inputs
from test_offline_candidate_packaging import candidate, fixture_root

BACKTEST = ('__init__ historical forecast_artifacts forecast_baselines forecast_cli '
            'forecast_comparison forecast_dashboard forecast_dataset forecast_evaluation '
            'forecast_outcomes forecast_replay forecast_report forecast_source forecast_uncertainty')
OBSERVATION = ('__init__ chart_archive chart_provenance contracts daily_afi_bridge daily_afi_export daily_availability daily_forecast_batch daily_forecast_visual daily_holdout_accountability daily_holdout_update daily_holdout_visual daily_probability_replay '
               'history market_refusals market_replay quality_report quote_quality '
               'r7e47cm_equities_snapshot r7e47cp_market_signals retained_research session_quality')
FILES = (['backend/app/__init__.py', 'frontend/offline/forecast-accountability/view.cjs'] +
         ['backend/app/backtest/'+name+'.py' for name in BACKTEST.split()] +
         ['scripts/observation_runtime/'+name+'.py' for name in OBSERVATION.split()] +
         ['backend/app/'+name+'.py' for name in (
             'core/__init__', 'core/durable_io', 'investment/__init__',
             'investment/extended_hours_integrity', 'investment/market_hours',
             'investment/offline_research', 'services/__init__', 'services/paper_execution_model')])

CHILD = """import sys,pathlib,os
root=pathlib.Path(sys.argv[1]).resolve();repo=pathlib.Path(sys.argv[2]).resolve()
tzdata=(pathlib.Path(sys.prefix)/'Lib/site-packages/tzdata').resolve()
sys.path[:0]=[str(root/'backend'),str(root)]
def guard(event,args):
 if event=='socket.connect':raise PermissionError('offline extracted CLI cannot connect')
 if event=='open' and isinstance(args[0],(str,bytes)):
  p=pathlib.Path(os.fsdecode(args[0])).resolve()
  if p.is_relative_to(repo) and not p.is_relative_to(root) and not p.is_relative_to(tzdata):
   raise PermissionError('extracted CLI cannot read original repository')
sys.addaudithook(guard)
import app
from scripts.observation_runtime import daily_afi_export
assert pathlib.Path(app.__file__).resolve().is_relative_to(root)
assert pathlib.Path(daily_afi_export.__file__).resolve().is_relative_to(root)
raise SystemExit(daily_afi_export.main(sys.argv[3:]))
"""


def extracted(tmp_path, monkeypatch):
    source, _ = fixture_root(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[1]
    for name in FILES:
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((repo/name).read_bytes())
    previous = candidate.git
    monkeypatch.setattr(candidate, 'git', lambda *args: previous(*args)+FILES if '--others' in args else previous(*args))
    first = candidate.build(tmp_path/'candidate')
    assert first == candidate.build(tmp_path/'candidate-repeated')
    clean = tmp_path/'clean'
    with zipfile.ZipFile(tmp_path/'candidate/atlas-source.zip') as archive:
        archive.extractall(clean)
    manifest = json.loads((clean/'release-manifest.json').read_bytes())
    assert manifest['activation_approved'] is False
    for item in manifest['files']:
        raw = (clean/item['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == item['sha256']
        assert len(raw) == item['bytes']
    assert all((clean/name).is_file() for name in FILES)
    return clean, repo


def invoke(clean, repo, args):
    return subprocess.run([sys.executable, '-I', '-c', CHILD, str(clean), str(repo), *args],
                          cwd=clean, capture_output=True, text=True, timeout=20, check=False)


@pytest.mark.parametrize('mode', ['roundtrip', 'action-receipts', 'tampered-artifact', 'missing-source', 'invalid-mode', 'live-policy'])
def test_clean_extracted_daily_export(tmp_path, monkeypatch, mode):
    clean, repo = extracted(tmp_path, monkeypatch)
    storage = clean/'synthetic-inputs'
    storage.mkdir()
    request = bundle(storage)
    if mode == 'action-receipts':
        raw = json.dumps({'schema': 'ATLAS_SYNTHETIC_CORPORATE_ACTIONS_V1', 'asset_id': 'ETF:SPY',
                          'actions': [
                              {'action_id': 'split-1', 'kind': 'SPLIT',
                               'effective_at': '2026-10-20T21:00:00+00:00', 'amount': 2,
                               'economic_unit': 'NEW_SHARES_PER_OLD_SHARE'},
                              {'action_id': 'dividend-1', 'kind': 'DIVIDEND',
                               'effective_at': '2026-10-20T21:00:00+00:00', 'amount': 0.5,
                               'economic_unit': 'USD_PER_SHARE'},
                          ]},
                         sort_keys=True, separators=(',', ':')).encode()
        pin = hashlib.sha256(raw).hexdigest()
        (storage/(pin+'.json')).write_bytes(raw)
        request['action_snapshots'] = [{'file': pin+'.json', 'sha256': pin,
                                        'received_at': '2026-10-20T22:00:00+00:00',
                                        'source_id': 'fixture-actions'}]
        request['asof'] = '2026-10-20T23:00:00+00:00'
        (storage/'request.json').write_text(json.dumps(request), encoding='utf-8')
    args = ['--bundle-root', str(storage), '--request', 'request.json', '--output-root', str(storage)]
    if mode == 'invalid-mode':
        result = invoke(clean, repo, args[:-2])
        assert result.returncode == 2
        assert 'Export requires output root' in result.stderr
        return
    if mode == 'live-policy':
        request['fixture_mode'] = 'LIVE'
        (storage/'request.json').write_text(json.dumps(request), encoding='utf-8')
        result = invoke(clean, repo, args)
        assert result.returncode == 2
        assert 'Daily export refused' in result.stderr
        assert len(list(storage.iterdir())) == 2
        return
    result = invoke(clean, repo, args)
    assert result.returncode == 0, result.stdout+result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['startup_authorized'] is False
    assert receipt['trading_authorized'] is False
    if mode == 'action-receipts':
        binding_value = json.loads((storage/receipt['binding']).read_bytes())
        audit = json.loads((storage/binding_value['artifacts']['audit']).read_bytes())
        dataset = json.loads((storage/binding_value['artifacts']['records']).read_bytes())
        assert binding_value['request']['action_snapshots'] == request['action_snapshots']
        assert audit['corporate_action_event_n'] == 2
        assert {row['kind'] for row in dataset['actions']} == {'SPLIT', 'DIVIDEND'}
        assert audit['corporate_action_provenance'][0]['source_id'] == 'fixture-actions'
    binding = receipt['binding']
    verify = ['--bundle-root', str(storage), '--verify-binding', binding,
              '--expected-binding-sha256', binding[:-5]]
    if mode == 'tampered-artifact':
        value = json.loads((storage/binding).read_bytes())
        (storage/value['artifacts']['records']).write_bytes(b'{}')
    elif mode == 'missing-source':
        (storage/request['snapshots'][0]['file']).rename(storage/'preserved-missing-source.json')
    else:
        before = {p.name: p.read_bytes() for p in storage.iterdir()}
        again = invoke(clean, repo, args)
        assert again.returncode == 0, again.stderr
        assert json.loads(again.stdout) == receipt
        assert before == {p.name: p.read_bytes() for p in storage.iterdir()}
    result = invoke(clean, repo, verify)
    assert result.returncode == (0 if mode in ('roundtrip', 'action-receipts') else 2), result.stdout+result.stderr
    if mode in ('roundtrip', 'action-receipts'):
        assert json.loads(result.stdout) == receipt
    else:
        assert 'Daily export refused' in result.stderr
        assert (storage/binding).is_file()


def test_clean_extracted_stock_etf_forecast_dashboard(tmp_path, monkeypatch):
    clean, repo = extracted(tmp_path, monkeypatch)
    storage = clean/'synthetic-inputs'
    storage.mkdir()
    forecast_inputs(storage)
    child = CHILD.replace('daily_afi_export', 'daily_forecast_batch')
    result = subprocess.run([sys.executable, '-I', '-c', child, str(clean), str(repo),
                             '--bundle-root', str(storage), '--request', 'forecast-request.json',
                             '--output-root', str(storage)],
                            cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['forecast_n'] == 4 and receipt['unique_asset_n'] == 2
    assert receipt['production_approved'] is receipt['startup_authorized'] is False
    index = json.loads((storage/receipt['index']).read_bytes())
    assert all(item['status'] == 'PUBLISHED_VERIFIED' for item in index['items'])
    assert all(asset in (storage/receipt['dashboard']).read_text(encoding='utf-8')
               for asset in ['US_EQUITY:AAPL', 'ETF:SPY'])
    before = {p.name: p.read_bytes() for p in storage.iterdir()}
    verified = subprocess.run([sys.executable, '-I', '-c', child, str(clean), str(repo),
                               '--bundle-root', str(storage), '--verify-receipt', receipt['daily_receipt'],
                               '--expected-receipt-sha256', receipt['daily_receipt'][:-5]],
                              cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert verified.returncode == 0, verified.stdout+verified.stderr
    assert json.loads(verified.stdout)['status'] == 'SYNTHETIC_DAILY_FORECAST_RECEIPT_REPRODUCED'
    assert before == {p.name: p.read_bytes() for p in storage.iterdir()}
    visual_child = CHILD.replace('daily_afi_export', 'daily_forecast_visual').replace(
        'raise SystemExit(daily_forecast_visual.main(sys.argv[3:]))',
        "import json\nprint(json.dumps(daily_forecast_visual.publish_daily_forecast_visual(bundle_root=sys.argv[3],receipt_name=sys.argv[4],expected_receipt_sha256=sys.argv[4][:-5],output_root=sys.argv[3],availability_budget_seconds=60)))")
    visualized = subprocess.run([sys.executable, '-I', '-c', visual_child, str(clean), str(repo),
                                 str(storage), receipt['daily_receipt']],
                                cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert visualized.returncode == 0, visualized.stdout+visualized.stderr
    companion = json.loads(visualized.stdout)
    assert companion['html'] != receipt['dashboard']
    assert companion['native_browser_acceptance'] == 'NOT_ESTABLISHED'
    assert (storage/companion['html']).read_text(encoding='utf-8').count('<svg ') == 4
    assert (storage/companion['html']).read_text(encoding='utf-8').count('SINGLE_RECEIPT_HISTORICAL_BATCH') == 4
    assert all((storage/name).read_bytes() == raw for name, raw in before.items())


def test_clean_extracted_daily_probability_replay_retains_refusals(tmp_path, monkeypatch):
    clean, repo = extracted(tmp_path, monkeypatch)
    storage = clean/'synthetic-inputs'
    storage.mkdir()
    request = replay_inputs(storage)
    child = CHILD.replace('daily_afi_export', 'daily_probability_replay')
    result = subprocess.run([sys.executable, '-I', '-c', child, str(clean), str(repo),
                             '--bundle-root', str(storage), '--request', 'replay-request.json', '--output-root', str(storage)],
                            cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    receipt = json.loads(result.stdout)
    assert receipt['requested_n'] == 15 and receipt['issued_n'] == 12 and receipt['refused_n'] == 3
    companion = json.loads((storage/receipt['daily_companion']).read_bytes())
    assert companion['expected_issues_sha256'] == request['expected_issues_sha256']
    assert companion['startup_authorized'] is companion['source_authenticated'] is False
    before = {p.name: p.read_bytes() for p in storage.iterdir()}
    verified = subprocess.run([sys.executable, '-I', '-c', child, str(clean), str(repo),
                               '--bundle-root', str(storage), '--verify-companion', receipt['daily_companion'],
                               '--expected-companion-sha256', receipt['daily_companion'][:-5]],
                              cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert verified.returncode == 0, verified.stdout+verified.stderr
    assert json.loads(verified.stdout)['status'] == 'SYNTHETIC_SOURCE_DAILY_REPLAY_REPRODUCED'
    assert before == {p.name: p.read_bytes() for p in storage.iterdir()}


def test_clean_extracted_daily_probability_protocol_and_holdout(tmp_path, monkeypatch):
    clean, repo = extracted(tmp_path, monkeypatch)
    storage = clean/'synthetic-inputs'
    storage.mkdir()
    source, _ = _freeze_request(storage)
    child = CHILD.replace('daily_afi_export', 'daily_probability_replay')

    frozen = subprocess.run([sys.executable, '-I', '-c', child, str(clean), str(repo),
                             '--bundle-root', str(storage), '--freeze-protocol', 'protocol-request.json',
                             '--output-root', str(storage)],
                            cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert frozen.returncode == 0, frozen.stdout+frozen.stderr
    protocol_result = json.loads(frozen.stdout)
    assert protocol_result['status'] == 'OFFLINE_SYNTHETIC_PROTOCOL_COMPLETE'
    before_protocol = {path.name: path.read_bytes() for path in storage.iterdir()}
    protocol_verified = subprocess.run(
        [sys.executable, '-I', '-c', child, str(clean), str(repo),
         '--bundle-root', str(storage), '--verify-protocol', protocol_result['daily_protocol'],
         '--expected-companion-sha256', protocol_result['daily_protocol'][:-5]],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert protocol_verified.returncode == 0, protocol_verified.stdout+protocol_verified.stderr
    assert json.loads(protocol_verified.stdout)['status'] == 'SYNTHETIC_DAILY_PROBABILITY_PROTOCOL_REPRODUCED'
    assert before_protocol == {path.name: path.read_bytes() for path in storage.iterdir()}
    _holdout_request(storage, source, protocol_result)

    evaluated = subprocess.run([sys.executable, '-I', '-c', child, str(clean), str(repo),
                                '--bundle-root', str(storage), '--evaluate-holdout', 'holdout-request.json',
                                '--output-root', str(storage)],
                               cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert evaluated.returncode == 0, evaluated.stdout+evaluated.stderr
    holdout_result = json.loads(evaluated.stdout)
    assert holdout_result['resolved_n'] == 2
    before = {path.name: path.read_bytes() for path in storage.iterdir()}

    verified = subprocess.run([sys.executable, '-I', '-c', child, str(clean), str(repo),
                               '--bundle-root', str(storage), '--verify-holdout',
                               holdout_result['daily_holdout'], '--expected-companion-sha256',
                               holdout_result['daily_holdout'][:-5]],
                              cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert verified.returncode == 0, verified.stdout+verified.stderr
    assert json.loads(verified.stdout)['status'] == 'SYNTHETIC_DAILY_PROBABILITY_HOLDOUT_REPRODUCED'
    diagnostic = subprocess.run(
        [sys.executable, '-I', '-c', child, str(clean), str(repo),
         '--bundle-root', str(storage), '--diagnose-holdout', holdout_result['daily_holdout'],
         '--expected-companion-sha256', holdout_result['daily_holdout'][:-5]],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert diagnostic.returncode == 0, diagnostic.stdout+diagnostic.stderr
    assert json.loads(diagnostic.stdout)['counts']['resolved_n'] == 2
    coverage_child = CHILD.replace('daily_afi_export', 'daily_holdout_visual')
    coverage = subprocess.run(
        [sys.executable, '-I', '-c', coverage_child, str(clean), str(repo),
         '--bundle-root', str(storage), '--companion', holdout_result['daily_holdout'],
         '--expected-companion-sha256', holdout_result['daily_holdout'][:-5],
         '--output-root', str(storage)],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert coverage.returncode == 0, coverage.stdout+coverage.stderr
    coverage_result = json.loads(coverage.stdout)
    coverage_path = storage/coverage_result['html']
    assert coverage_result['startup_authorized'] is False
    assert 'Requested 2 = refused 0 + issued 2' in coverage_path.read_text(encoding='utf-8')
    coverage_path.rename(storage/'retained-coverage-outside-snapshot')
    # This explicit derived publication is new; all existing inputs remain identical.
    before['retained-coverage-outside-snapshot'] = (storage/'retained-coverage-outside-snapshot').read_bytes()
    assert before == {path.name: path.read_bytes() for path in storage.iterdir()}


def test_clean_extracted_holdout_accountability_workspace_bridge(tmp_path, monkeypatch):
    from test_daily_holdout_diagnostics import evaluate
    from test_daily_probability_protocol import _freeze

    clean, repo = extracted(tmp_path, monkeypatch)
    storage = clean/'synthetic-bridge-inputs'
    storage.mkdir()
    source, frozen = _freeze(storage)
    held = evaluate(storage, source, frozen)
    before = {path.name: path.read_bytes() for path in storage.iterdir()}
    child = CHILD.replace('daily_afi_export', 'daily_holdout_accountability')
    result = subprocess.run(
        [sys.executable, '-I', '-c', child, str(clean), str(repo),
         '--bundle-root', str(storage), '--companion', held['daily_holdout'],
         '--expected-companion-sha256', held['daily_holdout'][:-5], '--output-root', str(storage)],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stdout+result.stderr
    exported = json.loads(result.stdout)
    assert exported['counts']['resolved_n'] == 2
    assert exported['startup_authorized'] is False
    verification = subprocess.run(
        [sys.executable, '-I', '-c', child, str(clean), str(repo),
         '--bundle-root', str(storage), '--verify-bridge', exported['bridge'],
         '--expected-companion-sha256', exported['bridge'][:-5]],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert verification.returncode == 0, verification.stdout+verification.stderr
    assert json.loads(verification.stdout)['counts']['resolved_n'] == 2
    prepared = subprocess.run(
        [sys.executable, '-I', '-c', child, str(clean), str(repo),
         '--bundle-root', str(storage), '--prepare-continuation', exported['bridge'],
         '--expected-companion-sha256', exported['bridge'][:-5], '--output-root', str(storage)],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert prepared.returncode == 0, prepared.stdout+prepared.stderr
    seed = json.loads(prepared.stdout)
    assert seed['outcome_appends_performed'] == 0
    verified_seed = subprocess.run(
        [sys.executable, '-I', '-c', child, str(clean), str(repo),
         '--bundle-root', str(storage), '--verify-continuation', seed['companion'],
         '--expected-companion-sha256', seed['companion'][:-5]],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert verified_seed.returncode == 0, verified_seed.stdout+verified_seed.stderr
    assert json.loads(verified_seed.stdout)['original_counts']['requested_n'] == 2
    source_companion = json.loads((storage/held['daily_holdout']).read_bytes())
    holdout_report = json.loads((storage/source_companion['holdout_result']['report']).read_bytes())['replay']
    (storage/'updates').mkdir()
    update_request = {'schema': 'ATLAS_SYNTHETIC_HOLDOUT_UPDATE_REQUEST_V1',
        'seed': seed['companion'], 'expected_seed_sha256': seed['companion'][:-5],
        'continuation': seed['bundle'], 'expected_continuation_sha256': seed['bundle'][:-5],
        'daily_export': source['daily_export'], 'expected_daily_export_sha256': source['expected_daily_export_sha256'],
        'asof': holdout_report['asof'], 'outcome_asof': holdout_report['asof'], 'output_prefix': 'updates'}
    request_raw = json.dumps(update_request, sort_keys=True, separators=(',', ':')).encode()
    request_name = hashlib.sha256(request_raw).hexdigest()+'.json'
    (storage/request_name).write_bytes(request_raw)
    update_child = CHILD.replace('daily_afi_export', 'daily_holdout_update')
    before_preview = {str(p.relative_to(storage)):p.read_bytes() for p in storage.rglob('*') if p.is_file()}
    previewed = subprocess.run(
        [sys.executable, '-I', '-c', update_child, str(clean), str(repo),
         '--bundle-root', str(storage), '--preview', request_name],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert previewed.returncode == 0, previewed.stdout+previewed.stderr
    preview = json.loads(previewed.stdout)
    assert preview['published'] is False and preview['new_forecasts_created'] == 0
    assert preview['proposed_issued_states'] == {'RESOLVED':2}
    assert before_preview == {str(p.relative_to(storage)):p.read_bytes() for p in storage.rglob('*') if p.is_file()}
    updated = subprocess.run(
        [sys.executable, '-I', '-c', update_child, str(clean), str(repo),
         '--bundle-root', str(storage), '--request', request_name],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert updated.returncode == 0, updated.stdout+updated.stderr
    assert json.loads(updated.stdout)['current_issued_states'] == {'RESOLVED': 2}
    update_result = json.loads(updated.stdout)
    checked_update = subprocess.run(
        [sys.executable, '-I', '-c', update_child, str(clean), str(repo),
         '--bundle-root', str(storage), '--verify', update_result['companion'],
         '--expected-companion-sha256', update_result['companion'].split('/')[-1][:-5]],
        cwd=clean, capture_output=True, text=True, timeout=30, check=False)
    assert checked_update.returncode == 0, checked_update.stdout+checked_update.stderr
    assert json.loads(checked_update.stdout)['status'] == 'SYNTHETIC_HOLDOUT_LABEL_UPDATE_REPRODUCED'
    browser = json.loads((storage/exported['browser_export']).read_bytes())
    assert browser['schema'] == 'AFI_BROWSER_REPORT_V1'
    # Exercise the actual extracted viewer against both CLI-produced envelopes.
    # No original-repository module or browser/server is used.
    viewer_script = r"""const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=process.argv[1],api=require(path.join(root,'frontend/offline/forecast-accountability/view.cjs'));
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
Promise.all(process.argv.slice(2).map(name=>api.verifyEnvelope(fs.readFileSync(name,'utf8'),hash))).then(([a,b])=>{
process.stdout.write(JSON.stringify({left_n:a.forecast_n,right_n:b.forecast_n,
left:api.signedErrorDiagnostics(a.rows),right:api.signedErrorDiagnostics(b.rows),impact:api.signedErrorVintageImpact(a,b),
plots:[a,b].map(r=>api.forecastPlot(r.rows).cohorts.map(c=>api.forecastPlot(r.rows,c.id))),
signed_rows:b.rows.map(r=>({forecast_sha256:r.forecast_sha256,actual:r.actual,error:r.status==='RESOLVED'?r.forecast_point-r.actual:null}))}));
}).catch(e=>{console.error(e);process.exitCode=1});"""
    loaded = subprocess.run(
        ['C:/Program Files/nodejs/node.exe', '-e', viewer_script, str(clean),
         str(storage/exported['browser_export']), str(storage/update_result['browser_export'])],
        cwd=clean, capture_output=True, text=True, timeout=15, check=False)
    assert loaded.returncode == 0, loaded.stdout+loaded.stderr
    visible = json.loads(loaded.stdout)
    assert visible['left_n'] == visible['right_n'] == 2
    assert sum(c['resolved_n'] for c in visible['right']['cohorts']) == 2
    assert len(visible['impact']['rows']) == 2
    assert visible['impact']['history_ancestry_verified'] is False
    assert visible['impact']['production_approved'] is False
    for plots in visible['plots']:
        assert sum(len(plot['points']) for plot in plots) == 2
        for plot in plots:
            assert plot['status'] == 'DISPLAYED' and plot['unbound_n'] == 0
            assert plot['predictive_skill_established'] is False
            assert len({point['row']['asset_id'] for point in plot['points']}) == 1
            assert all(point['actual'] is not None for point in plot['points'])
    signed_rows = {row['forecast_sha256']:row for row in visible['signed_rows']}
    assert len(signed_rows) == preview['current_issued_n'] == 2
    for plot in visible['plots'][1]:
        for point in plot['points']:
            assert point['row']['actual'] == signed_rows[point['row']['forecast_sha256']]['actual']
    for case in preview['cases']:
        row = signed_rows[case['forecast_sha256']]
        assert case['signed_error_impact']['proposed_actual'] == row['actual']
        assert case['signed_error_impact']['proposed_signed_error'] == row['error']

    assert all(row['state'] == 'FINITE' and row['right_minus_left_signed_error'] == 0
               for row in visible['impact']['rows'])
    assert all((storage/name).read_bytes() == raw for name, raw in before.items())
