"""Bounded append-only writer fencing in the ORIGINAL QD coordination image.

No account enrollment, authority issuer, schema migration or financial engine.
Native callers must supply separately verified exclusion, custody and approval.
PREPARED is deliberately terminal/unknown after interruption, never auto-replayed.
"""
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest, strict

NAME = 'original-two-account-writer-generations-v1'
SCHEMA = 'ATLAS_ORIGINAL_WRITER_GENERATIONS_V1'
MAX_RECORDS = 64


def replay(value, accounts):
    if (type(value) is not dict or set(value) != {'schema', 'accounts', 'records'}
            or value['schema'] != SCHEMA or value['accounts'] != accounts
            or type(value['records']) is not list or len(value['records']) > MAX_RECORDS):
        raise ValueError('WRITER_GENERATION_JOURNAL_BINDING')
    parent, previous, approvals = digest(accounts), None, set()
    for revision, row in enumerate(value['records'], 1):
        if (type(row) is not dict or set(row) != {'revision','parent','generation','state',
                'owner','scope_digest','cut_digest','previous_owner','exclusion_digest','approval_id'}
                or type(row['revision']) is not int or row['revision'] != revision
                or row['parent'] != parent or type(row['generation']) is not int
                or row['state'] not in ('PREPARED','ACTIVE')
                or type(row['owner']) is not dict
                or set(row['owner']) != {'pid','creation_filetime','image'}
                or type(row['owner']['pid']) is not int or row['owner']['pid'] <= 4
                or type(row['owner']['creation_filetime']) is not int
                or row['owner']['creation_filetime'] <= 0
                or type(row['owner']['image']) is not str
                or not row['owner']['image'].startswith('D:\\')
                or type(row['approval_id']) is not str or not 1<=len(row['approval_id'])<=128
                or any(type(row[k]) is not str or len(row[k]) != 64
                       or any(c not in '0123456789abcdef' for c in row[k])
                       for k in ('scope_digest','cut_digest','exclusion_digest'))):
            raise ValueError('WRITER_GENERATION_CORRUPT_RECORD')
        if row['state'] == 'PREPARED':
            if (previous is not None and previous['state'] != 'ACTIVE'
                    or row['generation'] != (0 if previous is None else previous['generation']+1)
                    or row['previous_owner'] != (None if previous is None else previous['owner'])
                    or previous is not None and row['owner'] == previous['owner']
                    or row['scope_digest'] in approvals or row['approval_id'] in approvals):
                raise ValueError('WRITER_GENERATION_REPLAY_OR_MIXED_GENERATION')
            approvals.add(row['scope_digest'])
            approvals.add(row['approval_id'])
        elif (previous is None or previous['state'] != 'PREPARED'
                or {k:v for k,v in row.items() if k not in ('revision','parent','state')} !=
                   {k:v for k,v in previous.items() if k not in ('revision','parent','state')}):
            raise ValueError('WRITER_GENERATION_ACTIVE_WITHOUT_EXACT_PREPARE')
        parent, previous = digest(row), row
    return previous


class WriterGenerationJournal:
    """Existing native SQL image CAS. No independent anti-rollback claim.

    One QD image is the authoritative fence for BOTH lanes. Never publish
    independently into two ledgers and pretend their commits were atomic.
    """
    def __init__(self, *, ledger, accounts):
        self.ledger, self.accounts = ledger, strict(body(accounts))
        if set(self.accounts) != {'QUALITY_DIPS','HYPERLIQUID'}:
            raise ValueError('WRITER_GENERATION_TWO_ORIGINAL_ACCOUNTS')
        self._binding = ledger, body(self.accounts)

    @contextmanager
    def exclusive(self):
        if self.ledger is not self._binding[0] or body(self.accounts) != self._binding[1]:
            raise ValueError('WRITER_GENERATION_JOURNAL_SUBSTITUTED')
        # Existing bounded Windows mutex; recursive acquisition is same-thread
        # only, allowing original image transactions within a fenced operation.
        with self.ledger.images._writer():
            yield

    def read(self):
        if self.ledger is not self._binding[0] or body(self.accounts)!=self._binding[1]:
            raise ValueError('WRITER_GENERATION_JOURNAL_SUBSTITUTED')
        with self.ledger.connect(readonly=True) as db:
            row = db.execute('SELECT body,generation FROM personal_current WHERE name=?',(NAME,)).fetchone()
        if row is None:
            value = {'schema':SCHEMA,'accounts':self.accounts,'records':[]}
        else:
            value = strict(row[0])
            if type(row[1]) is not int or row[1] != len(value.get('records',[])):
                raise ValueError('WRITER_GENERATION_IMAGE_REVISION_CONFLICT')
        replay(value,self.accounts)
        return strict(body(value))

    def append(self, before, record):
        if len(before['records']) >= MAX_RECORDS:
            raise ValueError('WRITER_GENERATION_CAPACITY')
        after = {**before,'records':[*before['records'],record]}
        replay(after,self.accounts)
        with self.ledger.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT body,generation FROM personal_current WHERE name=?',(NAME,)).fetchone()
            expected = None if not before['records'] else (body(before),len(before['records']))
            if row != expected:
                raise ValueError('WRITER_GENERATION_DURABLE_CAS_CONFLICT')
            if row is None:
                db.execute('INSERT INTO personal_current VALUES(?,?,?)',(NAME,body(after),len(after['records'])))
            else:
                changed=db.execute('UPDATE personal_current SET body=?,generation=? WHERE name=? AND body=? AND generation=?',
                    (body(after),len(after['records']),NAME,*row))
                if changed.rowcount != 1:
                    raise ValueError('WRITER_GENERATION_DURABLE_CAS_CONFLICT')
        if self.read() != after:
            raise ValueError('WRITER_GENERATION_PUBLICATION_ACK_UNKNOWN')
        return after


def accept_generation(*, journal, owner, authorize, inspect_cut, exclude_previous,
                      fault=lambda phase:None):
    """No external proof dictionaries are sufficient: callbacks are native ports.

    Internal orchestration is injectable offline. Only the native wrapper may
    yield a usable financial capability. This function returns journal evidence.
    """
    with journal.exclusive():
        before=journal.read();head=replay(before,journal.accounts)
        if head is not None and head['state'] != 'ACTIVE':
            raise ValueError('WRITER_GENERATION_UNKNOWN_PREPARED_REQUIRES_RECONCILIATION')
        if len(before['records']) > MAX_RECORDS-2:
            raise ValueError('WRITER_GENERATION_CAPACITY')
        cut=inspect_cut()
        previous=None if head is None else head['owner']
        exclusion=exclude_previous(previous)
        generation=0 if head is None else head['generation']+1
        context={'accounts':journal.accounts,'generation':generation,'previous_owner':previous,
                 'new_owner':owner,'cut_digest':digest(cut),
                 'previous_head':None if head is None else digest(head)}
        scope=authorize(context)
        fault('before_prepare')
        row={'revision':len(before['records'])+1,
             'parent':digest(journal.accounts) if head is None else digest(head),
             'generation':generation,'state':'PREPARED','owner':owner,
             'scope_digest':digest(scope),'cut_digest':digest(cut),
             'previous_owner':previous,'exclusion_digest':digest(exclusion),'approval_id':scope['approval_id']}
        prepared=journal.append(before,row)
        fault('after_prepare')
        if inspect_cut()!=cut or exclude_previous(previous)!=exclusion or authorize(context)!=scope:
            raise ValueError('WRITER_GENERATION_HANDOFF_CHANGED')
        active={**row,'revision':row['revision']+1,'parent':digest(row),'state':'ACTIVE'}
        result=journal.append(prepared,active)
        fault('after_active')
        if replay(journal.read(),journal.accounts)!=active or result['records'][-1]!=active:
            raise ValueError('WRITER_GENERATION_FINAL_ACK_UNKNOWN')
        return strict(body(active))
