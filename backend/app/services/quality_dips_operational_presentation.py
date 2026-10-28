"""Existing selected-account presentation with a distinct operational read version.

No route registration, issuer, test fallback or financial command entry point.
Native port must verify the operational codec, accepted roots and report custody.
"""
from app.services.paper_financial_replay import digest
from app.services.quality_dips_autonomous_enrollment import validate_enrollment
from app.services.quality_dips_autonomous_integration import AutonomousSelectedRead
from app.services.quality_dips_autonomous_paper import SCHEMA, validate_autonomous_manifest


class OperationalAutonomousSelectedRead(AutonomousSelectedRead):
    enrollment_schema = "QD_AUTO_OP_READ_ENROLLMENT_V1"

    def _manifest_scope(self, manifest, enrollment, account_id):
        validate_autonomous_manifest(manifest)
        native = validate_enrollment(self.port.enrollment)
        return (manifest['schema'] == SCHEMA
                and account_id == enrollment['account_id'] == native['account_id']
                and manifest['epoch'] == enrollment['epoch'] == native['epoch']
                and digest(manifest) == enrollment['manifest_digest'] == native['inception_digest']
                and digest(manifest['autonomous_policy']) == enrollment['policy_digest'] == native['policy_digest'])
