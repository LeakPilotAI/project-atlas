"""Known computation failures should not create partial immutable publications."""
from datetime import datetime

import pytest
from app.backtest import forecast_cli as cli
from test_afi_baselines import ASOF, ASSET
from test_afi_cli import inputs as single_inputs
from test_afi_probability_holdout import files as holdout_inputs
from test_afi_probability_replay import inputs as replay_inputs


@pytest.mark.parametrize('mode', ['single','replay','holdout'])
def test_render_failure_precedes_any_new_publication(tmp_path,monkeypatch,mode):
    error = ValueError('synthetic render computation failure')
    def fail(*args, **kwargs): raise error
    if mode == 'single':
        manifest,records,root = single_inputs(tmp_path)
        arguments = {'manifest':manifest,'records':records,'output_root':root,'asset_id':ASSET,
                     'issued_at':datetime.fromisoformat('2026-10-01T00:01:00+00:00'),'evidence_asof':ASOF,'lookback':5}
        operation,renderer = cli.run,'render_dashboard'
    elif mode == 'replay':
        arguments = replay_inputs(tmp_path)
        root = arguments['output_root']
        operation,renderer = cli.run_probability_replay,'render_probability_replay'
    else:
        arguments = holdout_inputs(tmp_path)
        created = cli.run_probability_protocol(**arguments)
        root = arguments['output_root']
        arguments.pop('plan')
        arguments.update(protocol_path=root/created['protocol'],expected_protocol_sha256=created['protocol_sha256'])
        operation,renderer = cli.run_probability_holdout,'render_probability_holdout'
    before = {p.name:p.read_bytes() for p in root.iterdir()}
    monkeypatch.setattr(cli,renderer,fail)
    with pytest.raises(ValueError) as captured: operation(**arguments)
    assert captured.value is error
    assert {p.name:p.read_bytes() for p in root.iterdir()} == before
