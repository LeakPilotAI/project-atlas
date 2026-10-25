"""Existing selected-account presentation with a distinct operational read version.

No route registration, issuer, test fallback or financial command entry point.
Native port must verify the operational codec, accepted roots and report custody.
"""
from app.services.quality_dips_autonomous_integration import AutonomousSelectedRead


class OperationalAutonomousSelectedRead(AutonomousSelectedRead):
    enrollment_schema = "QD_AUTO_OP_READ_ENROLLMENT_V1"
