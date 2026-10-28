"""Existing SQL coordination over an injected immutable native image store.

SQLite operates in memory only: no path-based VFS, sidecars or fixture database.
Financial arithmetic/receipts reuse the canonical SQL mixin and FS1. Native
financial records and FS3 remain the independently replayed financial authority.
Construction never installs a schema, creates a root or grants a session.
"""
import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.services.paper_coordination_sql import CanonicalCoordinationSQL
from app.services.paper_financial_replay import body, strict
from app.services.quality_dips_autonomous_paper import validate_autonomous_manifest

MAX_IMAGE = 1024 * 1024


def image_digest(data):
    return hashlib.sha256(data).hexdigest()


class _NativeConnection(sqlite3.Connection):
    def commit(self):
        super().commit()
        if self._readonly:
            return
        image = self.serialize()
        if len(image) > MAX_IMAGE:
            raise ValueError('PERSONAL_COORDINATION_CAPACITY')
        if image != self._before:
            self._transaction.publish(self._before, image)
            if self._transaction.read() != image:
                raise ValueError('PERSONAL_COORDINATION_ACK_UNKNOWN')
            self._before = image


def _restricted_sql(action, one, two, db, trigger):
    # No file VFS, attached databases, extension loading or VACUUM INTO escape.
    if action in (sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_PRAGMA and (one or '').lower() not in ('trusted_schema', 'quick_check', 'query_only'):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (two or '').lower() in ('load_extension', 'writefile', 'readfile'):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class PersonalNativeCoordination(CanonicalCoordinationSQL):
    def __init__(self, *, manifest, images, path):
        validate_autonomous_manifest(manifest)
        if images is None or path is None:
            raise ValueError('PERSONAL_NATIVE_COORDINATION_PORT_REQUIRED')
        self.manifest = strict(body(manifest))
        self.images, self.path = images, Path(path)
        self._manifest = body(self.manifest)
        self._ports = (images, self.path)

    @contextmanager
    def connect(self, *, readonly=False):
        if (type(readonly) is not bool or body(self.manifest) != self._manifest
                or self.images is not self._ports[0] or self.path != self._ports[1]):
            raise ValueError('PERSONAL_COORDINATION_BINDING_CHANGED')
        with self.images.transaction(readonly=readonly) as tx:
            image = tx.read()
            if type(image) is not bytes or not 0 < len(image) <= MAX_IMAGE:
                raise ValueError('PERSONAL_COORDINATION_IMAGE_REQUIRED')
            db = sqlite3.connect(':memory:', factory=_NativeConnection)
            try:
                db.execute('PRAGMA temp_store=MEMORY')
                db.deserialize(image)
                db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_IMAGE)
                db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 65536)
                db.enable_load_extension(False)
                db.set_authorizer(_restricted_sql)
                db.execute('PRAGMA trusted_schema=OFF')
                if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('PERSONAL_COORDINATION_IMAGE_CORRUPT')
                if db.execute('SELECT body FROM inception').fetchall() != [(self._manifest,)]:
                    raise ValueError('PERSONAL_COORDINATION_ACCOUNT_CONFLICT')
                db._readonly, db._transaction, db._before = readonly, tx, image
                if readonly:
                    db.execute('PRAGMA query_only=ON')
                yield db
                if not readonly:
                    db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    @staticmethod
    def initial_image(manifest):
        """Pure installer recipe, not account inception or publication permission.

        The installer may use this configuration image for durable PENDING
        before financial inception. It is not evidence of any account balance.
        Dispatch/read admission still requires acknowledged native inception.
        """
        validate_autonomous_manifest(manifest)
        db = sqlite3.connect(':memory:')
        try:
            db.executescript('''
                CREATE TABLE inception(body TEXT NOT NULL);
                CREATE TABLE events(revision INTEGER PRIMARY KEY,id TEXT UNIQUE,body TEXT,parent TEXT,digest TEXT,receipt TEXT);
                CREATE TABLE projections(id TEXT PRIMARY KEY,body TEXT,receipt TEXT);
                CREATE TABLE autonomous_control(revision INTEGER PRIMARY KEY,body TEXT,parent TEXT,digest TEXT);
                CREATE TABLE autonomous_activity(revision INTEGER PRIMARY KEY,body TEXT,parent TEXT,digest TEXT);
                CREATE TABLE personal_sessions(id TEXT PRIMARY KEY,body TEXT,state TEXT);
                CREATE TABLE personal_publications(id TEXT PRIMARY KEY,intent TEXT,context TEXT,state TEXT,current TEXT,commit_body TEXT,ack_body TEXT);
                CREATE TABLE personal_current(name TEXT PRIMARY KEY,body TEXT,generation INTEGER);
            ''')
            db.execute('INSERT INTO inception VALUES(?)', (body(manifest),))
            db.commit()
            return db.serialize()
        finally:
            db.close()
