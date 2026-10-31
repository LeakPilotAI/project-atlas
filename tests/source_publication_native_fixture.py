"""Disposable source archives and original cache inputs; never operational custody."""
import copy
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.adapters.hyperliquid import HyperliquidAdapter, _paper_execution_observation
from app.services.paper_financial_replay import body, digest
from app.services.paper_source_publication import (
    PerpSourcePublication,
    QualityDipsSourcePublication,
)
from test_paper_source_publication import auth


class DurableArchive:
    """Test-only fsync/CAS + immutable versions. Not native protected enrollment."""
    def __init__(self,root):
        self.root=Path(root);self.fault=lambda phase:None
        if not self.root.is_dir():self.root.mkdir()
        self.pin=self.root/'current.json'
        if not self.pin.exists():self.pin.write_text('{"revision":0}')
    def current(self):
        pin=json.loads(self.pin.read_text())
        expected={'current.json'}|{f'{i}.json' for i in range(1,pin['revision']+1)}|{f'{i}.ack' for i in range(1,pin['revision']+1)}
        if {p.name for p in self.root.iterdir()}!=expected:raise ValueError('SYNTHETIC_SOURCE_TAIL_OR_ACK_UNKNOWN')
        return pin
    def publish(self,*,expected,packet,sources):
        if self.current()!=expected:raise ValueError('SYNTHETIC_CAS_CONFLICT')
        revision=packet['revision'];self.fault('before')
        with (self.root/f'{revision}.json').open('xb') as f:
            f.write(body({'packet':packet,'sources':sources}).encode());f.flush();os.fsync(f.fileno())
        self.fault('record')
        pin={'revision':revision,'digest':digest(packet)}
        temp=self.root/'pending.json'
        with temp.open('xb') as f:f.write(body(pin).encode());f.flush();os.fsync(f.fileno())
        os.replace(temp,self.pin);self.fault('pin')
        with (self.root/f'{revision}.ack').open('xb') as f:f.write(body(pin).encode());f.flush();os.fsync(f.fileno())
        self.fault('ack')
    def read(self,pin):
        if self.current()!=pin:raise ValueError('SYNTHETIC_SOURCE_CHANGED')
        row=json.loads((self.root/f"{pin['revision']}.json").read_text())
        if json.loads((self.root/f"{pin['revision']}.ack").read_text())!=pin or digest(row['packet'])!=pin['digest']:
            raise ValueError('SYNTHETIC_SOURCE_RECEIPT_CONFLICT')
        return row['packet']


class Publications:
    def __init__(self,root):self.root=Path(root)
    def factory(self,q,p,q_packet,clock):
        self.q,self.p,self.q_packet,self.clock=q,p,q_packet,clock
        self.adapter=HyperliquidAdapter();self.adapter._connected=True
        self.raw={'board':q.b['board'],'observations':{q.b['instrument']['symbol']:q.b['observation']},
            'quotes':{q.b['instrument']['symbol']:q.b['quote']},'instruments':[q.b['instrument']],
            'publication':q.b['publication'],'monitors':{}}
        self.qpub=QualityDipsSourcePublication(research=SimpleNamespace(read_current=lambda:copy.deepcopy(self.raw)),
            candidates=q.writer.runtime.runtime.engine.candidates,source_id='SYNTHETIC_ORIGINAL_SCANNER',
            authority=auth(),archive=DurableArchive(self.root/'qd-publications'),clock=clock)
        self.makers={}
        self.originals={}
        self.ppub=PerpSourcePublication(adapter=self.adapter,orders=p.orders,
            settlements=SimpleNamespace(read=lambda symbol,at:copy.deepcopy(p.packet['oracles'].get(f'{symbol}:{at}'))),
            maker=SimpleNamespace(read=lambda key:copy.deepcopy(self.makers.get(key))),
            lifecycle=SimpleNamespace(read_current=lambda:copy.deepcopy(p.packet['setups'])),
            source_id='SYNTHETIC_ORIGINAL_HL_CACHE',authority=auth(),archive=DurableArchive(self.root/'perp-publications'),clock=clock)
        self.publish()
        return self.qpub,self.ppub

    def publish(self):
        q,p,now=self.q,self.p,self.clock()
        live=[r for r in q.writer._cut()['state']['positions'].values() if float(r['remaining'])>0]
        self.raw['instruments']=[] if live else [q.b['instrument']]
        self.raw['monitors']=copy.deepcopy(self.q_packet['monitors'])
        self.qpub.publish_scanner(q.b['board'],datetime.fromtimestamp(now,UTC).isoformat())
        parsed=p.packet['books']['BTC']
        meta=[{'universe':[{'name':'BTC','szDecimals':3,'maxLeverage':2}]},
            [{'markPx':parsed['mark'],'oraclePx':parsed['oracle'],'funding':parsed['indicative_funding_rate']}]]
        book={'coin':'BTC','time':now*1000,'levels':[[{'px':parsed['bid'],'sz':parsed['bid_size'],'n':3}],
            [{'px':parsed['ask'],'sz':parsed['ask_size'],'n':3}]]}
        if float(parsed['bid'])>99.75:book['levels'][0].append({'px':'99.75','sz':'1','n':1})
        self.originals[now]=(copy.deepcopy(meta),copy.deepcopy(book))
        actual=_paper_execution_observation('BTC',meta,book,now*1000,now*1000)
        self.adapter._cache_paper('books','BTC',{'parsed':actual,'metadata':meta,'book':book})
        self.adapter._cache_paper('markets',None,[{**r,'timestamp':datetime.fromtimestamp(now,UTC).isoformat()} for r in p.packet['markets']])
        self.adapter._cache_paper('candles','BTC',{'interval':'5m','observed_at_ms':now*1000,
            'rows':[{**r,'time':now*1000-(47-i)*300000} for i,r in enumerate(p.packet['candles']['BTC'])]})
        for symbol,row in p.packet['funding'].items():
            data=[{'coin':symbol,'time':r['settlement_at_ms'],'fundingRate':r['hourly_rate'],'premium':r['premium']} for r in row['records']]
            self.adapter._cache_paper('funding',symbol,{'parsed':row,'rows':data,'started_ms':row['observed_at_ms']})
        for key,proof in p.packet['maker_fills'].items():
            row=p.orders.snapshot()['state']['orders'][key]
            if row['state']!='RESERVED':continue
            order=row['order']
            frame={'channel':'trades','data':[{'coin':order['symbol'],'side':'A' if order['side']=='LONG' else 'B',
                'px':proof['trade_price'],'sz':proof['traded_quantity'],'time':proof['trade_at']*1000,'tid':1,'hash':'SYNTHETIC_PUBLIC_TRADE'}]}
            self.adapter.ingest_paper_trades(frame,received_ms=now*1000,continuity_receipt='SYNTHETIC_WINDOW_CUSTODY')
            trades=self.adapter.paper_source_snapshot()['facts']['trades'][order['symbol']]
            initial_meta,initial=self.originals[order['created_at']]
            queue={'book':initial,'metadata':initial_meta,'source_digest':order['source_digest'],
                   'source_revision':order['source_revision'],'receipt':'SYNTHETIC_ORIGINAL_QUEUE_ARCHIVE'}
            self.makers[key]={'proof':{**proof,'source_ref':digest({'queue':queue,'trades':trades})},
                'trade_ids':[[proof['trade_at']*1000,1]],'queue':queue}
        self.ppub.capture()
