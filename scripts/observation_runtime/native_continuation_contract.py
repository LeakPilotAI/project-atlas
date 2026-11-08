"""Pure fixture-only bridge from native FS2 export to continuation row inputs.

No native creation,writer activation,current-pin switch or operational route.
Actual native identity/security acceptance remains the source/custody owner's job.
"""
from app.investment.quality_dips_operational_contract import native_id
from app.services.paper_financial_audit import audit_financial_events
from app.services.paper_financial_replay import body, replay_verified_events, strict

LANES={'QUALITY_DIPS','HYPERLIQUID'}


def native_fixture_rows(exports, *, manifests, authority):
    if (authority is None or type(exports) is not dict or set(exports)!=LANES
            or type(manifests) is not dict or set(manifests)!=LANES):
        raise ValueError('EXACT_ENROLLED_FIXTURE_SOURCE_PORTS_REQUIRED')
    fingerprint=body(exports)
    exports=strict(fingerprint)
    if authority.verify_native_fixture_exports(exports, manifests) is not True:
        raise ValueError('NATIVE_FIXTURE_SOURCE_PIN_AUTHORITY_REQUIRED')
    rows={}
    roots=[]
    for lane in sorted(LANES):
        value=exports[lane]
        if (type(value) is not dict or set(value)!={'schema','execution_domain','source_pin','manifest',
                'rows','state','head','audit','remaining_operations','startup_authorized'}
                or value['schema']!='FS2_CONTINUATION_FIXTURE_EXPORT_V1'
                or value['execution_domain']!='DISPOSABLE' or value['startup_authorized'] is not False
                or value['manifest']!=manifests[lane] or value['source_pin'].get('schema')!='FS2_TEST_PIN_V1'
                or value['manifest']['currency']!=('USD' if lane=='QUALITY_DIPS' else 'USDC')
                or value['manifest']['schema'] not in ('PAPER_EPOCH_FIXTURE_V1','PAPER_EPOCH_AUTONOMOUS_QD_V1',
                                                       'PAPER_EPOCH_PERP_FIXTURE_V2')
                or type(value['rows']) is not list or len(value['rows'])>128
                or type(value['remaining_operations']) is not int
                or value['remaining_operations']!=128-len(value['rows'])
                or value['source_pin'].get('epoch')!=value['manifest']['epoch']
                or len(value['source_pin']['entries'])!=len(value['rows'])):
            raise ValueError('EXACT_NATIVE_FIXTURE_EXPORT_REQUIRED')
        state,head,_=replay_verified_events(value['manifest'],value['rows'])
        audit=audit_financial_events(value['manifest'],value['rows'],state)
        if state!=value['state'] or head!=value['head'] or audit!=value['audit']:
            raise ValueError('NATIVE_FIXTURE_REPLAY_AUDIT_OR_SOURCE_COUNT_MISMATCH')
        native_id(value['source_pin']['root'])
        roots.append(body(value['source_pin']['root']))
        rows[lane]=value['rows']
    if len(set(roots))!=2:
        raise ValueError('NATIVE_ACCOUNT_SOURCE_ROOT_ALIAS')
    if (authority.verify_native_fixture_exports(exports, manifests) is not True
            or body(exports)!=fingerprint):
        raise ValueError('NATIVE_FIXTURE_SOURCE_AUTHORITY_CHANGED')
    return rows


def native_fixture_delta(exports, *, archived_view, manifests, authority):
    """Append-only fixture catch-up; never reset native/local/global revisions.

    This is not a writable successor codec: current native files still stop at128.
    Empty deltas are an unchanged read,no publication/retry instruction.
    """
    rows=native_fixture_rows(exports,manifests=manifests,authority=authority)
    if (type(archived_view) is not dict or archived_view.get('schema')!='OFFLINE_CONTINUATION_VIEW_V1'
            or archived_view.get('execution')!='FIXTURE_ONLY' or archived_view.get('startup_authorized') is not False
            or set(archived_view.get('rows',{}))!=LANES or set(archived_view.get('accounts',{}))!=LANES):
        raise ValueError('ACKNOWLEDGED_FIXTURE_ARCHIVE_REQUIRED')
    result={}
    for lane in sorted(LANES):
        prior=archived_view['rows'][lane]
        if type(prior) is not list or len(prior)>len(rows[lane]) or prior!=rows[lane][:len(prior)]:
            raise ValueError('NATIVE_SOURCE_ROLLBACK_OR_ARCHIVE_PREFIX_CONFLICT')
        state,head,_=replay_verified_events(manifests[lane],prior)
        audit_financial_events(manifests[lane],prior,state)
        if archived_view['accounts'][lane]!={'state':state,'head':head}:
            raise ValueError('UNVERIFIED_ARCHIVE_PREFIX_ACCOUNTING')
        result[lane]=rows[lane][len(prior):]
    if sum(map(len,result.values()))>128:
        raise ValueError('JOINT_NATIVE_EXPORT_EXCEEDS_FIXTURE_SEGMENT_BOUND')
    return strict(body(result))
