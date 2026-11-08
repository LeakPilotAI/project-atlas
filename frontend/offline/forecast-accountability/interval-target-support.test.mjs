import {test} from 'node:test';
import assert from 'node:assert/strict';
import api from './view.cjs';
function row(target='2026-10-02T00:00:00Z'){return {asset_class:'US_EQUITY',asset_id:'US_EQUITY:TEST',horizon:'1D',model:'fixture',reference:100,forecast_point:110,actual:110,status:'RESOLVED',target_at:target,interval:{lower:100,upper:120,level:.8}};}
test('repeated targets do not become distinct support',()=>{const c=api.intervalTargetSupport(Array.from({length:20},()=>row())).cohorts[0];assert.equal(c.resolved_n,20);assert.equal(c.distinct_recorded_target_n,1);assert.equal(c.repeated_target_n,19);assert.equal(c.target_support_status,'REPEATED_TARGET_EVIDENCE');});
test('offset-equivalent targets count once',()=>{const c=api.intervalTargetSupport([row(),row('2026-10-01T19:00:00-05:00')]).cohorts[0];assert.equal(c.distinct_recorded_target_n,1)});
test('missing legacy clock remains unknown',()=>{const r=row();delete r.target_at;const c=api.intervalTargetSupport([r]).cohorts[0];assert.equal(c.missing_target_n,1);assert.equal(c.distinct_recorded_target_n,0);assert.equal(c.target_support_status,'UNRECORDED_TARGET_EVIDENCE')});
test('pending cases do not supply target support',()=>{const r=row();r.status='FORECAST_ONLY';r.actual=null;const c=api.intervalTargetSupport([r]).cohorts[0];assert.equal(c.resolved_n,0);assert.equal(c.distinct_recorded_target_n,0);assert.equal(c.target_support_status,'NO_RESOLVED_TARGETS')});
test('distinct targets remain descriptive, not independent observations',()=>{const result=api.intervalTargetSupport([row(),row('2026-10-03T00:00:00Z')]);assert.equal(result.cohorts[0].distinct_recorded_target_n,2);assert.equal(result.independent_samples_established,false);assert.equal(result.calibration_established,false)});
