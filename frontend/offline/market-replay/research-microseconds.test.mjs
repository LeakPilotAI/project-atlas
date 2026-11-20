import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import api from './view.cjs';
const original=JSON.parse(fs.readFileSync(new URL('../../../tests/fixtures/market-replay-v1/research.json',import.meta.url),'utf8'));
const stamp=micros=>'2026-10-20T13:33:10.'+String(micros).padStart(6,'0')+'+00:00';
function value(micros=0){const v=structuredClone(original);v.asof=stamp(micros);return v;}
test('reference one microsecond after report clock refuses',()=>{const v=value(100);v.analysis.reference_available_at=stamp(101);assert.throws(()=>api.parseRetainedResearch(JSON.stringify(v)));});
test('one microsecond beyond bar-start TTL refuses descriptive metrics',()=>{const v=value();v.asof='2026-10-20T13:35:00.000001+00:00';assert.throws(()=>api.parseRetainedResearch(JSON.stringify(v)));});
test('sub-minute-misaligned bar one microsecond after minute refuses',()=>{const v=value();v.analysis.bar_timestamp='2026-10-20T13:32:00.000001+00:00';assert.throws(()=>api.parseRetainedResearch(JSON.stringify(v)));});
test('unavailable research cannot carry unsafe timestamp precision',()=>{const v=value();v.asof='9999-01-01T00:00:00+00:00';v.status='REFUSED';v.analysis=null;v.sessions=[];assert.throws(()=>api.parseRetainedResearch(JSON.stringify(v)));});
for(const micros of [0,1,99,100,999,1000,123456,999999])test(`research valid ${micros}us clock preserves local reference date`,()=>{const v=value(micros);assert.deepEqual(api.parseRetainedResearch(JSON.stringify(v)),v);});
for(const micros of [1,123456,999999])test(`reference exactly available at ${micros}us report clock accepted`,()=>{const v=value(micros);v.analysis.reference_available_at=v.asof;assert.deepEqual(api.parseRetainedResearch(JSON.stringify(v)),v);});
for(const asof of ['2026-10-20T13:33:00+00:00','2026-10-20T13:34:59.999999+00:00','2026-10-20T13:35:00+00:00'])test(`completed/fresh boundary ${asof} accepted`,()=>{const v=value();v.asof=asof;assert.deepEqual(api.parseRetainedResearch(JSON.stringify(v)),v);});
for(const status of ['INSUFFICIENT_REFERENCE','INSUFFICIENT_HISTORY','REFUSED'])test(`${status} remains unavailable at a valid fractional clock`,()=>{const v=value(123456);v.status=status;v.analysis=null;v.sessions=[];assert.deepEqual(api.parseRetainedResearch(JSON.stringify(v)),v);});
