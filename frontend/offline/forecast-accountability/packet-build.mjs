/* Explicit static packet page; no browser, server, Atlas or provider is started. */
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {readBounded,publishNew} from '../market-replay/artifact-io.mjs';
const folder=path.dirname(fileURLToPath(import.meta.url));
const raw=name=>readBounded(path.join(folder,name));
const text=bytes=>new TextDecoder('utf-8',{fatal:true}).decode(bytes).replace(/^\uFEFF/,'').replace(/\r\n?/g,'\n');
const hex=bytes=>createHash('sha256').update(bytes).digest('hex');
export function buildPacketViewer(output){
  if(typeof output!=='string'||path.extname(output)!=='.html')throw Error('Explicit new HTML output required');
  const source=raw('view.cjs'),exporter=raw('vintage-export.mjs'),io=raw('../market-replay/artifact-io.mjs');
  const pins={comparator_source_sha256:hex(source),exporter_source_sha256:hex(exporter),artifact_io_source_sha256:hex(io)};
  const consumer=text(source),mount=text(raw('packet-mount.cjs')),style=text(raw('view.css'));
  const script=`(()=>{'use strict';const sourcePins=Object.freeze(${JSON.stringify(pins)});const api={exports:{}};(function(module){\n${consumer}\n})(api);const packet={exports:{}};(function(module){\n${mount}\n})(packet);packet.exports.mount(document,api.exports,sourcePins);})();`;
  if(/<\/script|<\/style/i.test(script+style))throw Error('Closing-tag escape refused');
  const sha=value=>createHash('sha256').update(value).digest('base64');
  const html=`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-${sha(script)}'; style-src 'sha256-${sha(style)}'; connect-src 'none'; base-uri 'none'; form-action 'none'"><title>Atlas supplied comparison</title><style>${style}</style></head><body><a class="skip" href="#packet-results">Skip to comparison</a><main><div class="brand">PROJECT ATLAS / OFFLINE EVIDENCE</div><h1>Reported outcome changes.</h1><p class="intro">Open one exported comparison packet. Both supplied snapshots are checked and compared again. No server, account or live feed is connected.</p><section class="notice"><strong>Production NO-GO · synthetic evidence only</strong><p>Source pins come from this build. Matching bytes do not prove source truth, independent history, calibrated skill or runtime safety.</p></section><section class="panel"><label for="packet-file">Comparison packet JSON — maximum 2 MB</label><input id="packet-file" type="file" accept=".json,application/json"><button id="clear-packet" type="button">Clear comparison</button><p id="packet-status" role="status" aria-live="polite"></p></section><div id="packet-results"></div><footer>Nothing is uploaded or saved. Existing evidence is never modified. Source/code mismatch refuses; retain matching archives. Native browser security and visual acceptance remain a separate gate.</footer></main><script>${script}</script></body></html>`;
  return {...publishNew(output,html),production_approved:false,source_authenticated:false,native_browser_acceptance:'NOT_ESTABLISHED',source_pins:pins};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  if(process.argv.length!==3)throw Error('Usage: node packet-build.mjs <new-output.html>');
  process.stdout.write(JSON.stringify(buildPacketViewer(process.argv[2]))+'\n');
}
