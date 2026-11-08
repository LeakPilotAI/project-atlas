from pathlib import Path
import pytest
from scripts.observation_runtime import qd_free_research_acquisition as probe


def test_missing_real_contact_refused_before_credentials(monkeypatch):
    monkeypatch.setattr(probe.Credentials, "load", lambda _: pytest.fail("credentials accessed"))
    with pytest.raises(ValueError, match="QD_REAL_SYMBOL_AND_SEC_CONTACT_REQUIRED"):
        probe.inspect_free_research(symbol="MSFT", contact=None, credentials_path=Path("unused"))


def test_real_data_diagnostic_does_not_promote_operational_authority(monkeypatch):
    monkeypatch.setattr(probe.Credentials, "load", lambda _: object())
    class Client:
        domain = "TLS_PUBLIC_PROVIDER"
        def __init__(self, **kwargs):
            assert kwargs["max_attempts"] == 12 and kwargs["seconds"] == 60
    class Metric:
        availability = False
    class Bundle:
        def __init__(self, **kwargs): pass
        def load(self, symbol):
            assert symbol == "MSFT"
            return {"paper_eligible": False, "receipts": [{"id": 1}], "bars": [1,2],
                    "valuation": {k: Metric() for k in ("target_low_price", "target_mean_price", "target_high_price")},
                    "fundamentals": {"revenue": 1},
                    "refusals": ["NO_THREE_EXPLICIT_ACCEPTED_NORMALIZATION_ESTIMATES"]}
    result = probe.inspect_free_research(
        symbol="MSFT", contact="ProjectAtlas/1.0 operator@realmail.org",
        credentials_path=Path("unused"), client_factory=Client, bundle_factory=Bundle)
    assert result["completed_daily_bar_count"] == 2
    assert result["normalization_estimates_accepted"] is False
    assert result["normalization_source_count"] == 0
    assert not any(result["explicit_target_availability"].values())
    assert result["operational_source_accepted"] is False
    assert result["paper_fill_authorized"] is False


def test_synthetic_transport_cannot_pass_as_real(monkeypatch):
    monkeypatch.setattr(probe.Credentials, "load", lambda _: object())
    class Client:
        domain = "SYNTHETIC"
        def __init__(self, **kwargs): pass
    with pytest.raises(ValueError, match="QD_REAL_PROVIDER_TRANSPORT_REQUIRED"):
        probe.inspect_free_research(
            symbol="MSFT", contact="ProjectAtlas/1.0 operator@realmail.org",
            credentials_path=Path("unused"), client_factory=Client)

def test_bounded_universe_deduplicates_and_never_promotes():
    from app.investment.free_research_transport import ResearchRefused
    with pytest.raises(ResearchRefused):
        probe.inspect_bounded_universe(symbols=['MSFT', 'MSFT'], contact='unused', credentials_path=None)
    with pytest.raises(ResearchRefused):
        probe.inspect_bounded_universe(symbols=['MSFT'] * 9, contact='unused', credentials_path=None)
    calls = []
    def inspect(*, symbol, **kwargs):
        calls.append(symbol)
        if symbol == 'AVGO':
            raise ResearchRefused('SOURCE_UNAVAILABLE')
        return {'schema': 'ATLAS_QD_FREE_RESEARCH_ACQUISITION_V1', 'symbol': symbol, 'transport': 'TLS_PUBLIC_PROVIDER', 'operational_source_accepted': False, 'paper_fill_authorized': False, 'live_order_authorized': False}
    result = probe.inspect_bounded_universe(symbols=['MSFT', 'AVGO'], contact='unused',
                                            credentials_path=None, inspect=inspect)
    assert calls == ['MSFT', 'AVGO']
    assert result['results'][1]['status'] == 'REFUSED'
    assert result['operational_source_accepted'] is result['paper_fill_authorized'] is False


def test_bounded_universe_rejects_cross_symbol_or_unverified_transport():
    def impostor(*, symbol, **kwargs):
        return {'schema': 'ATLAS_QD_FREE_RESEARCH_ACQUISITION_V1', 'symbol': 'OTHER',
                'transport': 'SYNTHETIC', 'operational_source_accepted': False,
                'paper_fill_authorized': False, 'live_order_authorized': False}
    result = probe.inspect_bounded_universe(symbols=['MSFT'], contact='unused',
                                            credentials_path=None, inspect=impostor)
    assert result['acquired_count'] == 0
    assert result['refused_count'] == 1
    assert result['results'][0]['status'] == 'REFUSED'
    assert result['paper_fill_authorized'] is False


def test_partial_bounded_scan_returns_nonzero_for_supervisor(monkeypatch, capsys):
    monkeypatch.setattr(probe, 'inspect_bounded_universe', lambda **kwargs: {
        'schema': 'ATLAS_QD_BOUNDED_RESEARCH_UNIVERSE_V1',
        'refused_count': 1, 'results': [{'symbol': 'AVGO', 'status': 'REFUSED'}],
        'paper_fill_authorized': False})
    assert probe.main(['--symbols', 'AVGO', '--sec-contact', 'ProjectAtlas/1.0 operator@realmail.org']) == 2
    import json
    assert json.loads(capsys.readouterr().out)['refused_count'] == 1


def test_prices_only_etf_diagnostic_never_requires_sec_companyfacts(monkeypatch):
    monkeypatch.setattr(probe.Credentials,'load',lambda _:object())
    class Client:
        domain='TLS_PUBLIC_PROVIDER'
        def __init__(self,**kwargs):
            assert kwargs['max_attempts']==12
    class Bundle:
        def __init__(self,**kwargs): pass
        def load(self,symbol,*,prices_only=False):
            assert symbol=='SPY' and prices_only is True
            return {'paper_eligible':False,'bars':[1,2,3],'receipts':[{'id':1}]}
    result=probe.inspect_prices_only(symbol='SPY',contact='ProjectAtlas/1.0 operator@realmail.org',
                                     credentials_path=Path('unused'),client_factory=Client,bundle_factory=Bundle)
    assert result['completed_daily_bar_count']==3
    assert result['fundamentals_available'] is False
    assert result['independent_analyst_targets_verified'] is False
    assert result['paper_fill_authorized'] is False

def test_prices_only_refuses_paper_eligible_data(monkeypatch):
    monkeypatch.setattr(probe.Credentials,'load',lambda _:object())
    class Client:
        domain='TLS_PUBLIC_PROVIDER'
        def __init__(self,**kwargs): pass
    class Bundle:
        def __init__(self,**kwargs): pass
        def load(self,symbol,*,prices_only=False):
            return {'paper_eligible':True,'bars':[],'receipts':[]}
    with pytest.raises(ValueError,match='QD_PRICE_ONLY_EVIDENCE_INCOMPLETE_OR_UNAUTHORIZED'):
        probe.inspect_prices_only(symbol='SPY',contact='ProjectAtlas/1.0 operator@realmail.org',
                                  credentials_path=Path('unused'),client_factory=Client,bundle_factory=Bundle)

def test_prices_only_cli_rejects_duplicate_universe_before_credentials(monkeypatch,capsys):
    monkeypatch.setattr(probe.Credentials,'load',lambda _:pytest.fail('credentials accessed'))
    assert probe.main(['--prices-only','--symbols','SPY','SPY'])==1
    assert 'REFUSED' in capsys.readouterr().out


def test_bounded_prices_only_partial_failure_is_not_success():
    from app.investment.free_research_transport import ResearchRefused
    def inspect(*,symbol,**kwargs):
        if symbol=='IWM':
            raise ResearchRefused('UNAVAILABLE')
        return {'schema':'ATLAS_QD_PRICE_ONLY_RESEARCH_V1','symbol':symbol,
                'completed_daily_bar_count':3,'provider_receipt_count':2,
                'fundamentals_available':False,'independent_analyst_targets_verified':False,
                'operational_source_accepted':False,'paper_fill_authorized':False,
                'live_order_authorized':False}
    result=probe.inspect_bounded_prices_only(symbols=['SPY','IWM'],contact=None,
                                              credentials_path=None,inspect=inspect)
    assert result['acquired_count']==1 and result['refused_count']==1
    assert result['paper_fill_authorized'] is False


def test_bounded_prices_only_refuses_authority_promotion():
    def inspect(*,symbol,**kwargs):
        return {'schema':'ATLAS_QD_PRICE_ONLY_RESEARCH_V1','symbol':symbol,
                'completed_daily_bar_count':3,'provider_receipt_count':2,
                'fundamentals_available':False,'independent_analyst_targets_verified':False,
                'operational_source_accepted':True,'paper_fill_authorized':False,
                'live_order_authorized':False}
    result=probe.inspect_bounded_prices_only(symbols=['SPY'],contact=None,
                                              credentials_path=None,inspect=inspect)
    assert result['refused_count']==1


def test_prices_only_does_not_require_sec_contact(monkeypatch):
    monkeypatch.setattr(probe.Credentials,'load',lambda _:object())
    class Client:
        domain='TLS_PUBLIC_PROVIDER'
        def __init__(self,**kwargs):
            assert kwargs['sec_user_agent']=='ProjectAtlas/1.0 prices-only-no-sec'
    class Bundle:
        def __init__(self,**kwargs): pass
        def load(self,symbol,*,prices_only=False):
            assert symbol=='SPY' and prices_only
            return {'paper_eligible':False,'bars':[1],'receipts':[{'id':1}]}
    result=probe.inspect_prices_only(symbol='SPY',contact=None,credentials_path=Path('unused'),
                                     client_factory=Client,bundle_factory=Bundle)
    assert result['operational_source_accepted'] is False

@pytest.mark.parametrize('symbol',['SPY\n','',None,'SPY/US'])
def test_prices_only_rejects_bad_symbol_before_credentials(monkeypatch,symbol):
    monkeypatch.setattr(probe.Credentials,'load',lambda _:pytest.fail('credentials accessed'))
    with pytest.raises(ValueError,match='QD_REAL_SYMBOL_REQUIRED'):
        probe.inspect_prices_only(symbol=symbol,contact=None,credentials_path=Path('unused'))


def test_bounded_prices_only_cli_partial_failure_exit_two(monkeypatch,capsys):
    monkeypatch.setattr(probe,'inspect_bounded_prices_only',lambda **kwargs:{
        'schema':'ATLAS_QD_BOUNDED_PRICES_ONLY_V1','refused_count':1,
        'results':[{'symbol':'IWM','status':'REFUSED'}],
        'paper_fill_authorized':False})
    assert probe.main(['--prices-only','--symbols','SPY','IWM'])==2
    import json
    assert json.loads(capsys.readouterr().out)['refused_count']==1


def test_bounded_prices_only_cli_all_success_exit_zero(monkeypatch,capsys):
    monkeypatch.setattr(probe,'inspect_bounded_prices_only',lambda **kwargs:{
        'schema':'ATLAS_QD_BOUNDED_PRICES_ONLY_V1','refused_count':0,
        'results':[{'symbol':'SPY'}],'paper_fill_authorized':False})
    assert probe.main(['--prices-only','--symbols','SPY'])==0
    import json
    assert json.loads(capsys.readouterr().out)['refused_count']==0


def test_bounded_prices_only_bad_provider_count_refused():
    def inspect(*,symbol,**kwargs):
        return {'schema':'ATLAS_QD_PRICE_ONLY_RESEARCH_V1','symbol':symbol,
                'completed_daily_bar_count':True,'provider_receipt_count':2,
                'fundamentals_available':False,'independent_analyst_targets_verified':False,
                'operational_source_accepted':False,'paper_fill_authorized':False,
                'live_order_authorized':False}
    result=probe.inspect_bounded_prices_only(symbols=['SPY'],contact=None,
                                              credentials_path=None,inspect=inspect)
    assert result['refused_count']==1


@pytest.mark.parametrize('bars,receipts',[(0,2),(3,0),(-1,2),(3,-1)])
def test_bounded_prices_only_empty_or_missing_evidence_is_refused(bars,receipts):
    def inspect(*,symbol,**kwargs):
        return {'schema':'ATLAS_QD_PRICE_ONLY_RESEARCH_V1','symbol':symbol,
                'completed_daily_bar_count':bars,'provider_receipt_count':receipts,
                'fundamentals_available':False,'independent_analyst_targets_verified':False,
                'operational_source_accepted':False,'paper_fill_authorized':False,
                'live_order_authorized':False}
    result=probe.inspect_bounded_prices_only(symbols=['SPY'],contact=None,
                                              credentials_path=None,inspect=inspect)
    assert result['acquired_count']==0 and result['refused_count']==1


@pytest.mark.parametrize('bars,receipts', [([], [{'id':1}]), ([1], []), ([1], None)])
def test_single_prices_only_rejects_empty_or_missing_evidence(monkeypatch,bars,receipts):
    monkeypatch.setattr(probe.Credentials,'load',lambda _:object())
    class Client:
        domain='TLS_PUBLIC_PROVIDER'
        def __init__(self,**kwargs): pass
    class Bundle:
        def __init__(self,**kwargs): pass
        def load(self,symbol,*,prices_only=False):
            return {'paper_eligible':False,'bars':bars,'receipts':receipts}
    with pytest.raises(ValueError,match='QD_PRICE_ONLY_EVIDENCE_INCOMPLETE_OR_UNAUTHORIZED'):
        probe.inspect_prices_only(symbol='SPY',contact=None,credentials_path=Path('unused'),
                                  client_factory=Client,bundle_factory=Bundle)


@pytest.mark.parametrize('error,category',[
    (OSError('secret-bearing transport URL'),'PROVIDER_IO_FAILURE'),
    (KeyError('secret-header'),'MALFORMED_PROVIDER_DATA'),
    (TypeError('secret token'),'MALFORMED_PROVIDER_DATA'),
    (ValueError('QD_PRICE_ONLY_EVIDENCE_INCOMPLETE_OR_UNAUTHORIZED'),'MISSING_RESEARCH_EVIDENCE'),
    (ValueError('provider secret message'),'PROVIDER_REFUSED_OR_UNAVAILABLE'),
])
def test_bounded_prices_only_sanitizes_failure_category(error,category):
    def inspect(**kwargs):
        raise error
    result=probe.inspect_bounded_prices_only(symbols=['SPY'],contact=None,
                                              credentials_path=None,inspect=inspect)
    assert result['refused_count']==1
    assert result['results'][0]['failure_category']==category
    assert 'secret' not in str(result)


def test_repeated_prices_only_finite_partial_failure():
    calls=[]
    def batch(**kwargs):
        calls.append(1)
        failed=len(calls)==2
        return {'schema':'ATLAS_QD_BOUNDED_PRICES_ONLY_V1','symbols':['SPY'],
                'results':[{'symbol':'SPY','status':'REFUSED'} if failed else {'symbol':'SPY'}],
                'acquired_count':0 if failed else 1,'refused_count':1 if failed else 0,
                'operational_source_accepted':False,'paper_fill_authorized':False,
                'live_order_authorized':False}
    result=probe.inspect_repeated_prices_only(symbols=['SPY'],rounds=3,contact=None,
                                               credentials_path=None,inspect_batch=batch)
    assert len(calls)==3 and result['refused_count']==1
    assert result['rounds_completed']==3 and result['paper_fill_authorized'] is False

@pytest.mark.parametrize('rounds',[0,4,True,-1])
def test_repeated_prices_only_refuses_unbounded_rounds(rounds):
    with pytest.raises(ValueError,match='QD_DIAGNOSTIC_ROUNDS_BOUNDED_REQUIRED'):
        probe.inspect_repeated_prices_only(symbols=['SPY'],rounds=rounds,contact=None,
                                           credentials_path=None,inspect_batch=lambda **kwargs:pytest.fail('called'))

def test_repeated_prices_only_cli_requires_research_universe(capsys):
    assert probe.main(['--diagnostic-rounds','2','--symbol','SPY'])==1
    assert 'REFUSED' in capsys.readouterr().out

def test_repeated_prices_only_cli_partial_exit_two(monkeypatch,capsys):
    monkeypatch.setattr(probe,'inspect_repeated_prices_only',lambda **kwargs:{
        'schema':'ATLAS_QD_REPEATED_PRICES_ONLY_V1','refused_count':1})
    assert probe.main(['--prices-only','--symbols','SPY','--diagnostic-rounds','2'])==2


def test_cli_bounded_price_journal_append(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(probe,'inspect_bounded_prices_only',lambda **kwargs:{
        'schema':'ATLAS_QD_BOUNDED_PRICES_ONLY_V1','symbols':['SPY'],
        'results':[{'symbol':'SPY','provider_secret':'do-not-save'}],
        'acquired_count':1,'refused_count':0,
        'operational_source_accepted':False,'paper_fill_authorized':False,
        'live_order_authorized':False})
    journal=tmp_path/'diagnostic.jsonl'
    assert probe.main(['--prices-only','--symbols','SPY','--diagnostic-journal',str(journal)])==0
    import json
    assert json.loads(journal.read_text().splitlines()[0])['symbols']==['SPY']
    assert 'do-not-save' not in journal.read_text()

def test_cli_journal_write_failure_is_nonzero(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(probe,'inspect_bounded_prices_only',lambda **kwargs:{
        'schema':'ATLAS_QD_BOUNDED_PRICES_ONLY_V1','symbols':['SPY'],
        'results':[{'symbol':'SPY'}], 'acquired_count':1,'refused_count':0,
        'operational_source_accepted':False,'paper_fill_authorized':False,
        'live_order_authorized':False})
    assert probe.main(['--prices-only','--symbols','SPY','--diagnostic-journal',
                       str(tmp_path/'missing'/'journal.jsonl')])==3
    assert 'ATLAS_QD_JOURNAL_FAILURE_V1' in capsys.readouterr().out

def test_cli_journal_requires_bounded_prices_only(tmp_path,capsys):
    assert probe.main(['--symbol','SPY','--diagnostic-journal',str(tmp_path/'journal')])==1
