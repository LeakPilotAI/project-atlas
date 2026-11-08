"""Synthetic supplied records, never a real PAPER journal or provider."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

import app.prediction.paper_engine as engine
import pytest
from app.prediction.paper_engine import PredictionPaperError, PredictionPaperJournal

NOW=datetime(2026,10,20,12,tzinfo=timezone.utc)


def journal(tmp_path):return PredictionPaperJournal(journal_path=tmp_path/'paper.jsonl',candidate_path=tmp_path/'candidates.jsonl')


def opened(trade_id='a'):
    return {'event':'open','trade_id':trade_id,'status':'open','ticker':'SYNTHETIC','side':'YES','quantity_contracts':'10','actual_entry_price':'0.42','entry_notional_dollars':'4.20','entry_fee_dollars':'0.18','entry_timestamp':'2026-10-19T12:00:00+00:00','occurrence_datetime':'2026-10-21T20:00:00+00:00','flat_deadline':'2026-10-21T19:30:00+00:00','live_capital_allowed':False,'automatic_real_money_execution':False}


def closed(trade_id='a'):
    return {**opened(trade_id),'event':'close','status':'closed','actual_exit_price':'0.50','exit_notional_dollars':'5.00','exit_fee_dollars':'0.18','gross_pnl_dollars':'0.80','net_pnl_dollars':'0.44','net_roi':str(Decimal('.44')/Decimal('4.38')),'win':True,'scratch':False,'violated_flat_deadline':False}


def evaluation():
    return {'eligible':True,'ticker':'SYNTHETIC','side':'YES','quantity_contracts':'10','entry_fill':{'fillable':True,'vwap_dollars':'0.42','notional_dollars':'4.20','estimated_taker_fee_dollars':'0.18','levels':[{'price_dollars':'0.42','quantity_contracts':'10'}]}}


def book():return {'yes':{'bids':[{'price_dollars':'0.50','quantity_contracts':'100'}]}}


def write_rows(j,rows):j.journal_path.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')


@pytest.mark.parametrize('value',['NaN','Infinity','-Infinity',float('nan'),True,'1e999999'])
def test_decimal_inputs_do_not_admit_nonfinite_boolean_or_unbounded_values(value):assert engine._d(value) is None


@pytest.mark.parametrize('field,value',[('vwap_dollars',None),('estimated_taker_fee_dollars',None),('notional_dollars',None),('vwap_dollars','NaN'),('vwap_dollars','1.1'),('estimated_taker_fee_dollars','-1'),('notional_dollars','999'),('levels',[]),('fillable','yes')])
def test_new_open_requires_complete_consistent_fill_evidence(tmp_path,field,value):
    j=journal(tmp_path);e=evaluation();e['entry_fill'][field]=value
    with pytest.raises(PredictionPaperError):j.open_from_evaluation(e)
    assert not j.journal_path.exists()


@pytest.mark.parametrize('field,value',[('actual_entry_price',None),('entry_fee_dollars',None),('actual_entry_price','NaN'),('entry_notional_dollars','999')])
def test_known_exit_can_flatten_legacy_position_without_inventing_entry_costs(tmp_path,field,value):
    j=journal(tmp_path);row=opened();row[field]=value;write_rows(j,[row]);before=j.journal_path.read_bytes()
    result=j.close_from_orderbook(orderbook=book(),exit_reason='SYNTHETIC_EXIT',now=NOW)
    assert result['status']=='closed' and result['actual_exit_price']=='0.50'
    assert result['net_pnl_dollars'] is None and result['win'] is None and result['scratch'] is None
    assert j.journal_path.read_bytes().startswith(before)
    s=j.snapshot()['summary'];assert s['closed_trades']==1 and s['net_pnl_dollars'] is None and s['win_rate'] is None
    assert s['accounting_status']=='INSUFFICIENT_EVIDENCE'


@pytest.mark.parametrize('field,value',[('vwap_dollars',None),('estimated_taker_fee_dollars',None),('notional_dollars','999'),('filled_quantity','9')])
def test_invalid_new_exit_receipt_does_not_create_close(tmp_path,monkeypatch,field,value):
    j=journal(tmp_path);write_rows(j,[opened()]);before=j.journal_path.read_bytes()
    fill={'fillable':True,'vwap_dollars':'0.50','notional_dollars':'5','filled_quantity':'10','estimated_taker_fee_dollars':'0.18','levels':[{'price_dollars':'0.50','quantity_contracts':'10'}]};fill[field]=value
    monkeypatch.setattr(engine,'walk_executable_depth',lambda *a,**k:fill)
    with pytest.raises(PredictionPaperError):j.close_from_orderbook(orderbook={},exit_reason='SYNTHETIC',now=NOW)
    assert j.journal_path.read_bytes()==before


@pytest.mark.parametrize('field,value',[('net_pnl_dollars',None),('net_pnl_dollars','bad'),('entry_fee_dollars',None),('net_pnl_dollars','999'),('win',False),('gross_pnl_dollars',None),('actual_exit_price','NaN')])
def test_incomplete_or_contradictory_close_never_enters_total_as_zero(tmp_path,field,value):
    j=journal(tmp_path);row=closed();row[field]=value;write_rows(j,[opened(),row]);before=j.journal_path.read_bytes()
    result=j.snapshot();s=result['summary']
    assert s['closed_trades']==1 and s['net_pnl_dollars'] is None and s['wins'] is None and s['losses_or_scratches'] is None
    assert s['accounting_status']=='INSUFFICIENT_EVIDENCE' and s['unscored_closed_trades']==1
    assert result['events'][-1]['net_pnl_dollars'] is None
    assert j.journal_path.read_bytes()==before


def test_valid_legacy_and_explicit_zero_fees_are_reconciled_without_rewriting(tmp_path):
    j=journal(tmp_path);a=opened();b=closed();a['entry_fee_dollars']=b['entry_fee_dollars']='0';b.update(net_pnl_dollars='0.62',net_roi=str(Decimal('.62')/Decimal('4.20')));write_rows(j,[a,b]);before=j.journal_path.read_bytes()
    s=j.snapshot()['summary'];assert s['net_pnl_dollars']=='0.62' and s['win_rate']==1 and s['unscored_closed_trades']==0
    assert j.journal_path.read_bytes()==before


def test_bad_close_stays_visible_and_partial_subtotal_is_not_full_performance(tmp_path):
    j=journal(tmp_path);bad=closed('b');bad['net_pnl_dollars']=None;write_rows(j,[opened(),closed(),opened('b'),bad])
    s=j.snapshot()['summary'];assert s['closed_trades']==2 and s['verified_closed_trades']==1
    assert s['net_pnl_dollars'] is None and s['verified_closed_net_pnl_dollars']=='0.44' and s['win_rate'] is None


def test_zero_basis_roi_is_undefined_not_zero(tmp_path):
    j=journal(tmp_path);row=opened();row.update(actual_entry_price='0',entry_notional_dollars='0',entry_fee_dollars='0');write_rows(j,[row])
    result=j.close_from_orderbook(orderbook=book(),exit_reason='SYNTHETIC',now=NOW)
    assert result['net_pnl_dollars']=='4.82' and result['net_roi'] is None
    assert 'ZERO_COST_BASIS_ROI_UNDEFINED' in result['accounting']['warnings']


def test_zero_price_depth_keeps_true_slippage_and_invalid_levels_refuse():
    b={'yes':{'asks':[{'price_dollars':'0','quantity_contracts':'5'},{'price_dollars':'.4','quantity_contracts':'5'}]}}
    fill=engine.walk_executable_depth(b,side='YES',action='BUY',quantity=Decimal(10));assert Decimal(fill['depth_slippage_dollars_per_contract'])==Decimal('.2')


@pytest.mark.parametrize('level',[{'quantity_contracts':'5'},{'price_dollars':'1.2','quantity_contracts':'5'},{'price_dollars':'.4','quantity_contracts':'NaN'}])
def test_invalid_depth_does_not_get_skipped_into_a_fake_fill(level):
    b={'yes':{'asks':[deepcopy(level),{'price_dollars':'.5','quantity_contracts':'10'}]}}
    fill=engine.walk_executable_depth(b,side='YES',action='BUY',quantity=Decimal(10));assert fill['fillable'] is False
