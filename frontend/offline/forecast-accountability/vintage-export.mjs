/* Explicit offline evidence export. No server, providers, storage authority or actions. */
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import api from './view.cjs';
import {readBounded,publishNew} from '../market-replay/artifact-io.mjs';
const VIEW = fileURLToPath(new URL('./view.cjs',import.meta.url));
const SELF = fileURLToPath(import.meta.url), IO = fileURLToPath(new URL('../market-replay/artifact-io.mjs',import.meta.url));
const hash = text => createHash('sha256').update(text).digest('hex');
const LOADED_SOURCE_SHA = hash(readBounded(VIEW)), EXPORTER_SHA = hash(readBounded(SELF)), IO_SHA = hash(readBounded(IO));
function sourceCheck(){if(hash(readBounded(VIEW))!==LOADED_SOURCE_SHA||hash(readBounded(SELF))!==EXPORTER_SHA||hash(readBounded(IO))!==IO_SHA)throw new Error('Comparator source changed; use a new isolated invocation');}
function jsonPath(value){if(typeof value!=='string'||path.extname(value).toLowerCase()!=='.json')throw new Error('Explicit JSON file required');}
const utf8 = bytes => new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);
const PINS = Object.freeze({comparator_source_sha256:LOADED_SOURCE_SHA,exporter_source_sha256:EXPORTER_SHA,artifact_io_source_sha256:IO_SHA});
export async function createComparisonPacket(leftBrowser,rightBrowser){
  sourceCheck();const result=await api.createComparisonPacket(leftBrowser,rightBrowser,PINS,hash);sourceCheck();return result;
}
export async function verifyComparisonPacket(text){
  sourceCheck();const result=await api.verifyComparisonPacket(text,PINS,hash);sourceCheck();return result;
}
export async function exportComparison(leftPath,rightPath,output){
  for(const value of [leftPath,rightPath,output])jsonPath(value);
  const left=readBounded(leftPath,api.LIMIT),right=readBounded(rightPath,api.LIMIT);
  const packet=await createComparisonPacket(utf8(left),utf8(right));await verifyComparisonPacket(packet);
  const stable=()=>{sourceCheck();if(!readBounded(leftPath,api.LIMIT).equals(left)||!readBounded(rightPath,api.LIMIT).equals(right))throw new Error('Input changed before acknowledgement');};
  stable();const receipt=publishNew(output,packet);
  if(!readBounded(output).equals(Buffer.from(packet)))throw new Error('Published comparison changed');
  await verifyComparisonPacket(packet);stable();
  return {...receipt,schema:'AFI_REPORT_VINTAGE_PACKET_V1',production_approved:false,source_authenticated:false,runtime_provenance_verified:false};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{
    const args=process.argv.slice(2);
    if(args.length===2&&args[0]==='--verify'){
      jsonPath(args[1]);const result=await verifyComparisonPacket(utf8(readBounded(args[1])));
      process.stdout.write(JSON.stringify({status:'VERIFIED_SUPPLIED_BYTES',union_forecast_n:result.comparison.union_forecast_n,production_approved:false,source_authenticated:false,runtime_provenance_verified:false})+'\n');
    }else if(args.length===4&&args[0]==='--export')process.stdout.write(JSON.stringify(await exportComparison(args[1],args[2],args[3]))+'\n');
    else throw new Error('Explicit export or verify arguments required');
  }catch{
    process.stderr.write('Comparison refused. Existing and partial evidence preserved. No authority granted.\n');process.exitCode=1;
  }
}
