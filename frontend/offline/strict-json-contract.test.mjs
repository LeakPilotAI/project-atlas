import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import market from './market-replay/view.cjs';
import forecast from './forecast-accountability/view.cjs';
const read=name=>fs.readFileSync(new URL('../../tests/fixtures/'+name,import.meta.url),'utf8');
const hash=text=>createHash('sha256').update(text).digest('hex');
const source=JSON.parse(read('afi-log-loss-v2/corrected-browser.json')).source_report_json;
const envelope=text=>JSON.stringify({schema:'AFI_BROWSER_REPORT_V1',report_json:text,payload_sha256:hash(text)});
function escapedStrings(text,seed){let offset=0;return text.replace(/"(?:\\.|[^"\\])*"/g,token=>{const value=JSON.parse(token);let encoded='"';for(let i=0;i<value.length;i++){const n=value.charCodeAt(i);encoded+=((offset+++seed)%3===0)?'\\u'+n.toString(16).padStart(4,'0'):JSON.stringify(value[i]).slice(1,-1);}return encoded+'"';});}
const strings=['braces { } [ ] , : "symbol" "symbol"','escaped \\ \\\\ \\" quoted','literal \\u0061 and actual a','astral 🚀 and unicode Ω','line\ncarriage\rtab\tcontrol\u0000','quotes "a":"b", "a":"c"','ending backslash \\','[{},[{},{}]], true false null -1.2e+5'];
for(const [index,text] of strings.entries())test(`market string corpus ${index} is preserved as inert source text`,()=>{const report=JSON.parse(read('market-replay-v1/research.json'));report.analysis.reference_source=text;const raw=JSON.stringify(report);assert.deepEqual(JSON.parse(escapedStrings(raw,index)),report);assert.deepEqual(market.parseRetainedResearch(escapedStrings(raw,index)),report);});
for(let seed=0;seed<3;seed++)test(`escaped forecast envelope corpus ${seed} preserves exact original source`,async()=>{const original=envelope(source),encoded=escapedStrings(original,seed);assert.deepEqual(JSON.parse(encoded),JSON.parse(original));assert.deepEqual(await forecast.verifyEnvelope(encoded,hash),JSON.parse(source));});
for(let seed=0;seed<3;seed++)test(`escaped hashed forecast source corpus ${seed} preserves scores`,async()=>{const encoded=escapedStrings(source,seed);assert.deepEqual(JSON.parse(encoded),JSON.parse(source));const result=await forecast.verifyEnvelope(envelope(encoded),hash);assert.deepEqual(result,JSON.parse(source));});
for(const spelling of ['network_authorized','net\\u0077ork_authorized','network\\u005fauthorized'])test(`market duplicate key alias ${spelling} refuses`,()=>{const raw=read('market-replay-v1/api.json').replace('{','{"'+spelling+'":false,');assert.throws(()=>market.parseExport(raw),/Duplicate/);});
test('escaped paired forecast keys remain ambiguous and refuse before scores',async()=>{const raw=source.replace('{','{"production\\u005fapproved":false,');await assert.rejects(()=>forecast.verifyEnvelope(envelope(raw),hash),/Duplicate/);});
