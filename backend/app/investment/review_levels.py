"""Investment review levels. Recovery / Fair Value / Overvaluation / Thesis Review.

These are NOT take-profit orders and NOT Hyperliquid 1.8R targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.investment.enums import ThesisState
from app.investment.moves import MoveReport

REVIEW_VERSION = "atlas-review-7.0"


@dataclass
class ReviewLevels:
    recovery: Optional[float] = None
    fair_value: Optional[float] = None
    overvaluation: Optional[float] = None
    thesis_review: Optional[float] = None
    reasons: Dict[str, str] = field(default_factory=dict)
    invalidation: List[str] = field(default_factory=list)
    version: str = REVIEW_VERSION
    disclaimer: str = (
        "Review levels are conditions to reassess a manual accumulation, not automatic sells."
    )

    def as_dict(self) -> Dict[str, object]:
        return {
            "recovery": self.recovery,
            "fair_value": self.fair_value,
            "overvaluation": self.overvaluation,
            "thesis_review": self.thesis_review,
            "reasons": dict(self.reasons),
            "invalidation": list(self.invalidation),
            "version": self.version,
            "disclaimer": self.disclaimer,
        }


def build_review_levels(
    *,
    price: Optional[float],
    atr: Optional[float] = None,
    drawdown: Optional[float] = None,
    vol_ann: Optional[float] = None,
    thesis: ThesisState = ThesisState.UNKNOWN,
    move: Optional[MoveReport] = None,
) -> ReviewLevels:
    if price is None or price <= 0:
        return ReviewLevels(invalidation=["no price — review levels not issued"])
    px = float(price)
    step = 0.08
    if atr is not None and atr > 0:
        step = max(0.04, min(0.18, (atr / px) * 3.0))
    elif vol_ann is not None and vol_ann > 0:
        step = max(0.04, min(0.18, vol_ann / 12 ** 0.5))
    elif drawdown is not None:
        step = max(0.04, min(0.15, abs(float(drawdown)) * 0.35))

    recovery = round(px * (1.0 + step), 2)
    fair = round(px * (1.0 + 2.2 * step), 2)
    over = round(px * (1.0 + 3.5 * step), 2)
    # Thesis review is a *price path* reminder plus fundamental invalidation list.
    thesis_px = round(px * (1.0 + 1.4 * step), 2)

    invalidation = [
        "FCF collapse or persistent negative free cash flow",
        "earnings deterioration vs the last usable snapshot",
        "debt explosion or cash burn that breaks the balance-sheet view",
        "margin collapse",
        "guidance deterioration (sourced headline required)",
        "regulatory impairment or major dilution",
        "accounting concerns",
    ]
    if thesis in (ThesisState.DAMAGED, ThesisState.BROKEN, ThesisState.UNDER_PRESSURE):
        invalidation.insert(0, "thesis already not INTACT — do not add; review whether to hold existing shares")

    return ReviewLevels(
        recovery=recovery,
        fair_value=fair,
        overvaluation=over,
        thesis_review=thesis_px,
        reasons={
            "recovery": f"~{step:.1%} above last (vol/ATR-scaled) — first reassessment, not a sell order",
            "fair_value": f"~{2.2 * step:.1%} above last — valuation-normalization review",
            "overvaluation": f"~{3.5 * step:.1%} above last — trim/overvaluation review",
            "thesis_review": "re-read fundamentals and any sourced catalyst; stop adding if thesis breaks",
        },
        invalidation=invalidation,
    )
