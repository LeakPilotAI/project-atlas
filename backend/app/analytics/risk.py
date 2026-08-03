from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskSuggestion:
    position_size_pct: float          # % of account to risk
    risk_amount_note: str
    stop_distance_pct: float
    suggested_leverage: Optional[str] = None


def calculate_position_size(
    account_balance: float = 10000.0,
    risk_per_trade_pct: float = 1.0,
    entry_price: float = 0.0,
    invalidation: float = 0.0,
    confidence: float = 50.0,
) -> RiskSuggestion:
    """
    Simple but practical position sizing.
    - Base risk 1% of account
    - Scale slightly with confidence
    """
    if entry_price <= 0 or invalidation <= 0:
        return RiskSuggestion(
            position_size_pct=1.0,
            risk_amount_note="Unable to calculate precise size",
            stop_distance_pct=0.0,
        )

    stop_distance_pct = abs(entry_price - invalidation) / entry_price * 100

    # Confidence scaling (0.7x to 1.3x)
    conf_mult = 0.7 + (confidence / 100) * 0.6
    adjusted_risk_pct = risk_per_trade_pct * conf_mult

    # Position size so that stop loss = adjusted_risk_pct of account
    if stop_distance_pct > 0:
        position_pct_of_account = (adjusted_risk_pct / stop_distance_pct) * 100
    else:
        position_pct_of_account = 5.0

    # Cap extreme sizes
    position_pct_of_account = max(1.0, min(position_pct_of_account, 25.0))

    risk_amount = account_balance * (adjusted_risk_pct / 100)

    leverage_note = None
    if stop_distance_pct < 1.5:
        leverage_note = "Low stop distance – consider lower leverage"
    elif stop_distance_pct > 4.0:
        leverage_note = "Wide stop – size down or skip"

    return RiskSuggestion(
        position_size_pct=round(position_pct_of_account, 1),
        risk_amount_note=f"Risking ~${risk_amount:.0f} ({adjusted_risk_pct:.1f}% of account)",
        stop_distance_pct=round(stop_distance_pct, 2),
        suggested_leverage=leverage_note,
    )