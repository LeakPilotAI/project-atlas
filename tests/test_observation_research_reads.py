import copy

import pytest

from scripts.observation_runtime.research_reads import (
 ResearchPublicationRead,
 retained_hyperliquid,
)


class Source:
 def __init__(self):self.value={'schema':'QD_RESEARCH_PUBLICATION_V1','source_id':'test','revision':1,'observed_at':100,'complete':True,'board':[{'symbol':'MSFT','instrument_id':'stock:MSFT','research_observed_at':100},{'symbol':'SPY','instrument_id':'etf:SPY','research_observed_at':100}]}
 def read_publication(self,timeout):assert timeout==.2;return self.value
class Authority:
 def verify_research_publication(self,packet,now):return True

def setup():
 source=Source();return source,ResearchPublicationRead(source=source,authority=Authority(),clock=lambda:100,expected_source='test')

def test_read_preserves_source_and_refuses_financial_authority():
 source,reader=setup();before=copy.deepcopy(source.value);view=reader.read()
 assert source.value==before and view['board']==before['board'] and view['financial_execution_authorized'] is False

@pytest.mark.parametrize('field,value',[('observed_at',69),('observed_at',101),('complete',False),('revision',True),('source_id','other'),('schema','FS2_TEST_PIN_V1'),('board',[{'symbol':'X'},{'symbol':'X'}]),('board',[{'symbol':'X','price':float('inf')}])])
def test_invalid_stale_incomplete_refuses(field,value):
 source,reader=setup();source.value[field]=value
 with pytest.raises(ValueError):reader.read()

def test_conflict_rollback_revocation():
 source,reader=setup();reader.read();source.value['board'][0]['symbol']='OTHER'
 with pytest.raises(ValueError,match='CONFLICT'):reader.read()
 source.value['revision']=2;reader.read();source.value['revision']=1
 with pytest.raises(ValueError,match='ROLLBACK'):reader.read()
 reader.authority.verify_research_publication=lambda *args:False
 with pytest.raises(ValueError,match='AUTHORITY'):reader.read()

def history():
 return {'status':'PARTIAL_ARCHIVE_WINDOW','omitted_sessions':2,'sessions':[{'session':'synthetic','status':'CLOSED','records':[{'kind':'HYPERLIQUID_PUBLIC_RESPONSE','at':50,'revision':2,'digest':'synthetic','value':{'request':{'type':'metaAndAssetCtxs'},'received_at':50,'response':[{'universe':[{'name':s} for s in ['BTC','ETH','SOL']]},[{'markPx':'100','funding':'0'} for _ in range(3)]]}}]}]}

def test_retained_never_current_and_missing_values_not_zero():
 h=history();before=copy.deepcopy(h);v=retained_hyperliquid(h)
 assert h==before and v['current_signals'] is None and v['freshness']=='STALE_NOT_EXECUTABLE'
 assert v['markets'][0]['volume_24h'] is None and v['omitted_sessions']==2

@pytest.mark.parametrize('broken',['roster','nonfinite','missing'])
def test_retained_refusal(broken):
 h=history();v=h['sessions'][0]['records'][0]['value']
 if broken=='roster':v['response'][1].pop()
 if broken=='nonfinite':v['response'][1][0]['markPx']='NaN'
 if broken=='missing':h['sessions']=[]
 with pytest.raises(ValueError):retained_hyperliquid(h)

@pytest.mark.parametrize('field,value',[('research_observed_at',69),('instrument_id',''),('quote_quality','LIVE')])
def test_row_evidence_cannot_borrow_publication_freshness(field,value):
 source,reader=setup();source.value['board'][0][field]=value
 with pytest.raises(ValueError):reader.read()
