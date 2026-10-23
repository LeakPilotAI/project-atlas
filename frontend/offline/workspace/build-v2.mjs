/* Explicit V2 static workspace; default V1 build remains independent. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {rootIdentity,sameRoot,workspaceMembers,verifyWorkspace} from './build.mjs';
import {build as buildMarket} from '../market-replay/build.mjs';
import forecast from '../forecast-accountability/build.cjs';
import {buildPacketViewer} from '../forecast-accountability/packet-build.mjs';
import {checkParents,publishNew,readBounded} from '../market-replay/artifact-io.mjs';
const SCHEMA='ATLAS_OFFLINE_EVIDENCE_WORKSPACE_V2';
const onboarding=`FORECAST HISTORY WALKTHROUGH — SYNTHETIC OFFLINE ONLY
1. Keep the completed build receipt and manifest SHA-256 separately. Verify the bundle before reading it. Never add evidence files inside this immutable directory.
2. This package is a viewer, not a forecast generator. Use the existing reviewed offline producer workflow in scripts/observation_runtime/DAILY_FORECAST_WORKFLOW.md from the matching source archive. It requires explicit synthetic inputs, model choices, clocks and source commitments; none are supplied or guessed here.
3. Preserve each producer receipt and its browser_export JSON. Keep the original forecast artifact, dataset/source archive, continuation and expected heads. A raw forecast, raw report, request plan or scenario is not the browser envelope.
4. Open forecast.html only under a permitted local-browser workflow. Choose the later browser_export as the main report and an earlier browser_export as the prior report. Selecting files never appends outcomes or changes history.
5. Pending outcomes have no observed value or error. After an explicit offline outcome update, load the new export. Corrections revise the outcome of the same original forecast, not the number of samples. Earlier snapshots remain immutable.
6. Choose one recorded cohort for the plot. Filters affect displayed cases; different assets, horizons, versions and provenance are never pooled. Inspect the exact-value table, missing binding counts and full report counts. Synthetic results establish no market accuracy or calibrated interval coverage.
7. For a proposed update, the existing daily_holdout_update --preview path is read-only. Publication is a separate explicit --request operation. Never edit a hash, expected head or manifest to overcome a refusal. Supplied continuation is not independent proof of the latest history.
8. comparison.html accepts a comparison packet, not two reports. It requires the exact matching source pins from its archived build. Use forecast.html for explicitly supplied earlier/later browser reports. A source mismatch is not permission to rewrite a packet.
9. Clear removes the displayed evidence; failed replacement clears earlier results and late reads cannot restore them. Closing a page does not delete source files. If browser policy refuses local files, stop that browser path; do not start a server or bypass restrictions.
Native browser acceptance remains NOT_ESTABLISHED. No production, provider, PAPER, live-order, Discord or recovery authority follows.

`;

const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
export function buildWorkspaceV2(destination){
  if(typeof destination!=='string'||!destination)throw Error('Explicit new V2 directory required');
  const root=path.resolve(destination);checkParents(root);fs.mkdirSync(root,{recursive:false});const identity=rootIdentity(root);
  buildMarket(path.join(root,'market.html'));sameRoot(root,identity);
  forecast.build(path.join(root,'forecast.html'));sameRoot(root,identity);
  const comparison=buildPacketViewer(path.join(root,'comparison.html'));sameRoot(root,identity);
  const style='body{background:#08111d;color:#e9f1fb;font:18px system-ui;max-width:68rem;margin:3rem auto;padding:1rem}a{color:#85f2e4}section{border:1px solid #5c7490;border-radius:12px;padding:1.5rem;margin:1.5rem 0}p{line-height:1.6}:focus-visible{outline:3px solid #85f2e4;outline-offset:4px}';
  const stylePin=createHash('sha256').update(style).digest('base64');
  const index=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'sha256-${stylePin}'; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>Atlas offline evidence workspace V2</title><style>${style}</style><main><h1>Atlas evidence workspace</h1><p><strong>Production NO-GO · local synthetic evidence only · V2</strong></p><p>Choose a local evidence viewer. No server, account, provider connection or data is included. Browser visual/security acceptance remains unestablished.</p><section><h2><a href="market.html">Market observations and research</a></h2><p>Bar closes, quote references, observed-window quality and descriptive replay. Freshness refers to the recorded clock, never a live feed.</p></section><section><h2><a href="forecast.html">Forecast accountability</a></h2><p>Original forecasts, outcomes, corrections, intervals and recorded probabilities. Select a supplied browser report or log-loss companion.</p></section><section><h2><a href="comparison.html">Reported outcome changes</a></h2><p>Open one matching comparison packet. Both supplied report snapshots are reproduced using pins from this build. Missing/pending/conflicted cases remain visible. No source authenticity, chain ancestry, calibrated skill or trading authority follows.</p></section><p><a href="README.txt">Forecast-history walkthrough and refusal guidance</a></p><p>Files are explicitly selected and stay in memory; nothing is uploaded or saved. Keep data outside this immutable bundle. Clear or close a page to release its view. Verify bundle bytes with the separately retained manifest SHA-256. Matching archives are needed for old comparison packets.</p></main></html>`;
  publishNew(path.join(root,'index.html'),index);sameRoot(root,identity);
  publishNew(path.join(root,'README.txt'),onboarding+'ATLAS OFFLINE EVIDENCE WORKSPACE V2\nProduction NO-GO. No services, providers, orders, credentials or datasets are included.\nindex.html links market.html, forecast.html and comparison.html.\nSelect data explicitly; store source reports/packets outside this bundle.\nComparison packets require the exact source pins embedded in comparison.html; no automatic upgrade.\nNo live freshness, calibrated skill, source authenticity, ancestry or runtime authority is established.\nNative browser visual/CSP/file acceptance is NOT_ESTABLISHED. Do not bypass browser URL policy.\nRetain the manifest SHA256 separately; verification checks supplied bytes only.\nFailed/partial outputs are preserved; never reuse an existing destination.\n');sameRoot(root,identity);
  const files=workspaceMembers(SCHEMA).map(name=>{const bytes=readBounded(path.join(root,name));sameRoot(root,identity);return {path:name,bytes:bytes.length,sha256:hash(bytes)};});
  const manifest={schema:SCHEMA,production_approved:false,source_authenticated:false,native_browser_acceptance:'NOT_ESTABLISHED',data_included:false,files};
  const receipt=publishNew(path.join(root,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');sameRoot(root,identity);verifyWorkspace(root,receipt.sha256);
  return {root,schema:SCHEMA,manifest_sha256:receipt.sha256,comparison_source_pins:comparison.source_pins,production_approved:false,source_authenticated:false,native_browser_acceptance:'NOT_ESTABLISHED'};
}
export function mainV2(args=process.argv.slice(2)){
  if(args.length===1&&!args[0].startsWith('--'))return buildWorkspaceV2(args[0]);
  if(args.length===4&&args[0]==='--verify'&&args[2]==='--expected-manifest-sha256'){
    const value=verifyWorkspace(args[1],args[3]);if(value.schema!=='ATLAS_OFFLINE_EVIDENCE_WORKSPACE_VERIFIED_V2')throw Error('V2 workspace required');return value;
  }
  throw Error('Usage: node build-v2.mjs <new-directory> OR --verify <directory> --expected-manifest-sha256 <retained-sha256>');
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))process.stdout.write(JSON.stringify(mainV2())+'\n');
