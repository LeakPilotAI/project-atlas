import type { SurfaceStatus } from "@/app/components/SurfaceStatusBadge";

export type ResearchSurfaceDefinition = Readonly<{
 title:string;
 status:SurfaceStatus;
 href:string;
 detail:string;
 purpose:string;
 dataPosture:string;
 authorityPosture:string;
}>;

export type GatedCapabilityDefinition = Readonly<{
 title:string;
 detail:string;
}>;

export const RESEARCH_SURFACES: readonly ResearchSurfaceDefinition[] = Object.freeze([
 Object.freeze({title:"Alpha / Forward Evidence",status:"ACTIVE_EVIDENCE",href:"/research",detail:"Prospective challenger evidence, diversity, maturity, and confirmation diagnostics.",purpose:"Evaluate genuine forward challenger evidence for human review.",dataPosture:"Prospective evidence · accumulated over time · no synthetic acceleration.",authorityPosture:"Human review only · production promotion gated · strategy selection remains gated."}),
 Object.freeze({title:"Crypto Quality Dips",status:"RESEARCH_ONLY",href:"/",detail:"Public-contract evidence readiness, chain context, freshness, and operator attention.",purpose:"Present bounded Crypto Quality Dips evidence readiness and integrity context.",dataPosture:"Frozen public read-only contract · fail-closed consumer · no store internals.",authorityPosture:"Authority locked · no scoring, PAPER, execution, or live capital · repair authority unavailable."}),
 Object.freeze({title:"Command Center Operations",status:"OPERATIONAL_VIEW",href:"/",detail:"Atlas runtime and operator-facing system state, including the bounded Crypto Quality Dips panel.",purpose:"Provide operator visibility into Atlas runtime and bounded research status.",dataPosture:"Operational observation · existing runtime feeds only · no authority inferred from display.",authorityPosture:"Watch-only visibility · navigation and observation do not grant trading authority."}),
]);

export const GATED_CAPABILITIES: readonly GatedCapabilityDefinition[] = Object.freeze([
 Object.freeze({title:"Crypto Quality Dips autonomy",detail:"INACTIVE / GATED · autonomous acquisition, scoring/outcomes, alerts/scheduling, PAPER, and execution remain unavailable."}),
 Object.freeze({title:"Alpha strategy selection",detail:"Forward evidence collection remains active; strategy-selection and production-promotion authority remain gated."}),
 Object.freeze({title:"Residual trading Discord lifecycle",detail:"Remaining trading-adjacent lifecycle producers require dedicated lifecycle contracts rather than bulk migration."}),
 Object.freeze({title:"Automated real-money execution",detail:"Live-capital execution remains gated and is not exposed as an operator action."}),
]);
