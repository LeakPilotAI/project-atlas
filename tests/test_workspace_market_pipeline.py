"""Fresh synthetic retained/API evidence through the actual V2 embedded market page."""
import asyncio
import json
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from test_market_replay_integration import fixture, quote_fixture

from scripts.observation_runtime.market_replay import ReplayStore, create_replay_app


@pytest.mark.parametrize('hour,asset,session', [
    (12, 'US_ETF', 'Premarket'), (14, 'US_EQUITY', 'Regular session'),
    (21, 'US_ETF', 'After hours'),
])
def test_retained_api_to_workspace_freshness_and_refusal(tmp_path, hour, asset, session):
    repo = Path(__file__).resolve().parents[1]
    ts = datetime(2026, 10, 20, hour, tzinfo=UTC)
    received = ts + timedelta(seconds=70)
    source = {'bars': fixture(ts), 'quotes': quote_fixture(ts + timedelta(seconds=60))}
    source_bytes = json.dumps(source, sort_keys=True).encode()
    source_path = tmp_path / 'synthetic-source.json'
    source_path.write_bytes(source_bytes)
    database = tmp_path / 'retained.db'
    with sqlite3.connect(database) as db:
        store = ReplayStore(db)
        store.ingest(source['bars'], observed_at=received, asset_class=asset)
        store.ingest_quote(source['quotes'], observed_at=received, asset_class=asset)

    async def exports():
        with sqlite3.connect(database) as db:
            store = ReplayStore(db)  # Reopen retained evidence, no provider or listener.
            clock = [received]
            app = create_replay_app(store, symbols=['SPY', 'MISSING'], clock=lambda: clock[0])
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://fixture') as client:
                result = {}
                for name, now in [('fresh', received), ('unobserved', ts + timedelta(seconds=65)),
                                  ('stale', received + timedelta(minutes=5))]:
                    clock[0] = now
                    response = await client.get('/api/market-data')
                    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
                    result[name] = response.text
                db.execute("UPDATE replay_bars SET digest='synthetic-corruption'")
                db.commit()
                response = await client.get('/api/market-data')
                assert response.status_code == 503
                result['refusal'] = response.text
                return result

    bundle = tmp_path / 'exports.json'
    bundle.write_text(json.dumps(asyncio.run(exports())), encoding='utf-8')
    workspace = tmp_path / 'workspace'
    node = 'C:/Program Files/nodejs/node.exe'
    build = subprocess.run([node, str(repo / 'frontend/offline/workspace/build-v2.mjs'), str(workspace)],
                           capture_output=True, text=True, timeout=20, check=False)
    assert build.returncode == 0, build.stdout + build.stderr
    before = {p.name: p.read_bytes() for p in workspace.iterdir()}
    harness = tmp_path / 'acceptance.cjs'
    harness.write_text(r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {createHash,webcrypto}=require('node:crypto');
const {File}=require('node:buffer');
class Element {
 constructor(){this.children=[];this.listeners=new Map();this.value='';this._text='';}
 set textContent(v){this._text=String(v);this.children=[];}
 get textContent(){return this._text+this.children.map(n=>n.textContent).join(' ');}
 set innerHTML(v){throw Error('No HTML interpolation');}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this._text='';this.children=nodes;}
 setAttribute(){}
 addEventListener(k,v){this.listeners.set(k,v);}
 removeEventListener(k){this.listeners.delete(k);}
}
const elements=new Map(['market-file','clear-market','market-status','market-clock','market-results','market-symbol','market-import-identity'].map(k=>[k,new Element()]));
const document={getElementById:k=>elements.get(k),createElement:()=>new Element()};
const html=fs.readFileSync(process.argv[2],'utf8'),data=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
assert.ok(html.includes("'sha256-"+createHash('sha256').update(script).digest('base64')+"'"));
const sandbox={document,crypto:webcrypto,TextEncoder,structuredClone,fetch:()=>{throw Error('No network');}};
Object.defineProperty(sandbox,'localStorage',{get(){throw Error('No storage');}});
vm.runInNewContext(script,sandbox,{timeout:2000});
const input=elements.get('market-file'),results=elements.get('market-results'),status=elements.get('market-status');
async function load(raw){input.files=[new File([raw],'explicit.json')];return input.listeners.get('change')();}
(async()=>{
 assert.equal((await load(data.fresh)).status,'LOADED');
 for(const text of ['Freshness across supplied symbols','Fresh at report clock',process.argv[4],'YAHOO_CHART_SHAPED_FIXTURE','YAHOO_QUOTE_RESPONSE_SHAPED_FIXTURE','MISSING','Unavailable'])assert.ok(results.textContent.includes(text),text);
 assert.ok(elements.get('market-clock').textContent.includes(JSON.parse(data.fresh).asof));
 assert.match(status.textContent,/source and live status are not verified/);
 assert.ok(elements.get('market-import-identity').textContent.includes(createHash('sha256').update(data.fresh).digest('hex')));
 const selector=elements.get('market-symbol');selector.value='MISSING';selector.listeners.get('change')();
 assert.match(results.textContent,/Displayed symbols: MISSING/);
 assert.doesNotMatch(results.textContent,/YAHOO_CHART_SHAPED_FIXTURE|YAHOO_QUOTE_RESPONSE_SHAPED_FIXTURE/);
 assert.match(results.textContent,/Freshness across supplied symbols/);
 assert.equal((await load(data.unobserved)).status,'LOADED');
 assert.equal(selector.value,'');
 assert.match(results.textContent,/Not observed by report clock/);
 assert.doesNotMatch(results.textContent,/YAHOO_CHART_SHAPED_FIXTURE|YAHOO_QUOTE_RESPONSE_SHAPED_FIXTURE/);
 assert.equal((await load(data.stale)).status,'LOADED');
 assert.match(results.textContent,/Stale at report clock/);
 const stale=JSON.parse(data.stale);for(const kind of ['rows','quote_rows'])assert.equal(stale[kind].find(r=>r.symbol==='SPY').price,null);
 assert.equal((await load(data.refusal)).status,'LOADED');
 assert.match(status.textContent,/No usable prices/);assert.doesNotMatch(results.textContent,/Completed bar closes|Separate quote references/);
 const bad=JSON.parse(data.fresh);bad.rows.find(r=>r.symbol==='SPY').source='UNVERIFIED_OTHER_SOURCE';
 await load(data.fresh);assert.equal((await load(JSON.stringify(bad))).status,'REFUSED');
 assert.equal(results.textContent,'');assert.equal(elements.get('market-clock').textContent,'No report loaded');
 assert.equal(elements.get('market-import-identity').textContent,'No decoded export identity');
 assert.match(status.textContent,/Previous evidence cleared/);
 await load(data.fresh);elements.get('clear-market').listeners.get('click')();assert.equal(results.textContent,'');
 console.log('Embedded Workspace V2 synthetic source/freshness/refusal acceptance passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
""", encoding='utf-8')
    checked = subprocess.run([node, str(harness), str(workspace / 'market.html'), str(bundle), session],
                             capture_output=True, text=True, timeout=20, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert before == {p.name: p.read_bytes() for p in workspace.iterdir()}
    assert source_path.read_bytes() == source_bytes
