"""Native operator session -> existing engine proof, with no source authority.

This binds automatic simulated entry/exit permission only. It does not verify
provider entitlements, quotes, instruments, rankings or calendar correctness.
Those remain independently checked by the existing financial/source validators.
"""
from app.investment.alpaca_iex import FEED
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_paper import validate_autonomous_manifest, validate_grant

from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority


class NativePersonalEngineSession:
    def __init__(self, *, operator=None, manifest=None, calendar_id=None):
        if (type(operator) is not NativePersonalOperatorAuthority or type(manifest) is not dict
                or type(calendar_id) is not str or not calendar_id):
            raise ValueError('PERSONAL_ENGINE_SESSION_NATIVE_DEPENDENCIES')
        validate_autonomous_manifest(manifest)
        if (digest(manifest) != operator.enrollment['inception_digest']
                or manifest['epoch'] != operator.enrollment['epoch']):
            raise ValueError('PERSONAL_ENGINE_SESSION_ACCOUNT_BINDING')
        self.operator, self.manifest, self.calendar_id = operator, strict(body(manifest)), calendar_id
        self._operator, self._manifest, self._calendar = operator, body(manifest), calendar_id

    def verify(self, grant, *, now):
        if (self.operator is not self._operator or body(self.manifest) != self._manifest
                or self.calendar_id != self._calendar or type(now) is not int
                or now != self.operator.clock()):
            raise ValueError('PERSONAL_ENGINE_SESSION_BINDING_CHANGED')
        grant = strict(body(grant))
        validate_grant(self.manifest, grant, now)
        if (grant['schema'] != 'QD_AUTO_ENGINE_SESSION_V5' or grant['feed_id'] != FEED
                or grant['calendar_id'] != self.calendar_id):
            raise ValueError('PERSONAL_ENGINE_NO_FIXTURE_OR_FOREIGN_FEED')
        native = {'schema': 'QD_AUTO_NATIVE_SESSION_V4', 'session_id': grant['session_id'],
                  'enrollment_digest': digest(self.operator.enrollment),
                  'issued_at': grant['issued_at'], 'expires_at': grant['expires_at'],
                  'capabilities': ['AUTO_PAPER']}
        self.operator.verify({'scope': 'LOCAL_ENROLLED', 'enrollment': self.operator.enrollment,
                              'grant': native})
        activation = self.operator.activation('AUTO_PAPER')
        if now != self.operator.clock():
            raise ValueError('PERSONAL_ENGINE_SESSION_CLOCK_CHANGED')
        return {'schema': 'QD_AUTO_SESSION_PROOF_V1', 'verified': True, 'binding': digest(grant),
                'receipt_id': digest({'activation': activation['activation_id'], 'grant': native}),
                'authority_domain': 'PERSONAL_LOCAL_OPERATOR', 'market_evidence_verified': False}
