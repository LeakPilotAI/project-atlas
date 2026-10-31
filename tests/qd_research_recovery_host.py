"""Confined original-page recovery host; synthetic research, no providers/financial stores."""
import json
import os
import sys
import threading
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts/observation_runtime')]
import desktop_observation
from desktop_observation import Session, assets, make_host
from research_reads import ResearchPublicationRead


def main():
 root=ROOT/'logs/diagnostics'/('qd-research-browser-'+uuid.uuid4().hex)
 root.mkdir(exist_ok=False)
 (root/'phase.json').write_text(json.dumps({'mode':'valid','symbol':'MSFT','revision':1}))
 class Source:
  def read_publication(self,timeout):
   value=json.loads((root/'phase.json').read_text())
   if value['mode']!='valid':raise ValueError('SYNTHETIC_503')
   symbol=value['symbol']
   return {'schema':'QD_RESEARCH_PUBLICATION_V1','source_id':'DISPOSABLE_SYNTHETIC_RESEARCH','revision':value['revision'],'observed_at':100,'complete':True,'board':[{'symbol':symbol,'instrument_id':'fixture:'+symbol,'research_observed_at':100,'quote_observed_at':100,'quote_quality':'FRESH','quote_display_price':100,'opportunity_score':80,'stance':'WATCH','quality_dips_v2':{'patient_state':'WATCH','quality_dips_v3':{'patient_state':'WATCH','blockers':['SYNTHETIC TEST ONLY'],'entry_ladder':{'ready':False,'levels':[]}}}}]}
 class Authority:
  def verify_research_publication(self,packet,now):return packet['source_id']=='DISPOSABLE_SYNTHETIC_RESEARCH' and now==100
 reader=ResearchPublicationRead(source=Source(),authority=Authority(),clock=lambda:100,expected_source='DISPOSABLE_SYNTHETIC_RESEARCH')
 session=Session(ROOT/'logs/observation-only'/('session-test-'+uuid.uuid4().hex),test=True)
 def test_assets():
  result=assets()
  for key,(value,mime) in list(result.items()):
   if key in ('/quality_dips.html','/api/investments/quality-dips/view'):
    value=value.replace(b'<body>',b'<body><p style="color:#ffbd55" role="status">DISPOSABLE SYNTHETIC BROWSER ACCEPTANCE - NO ACCOUNT OR PROVIDERS</p>');result[key]=(value,mime)
    driver=(ROOT/'tests/qd_research_browser_acceptance.js').read_bytes()
  for key in ('/quality_dips.html','/api/investments/quality-dips/view'):
   value,mime=result[key];result[key]=(value.replace(b'</body>',b'<script>'+driver+b'</script></body>'),mime)
  hub_driver=(ROOT/'tests/atlas_hub_browser_acceptance.js').read_bytes()
  for key in ('/','/dashboard'):
   value,mime=result[key];result[key]=(value.replace(b'</body>',b'<script>'+hub_driver+b'</script></body>'),mime)
  return result
 desktop_observation.assets=test_assets
 host,identity=make_host(session,research_reader=reader,request_limit=96,deadline_seconds=180)
 original_get=host.RequestHandlerClass.do_GET
 def test_get(self):
  if self.path in ('/__test__/phase/unavailable','/__test__/phase/recovered'):
   mode='unavailable' if self.path.endswith('unavailable') else 'valid'
   (root/'phase.json').write_text(json.dumps({'mode':mode,'symbol':'SPY','revision':2}))
   return self.response(200,{'fixture_phase':mode})
  return original_get(self)
 host.RequestHandlerClass.do_GET=test_get
 original=host.RequestHandlerClass.response
 def response(self,status,value,mime='application/json'):
  with (root/'http.jsonl').open('a') as f:f.write(json.dumps({'path':self.path,'status':status})+'\n')
  return original(self,status,value,mime)
 host.RequestHandlerClass.response=response
 worker=threading.Thread(target=host.serve_forever,daemon=True);worker.start()
 from disposable_host_owner import observe_pid
 process=observe_pid(os.getpid())
 ready={'pid':os.getpid(),'creation_filetime':process['created'],'image':process['image'],'root':str(root),'url':'http://127.0.0.1:'+str(host.server_port)+'/quality_dips.html','host_id':identity,'mode':'DISPOSABLE_SYNTHETIC_ONLY'}
 (root/'ready.json').write_text(json.dumps(ready));print(json.dumps(ready),flush=True)
 try:sys.stdin.readline()
 finally:host.shutdown();host.server_close();worker.join(5);session.append('SESSION_STOP',{'financial_writers':False});(root/'closed.json').write_text(json.dumps({'closed':not worker.is_alive(),'request_counts':host.counts()}))

if __name__=='__main__':main()
