export type AuthorityLegendDefinition = Readonly<{
 term:string;
 meaning:string;
}>;

export const AUTHORITY_LEGEND: readonly AuthorityLegendDefinition[] = Object.freeze([
 Object.freeze({term:"Read-only presentation",meaning:"Information can be viewed and navigated; viewing it grants no trading authority."}),
 Object.freeze({term:"Human-review-only evidence",meaning:"Evidence can inform human review; strategy selection and production promotion remain gated."}),
 Object.freeze({term:"Gated capability",meaning:"Capability remains unavailable pending a separate validated roadmap unlock."}),
]);

export const SECTION_POSTURE = Object.freeze({
 navigable:"Purpose: open established read-only operator and research views. Authority: navigation and observation do not grant trading authority.",
 gated:"Roadmap-confirmed boundaries shown for operator context. These are not destinations or disabled controls. Purpose: show roadmap-confirmed unavailable capabilities for operator context. Authority: gated items are not destinations, controls, or readiness claims.",
 active:"Genuine evidence accumulation currently in progress. Gated capabilities are listed separately above. Purpose: show genuine evidence accumulation currently in progress. Authority: active evidence does not unlock strategy selection, promotion, PAPER, or execution.",
} as const);
