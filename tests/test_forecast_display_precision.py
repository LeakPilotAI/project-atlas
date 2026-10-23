"""No two-decimal rounding of positive crypto prices or nominal intervals."""
from app.backtest import forecast_dashboard as dashboard


def test_comparison_renders_exact_small_prices_and_nominal_level(monkeypatch):
    row={'asset_id':'CRYPTO:TINY-USD','method':'NO_CHANGE','horizon':'1D','issued_at':'2026-10-20T00:00:00Z','target_at':'2026-10-21T00:00:00Z','currency':'USD','reference':.000123456789,'point':.000123456791,'implied_change_percent':.0000016200001,'lower':.000123456781,'upper':.000123456799,'interval_level':.955,'probability_up':None,'probability_method':None,'actual':None,'status':'PENDING','absolute_error':None,'relative_error_percent':None,'training_n':20,'dataset_version':'v1','accuracy_status':'INSUFFICIENT_EVIDENCE','manifest_sha256':'a'*64,'forecast_sha256':'b'*64,'source_binding':'UNBOUND_LEGACY_DIAGNOSTIC','release_source_sha256':None}
    monkeypatch.setattr(dashboard,'compare_forecasts',lambda *a,**kw:{'rows':[row],'asof':'2026-10-20T00:00:00Z'})
    html=dashboard.render_dashboard([],evidence_asof=None)
    for key in ('reference','point','lower','upper','interval_level','implied_change_percent'):
        assert str(row[key]) in html
    assert '>0.00<' not in html and '>Unavailable<' in html
    assert '<script' not in html


def test_resolved_comparison_exposes_existing_errors_without_recalculation():
    original=dashboard.compare_forecasts
    from test_afi_baselines import ASOF, fit, history
    review=history();entries=[(review,fit(review))]
    report=original(entries,evidence_asof=ASOF)
    html=dashboard.render_dashboard(entries,evidence_asof=ASOF)
    assert 'Absolute error (price units)' in html
    assert 'Absolute percentage error (%)' in html
    for row in report['rows']:
        for key in ('absolute_error','relative_error_percent'):
            value='Unavailable' if row[key] is None else str(row[key])
            assert '<td>'+value+'</td>' in html
    assert report['pooled_price_error'] is None and report['ranking'] is None
