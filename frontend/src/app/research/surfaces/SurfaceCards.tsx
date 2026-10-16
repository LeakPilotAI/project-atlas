import Link from "next/link";
import { SurfaceStatusBadge } from "@/app/components/SurfaceStatusBadge";
import type { GatedCapabilityDefinition, ResearchSurfaceDefinition } from "./catalog";

export function ResearchSurfaceCard({surface}:{surface:ResearchSurfaceDefinition}){
 const headingId=`research-surface-${surface.title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"")}`;
 const detailId=`${headingId}-detail`;
 return <article aria-labelledby={headingId} aria-describedby={detailId} className="flex min-h-60 flex-col rounded-2xl border border-white/8 bg-[#10131a] p-4 sm:p-5">
  <SurfaceStatusBadge status={surface.status}/>
  <h2 id={headingId} className="mt-2 text-lg font-semibold text-white">{surface.title}</h2>
  <p id={detailId} className="mt-3 text-sm leading-6 text-zinc-400">{surface.detail}</p>
  <dl className="mt-4 space-y-3 rounded-lg border border-white/5 bg-black/20 p-3 text-xs">
   <Posture label="Purpose" value={surface.purpose}/>
   <Posture label="Data posture" value={surface.dataPosture}/>
   <Posture label="Authority posture" value={surface.authorityPosture}/>
  </dl>
  <Link href={surface.href} aria-label={`Open ${surface.title} read-only surface`} className="mt-auto pt-5 text-xs font-medium text-cyan-300">Open read-only surface →</Link>
 </article>
}

export function GatedCapabilityCard({capability}:{capability:GatedCapabilityDefinition}){
 const headingId=`gated-capability-${capability.title.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"")}`;
 const detailId=`${headingId}-detail`;
 return <article aria-labelledby={headingId} aria-describedby={detailId} className="rounded-2xl border border-white/8 bg-[#0c0e13] p-4">
  <SurfaceStatusBadge status="GATED"/>
  <h3 id={headingId} className="mt-2 text-sm font-medium text-zinc-300">{capability.title}</h3>
  <p id={detailId} className="mt-2 text-xs leading-5 text-zinc-500">{capability.detail}</p>
 </article>
}

function Posture({label,value}:{label:string;value:string}){return <div><dt className="uppercase tracking-wider text-zinc-600">{label}</dt><dd className="mt-1 leading-5 text-zinc-400">{value}</dd></div>}
