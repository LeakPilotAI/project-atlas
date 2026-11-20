import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import api from './view.cjs';
const raw=fs.readFileSync(new URL('../../../tests/fixtures/market-replay-v1/quality.json',import.meta.url),'utf8');
const row=()=>JSON.parse(raw);
test('quality accepts exact microsecond report age',()=>{const v=row();v.asof='2026-11-03T00:02:10.000001+00:00';v.windows[0].latest_completed_bar_age_seconds=10.000001;assert.equal(api.parseQuality(JSON.stringify(v)).windows[0].latest_completed_bar_age_seconds,10.000001);});
for(const kind of ['future-source','wrong-age','fractional-minute','max-delay','min-delay'])test(`quality refuses microsecond contradiction ${kind}`,()=>{const v=row();if(kind==='future-source')v.source_asof='2026-11-03T00:02:10.000001+00:00';if(kind==='wrong-age')v.windows[0].latest_completed_bar_age_seconds=10.000001;if(kind==='fractional-minute')v.windows[0].first_bar='2026-11-02T23:58:00.000001+00:00';if(kind==='max-delay')v.windows[0].receipt_delay_max_seconds=190.000001;if(kind==='min-delay')v.windows[0].receipt_delay_min_seconds=10.000001;assert.throws(()=>api.parseQuality(JSON.stringify(v)));});
test('quality retains explicit missing-window and unauthenticated lifecycle limitations',()=>{const v=api.parseQuality(raw);assert.equal(v.windows[0].missing_minutes_between_observed_bars,1);assert.equal(v.lifecycle.authenticated,false);assert.equal(v.session_completeness_verified,false);});
