import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import api from './view.cjs';
const digest=text=>createHash('sha256').update(text).digest('hex');
const originalReplay=JSON.parse(fs.readFileSync(new URL('../../../tests/fixtures/market-replay-v1/research-replay.json',import.meta.url),'utf8'));
const originalComparison=JSON.parse(fs.readFileSync(new URL('../../../tests/fixtures/market-replay-v1/research-comparison.json',import.meta.url),'utf8'));
const stamp=micros=>'2026-10-20T13:30:00.'+String(micros).padStart(6,'0')+'+00:00';
function envelope(original,report){const text=JSON.stringify(report);return JSON.stringify({...original,report_json:text,payload_sha256:digest(text)});}
function replay(clocks,cutoff=clocks.at(-1)){const r=JSON.parse(originalReplay.report_json),template=r.cases[0];r.archive_asof=cutoff;r.cases=clocks.map((clock,index)=>{const row=structuredClone(template);row.index=index;row.decision_at=clock;row.report.asof=clock;row.report_sha256=digest(JSON.stringify(row.report));row.decision_sha256=digest('synthetic'+clock+index);return row;});r.planned_decision_n=r.cases.length;r.row_decision_work=r.cases.reduce((n,c)=>n+c.visible_bar_n,0);for(const key of Object.keys(r.status_counts))r.status_counts[key]=key==='REFUSED'?clocks.length:0;return envelope(originalReplay,r);}
function comparison(clocks){const r=JSON.parse(originalComparison.report_json),template=r.pairs[0];r.pairs=clocks.map(clock=>({...structuredClone(template),decision_at:clock,left_decision_sha256:digest('left'+clock),right_decision_sha256:digest('right'+clock)}));r.planned_pair_n=clocks.length;r.both_descriptive_n=0;r.not_both_descriptive_n=clocks.length;r.same_evidence_n=0;r.changed_evidence_n=clocks.length;for(const left of Object.keys(r.status_pair_counts))for(const right of Object.keys(r.status_pair_counts[left]))r.status_pair_counts[left][right]=left==='REFUSED'&&right==='INSUFFICIENT_HISTORY'?clocks.length:0;return envelope(originalComparison,r);}
for(const micros of [[1,2],[1,2,3],[999,1000],[1]])test(`replay distinct clocks ${micros} preserve all refusal decisions`,async()=>{const result=await api.verifyResearchReplay(replay(micros.map(stamp)));assert.equal(result.planned_decision_n,micros.length);assert.equal(result.status_counts.REFUSED,micros.length);});
for(const micros of [[1,1],[2,1]])test(`replay duplicate/reversed ${micros} refuses`,async()=>{await assert.rejects(()=>api.verifyResearchReplay(replay(micros.map(stamp),stamp(3))));});
test('replay one microsecond beyond archive cutoff refuses despite valid outer hash',async()=>{await assert.rejects(()=>api.verifyResearchReplay(replay([stamp(3)],stamp(2))));});
test('unsafe replay cutoff epoch refuses',async()=>{await assert.rejects(()=>api.verifyResearchReplay(replay([stamp(1)],'9999-01-01T00:00:00+00:00')));});
for(const micros of [[1,2],[999,1000]])test(`comparison exact clock plan ${micros} accepted`,async()=>{const result=await api.verifyResearchComparison(comparison(micros.map(stamp)));assert.equal(result.planned_pair_n,2);assert.equal(result.not_both_descriptive_n,2);});
for(const micros of [[1,1],[2,1]])test(`comparison duplicate/reversed ${micros} refuses`,async()=>{await assert.rejects(()=>api.verifyResearchComparison(comparison(micros.map(stamp))));});
test('unsafe comparison clock epoch refuses',async()=>{await assert.rejects(()=>api.verifyResearchComparison(comparison(['9999-01-01T00:00:00+00:00'])));});
