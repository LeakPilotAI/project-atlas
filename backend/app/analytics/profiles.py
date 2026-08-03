from dataclasses import dataclass
from typing import Dict


@dataclass
class StrategyProfile:
    name: str
    description: str
    min_rel_volume: float
    min_abs_change_pct: float
    min_zscore: float
    require_multi_tf: bool
    prefer_mean_reversion: bool
    prefer_momentum: bool
    prefer_breakout: bool


PROFILES: Dict[str, StrategyProfile] = {
    "mean_reversion": StrategyProfile(
        name="Mean Reversion",
        description="Fade statistically extreme moves with volume confirmation",
        min_rel_volume=2.8,
        min_abs_change_pct=1.6,
        min_zscore=2.8,
        require_multi_tf=True,
        prefer_mean_reversion=True,
        prefer_momentum=False,
        prefer_breakout=False,
    ),
    "momentum": StrategyProfile(
        name="Momentum",
        description="Ride strong directional moves with volume and structure",
        min_rel_volume=2.2,
        min_abs_change_pct=1.2,
        min_zscore=1.8,
        require_multi_tf=True,
        prefer_mean_reversion=False,
        prefer_momentum=True,
        prefer_breakout=False,
    ),
    "breakout": StrategyProfile(
        name="Breakout",
        description="Catch range expansions and structure breaks",
        min_rel_volume=3.0,
        min_abs_change_pct=2.0,
        min_zscore=2.2,
        require_multi_tf=True,
        prefer_mean_reversion=False,
        prefer_momentum=False,
        prefer_breakout=True,
    ),
    "balanced": StrategyProfile(
        name="Balanced",
        description="Default high-quality mixed profile (current live behavior)",
        min_rel_volume=3.5,
        min_abs_change_pct=1.8,
        min_zscore=3.2,
        require_multi_tf=True,
        prefer_mean_reversion=True,
        prefer_momentum=True,
        prefer_breakout=False,
    ),
}


def get_profile(name: str = "balanced") -> StrategyProfile:
    return PROFILES.get(name, PROFILES["balanced"])


def list_profiles() -> list[dict]:
    return [
        {
            "id": key,
            "name": p.name,
            "description": p.description,
        }
        for key, p in PROFILES.items()
    ]