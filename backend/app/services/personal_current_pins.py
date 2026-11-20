"""Local current-pin coordination;native financial audit remains authoritative.

Same-user SQLite is not independent anti-rollback custody. Installation is explicit.
No default path,table repair,account initialization or successor adoption exists.
"""
from app.services.paper_financial_replay import body, digest, strict


class PersonalCurrentPins:
    def __init__(self,*,ledger,name,clock):
        if ledger is None or clock is None or type(name) is not str or not name:raise ValueError('PERSONAL_PIN_DEPENDENCIES')
        self.ledger,self.name,self.clock=ledger,name,clock;self.known=None
    @staticmethod
    def install_schema(connection):connection.execute('CREATE TABLE personal_current(name TEXT PRIMARY KEY,body TEXT,generation INTEGER)')
    @staticmethod
    def initialize(connection,name,pin):
        # Only an explicitly approved installer may call this after native readback.
        connection.execute('INSERT INTO personal_current VALUES(?,?,?)',(name,body(pin),0))
    def current(self):
        with self.ledger.connect(readonly=True) as db:row=db.execute('SELECT body,generation FROM personal_current WHERE name=?',(self.name,)).fetchone()
        if row is None or type(row[1]) is not int or row[1]<0:raise ValueError('PERSONAL_CURRENT_MISSING_OR_CORRUPT')
        value=strict(row[0]);mark=(row[1],digest(value))
        if self.known and (mark[0]<self.known[0] or mark[0]==self.known[0] and mark[1]!=self.known[1]):raise ValueError('PERSONAL_CURRENT_OBSERVED_ROLLBACK')
        self.known=mark;return value
    def check_clock(self,stamp):
        now=self.clock()
        if type(stamp) is not int or type(now) is not int or not 0<=now-stamp<=5:raise ValueError('PERSONAL_PIN_CLOCK_STALE_OR_DISCONTINUOUS')
    def advance(self,before,after):
        before,after=strict(body(before)),strict(body(after))
        field='entries' if 'entries' in before else 'reports' if 'reports' in before else None
        if (field is None or set(before)!=set(after) or type(before[field]) is not list or type(after[field]) is not list
                or len(after[field])!=len(before[field])+1 or len(after[field])>128 or after[field][:-1]!=before[field]
                or {k:v for k,v in before.items() if k!=field}!={k:v for k,v in after.items() if k!=field}):raise ValueError('PERSONAL_PIN_NONAPPEND_OR_RESOURCE_SUBSTITUTION')
        if self.current()!=before:raise ValueError('PERSONAL_PIN_STALE_CAS')
        expected_generation=self.known[0]
        with self.ledger.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute('UPDATE personal_current SET body=?,generation=generation+1 WHERE name=? AND body=? AND generation=?',(body(after),self.name,body(before),expected_generation))
            if changed.rowcount!=1:raise ValueError('PERSONAL_PIN_STALE_CAS')
        if self.current()!=after:raise ValueError('PERSONAL_PIN_COMMIT_READBACK_UNKNOWN')
