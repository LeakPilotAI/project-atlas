"""In-memory local pin CAS tests;no native/operational financial files."""
import copy

import pytest
from app.services.personal_current_pins import PersonalCurrentPins
from test_personal_session_reservation_integrity import Memory


def system():
    m=Memory();PersonalCurrentPins.install_schema(m.db);pin={'schema':'QD_AUTO_OP_PIN_V1','root':[1,2,3],'inception':{'id':[1,2,4],'sha256':'a'*64},'epoch':'SYNTHETIC','entries':[]}
    PersonalCurrentPins.initialize(m.db,'source',pin);m.db.commit();p=PersonalCurrentPins(ledger=m,name='source',clock=lambda:1000)
    return m,p,pin


def test_current_cas_and_restart_keep_exact_source():
    m,p,pin=system()
    try:
        after=copy.deepcopy(pin);after['entries'].append({'SYNTHETIC_ACK':'a'})
        p.advance(pin,after);assert p.current()==after
        assert PersonalCurrentPins(ledger=m,name='source',clock=lambda:1000).current()==after
        with pytest.raises(ValueError):p.advance(pin,after)
    finally:m.db.close()


@pytest.mark.parametrize('damage',['root','epoch','erase','two','overflow','schema'])
def test_pin_never_resets_or_adopts_foreign_resource(damage):
    m,p,pin=system();after=copy.deepcopy(pin);after['entries']=[{}]
    if damage=='root':after['root']=[9,9,9]
    elif damage=='epoch':after['epoch']='FOREIGN'
    elif damage=='erase':after['entries']=[]
    elif damage=='two':after['entries']=[{},{}]
    elif damage=='overflow':pin['entries']=[{}]*128;after['entries']=[{}]*129
    else:after['schema']='FS2_TEST_PIN_V1'
    try:
        with pytest.raises(ValueError):p.advance(pin,after)
    finally:m.db.close()


def test_missing_pin_does_not_initialize_or_repair():
    m,p,_=system()
    try:
        with m.db:m.db.execute('DELETE FROM personal_current')
        with pytest.raises(ValueError):p.current()
        assert m.db.execute('SELECT COUNT(*) FROM personal_current').fetchone()==(0,)
    finally:m.db.close()
