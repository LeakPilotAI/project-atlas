from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import Side


class PerpSetupState(str, Enum):
    WAIT = "WAIT"
    PREPARE = "PREPARE"
    L1_ACTIVE = "L1_ACTIVE"
    L2_ACTIVE = "L2_ACTIVE"
    L3_ACTIVE = "L3_ACTIVE"
    TP1_HIT = "TP1_HIT"
    TP2_HIT = "TP2_HIT"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class SetupStateSnapshot:
    state: PerpSetupState
    next_action: str
    distance_to_l1_pct: float


def classify_setup_state(*, side: Side, mark: float, l1: float, l2: float, l3: float, stop: float, tp1: float, tp2: float, prepare_distance_pct: float = 0.6) -> SetupStateSnapshot:
    mark = float(mark)
    if mark <= 0:
        raise ValueError("mark must be positive")
    if prepare_distance_pct < 0:
        raise ValueError("prepare_distance_pct cannot be negative")

    if side is Side.LONG:
        if mark <= stop:
            return SetupStateSnapshot(PerpSetupState.INVALIDATED, "Do not enter; setup invalidated below stop.", 0.0)
        if mark >= tp2:
            return SetupStateSnapshot(PerpSetupState.TP2_HIT, "TP2 reached; do not chase a fresh entry.", 0.0)
        if mark >= tp1:
            return SetupStateSnapshot(PerpSetupState.TP1_HIT, "TP1 reached; manage remaining position only.", 0.0)
        if mark <= l3:
            return SetupStateSnapshot(PerpSetupState.L3_ACTIVE, "L3 reached; final planned layer active, respect stop.", 0.0)
        if mark <= l2:
            return SetupStateSnapshot(PerpSetupState.L2_ACTIVE, "L2 reached; second planned layer active.", 0.0)
        if mark <= l1:
            return SetupStateSnapshot(PerpSetupState.L1_ACTIVE, "L1 reached; starter limit is active.", 0.0)
        distance = ((mark - l1) / mark) * 100.0
        if distance <= prepare_distance_pct:
            return SetupStateSnapshot(PerpSetupState.PREPARE, "Prepare L1/L2/L3 limits; do not chase above L1.", distance)
        return SetupStateSnapshot(PerpSetupState.WAIT, "Wait for price to approach L1 before placing emphasis on the setup.", distance)

    if side is Side.SHORT:
        if mark >= stop:
            return SetupStateSnapshot(PerpSetupState.INVALIDATED, "Do not enter; setup invalidated above stop.", 0.0)
        if mark <= tp2:
            return SetupStateSnapshot(PerpSetupState.TP2_HIT, "TP2 reached; do not chase a fresh entry.", 0.0)
        if mark <= tp1:
            return SetupStateSnapshot(PerpSetupState.TP1_HIT, "TP1 reached; manage remaining position only.", 0.0)
        if mark >= l3:
            return SetupStateSnapshot(PerpSetupState.L3_ACTIVE, "L3 reached; final planned layer active, respect stop.", 0.0)
        if mark >= l2:
            return SetupStateSnapshot(PerpSetupState.L2_ACTIVE, "L2 reached; second planned layer active.", 0.0)
        if mark >= l1:
            return SetupStateSnapshot(PerpSetupState.L1_ACTIVE, "L1 reached; starter limit is active.", 0.0)
        distance = ((l1 - mark) / mark) * 100.0
        if distance <= prepare_distance_pct:
            return SetupStateSnapshot(PerpSetupState.PREPARE, "Prepare L1/L2/L3 limits; do not chase below L1.", distance)
        return SetupStateSnapshot(PerpSetupState.WAIT, "Wait for price to approach L1 before placing emphasis on the setup.", distance)

    raise ValueError(f"unsupported side: {side}")
