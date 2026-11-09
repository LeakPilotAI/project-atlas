"""Durable sanitized IEX diagnostic receipt; no real provider or financial grant."""
import hashlib
import json
import subprocess
import sys

import pytest

from scripts.observation_runtime import atlas_r12_iex_diagnostic_receipt as receipts
from scripts.observation_runtime import alpaca_iex_probe as probe
from tests.test_alpaca_iex_probe_cli import StubFeed,dummy_creds

OP='a'*32


def positive():
    packet={'schema':'ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1',
      'status':'BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY',
      'authenticated':True,'subscribed':True,'quote_count':2,
      'fresh_quote_observed_during_connection':True,
      'observed_symbols':['MSFT'],'callback_quote_count':1,
      'connection_closed':True,
      'single_exchange_not_nbbo':True,
      'continuous_executable_prices_verified':False,
      'provider_rights_independently_accepted':False,
      'paper_fill_authorized':False,'live_order_authorized':False}
    return packet


def test_create_once_durable_diagnostic_readback_after_independent_python_process(tmp_path):
    got=receipts.write_receipt(positive(),['MSFT','SPY'],OP,root=tmp_path)
    assert got['status']=='DIAGNOSTIC_DATA_ONLY_RECEIPT_VERIFIED_NOT_FINANCIAL_AUTHORITY'
    assert got['observed_symbols']==['MSFT']
    assert got['paper_execution_authorized'] is False
    assert got['native_forward_source_published'] is False
    p=tmp_path/('receipt-'+OP+'.json')
    raw=p.read_bytes()
    assert b'API_SECRET' not in raw and b'key-for-tests' not in raw
    assert b'"ask":' not in raw and b'"bid":' not in raw
    assert b'FINANCIAL_PAPER' not in raw
    cmd=[sys.executable,'-B','-c',
      'from scripts.observation_runtime.atlas_r12_iex_diagnostic_receipt import read_receipt; import json,sys; print(json.dumps(read_receipt(sys.argv[1],root=sys.argv[2])))',
      OP,str(tmp_path)]
    result=subprocess.run(cmd,capture_output=True,text=True,timeout=30,cwd=receipts.ROOT)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['body_sha256']==got['body_sha256']
    with pytest.raises(FileExistsError):
        receipts.write_receipt(positive(),['MSFT','SPY'],OP,root=tmp_path)
    assert p.read_bytes()==raw


@pytest.mark.parametrize('change',[
 {'authenticated':False},
 {'subscribed':False},
 {'connection_closed':False},
 {'quote_count':0},
 {'fresh_quote_observed_during_connection':False},
 {'callback_quote_count':0},
 {'observed_symbols':['TSLA']},
 {'observed_symbols':['MSFT','MSFT']},
 {'paper_fill_authorized':True},
 {'live_order_authorized':True},
 {'provider_rights_independently_accepted':True},
 {'continuous_executable_prices_verified':True},
 {'status':'SCANNER_PUBLISHED'},
])
def test_false_or_broadened_observation_never_creates_success_receipt(tmp_path,change):
    packet=positive();packet.update(change)
    with pytest.raises(ValueError):
        receipts.write_receipt(packet,['MSFT','SPY'],OP,root=tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('bad',['0','../escape','A'*32,'x'*32,'a'*33])
def test_unreviewed_record_id_refuses_without_files(tmp_path,bad):
    with pytest.raises(ValueError,match='OPERATION_ID_REQUIRED'):
        receipts.write_receipt(positive(),['MSFT'],bad,root=tmp_path)
    assert not list(tmp_path.iterdir())


def test_receipt_integrity_tamper_and_self_recomputed_new_authority_refuse(tmp_path):
    receipts.write_receipt(positive(),['MSFT'],OP,root=tmp_path)
    path=tmp_path/('receipt-'+OP+'.json')
    row=json.loads(path.read_bytes())
    row['body']['startup_authorized']=True
    row['body_sha256']=receipts.digest(row['body'])
    path.write_bytes(receipts.canonical(row))
    with pytest.raises(ValueError,match='RECEIPT_INTEGRITY_OR_SCOPE_CHANGED'):
        receipts.read_receipt(OP,root=tmp_path)
    row['body']['startup_authorized']=False
    row['body']['private_api_key']='FAKE-KEY'
    row['body_sha256']=receipts.digest(row['body'])
    path.write_bytes(receipts.canonical(row))
    with pytest.raises(ValueError,match='NONCANONICAL_BODY'):
        receipts.read_receipt(OP,root=tmp_path)


def test_partial_receipt_or_symlinked_dir_refuses(tmp_path):
    path=tmp_path/('receipt-'+OP+'.json')
    path.write_bytes(b'{')
    with pytest.raises(ValueError,match='MALFORMED'):
        receipts.read_receipt(OP,root=tmp_path)
    with pytest.raises(FileExistsError):
        receipts.write_receipt(positive(),['MSFT'],OP,root=tmp_path)


def test_probe_true_synthetic_quote_writes_only_sanitized_once(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(receipts,'RECORDS_DIR',tmp_path)
    args=['--execute-data-only','--confirm-scope',probe.SCOPE,
          '--symbols','MSFT','SPY','--seconds','1','--receipt-id',OP]
    rc=probe.main(args,credentials_loader=lambda path:dummy_creds(),
                  feed_factory=lambda symbols:StubFeed(symbols))
    data=json.loads(capsys.readouterr().out)
    assert rc==0
    assert data['diagnostic_receipt']['financial_authority'] is False
    assert data['diagnostic_receipt']['body_sha256']==receipts.read_receipt(OP,root=tmp_path)['body_sha256']
    assert not data['provider_rights_independently_accepted']
    assert not data['paper_fill_authorized']
    again=probe.main(args,credentials_loader=lambda path:dummy_creds(),
                  feed_factory=lambda symbols:StubFeed(symbols))
    assert again==1
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'


def test_probe_failed_auth_never_writes_success_receipt(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(receipts,'RECORDS_DIR',tmp_path)
    args=['--execute-data-only','--confirm-scope',probe.SCOPE,
          '--symbols','MSFT','--seconds','1','--receipt-id',OP]
    rc=probe.main(args,credentials_loader=lambda path:dummy_creds(),
                  feed_factory=lambda symbols:StubFeed(symbols,auth=False))
    assert rc==1
    assert json.loads(capsys.readouterr().out)['status']=='REFUSED'
    assert not list(tmp_path.iterdir())


def test_offline_and_unscoped_probe_cannot_mint_receipt(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(receipts,'RECORDS_DIR',tmp_path)
    assert probe.main(['--inspect','--receipt-id',OP],
        credentials_loader=lambda path:pytest.fail('KEYS_READ'))==1
    assert probe.main(['--execute-data-only','--receipt-id',OP,'--seconds','1'],
        credentials_loader=lambda path:pytest.fail('KEYS_READ'))==1
    assert probe.main(['--execute-data-only','--confirm-scope',probe.SCOPE,
        '--seconds','1','--receipt-id','INVALID'],
        credentials_loader=lambda path:pytest.fail('KEYS_READ'))==1
    assert not list(tmp_path.iterdir())
