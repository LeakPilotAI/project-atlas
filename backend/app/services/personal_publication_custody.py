"""Local once-only publication coordination,not financial or anti-rollback authority.

Schema installation is explicit and must occur only in an approved activation.
This module never opens a path,creates an account or retries financial callbacks.
"""
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest, strict


class PersonalPublicationCustody:
    intent_schema='PERSONAL_GENESIS_INTENT_V1'
    pending_schema='PERSONAL_GENESIS_PENDING_V1'
    commit_schema='PERSONAL_GENESIS_COMMIT_V1'
    ack_schema='PERSONAL_GENESIS_ACK_V1'
    def __init__(self,ledger):
        if ledger is None:raise ValueError('PERSONAL_PUBLICATION_LEDGER_REQUIRED')
        self.ledger=ledger
    @staticmethod
    def install_schema(connection):
        connection.execute('CREATE TABLE personal_publications(id TEXT PRIMARY KEY,intent TEXT,context TEXT,state TEXT,current TEXT,commit_body TEXT,ack_body TEXT)')
    def row(self,ident):
        with self.ledger.connect(readonly=True) as db:return db.execute('SELECT intent,context,state,current,commit_body,ack_body FROM personal_publications WHERE id=?',(ident,)).fetchone()
    @contextmanager
    def reserve(self,intent,context,now):
        intent,context=strict(body(intent)),strict(body(context))
        ident=intent['operation_id'];i,c=body(intent),body(context)
        with self.ledger.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM personal_publications WHERE id=?',(ident,)).fetchone():raise ValueError('PERSONAL_INCEPTION_ALREADY_RESERVED_NO_REPLAY')
            db.execute('INSERT INTO personal_publications VALUES(?,?,?,?,NULL,NULL,NULL)',(ident,i,c,'PENDING'))
        owner=self;pending={'schema':self.pending_schema,'operation_id':ident,'intent_digest':digest(intent),'writer_digest':digest(context),'state':'PENDING','pending_durable':True}
        sealed_pending=body(pending)
        class Transaction:
            snapshot=pending
            def check(self,p,stamp):
                row=owner.row(ident)
                return body(p)==sealed_pending and body(pending)==sealed_pending and type(stamp) is int and now<=stamp<=now+30 and row is not None and row[:2]==(i,c) and row[2] in ('PENDING','COMMITTED','ACKNOWLEDGED')
            def commit(self,current,stamp):
                if not self.check(pending,stamp):raise ValueError('PERSONAL_PUBLICATION_UNCERTAIN')
                receipt={'schema':owner.commit_schema,'operation_id':ident,'intent_digest':digest(intent),'current_digest':digest(current),'state':'COMMITTED'}
                with owner.ledger.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    changed=db.execute("UPDATE personal_publications SET state='COMMITTED',current=?,commit_body=? WHERE id=? AND intent=? AND context=? AND state='PENDING'",(body(current),body(receipt),ident,i,c))
                    if changed.rowcount!=1:raise ValueError('PERSONAL_PUBLICATION_COMMIT_CONFLICT')
                return receipt
            def acknowledge(self,commit,stamp):
                row=owner.row(ident)
                if not self.check(pending,stamp) or row[2]!='COMMITTED' or row[4]!=body(commit):raise ValueError('PERSONAL_PUBLICATION_ACK_CONFLICT')
                ack={'schema':owner.ack_schema,'operation_id':ident,'commit_digest':digest(commit),'current_digest':commit['current_digest'],'state':'ACKNOWLEDGED'}
                with owner.ledger.connect() as db:
                    db.execute('BEGIN IMMEDIATE')
                    if db.execute("UPDATE personal_publications SET state='ACKNOWLEDGED',ack_body=? WHERE id=? AND state='COMMITTED' AND commit_body=?",(body(ack),ident,body(commit))).rowcount!=1:raise ValueError('PERSONAL_PUBLICATION_ACK_UNCERTAIN')
                return ack
            def mark_unknown(self,reason):
                with owner.ledger.connect() as db:
                    db.execute('BEGIN IMMEDIATE');db.execute("UPDATE personal_publications SET state='UNKNOWN' WHERE id=?",(ident,))
        yield Transaction()
    def acknowledged(self,ident):
        row=self.row(ident)
        if row is None or row[2]!='ACKNOWLEDGED':raise ValueError('PERSONAL_PUBLICATION_NOT_ACKNOWLEDGED')
        intent,current,commit,ack=(strict(row[n]) for n in (0,3,4,5))
        if (commit.get('schema')!=self.commit_schema or commit.get('state')!='COMMITTED'
                or ack.get('schema')!=self.ack_schema or ack.get('state')!='ACKNOWLEDGED'
                or intent.get('schema')!=self.intent_schema or intent.get('operation_id')!=ident
                or commit['operation_id']!=ident or commit['intent_digest']!=digest(intent) or commit['current_digest']!=digest(current)
                or ack['operation_id']!=ident or ack['commit_digest']!=digest(commit) or ack['current_digest']!=digest(current)):
            raise ValueError('PERSONAL_PUBLICATION_RECEIPT_CONFLICT')
        return current,ack


class PersonalFinancialOperationCustody(PersonalPublicationCustody):
    """Same durable reservation protocol; distinct operation receipt versions."""
    intent_schema='PERSONAL_FINANCIAL_INTENT_V1'
    pending_schema='PERSONAL_FINANCIAL_PENDING_V1'
    commit_schema='PERSONAL_FINANCIAL_COMMIT_V1'
    ack_schema='PERSONAL_FINANCIAL_ACK_V1'
