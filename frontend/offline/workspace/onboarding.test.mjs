import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import vm from 'node:vm';
import {createHash,webcrypto} from 'node:crypto';
import {buildWorkspaceV2} from './build-v2.mjs';
import {verifyWorkspace} from './build.mjs';

test('packaged walkthrough and embedded viewer accept immutable pending/resolved/corrected histories',async()=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'atlas-onboarding-')),output=path.join(root,'workspace');
 const receipt=buildWorkspaceV2(output);assert.equal(verifyWorkspace(output,receipt.manifest_sha256).native_browser_acceptance,'NOT_ESTABLISHED');
 const before=Object.fromEntries(fs.readdirSync(output).map(n=>[n,fs.readFileSync(path.join(output,n))]));
 const readme=before['README.txt'].toString('utf8'),html=before['forecast.html'].toString('utf8');
 for(const text of ['browser_export','main report','prior report','--preview','--request','expected heads','comparison.html','NOT_ESTABLISHED'])assert.ok(readme.includes(text));
 assert.ok(before['index.html'].toString('utf8').includes('href="README.txt"'));
 const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
 assert.ok(html.includes("'sha256-"+createHash('sha256').update(script).digest('base64')+"'"));
 const exportBox={exports:{}};vm.runInNewContext(script,{module:exportBox,crypto:webcrypto,TextEncoder,TextDecoder},{timeout:2000});
 const api=exportBox.exports,fixtures=JSON.parse(fs.readFileSync(new URL('../../../tests/fixtures/afi-vintage-score-impact-v1/reports.json',import.meta.url),'utf8')).interval;
 const reports=[];
 for(const r of fixtures){const report_json=JSON.stringify(r),raw=JSON.stringify({schema:'AFI_BROWSER_REPORT_V1',report_json,payload_sha256:createHash('sha256').update(report_json).digest('hex')});reports.push(await api.verifyEnvelope(raw));}
 assert.equal(reports[0].rows[0].actual,null);assert.equal(reports[1].rows[0].status,'RESOLVED');assert.equal(reports[2].rows[0].correction_n,1);
 const identities=reports.map(r=>r.rows[0].forecast_sha256);assert.equal(new Set(identities).size,1);
 for(const report of reports){const groups=api.forecastPlot(report.rows).cohorts;assert.equal(groups.length,1);const plotted=api.forecastPlot(report.rows,groups[0].id);assert.equal(plotted.points.length,1);assert.equal(plotted.points[0].actual===null,report.rows[0].actual===null);}
 const comparison=api.compareReportVintages(reports[1],reports[2]);assert.equal(comparison.union_forecast_n,1);assert.equal(comparison.history_ancestry_verified,false);
 const states=[],loader=api.createLoader(s=>states.push(s));await loader.load('{');assert.equal(states.at(-1).status,'REFUSED');assert.equal(states.at(-1).report,null);
 loader.clear();assert.equal(states.at(-1).status,'EMPTY');
 for(const [name,bytes] of Object.entries(before))assert.deepEqual(fs.readFileSync(path.join(output,name)),bytes);
});
