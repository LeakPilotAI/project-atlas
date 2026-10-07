import { ReadOnlyPageShell } from "@/app/components/ReadOnlyPageShell";
import { PageIdentity } from "@/app/components/PageIdentity";
import { SurfaceNavLink } from "@/app/components/SurfaceNavLink";
import { GATED_CAPABILITIES, RESEARCH_SURFACES } from "./catalog";
import { AUTHORITY_LEGEND, SECTION_POSTURE } from "./presentation";
import { GatedCapabilityCard, ResearchSurfaceCard } from "./SurfaceCards";
import { SectionHeading } from "./SectionHeading";
import { ActiveEvidenceState, AuthorityLegendItem } from "./ResearchPrimitives";

export default function ResearchSurfacesPage(){
 return <ReadOnlyPageShell>
  <header className="flex flex-wrap items-start justify-between gap-4">
   <PageIdentity eyebrow="Atlas research architecture" title="Research Surfaces" description="Read-only map of operator and research surfaces. Evidence presentation does not create strategy-selection, PAPER, execution, promotion, or live-capital authority." constrainDescription/>
   <nav className="flex flex-wrap gap-2" aria-label="Research navigation"><SurfaceNavLink href="/research" variant="primary">Forward Evidence</SurfaceNavLink><SurfaceNavLink href="/">Command Center</SurfaceNavLink></nav>
  </header>
  <section className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 sm:p-5" aria-labelledby="research-boundary-title">
   <p id="research-boundary-title" className="text-[11px] uppercase tracking-widest text-amber-400">Shared safety boundary</p>
   <p className="mt-2 text-sm text-zinc-300">Research surfaces remain descriptive and read-only. Trading authority stays gated unless a separate validated roadmap execution explicitly unlocks it.</p>
  </section>
  <section className="rounded-2xl border border-white/8 bg-[#10131a] p-4 sm:p-5" aria-labelledby="authority-legend-title">
   <h2 id="authority-legend-title" className="text-sm font-medium text-zinc-300">Authority legend</h2>
   <dl className="mt-3 grid gap-3 text-xs md:grid-cols-3">
    {AUTHORITY_LEGEND.map(item=><AuthorityLegendItem key={item.term} term={item.term} meaning={item.meaning}/>)}
   </dl>
  </section>
  <section aria-labelledby="navigable-surfaces-title">
   <SectionHeading id="navigable-surfaces-title" title="Current navigable surfaces" posture={SECTION_POSTURE.navigable}/>
   <div className="grid gap-4 lg:grid-cols-3" aria-label="Atlas research surfaces">
   {RESEARCH_SURFACES.map(surface=><ResearchSurfaceCard key={surface.title} surface={surface}/>)}
   </div>
  </section>
  <section aria-labelledby="gated-capabilities-title">
   <SectionHeading id="gated-capabilities-title" title="Gated roadmap capabilities" posture={SECTION_POSTURE.gated}/>
   <div className="grid gap-3 md:grid-cols-2">
    {GATED_CAPABILITIES.map(capability=><GatedCapabilityCard key={capability.title} capability={capability}/>)}
   </div>
  </section>
  <section className="rounded-2xl border border-white/8 bg-[#10131a] p-4 sm:p-5" aria-labelledby="active-evidence-title">
   <h2 id="active-evidence-title" className="text-sm font-medium text-zinc-300">Active evidence collection</h2>
   <p className="mt-1 text-xs text-zinc-600">{SECTION_POSTURE.active}</p>
   <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
    <ActiveEvidenceState label="E29 forward strategy evidence" value="ACTIVE · genuine evidence only"/>
    <ActiveEvidenceState label="Alpha / cadence / corroboration" value="ACTIVE · strategy selection gated"/>
   </div>
  </section>
 </ReadOnlyPageShell>
}
