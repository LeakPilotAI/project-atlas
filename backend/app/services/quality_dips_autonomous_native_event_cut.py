"""Read-only, explicitly disposable FS1-to-V4 resource-cut research adapter.

Never accepts LOCAL_ENROLLED: fixture envelopes cannot be promoted to
operational QD_AUTO_NATIVE financial records or independent authority.
"""
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_enrollment import validate_enrollment
from app.services.quality_dips_autonomous_financial_reconciliation import reconcile_authenticated_financial_cut


class DisposableNativeEventCutVerifier:
    """Verify complete native-read documents for a synthetic FS1 event history."""

    def verify_cut(self, enrollment, current, documents, now, *, scope):
        if scope != 'DISPOSABLE_TEST' or type(now) is not int or now <= 0:
            raise ValueError('AUTO_EVENT_CUT_DISPOSABLE_ONLY')
        e = validate_enrollment(enrollment)
        if (type(current) is not dict or current.get('scope') != scope
                or type(documents) is not dict or set(documents) != set(e['resources'])):
            raise ValueError('AUTO_EVENT_CUT_SCOPE_OR_ROSTER')
        revision = current.get('revision')
        if type(revision) is not int or not 0 < revision <= 128:
            raise ValueError('AUTO_EVENT_CUT_REVISION')
        names = {'source': {'manifest.json', *(f'{i:04d}-event.json' for i in range(1, revision + 1))},
                 'projection': {'projection.json'}, 'report': {'report.json'},
                 'control': set(), 'coordination': set(), 'custody': set()}
        if any(type(documents[role]) is not dict or set(documents[role]) != names[role]
               for role in names):
            raise ValueError('AUTO_EVENT_CUT_NAMESPACE')
        manifest_doc = strict(body(documents['source']['manifest.json']))
        projection = strict(body(documents['projection']['projection.json']))
        report = strict(body(documents['report']['report.json']))
        common = {'account_id': e['account_id'], 'epoch': e['epoch'],
                  'enrollment_digest': digest(e), 'revision': revision}
        for doc, schema, extra in (
            (manifest_doc, 'QD_AUTO_NATIVE_DISPOSABLE_MANIFEST_V1', {'manifest'}),
            (projection, 'QD_AUTO_NATIVE_DISPOSABLE_PROJECTION_V1', {'state'}),
            (report, 'QD_AUTO_NATIVE_DISPOSABLE_REPORT_V1', {'head', 'state_digest', 'audit_digest'}),
        ):
            if (type(doc) is not dict or set(doc) != {'schema', *common, *extra}
                    or doc['schema'] != schema
                    or any(doc[k] != v or (k == 'revision' and type(doc[k]) is not int)
                           for k, v in common.items())):
                raise ValueError('AUTO_EVENT_CUT_DOCUMENT_BINDING')
        rows = []
        for i in range(1, revision + 1):
            doc = strict(body(documents['source'][f'{i:04d}-event.json']))
            if (set(doc) != {'schema', *common, 'record'} or
                    doc['schema'] != 'QD_AUTO_NATIVE_DISPOSABLE_EVENT_V1'
                    or any(doc[k] != v or (k == 'revision' and type(doc[k]) is not int)
                           for k, v in {**common, 'revision': i}.items())):
                # Each event carries its own exact revision, not the cut's head revision.
                raise ValueError('AUTO_EVENT_CUT_RECORD_BINDING')
            rows.append(doc['record'])
        result = reconcile_authenticated_financial_cut(
            manifest_doc['manifest'], rows, projection['state'],
            expected_epoch=e['epoch'], expected_revision=revision,
            expected_head=report['head'], expected_state_digest=report['state_digest'])
        if result['audit_digest'] != report['audit_digest']:
            raise ValueError('AUTO_EVENT_CUT_REPORT_AUDIT_MISMATCH')
        return True
