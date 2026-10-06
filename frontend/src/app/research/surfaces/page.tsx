import Link from "next/link";
import { SurfaceStatusBadge, type SurfaceStatus } from "@/app/components/SurfaceStatusBadge";

const surfaces: ReadonlyArray<{title:string;status:SurfaceStatus;href:string;detail:string;purpose:string;dataPosture:string;authorityPosture:string}>=[
 {title:"Alpha / Forward Evidence",status:"ACTIVE_EVIDENCE",href:"/research",detail:"Prospective challenger evidence, diversity, maturity, and confirmation diagnostics.",purpose:"Evaluate genuine forward challenger evidence for human review.",dataPosture:"Prospective evidence · accumulated over time · no synthetic acceleration.",authorityPosture:"Human review only · production promotion gated · strategy selection remains gated."},
 {title:"Crypto Quality Dips",status:"RESEARCH_ONLY",href:"/",detail:"Public-contract evidence readiness, chain context, freshness, and operator attention.",purpose:"Present bounded Crypto Quality Dips evidence readiness and integrity context.",dataPosture:"Frozen public read-only contract · fail-closed consumer · no store internals.",authorityPosture:"Authority locked · no scoring, PAPER, execution, or live capital · repair authority unavailable."},
 {title:"Command Center Operations",status:"OPERATIONAL_VIEW",href:"/",detail:"Atlas runtime and operator-facing system state, including the bounded Crypto Quality Dips panel.",purpose:"Provide operator visibility into Atlas runtime and bounded research status.",dataPosture:"Operational observation · existing runtime feeds only · no authority inferred from display.",authorityPosture:"Watch-only visibility · navigation and observation do not grant trading authority."},
];

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
    <Legend term="Read-only presentation" meaning="Information can be viewed and navigated; viewing it grants no trading authority."/>
    <Legend term="Human-review-only evidence" meaning="Evidence can inform human review; strategy selection and production promotion remain gated."/>
    <Legend term="Gated capability" meaning="Capability remains unavailable pending a separate validated roadmap unlock."/>
   </dl>
  </section>
  <section className="grid gap-4 lg:grid-cols-3" aria-label="Atlas research surfaces">
   {surfaces.map(surface=><article key={surface.title} className="flex min-h-64 flex-col rounded-2xl border border-white/8 bg-[#10131a] p-5">
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
  </section>
  <section className="rounded-2xl border border-white/8 bg-[#10131a] p-5">
   <h2 className="text-sm font-medium text-zinc-300">Current roadmap state</h2>
   <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
    <State label="E29 forward strategy evidence" value="ACTIVE · genuine evidence only"/>
    <State label="Alpha / cadence / corroboration" value="ACTIVE · strategy selection gated"/>
    <State label="Crypto Quality Dips autonomy" value="INACTIVE / GATED"/>
    <State label="Residual trading Discord lifecycle" value="GATED"/>
   </div>
  </section>
 </main></div>
}
function Legend({term,meaning}:{term:string;meaning:string}){return <div className="rounded-lg border border-white/5 p-3"><dt className="font-medium text-zinc-300">{term}</dt><dd className="mt-1 leading-5 text-zinc-500">{meaning}</dd></div>}
function Posture({label,value}:{label:string;value:string}){return <div><dt className="uppercase tracking-wider text-zinc-600">{label}</dt><dd className="mt-1 leading-5 text-zinc-400">{value}</dd></div>}
function State({label,value}:{label:string;value:string}){return <div className="rounded-lg border border-white/5 px-3 py-3"><p className="text-zinc-500">{label}</p><p className="mt-1 text-zinc-300">{value}</p></div>}
