"""Nonfinancial QD source archive over existing immutable native image storage.

No root creation, initialization, issuer, provider, scanner or financial writer.
Current-source authority remains an explicitly accepted injected dependency;
local native/hash consistency alone never authenticates market research.
"""
import re

from app.services.paper_financial_replay import body, digest, strict, text

from scripts.observation_runtime.personal_coordination_store import (
    NativePersonalCoordinationImages,
)

SCHEMA='PERSONAL_QD_SOURCE_ARCHIVE_V1'
IMAGE='PERSONAL_QD_SOURCE_IMAGE_V1'


def validate_enrollment(value):
    if (type(value) is not dict or set(value)!={'schema','account_id','epoch','source_id','release_digest','source_commit','root_id'}
            or value['schema']!=SCHEMA or type(value['release_digest']) is not str
            or not re.fullmatch('[0-9a-f]{64}',value['release_digest']) or type(value['source_commit']) is not str
            or not re.fullmatch('[0-9a-f]{40}',value['source_commit'])
            or type(value['root_id']) is not list or len(value['root_id'])!=3
            or any(type(n) is not int or n<0 for n in value['root_id'])):
        raise ValueError('EXPLICIT_QD_SOURCE_ARCHIVE_ENROLLMENT_REQUIRED')
    for name in ('account_id','epoch','source_id'):text(value[name])
    return strict(body(value))


def initial_image(enrollment):
    """Pure empty source recipe. Not native initialization or account inception."""
    enrollment=validate_enrollment(enrollment)
    return body({'schema':IMAGE,'enrollment':digest(enrollment),'revision':0,
        'previous':None,'packet':None,'sources':None}).encode()


class NativePersonalResearchArchive:
    # Reuse this immutable image protocol for another explicitly typed source,
    # without accepting that source in the existing QD schema or constructors.
    _validate_enrollment=staticmethod(validate_enrollment)
    _initial_image=staticmethod(initial_image)
    _image_schema=IMAGE
    _max_packet_age=30

    def __init__(self, *, enrollment=None, images=None, authority=None, clock=None):
        self.enrollment=self._validate_enrollment(enrollment)
        if type(images) is not NativePersonalCoordinationImages or authority is None or clock is None:
            raise ValueError('ACCEPTED_QD_SOURCE_ARCHIVE_PORTS_REQUIRED')
        self.images,self.authority,self.clock=images,authority,clock
        self._scope=body(self.enrollment)
        self._ports=images,authority,clock
        self._water=None
        self._verify()

    def _verify(self):
        if (body(self.enrollment)!=self._scope or any(a is not b for a,b in zip(
                (self.images,self.authority,self.clock),self._ports,strict=True))
                or self.images.enrollment!=digest(self.enrollment) or self.images.root_id!=self.enrollment['root_id']
                or self.authority.verify_archive(self.enrollment,self.images,self.clock) is not True):
            raise ValueError('QD_SOURCE_ARCHIVE_BINDING_UNACCEPTED_OR_CHANGED')

    def _now(self):
        now=self.clock()
        if type(now) is not int or now<0:raise ValueError('QD_SOURCE_ARCHIVE_CLOCK_REQUIRED')
        return now

    def _packet_valid(self,packet,revision):
        return (type(packet) is dict and set(packet)=={'schema','source_id','revision','observed_at','bundles','monitors'}
                and packet['schema']=='QD_SCANNER_PUBLICATION_V1' and type(packet['bundles']) is list
                and len(packet['bundles'])<=16 and type(packet['monitors']) is dict and len(packet['monitors'])<=16)

    def _image(self,raw):
        if type(raw) is not bytes or not 0<len(raw)<=1024*1024:raise ValueError('QD_SOURCE_ARCHIVE_IMAGE_CAPACITY')
        value=strict(raw.decode())
        if (type(value) is not dict or set(value)!={'schema','enrollment','revision','previous','packet','sources'}
                or value['schema']!=self._image_schema or value['enrollment']!=digest(self.enrollment)
                or type(value['revision']) is not int or not 0<=value['revision']<=127):
            raise ValueError('QD_SOURCE_ARCHIVE_IMAGE_SCOPE')
        if value['revision']==0:
            if value!=strict(self._initial_image(self.enrollment).decode()):raise ValueError('QD_SOURCE_ARCHIVE_FALSE_INITIAL')
        else:
            packet=value['packet']
            if (not self._packet_valid(packet,value['revision']) or packet['source_id']!=self.enrollment['source_id']
                    or type(packet['revision']) is not int or packet['revision']!=value['revision']
                    or type(packet['observed_at']) is not int
                    or len(body(packet).encode())>131072 or type(value['sources']) is not dict
                    or type(value['previous']) is not str or not re.fullmatch('[0-9a-f]{64}',value['previous'])):
                raise ValueError('QD_SOURCE_ARCHIVE_RECORD_SCHEMA')
        return value

    def _head(self,value):
        native=self.images.known
        if type(native) is not dict or native.get('revision')!=value['revision']+1:
            raise ValueError('QD_SOURCE_ARCHIVE_NATIVE_REVISION_MISMATCH')
        return {'revision':value['revision'],'digest':digest(value['packet']) if value['revision'] else None,
            'archive_binding':digest(self.enrollment),'image_digest':digest(value),
            'native_revision':native['revision'],'native_head':native['head'],'native_ack':strict(body(native['ack']))}

    def _accepted(self,value,now):
        head=self._head(value)
        if (self.authority.verify_archive_head(self.enrollment,head,now) is not True
                or self._water is not None and (head['revision']<self._water['revision']
                    or head['revision']==self._water['revision'] and head!=self._water)):
            raise ValueError('QD_SOURCE_ARCHIVE_CURRENT_CUSTODY_REFUSED')
        return head

    def current(self):
        self._verify();now=self._now()
        with self.images.transaction(readonly=True) as tx:
            value=self._image(tx.read());head=self._accepted(value,now)
        self._verify()
        if not 0<=self._now()-now<=1:raise ValueError('QD_SOURCE_ARCHIVE_READ_CLOCK_CHANGED')
        self._water=head
        return strict(body(head))

    def capacity_readonly(self, *, horizon_seconds=0, publication_interval_seconds=30):
        """Verify immutable source head and native remaining writes, with NO effects.

        This is not an epoch rollover, future lease, original source issuer, or
        financial approval. The source has a cumulative 128-native-revision
        budget including genesis; a 30s current-source TTL cannot be turned
        into months of continuous PAPER via a revised forecast or local hash.
        """
        from scripts.observation_runtime import personal_coordination_store as native

        if (type(horizon_seconds) is not int or not 0 <= horizon_seconds <= 366 * 86400
                or type(publication_interval_seconds) is not int
                # A slower forecast is NOT continuously current QD research.
                # The original source reader has a maximum 30-second TTL.
                or not 1 <= publication_interval_seconds <= 30
                or native.MAX_REVISIONS != 128):
            raise ValueError('QD_SOURCE_CAPACITY_EXACT_BOUNDED_HORIZON_REQUIRED')
        self._verify()
        head = self.current()
        remaining = self.images.remaining_commits()
        # Native genesis consumes one revision; current logical head consumes
        # all further native commits. Compare exact original on-disk ACK.
        if (type(remaining) is not int
                or not 0 <= remaining <= 127
                or head['native_revision'] != head['revision'] + 1
                or remaining != native.MAX_REVISIONS - head['native_revision']
                or self.current() != head):
            raise ValueError('QD_SOURCE_CAPACITY_ORIGINAL_ACK_CHANGED')
        expected = ((horizon_seconds + publication_interval_seconds - 1)
                    // publication_interval_seconds)
        return strict(body({
            'schema': 'QD_ORIGINAL_NATIVE_SOURCE_CAPACITY_READONLY_V1',
            'source_id': self.enrollment['source_id'],
            'archive_epoch': self.enrollment['epoch'],
            'logical_revision': head['revision'],
            'native_revision': head['native_revision'],
            'native_remaining_publications': remaining,
            'required_horizon_seconds': horizon_seconds,
            'assumed_publication_interval_seconds': publication_interval_seconds,
            'required_new_publications_for_horizon': expected,
            'within_existing_epoch': expected <= remaining,
            'requires_new_original_source_epoch': expected > remaining,
            'native_root_modified': False,
            'automatic_rollover_verified': False,
            'paper_startup_authorized': False,
            'live_trading_authorized': False,
        }))

    def read(self,expected):
        return self.read_evidence(expected)['packet']

    def read_evidence(self,expected):
        """Read the same acknowledged cut, including its original source evidence."""
        self._verify();now=self._now()
        with self.images.transaction(readonly=True) as tx:
            value=self._image(tx.read());head=self._accepted(value,now)
            if head!=expected or value['revision']==0:raise ValueError('QD_SOURCE_ARCHIVE_EXPECTED_CURRENT_REQUIRED')
            result=strict(body({'packet':value['packet'],'sources':value['sources']}))
        self._verify()
        if not 0<=self._now()-now<=1:raise ValueError('QD_SOURCE_ARCHIVE_READ_CLOCK_CHANGED')
        self._water=head
        return result

    def publish(self, *, expected, packet, sources):
        self._verify();now=self._now();packet,sources=strict(body(packet)),strict(body(sources))
        request={'schema':'PERSONAL_QD_SOURCE_PUBLICATION_REQUEST_V1','enrollment':digest(self.enrollment),
            'expected':strict(body(expected)),'packet_digest':digest(packet),'sources_digest':digest(sources)}
        published=False
        try:
            with self.authority.lease_source_publication(request,now) as lease:
                if lease.check(request,now) is not True:raise ValueError('QD_SOURCE_ARCHIVE_PUBLICATION_REFUSED')
                with self.images.transaction(readonly=False) as tx:
                    before=tx.read();old=self._image(before);head=self._accepted(old,now)
                    if head!=expected:raise ValueError('QD_SOURCE_ARCHIVE_STALE_CAS')
                    after={'schema':self._image_schema,'enrollment':digest(self.enrollment),'revision':old['revision']+1,
                        'previous':digest(old),'packet':packet,'sources':sources}
                    raw=body(after).encode();self._image(raw)
                    stamp=self._now()
                    if not 0<=stamp-packet['observed_at']<=self._max_packet_age:raise ValueError('QD_SOURCE_ARCHIVE_PUBLICATION_NOT_CURRENT')
                    if not 0<=stamp-now<=1 or lease.check(request,stamp) is not True:
                        raise ValueError('QD_SOURCE_ARCHIVE_AUTHORITY_CHANGED_BEFORE_EFFECT')
                    tx.publish(before,raw)
                    published=True
                    stamp=self._now()
                    if tx.read()!=raw or not 0<=stamp-now<=1 or lease.check(request,stamp) is not True:
                        raise ValueError('QD_SOURCE_ARCHIVE_PUBLICATION_UNKNOWN')
                    acknowledged=self._head(after)
        except BaseException:
            # NativeImages latches UNKNOWN for its own interrupted publication.
            # A known pre-effect CAS/capacity refusal leaves the prior cut readable.
            if published:self.images._poison()
            raise
        if self._water is None or acknowledged['revision']>=self._water['revision']:
            self._water=acknowledged
