import Link from "next/link";
import { SurfaceStatusBadge } from "@/app/components/SurfaceStatusBadge";
import { GATED_CAPABILITIES, RESEARCH_SURFACES } from "./catalog";
import { AUTHORITY_LEGEND, SECTION_POSTURE } from "./presentation";

export default function ResearchSurfacesPage(){
 return <div className="min-h-screen bg-[#07080b] text-zinc-200"><main className="mx-auto max-w-6xl space-y-6 px-6 py-8">
  <header className="flex flex-wrap items-start justify-between gap-4">
   <div><p className="text-[11px] uppercase tracking-[0.22em] text-cyan-400/80">Atlas research architecture</p><h1 className="mt-1 text-2xl font-semibold text-white">Research Surfaces</h1><p className="mt-1 max-w-2xl text-xs text-zinc-500">Read-only map of operator and research surfaces. Evidence presentation does not create strategy-selection, PAPER, execution, promotion, or live-capital authority.</p></div>
   <nav className="flex gap-2" aria-label="Research navigation"><Link href="/research" className="rounded-lg border border-cyan-500/20 px-3 py-2 text-xs text-cyan-300">Forward Evidence</Link><Link href="/" className="rounded-lg border border-white/10 px-3 py-2 text-xs text-zinc-400">Command Center</Link></nav>
  </header>
  <section className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5" aria-labelledby="research-boundary-title">
   <p id="research-boundary-title" className="text-[11px] uppercase tracking-widest text-amber-400">Shared safety boundary</p>
   <p className="mt-2 text-sm text-zinc-300">Research surfaces remain descriptive and read-only. Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it.</p>
  </section>
  <section className="rounded-2xl border border-white/8 bg-[#10131a] p-5" aria-labelledby="authority-legend-title">
   <h2 id="authority-legend-title" className="text-sm font-medium text-zinc-300">Authority legend</h2>
   <dl className="mt-3 grid gap-3 text-xs md:grid-cols-3">
    {AUTHORITY_LEGEND.map(item=><Legend key={item.term} term={item.term} meaning={item.meaning}/>)}
   </dl>
  </section>
  <section aria-labelledby="navigable-surfaces-title">
   <div className="mb-3"><h2 id="navigable-surfaces-title" className="text-sm font-medium text-zinc-300">Current navigable surfaces</h2><p className="mt-1 text-xs text-zinc-600">{SECTION_POSTURE.navigable}</p></div>
   <div className="grid gap-4 lg:grid-cols-3" aria-label="Atlas research surfaces">
   {RESEARCH_SURFACES.map(surface=><article key={surface.title} className="flex min-h-64 flex-col rounded-2xl border border-white/8 bg-[#10131a] p-5">
    <SurfaceStatusBadge status={surface.status}/>
    <h2 className="mt-2 text-lg font-semibold text-white">{surface.title}</h2>
    <p className="mt-3 text-sm leading-6 text-zinc-400">{surface.detail}</p>
    <dl className="mt-4 space-y-3 rounded-lg border border-white/5 bg-black/20 p-3 text-xs">
     <Posture label="Purpose" value={surface.purpose}/>
     <Posture label="Data posture" value={surface.dataPosture}/>
     <Posture label="Authority posture" value={surface.authorityPosture}/>
    </dl>
    <Link href={surface.href} className="mt-auto pt-5 text-xs font-medium text-cyan-300">Open read-only surface →</Link>
   </article>)}
   </div>
  </section>
  <section aria-labelledby="gated-capabilities-title">
   <div className="mb-3"><h2 id="gated-capabilities-title" className="text-sm font-medium text-zinc-300">Gated roadmap capabilities</h2><p className="mt-1 text-xs text-zinc-600">{SECTION_POSTURE.gated}</p></div>
   <div className="grid gap-3 md:grid-cols-2">
    {GATED_CAPABILITIES.map(capability=><article key={capability.title} className="rounded-2xl border border-white/8 bg-[#0c0e13] p-4">
     <SurfaceStatusBadge status="GATED"/>
     <h3 className="mt-2 text-sm font-medium text-zinc-300">{capability.title}</h3>
     <p className="mt-2 text-xs leading-5 text-zinc-500">{capability.detail}</p>
    </article>)}
   </div>
  </section>
  <section className="rounded-2xl border border-white/8 bg-[#10131a] p-5" aria-labelledby="active-evidence-title">
   <h2 id="active-evidence-title" className="text-sm font-medium text-zinc-300">Active evidence collection</h2>
   <p className="mt-1 text-xs text-zinc-600">{SECTION_POSTURE.active}</p>
   <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
    <State label="E29 forward strategy evidence" value="ACTIVE · genuine evidence only"/>
    <State label="Alpha / cadence / corroboration" value="ACTIVE · strategy selection gated"/>
   </div>
  </section>
 </main></div>
}
function Legend({term,meaning}:{term:string;meaning:string}){return <div className="rounded-lg border border-white/5 p-3"><dt className="font-medium text-zinc-300">{term}</dt><dd className="mt-1 leading-5 text-zinc-500">{meaning}</dd></div>}
function Posture({label,value}:{label:string;value:string}){return <div><dt className="uppercase tracking-wider text-zinc-600">{label}</dt><dd className="mt-1 leading-5 text-zinc-400">{value}</dd></div>}
function State({label,value}:{label:string;value:string}){return <div className="rounded-lg border border-white/5 px-3 py-3"><p className="text-zinc-500">{label}</p><p className="mt-1 text-zinc-300">{value}</p></div>}
