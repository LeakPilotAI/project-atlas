"""Pure publication-port race tests. No stores, providers, accounts or hosts."""
import copy
from types import SimpleNamespace

import pytest
from app.services.quality_dips_publication_reader import QualityDipsPublicationReader


def fixture():
    now = [100]
    cut = {'state': {'positions': {}}}
    packet = {'schema': 'QD_SCANNER_PUBLICATION_V1', 'source_id': 'SYNTHETIC', 'revision': 1,
              'observed_at': 100, 'bundles': [], 'monitors': {}}
    authority = SimpleNamespace(verify_publication_components=lambda *args: True,
                                verify_scanner_publication=lambda *args: True)
    runtime = SimpleNamespace(grant={}, stopped=SimpleNamespace(is_set=lambda: False), halted=False,
                              _now=lambda: now[0])
    writer = SimpleNamespace(authority=authority, binding={}, runtime=SimpleNamespace(runtime=runtime),
                             _cut=lambda: copy.deepcopy(cut))
    source = SimpleNamespace(read_publication=lambda timeout: copy.deepcopy(packet))
    reader = QualityDipsPublicationReader(writer=writer, source=source)
    return SimpleNamespace(**locals())


def test_valid_empty_publication_is_healthy_no_signal():
    s = fixture()
    assert s.reader.read_request(.2) is None
    assert s.reader._last[1] == 1


def test_authenticated_no_entry_monitor_keeps_observation_without_inventing_candidate():
    s = fixture()
    from test_quality_dips_integration_v1 import bundle_for
    for symbol in ('SPY','MSFT'):
        _m, bundle, _now = bundle_for(symbol, 'ETF' if symbol == 'SPY' else 'STOCK')
        instrument = bundle['instrument']
        s.packet['monitors'][instrument['instrument_id']] = {
            'instrument': instrument, 'symbol': symbol, 'observed_at':100,
            'current': {'evidence_quality':'UNAVAILABLE'}}
    result = s.reader.read_request(.2)
    assert result['instrument']['symbol'] == 'MSFT'
    assert result['bundles'] == [] and result['observation'] is None
    assert s.cut['state']['positions'] == {} and s.packet['bundles'] == []


@pytest.mark.parametrize('damage', ['stale','future','identity','symbol','currency','class','units','shape'])
def test_no_entry_observation_never_admits_missing_or_foreign_monitor(damage):
    s = fixture()
    item = {'instrument': {'instrument_id':'accepted-id','symbol':'MSFT','asset_class':'STOCK',
                          'currency':'USD','units':'SHARES'}, 'symbol':'MSFT','observed_at':100}
    s.packet['monitors']['accepted-id'] = item
    if damage == 'stale': item['observed_at']=69
    elif damage == 'future': item['observed_at']=101
    elif damage == 'identity': item['instrument']['instrument_id']='foreign'
    elif damage == 'symbol': item['symbol']='OTHER'
    elif damage == 'currency': item['instrument']['currency']='USDC'
    elif damage == 'class': item['instrument']['asset_class']='PERP'
    elif damage == 'units': item['instrument']['units']='CONTRACTS'
    else: s.packet['monitors']['accepted-id']=None
    with pytest.raises(ValueError): s.reader.read_request(.2)
    assert s.reader._last is None


@pytest.mark.parametrize('damage', ['expiry', 'clock-backward', 'clock-type', 'cut', 'stop', 'revocation'])
def test_qd_completion_refuses_changed_source_context(damage):
    s = fixture()
    calls = [0]
    def verify(*args):
        calls[0] += 1
        if calls[0] > 1:
            return damage != 'revocation'
        if damage == 'expiry': s.now[0] = 131
        elif damage == 'clock-backward': s.now[0] = 99
        elif damage == 'clock-type': s.now[0] = 100.0
        elif damage == 'cut': s.cut['state']['unexpected_revision'] = 2
        elif damage == 'stop': s.runtime.halted = True
        return True
    s.authority.verify_scanner_publication = verify
    with pytest.raises(ValueError):
        s.reader.read_request(.2)
    assert s.reader._last is None
