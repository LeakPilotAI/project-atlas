export const SURFACE_STATUS = {
  ACTIVE_EVIDENCE: { label: "ACTIVE EVIDENCE", meaning: "Evidence collection is active; production promotion remains gated." },
  RESEARCH_ONLY: { label: "RESEARCH ONLY", meaning: "Research presentation only; no trading authority is granted." },
  OPERATIONAL_VIEW: { label: "OPERATIONAL VIEW", meaning: "Operational visibility only; observation does not grant trading authority." },
  GATED: { label: "GATED", meaning: "Capability is intentionally unavailable pending a separate validated unlock." },
} as const;

export type SurfaceStatus = keyof typeof SURFACE_STATUS;

export function SurfaceStatusBadge({ status }: { status: SurfaceStatus }) {
  const definition = SURFACE_STATUS[status];
  return (
    <div className="space-y-1" data-surface-status={status}>
      <span className="inline-flex rounded-full border border-cyan-500/20 bg-cyan-500/5 px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-cyan-300">
        {definition.label}
      </span>
      <p className="text-[11px] leading-5 text-zinc-500">{definition.meaning}</p>
    </div>
  );
}
