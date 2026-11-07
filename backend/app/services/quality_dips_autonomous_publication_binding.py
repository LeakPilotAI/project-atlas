"""Pure binding of V4 publication metadata to an existing native resource cut.

Native file bytes/identities and acknowledgment authority must be authenticated
by independent ports. This module cannot create or accept such authority.
"""
from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_enrollment import ROLES, validate_enrollment
from app.services.quality_dips_autonomous_publication_contract import validate_financial_publication


def bind_financial_publication_to_native_cut(enrollment, publication, cut, documents):
    """Reject inconsistent file rosters, pinned digests, revisions or report heads."""
    e = validate_enrollment(enrollment)
    p = validate_financial_publication(e, publication)
    c = strict(body(cut))
    d = strict(body(documents))
    if (type(c) is not dict or set(c) != {'schema', 'enrollment_digest', 'scope', 'resources'}
            or c['schema'] != 'QD_AUTO_NATIVE_RESOURCE_CUT_V4'
            or c['enrollment_digest'] != digest(e)
            or c['scope'] not in ('DISPOSABLE_TEST', 'LOCAL_ENROLLED')
            or type(c['resources']) is not dict or set(c['resources']) != set(ROLES)
            or type(d) is not dict or set(d) != set(ROLES)):
        raise ValueError('AUTO_PUBLICATION_NATIVE_CUT_REQUIRED')
    names = {'source': set(p['source_files']), 'projection': {p['projection_file']},
             'report': {p['report_file']}, 'control': set(),
             'coordination': set(), 'custody': set()}
    for role in ROLES:
        pins, files = c['resources'][role], d[role]
        if (type(pins) is not dict or type(files) is not dict
                or set(pins) != names[role] or set(files) != names[role]):
            raise ValueError('AUTO_PUBLICATION_NATIVE_ROSTER_MISMATCH')
        for name in names[role]:
            pin = pins[name]
            doc = files[name]
            if (type(pin) is not dict or set(pin) != {'schema', 'native_id', 'sha256', 'record_schema'}
                    or pin['schema'] != 'QD_AUTO_NATIVE_FILE_V4'
                    or type(pin['sha256']) is not str or len(pin['sha256']) != 64
                    or pin['record_schema'] != doc.get('schema')):
                raise ValueError('AUTO_PUBLICATION_NATIVE_PIN_INVALID')
            import hashlib
            if hashlib.sha256(body(doc).encode('utf-8')).hexdigest() != pin['sha256']:
                raise ValueError('AUTO_PUBLICATION_NATIVE_FILE_DIGEST_MISMATCH')
    projection = d['projection'][p['projection_file']]
    report = d['report'][p['report_file']]
    if (projection.get('revision') != p['revision']
            or type(projection.get('revision')) is not int
            or report.get('revision') != p['revision']
            or type(report.get('revision')) is not int
            or projection.get('account_id') != e['account_id']
            or report.get('account_id') != e['account_id']
            or projection.get('epoch') != e['epoch']
            or report.get('epoch') != e['epoch']
            or projection.get('enrollment_digest') != digest(e)
            or report.get('enrollment_digest') != digest(e)
            or report.get('head') != p['event_head']
            or report.get('state_digest') != p['projection_digest']
            or digest(projection.get('state')) != p['projection_digest']
            or digest(report) != p['report_digest']):
        raise ValueError('AUTO_PUBLICATION_NATIVE_FINANCIAL_MISMATCH')
    for i, name in enumerate(p['source_files'][1:], 1):
        doc = d['source'][name]
        if (doc.get('revision') != i or type(doc.get('revision')) is not int
                or doc.get('account_id') != e['account_id']
                or doc.get('epoch') != e['epoch']
                or doc.get('enrollment_digest') != digest(e)):
            raise ValueError('AUTO_PUBLICATION_NATIVE_EVENT_MISMATCH')
    inception = d['source']['inception.json']
    if (inception.get('account_id') != e['account_id']
            or inception.get('epoch') != e['epoch']
            or inception.get('enrollment_digest') != digest(e)
            or inception.get('inception_digest') != e['inception_digest']):
        raise ValueError('AUTO_PUBLICATION_NATIVE_INCEPTION_MISMATCH')
    return True
