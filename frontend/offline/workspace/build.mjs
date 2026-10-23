/* Independent static workspace packaging; never opens a browser or starts a service. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {build as buildMarket} from '../market-replay/build.mjs';
import forecast from '../forecast-accountability/build.cjs';
import {checkParents, publishNew, readBounded, MAX_ARTIFACT_BYTES} from '../market-replay/artifact-io.mjs';
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const FILES = ['index.html', 'market.html', 'forecast.html', 'README.txt'];
export function workspaceMembers(schema) {
  if (schema === 'ATLAS_OFFLINE_EVIDENCE_WORKSPACE_V1') return FILES.slice();
  if (schema === 'ATLAS_OFFLINE_EVIDENCE_WORKSPACE_V2') return ['index.html','market.html','forecast.html','comparison.html','README.txt'];
  throw new Error('Unsupported workspace schema');
}
export function rootIdentity(root) {
  checkParents(root);
  const value = fs.lstatSync(root, {bigint:true});
  if (!value.isDirectory() || value.isSymbolicLink()) throw new Error('Ordinary workspace directory required');
  return value;
}
export function sameRoot(root, expected) {
  const current = rootIdentity(root);
  if (current.dev !== expected.dev || current.ino !== expected.ino) throw new Error('Workspace directory replaced');
}
export function buildWorkspace(destination) {
  if (typeof destination !== 'string' || !destination) throw new Error('Explicit new workspace directory required');
  const root = path.resolve(destination);
  checkParents(root);
  fs.mkdirSync(root, {recursive:false});
  const identity = rootIdentity(root);
  buildMarket(path.join(root, 'market.html'));
  sameRoot(root, identity);
  forecast.build(path.join(root, 'forecast.html'));
  sameRoot(root, identity);
  const style = 'body{background:#08111d;color:#e9f1fb;font:18px system-ui;max-width:68rem;margin:3rem auto;padding:1rem}a{color:#85f2e4}section{border:1px solid #5c7490;border-radius:12px;padding:1.5rem;margin:1.5rem 0}p{line-height:1.6}:focus-visible{outline:3px solid #85f2e4;outline-offset:4px}';
  const stylePin = crypto.createHash('sha256').update(style).digest('base64');
  const index = `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; style-src 'sha256-${stylePin}'; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>Atlas offline evidence workspace</title><style>${style}</style><main><h1>Atlas evidence workspace</h1><p><strong>Production NO-GO · local synthetic evidence only</strong></p><p>These static viewers require no Atlas service, server, provider account or internet connection. No data is preloaded, sent or saved. Native browser acceptance is not established.</p><section><h2><a href="market.html">Market observations and research</a></h2><p>Inspect bar closes, separate quote references, quality reports, descriptive research and replay comparisons. Freshness is relative to the recorded clock, never a live-feed claim.</p></section><section><h2><a href="forecast.html">Forecast accountability</a></h2><p>Inspect recorded forecasts, outcomes, corrections, interval evidence and explicitly imported probability companions. No calibrated market skill, winner or trading authority is established.</p></section><p>Choose a viewer, then explicitly select its local JSON export. Clear or close it to release the loaded view. Missing and refused evidence remains explicit. Hashes check supplied bytes, not provenance or permissions. The separate manifest verifier requires the retained manifest SHA-256.</p></main></html>`;
  publishNew(path.join(root, 'index.html'), index);
  publishNew(path.join(root, 'README.txt'), 'ATLAS OFFLINE EVIDENCE WORKSPACE\nProduction NO-GO. No services, providers, orders, data or credentials are included.\nOpen index.html locally; then select a supported JSON export in the desired viewer.\nNative visual/CSP/browser-file acceptance is not established by this package.\nFile URL automation may be blocked by the current environment; do not bypass that policy.\nVerify with a separately retained manifest SHA256. Verification checks bytes, not source authenticity.\nA partial/failed build is retained, never overwritten, deleted or called accepted. Use a new path after investigation.\nThis package does not start or authorize Atlas, Docker, PAPER/live orders, predictions or Discord.\n');
  sameRoot(root, identity);
  const files = FILES.map(name => {const bytes=readBounded(path.join(root,name));return {path:name,bytes:bytes.length,sha256:hash(bytes)};});
  const manifest = {schema:'ATLAS_OFFLINE_EVIDENCE_WORKSPACE_V1',production_approved:false,source_authenticated:false,
    native_browser_acceptance:'NOT_ESTABLISHED',data_included:false,files};
  const published = publishNew(path.join(root, 'manifest.json'), JSON.stringify(manifest,null,2)+'\n');
  sameRoot(root, identity);
  verifyWorkspace(root, published.sha256);
  return {root,manifest_sha256:published.sha256,production_approved:false,source_authenticated:false};
}
export function verifyWorkspace(directory, expectedManifestSHA256) {
  if (typeof directory !== 'string' || !directory || typeof expectedManifestSHA256 !== 'string' || !/^[0-9a-f]{64}$/.test(expectedManifestSHA256)) throw new Error('Explicit workspace and retained manifest SHA256 required');
  const root = path.resolve(directory), identity = rootIdentity(root);
  const raw = readBounded(path.join(root, 'manifest.json'), 64000);
  if (hash(raw) !== expectedManifestSHA256) throw new Error('Workspace manifest pin mismatch');
  const text = new TextDecoder('utf-8',{fatal:true}).decode(raw), value = JSON.parse(text);
  if (JSON.stringify(value,null,2)+'\n' !== text || !value || Object.keys(value).sort().join('|') !== 'data_included|files|native_browser_acceptance|production_approved|schema|source_authenticated' ||
      !['ATLAS_OFFLINE_EVIDENCE_WORKSPACE_V1','ATLAS_OFFLINE_EVIDENCE_WORKSPACE_V2'].includes(value.schema) || value.production_approved !== false || value.source_authenticated !== false || value.native_browser_acceptance !== 'NOT_ESTABLISHED' || value.data_included !== false ||
      !Array.isArray(value.files)) throw new Error('Workspace manifest contract mismatch');
  if (value.schema === 'ATLAS_OFFLINE_EVIDENCE_WORKSPACE_V2' && !Buffer.from(text).equals(raw)) throw new Error('Workspace manifest contract mismatch');
  const files = workspaceMembers(value.schema);
  if (value.files.length !== files.length) throw new Error('Workspace manifest contract mismatch');
  for (const [index,entry] of value.files.entries()) {
    if (!entry || Object.keys(entry).sort().join('|') !== 'bytes|path|sha256' || entry.path !== files[index] || !Number.isSafeInteger(entry.bytes) || entry.bytes < 0 || entry.bytes > MAX_ARTIFACT_BYTES || typeof entry.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(entry.sha256)) throw new Error('Workspace member identity mismatch');
    const bytes = readBounded(path.join(root,entry.path));
    if (bytes.length !== entry.bytes || hash(bytes) !== entry.sha256) throw new Error('Workspace member bytes mismatch');
    sameRoot(root,identity);
  }
  const names = fs.readdirSync(root).sort();
  if (names.join('|') !== [...files,'manifest.json'].sort().join('|')) throw new Error('Unexpected workspace members');
  return {schema:value.schema==='ATLAS_OFFLINE_EVIDENCE_WORKSPACE_V1'?'ATLAS_OFFLINE_EVIDENCE_WORKSPACE_VERIFIED_V1':'ATLAS_OFFLINE_EVIDENCE_WORKSPACE_VERIFIED_V2',files:files.length,manifest_sha256:expectedManifestSHA256,
    supplied_bytes_consistent:true,source_authenticated:false,native_browser_acceptance:'NOT_ESTABLISHED',production_approved:false};
}
export function main(args=process.argv.slice(2)) {
  if (args.length===1 && !args[0].startsWith('--')) return buildWorkspace(args[0]);
  if (args.length===4 && args[0]==='--verify' && args[2]==='--expected-manifest-sha256') return verifyWorkspace(args[1],args[3]);
  throw new Error('Usage: node build.mjs <new-directory> OR --verify <directory> --expected-manifest-sha256 <retained-sha256>');
}
if (process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) console.log(JSON.stringify(main()));
