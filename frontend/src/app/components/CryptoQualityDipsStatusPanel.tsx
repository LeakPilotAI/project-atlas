"use client";
import {useEffect,useState} from "react";
import {consumeCryptoQualityDipsStatus,type CryptoQualityDipsConsumerResult,type CryptoQualityDipsViewModel} from "@/lib/cryptoQualityDipsStatus";
const API="http://127.0.0.1:8000", STATUS_PATH="/api/investments/crypto-quality-dips/status";
const INITIAL:CryptoQualityDipsViewModel={schemaVersion:"E72_CRYPTO_QUALITY_DIPS_PUBLIC_V1",displayState:"UNAVAILABLE",severity:"CRITICAL",status:"PUBLIC_STATUS_UNAVAILABLE",operatorAttentionRequired:true,chainState:"UNKNOWN",recoveryStatus:"UNKNOWN",readiness:{gatesMet:false,totalObservations:0,validObservations:0,validFraction:0,distinctObservationDays:0},authorityLocked:true};
function words(v:string){return v.replaceAll("_"," ")}
export default function CryptoQualityDipsStatusPanel(){
 const[result,setResult]=useState<CryptoQualityDipsConsumerResult>({ok:false,value:INITIAL,reason:"LOADING"});
 useEffect(()=>{let stop=false;async function load(){try{const response=await fetch(`${API}${STATUS_PATH}`,{method:"GET",cache:"no-store"});if(!response.ok)throw new Error(String(response.status));const consumed=consumeCryptoQualityDipsStatus(await response.json());if(!stop)setResult(consumed)}catch{if(!stop)setResult({ok:false,value:INITIAL,reason:"NETWORK_OR_HTTP_ERROR"})}}load();const id=setInterval(load,15000);return()=>{stop=true;clearInterval(id)}},[]);
 const vm=result.value,validPct=Math.round(vm.readiness.validFraction*100);
 const tone=vm.severity==="CRITICAL"?"border-rose-500/30 bg-rose-500/5 text-rose-300":vm.severity==="WARNING"?"border-amber-500/30 bg-amber-500/5 text-amber-300":"border-cyan-500/20 bg-cyan-500/5 text-cyan-300";
 return <section className="rounded-2xl border border-cyan-500/15 bg-[#0d1118] p-5">
  <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-[11px] uppercase tracking-[0.2em] text-cyan-400/80">Crypto Quality Dips · Research only</p><h2 className="mt-1 text-lg font-semibold text-white">Evidence readiness</h2><p className="mt-1 text-xs text-zinc-500">Read-only evidence surface. No scoring, PAPER, execution, repair, or live-capital authority.</p></div><div className={`rounded-lg border px-3 py-2 text-right ${tone}`}><p className="text-[10px] uppercase tracking-wider opacity-70">{vm.severity}</p><p className="text-xs font-medium">{words(vm.displayState)}</p></div></div>
  {!result.ok&&<div className="mt-4 rounded-lg border border-rose-500/25 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">Status unavailable / fail closed · {words(result.reason)}</div>}
  <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5"><Metric label="Observations" value={vm.readiness.totalObservations}/><Metric label="Valid" value={vm.readiness.validObservations}/><Metric label="Valid fraction" value={`${validPct}%`}/><Metric label="Evidence days" value={vm.readiness.distinctObservationDays}/><Metric label="Research gates" value={vm.readiness.gatesMet?"MET":"NOT MET"}/></div>
  <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/5" aria-label="valid evidence fraction"><div className="h-full bg-cyan-500/70" style={{width:`${validPct}%`}}/></div>
  <div className="mt-4 grid gap-2 text-xs md:grid-cols-3"><Context label="Operator status" value={words(vm.status)}/><Context label="Evidence chain" value={words(vm.chainState)}/><Context label="Recovery" value={words(vm.recoveryStatus)}/></div>
  <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-3 text-[11px]"><span className={vm.operatorAttentionRequired?"text-amber-300":"text-zinc-500"}>Operator attention: {vm.operatorAttentionRequired?"REQUIRED":"not required"}</span><span className="font-medium text-emerald-300">AUTHORITY LOCKED · READ ONLY</span></div>
 </section>
}
function Metric({label,value}:{label:string;value:string|number}){return <div className="rounded-xl border border-white/8 bg-black/20 p-3"><p className="text-[10px] uppercase tracking-wider text-zinc-600">{label}</p><p className="mt-1 text-base font-semibold text-zinc-100 tabular-nums">{value}</p></div>}
function Context({label,value}:{label:string;value:string}){return <div className="rounded-lg border border-white/5 px-3 py-2"><span className="text-zinc-600">{label}: </span><span className="text-zinc-300">{value}</span></div>}
