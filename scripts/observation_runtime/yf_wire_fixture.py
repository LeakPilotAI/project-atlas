"""Pinned installed request control flow with synthetic-only transport dependencies.

No real yfinance package, curl/requests backend, cache or credentials are imported.
This is not production transport integration or provider permission evidence.
"""
from __future__ import annotations

import ast
import builtins
import copy
import datetime
import functools
import hashlib
import json
import math
import threading
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urljoin, urlsplit

from scripts.observation_runtime.r7e47ck_equities_budget import (
    EquitiesObservationBudget,
)

PIN='5f41a4cec99d50be3a13c8ae5f2674e1b5e1582be1a861fcdbb57bba783629da'
VERSION='1.7.0'


class WireFixtureRefused(RuntimeError):
    pass


class FixtureDNSError(Exception):
    pass


class FixtureChunkError(Exception):
    pass


class FixtureHTTPError(Exception):
    pass


class VirtualDeadline:
    """Controlled fixture time only; cannot interrupt a real blocking operation."""
    def __init__(self,seconds):
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=120:
            raise WireFixtureRefused('Bounded synthetic deadline required')
        self.limit=seconds;self.elapsed=0
    def remaining(self):
        value=self.limit-self.elapsed
        if value<=0:raise WireFixtureRefused('Synthetic end-to-end deadline exhausted')
        return value
    def advance(self,seconds):
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or seconds<0:
            raise WireFixtureRefused('Invalid synthetic elapsed time')
        self.elapsed+=seconds


def route(url):
    if type(url) is not str or len(url)>2048:raise WireFixtureRefused('Bounded fixture URL required')
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port or parsed.fragment:
        raise WireFixtureRefused('Unsafe fixture URL refused')
    paths={('fc.yahoo.com',''):'COOKIE',('fc.yahoo.com','/'):'COOKIE',
      ('query1.finance.yahoo.com','/v1/test/getcrumb'):'CRUMB_BASIC',
      ('query2.finance.yahoo.com','/v1/test/getcrumb'):'CRUMB_CSRF',
      ('guce.yahoo.com','/consent'):'CONSENT',('consent.yahoo.com','/v2/collectConsent'):'COLLECT',
      ('guce.yahoo.com','/copyConsent'):'COPY'}
    if (parsed.hostname,parsed.path) in paths:return paths[(parsed.hostname,parsed.path)]
    if parsed.hostname in ('query1.finance.yahoo.com','query2.finance.yahoo.com'):
        if parsed.path=='/v7/finance/quote':return 'QUOTE'
        prefix='/v8/finance/chart/'
        if parsed.path.startswith(prefix):
            from app.investment.offline_research import symbol_identity
            symbol=parsed.path[len(prefix):]
            if symbol_identity(symbol)==symbol:return 'CHART'
    raise WireFixtureRefused('Unreviewed fixture endpoint refused')


@dataclass(frozen=True)
class Step:
    method:str
    kind:str
    status:int=200
    text:str=''
    payload:object=None
    location:str|None=None
    error:str|None=None
    cookie:bool=False
    elapsed:float=0


class Response:
    def __init__(self,step,url):
        self.status_code=step.status;self.url=url;self.text=step.text;self.content=step.text.encode()
        self.headers={'Location':step.location} if step.location else {};self.payload=copy.deepcopy(step.payload)
    def json(self):
        if self.payload is None:raise ValueError('Fixture response has no JSON')
        return copy.deepcopy(self.payload)
    def raise_for_status(self):
        if self.status_code>=400:raise FixtureHTTPError('Synthetic HTTP response failed')


class Session:
    """Each synthetic hop debits before execution, including redirect hops."""
    def __init__(self,budget,steps, *, timeout_ceiling=30,halt_on_throttle=True,deadline=None):
        if type(budget) is not EquitiesObservationBudget:raise WireFixtureRefused('Explicit existing fixture budget required')
        if type(steps) is not list or not 1<=len(steps)<=128 or any(type(s) is not Step for s in steps):
            raise WireFixtureRefused('Bounded exact synthetic script required')
        if type(timeout_ceiling) not in (int,float) or not 0<timeout_ceiling<=30:
            raise WireFixtureRefused('Bounded timeout ceiling required')
        if type(halt_on_throttle) is not bool:raise WireFixtureRefused('Explicit fixture throttle policy required')
        if deadline is not None and type(deadline) is not VirtualDeadline:
            raise WireFixtureRefused('Exact synthetic deadline required')
        for step in steps:
            if (step.method not in ('GET','POST') or step.kind not in ('COOKIE','CRUMB_BASIC','CRUMB_CSRF','CONSENT','COLLECT','COPY','CHART','QUOTE')
                    or type(step.status) is not int or not 200<=step.status<=599 or type(step.text) is not str
                    or step.error not in (None,'TIMEOUT','DNS','CHUNK') or type(step.cookie) is not bool
                    or type(step.elapsed) not in (int,float) or not math.isfinite(step.elapsed) or not 0<=step.elapsed<=120
                    or len(json.dumps([step.text,step.payload],allow_nan=False).encode())>65536):
                raise WireFixtureRefused('Invalid synthetic script step')
            if step.location is not None:route(step.location)
        self.budget=budget;self.steps=copy.deepcopy(steps);self.timeout_ceiling=timeout_ceiling
        self.halt_on_throttle=halt_on_throttle
        self.deadline=deadline
        self.initial_remaining=budget.remaining();self.events=[];self._fault=None;self._index=0;self._lock=threading.RLock()
        self.cookies=SimpleNamespace(_cookies={});self.cookies.jar=self.cookies
        self.cookies.clear=lambda:self.cookies._cookies.clear()
        self.cookies.update=self._deny_login
        self.cache=None;self.proxies={}
    @staticmethod
    def _deny_login(*args,**kwargs):raise WireFixtureRefused('Login/credential operations are not fixture authority')
    def _refusal(self):
        if self._fault is None:self._fault=WireFixtureRefused('Synthetic wire specification or accounting refused')
        return self._fault
    def get(self,url=None,**kwargs):return self._request('GET',url,kwargs)
    def post(self,url=None,**kwargs):return self._request('POST',url,kwargs)
    def backoff(self,seconds):
        with self._lock:
            self.check()
            if self.deadline is not None:
                try:
                    self.deadline.advance(seconds);self.deadline.remaining()
                except WireFixtureRefused as error:raise self._refusal() from error
    def _request(self,method,url,kwargs):
        with self._lock:
            if self._fault is not None:raise self._fault
            for hop in range(5):
                try:
                    kind=route(url);timeout=kwargs.get('timeout')
                    if self.deadline is not None:
                        if type(timeout) not in (int,float) or not math.isfinite(timeout) or timeout<=0:
                            raise WireFixtureRefused('Invalid requested timeout')
                        timeout=min(timeout,self.timeout_ceiling,self.deadline.remaining())
                    if (type(timeout) not in (int,float) or not 0<timeout<=self.timeout_ceiling
                            or set(kwargs)-{'timeout','params','json','data','headers','allow_redirects'}
                            or type(kwargs.get('allow_redirects',True)) is not bool
                            or len(json.dumps(kwargs,allow_nan=False).encode())>32768 or hop>=4):
                        raise WireFixtureRefused('Unbounded or unsupported fixture request')
                    if self._index>=len(self.steps):raise WireFixtureRefused('Synthetic script exhausted')
                    step=self.steps[self._index]
                    if step.kind!=kind or step.method!=method:raise WireFixtureRefused('Unplanned fake request')
                    remaining=self.budget.consume_before_attempt()
                    if (type(remaining) is not int or not 0<=remaining<=self.initial_remaining-len(self.events)-1
                            or self.budget.remaining()>remaining):
                        raise WireFixtureRefused('Wire debit acknowledgement is not confirmed')
                    if self.deadline is not None:timeout=min(timeout,self.deadline.remaining())
                except Exception as error:
                    raise self._refusal() from error
                self._index+=1
                self.events.append({'ordinal':self._index,'method':method,'kind':kind,'timeout':timeout,
                                    'remaining_after_debit':remaining,'status':None if step.error else step.status,'error':step.error})
                if self.deadline is not None:
                    self.deadline.advance(min(step.elapsed,timeout))
                    try:self.deadline.remaining()
                    except WireFixtureRefused as error:raise self._refusal() from error
                    if step.elapsed>=timeout:raise TimeoutError('Synthetic per-hop deadline exhausted')
                if step.cookie:
                    self.cookies._cookies={'.yahoo.com':{'/':{'A3':SimpleNamespace(expires=1999999999)}}}
                if step.error:
                    errors={'TIMEOUT':TimeoutError,'DNS':FixtureDNSError,'CHUNK':FixtureChunkError}
                    raise errors[step.error]('Synthetic transport failure')
                response=Response(step,url)
                if step.status==429 and self.halt_on_throttle:
                    self._fault=WireFixtureRefused('Synthetic throttle requires explicit policy review; no further attempts')
                if step.status in (301,302,303,307,308) and step.location and kwargs.get('allow_redirects',True):
                    url=urljoin(url,step.location)
                    if step.status==303:method='GET'
                    continue
                return response
            raise AssertionError('unreachable bounded redirect loop')
    def check(self):
        if self._fault is not None:raise self._fault
        try:
            if self.deadline is not None:self.deadline.remaining()
            remaining=self.budget.remaining()
            if remaining>self.initial_remaining-len(self.events):raise WireFixtureRefused('Known debit was rolled back')
        except Exception as error:raise self._refusal() from error
        return remaining


class Node:
    def __init__(self,tag,attrs=None):self.tag=tag;self.attrs=dict(attrs or ());self.children=[]
    def get(self,key,default=None):return self.attrs.get(key,default)
    def __getitem__(self,key):return self.attrs[key]
    def has_attr(self,key):return key in self.attrs
    def find_all(self,tag):
        return [node for child in self.children for node in ([child] if child.tag==tag else [])+child.find_all(tag)]
    def find(self,tag,attrs=None):
        return next((n for n in self.find_all(tag) if all(n.get(k)==v for k,v in (attrs or {}).items())),None)


class Soup(HTMLParser,Node):
    def __init__(self,text,parser):
        if parser!='html.parser':raise WireFixtureRefused('Unsupported fixture parser')
        HTMLParser.__init__(self);Node.__init__(self,'root');self.stack=[self];self.node_n=0
        self.feed(text.decode() if isinstance(text,bytes) else text)
    def handle_starttag(self,tag,attrs):
        self.node_n+=1
        if self.node_n>2048 or len(self.stack)>32:raise WireFixtureRefused('Fixture HTML traversal bound exceeded')
        node=Node(tag,attrs);self.stack[-1].children.append(node)
        if tag not in ('input','br','meta','link','img','hr'):self.stack.append(node)
    def handle_endtag(self,tag):
        if len(self.stack)>1 and self.stack[-1].tag==tag:self.stack.pop()


class Frozen(dict):
    def __hash__(self):return hash(tuple(sorted(self.items())))


class YFException(Exception):
    pass


class YFRateLimitError(YFException):
    pass


class DataFixture:
    """Complete pinned data.py in a fresh namespace; not the real SDK package.

    Synthetic dependencies replace logging, cache, configuration, HTTP, parsing,
    sleeping and time. The fixture cannot confer rights or prove real backends.
    """
    def __init__(self,source_file,session, *, retries=0):
        if type(session) is not Session or type(retries) is not int or not 0<=retries<=3:
            raise WireFixtureRefused('Exact synthetic session and bounded retries required')
        path=Path(source_file).absolute()
        if path.name!='data.py' or path.parent.name!='yfinance' or any(p.is_symlink() or p.is_junction() for p in (path,*path.parents)):
            raise WireFixtureRefused('Explicit unlinked provider source required')
        if not path.is_file() or path.stat().st_size>65536:raise WireFixtureRefused('Bounded source required')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=PIN:raise WireFixtureRefused('Installed source differs from reviewed pin')
        self.session=session;self.backoffs=[];self.cache_calls={'lookup':0,'store':0};cached={}
        def lookup(key):
            self.cache_calls['lookup']+=1
            return {'cookie':copy.deepcopy(cached[key])} if key in cached else None
        def store(key,value):
            self.cache_calls['store']+=1;cached[key]=copy.deepcopy(value)
        def sleep(seconds):
            if type(seconds) not in (int,float) or not 0<=seconds<=4 or len(self.backoffs)>=8:
                raise WireFixtureRefused('Unbounded SDK backoff')
            self.backoffs.append(seconds)
            self.session.backoff(seconds)
        def deny(*args,**kwargs):raise WireFixtureRefused('Unreviewed fixture capability refused')
        class FixedDate(datetime.datetime):
            @classmethod
            def now(cls,tz=None):
                value=cls(2026,10,20,tzinfo=datetime.UTC)
                return value.astimezone(tz) if tz is not None else value.replace(tzinfo=None)
        logger=SimpleNamespace(**{name:(lambda *a,**kw:None) for name in ('debug','warning','error')})
        utils=SimpleNamespace(log_indent_decorator=lambda f:f,get_yf_logger=lambda:logger,frozendict=Frozen)
        http=SimpleNamespace(requests=SimpleNamespace(Response=Response,exceptions=SimpleNamespace(DNSError=FixtureDNSError,
            ChunkedEncodingError=FixtureChunkError)),new_session=deny,is_supported_session=lambda s:type(s) is Session,
            cookie_jar=lambda s:s.cookies.jar)
        relatives={'_http':http,'utils':utils,'cache':SimpleNamespace(get_cookie_cache=lambda:SimpleNamespace(lookup=lookup,store=store)),
          'config':SimpleNamespace(YfConfig=SimpleNamespace(network=SimpleNamespace(proxy=None,retries=retries),debug=SimpleNamespace(hide_exceptions=False))),
          'exceptions':SimpleNamespace(YFException=YFException,YFDataException=YFException,YFRateLimitError=YFRateLimitError)}
        absolute={'functools':functools,'socket':SimpleNamespace(error=OSError),'time':SimpleNamespace(sleep=sleep),
          'urllib.parse':SimpleNamespace(urlsplit=urlsplit,urljoin=urljoin),'bs4':SimpleNamespace(BeautifulSoup=Soup),
          'datetime':SimpleNamespace(datetime=FixedDate,timezone=datetime.timezone),'threading':SimpleNamespace(Lock=threading.Lock)}
        def fixture_import(name,globals=None,locals=None,fromlist=(),level=0):
            if level==1 and name=='':return SimpleNamespace(**relatives)
            if level==1 and name in relatives:return relatives[name]
            if level==0 and name in absolute:return absolute[name]
            raise WireFixtureRefused('Unreviewed dependency import refused')
        tree=ast.parse(raw)
        if any(isinstance(n,ast.ImportFrom) and n.level not in (0,1) for n in ast.walk(tree)):
            raise WireFixtureRefused('Unexpected provider import scope')
        safe=dict(vars(builtins))
        for name in ('open','eval','exec','compile','input','breakpoint'):safe[name]=deny
        safe['__import__']=fixture_import
        namespace={'__name__':'atlas_pinned_yf_fixture','__package__':'atlas_pinned_yf_fixture','__builtins__':safe}
        # Exact reviewed source only, never user expressions or the real package.
        exec(compile(tree,'<PINNED_YFINANCE_DATA_FIXTURE>','exec'),namespace)  # noqa: S102 -- pinned synthetic dependency execution
        self._client=namespace['YfData'](session=session)
    def request_json(self,url, *, method='GET',params=None,body=None,timeout=30,cached=False):
        if (route(url) not in ('CHART','QUOTE') or method not in ('GET','POST') or type(cached) is not bool
                or type(timeout) not in (int,float) or not 0<timeout<=30):
            raise WireFixtureRefused('Bounded chart/quote fixture request required')
        self.session.check()
        try:
            if method=='GET':
                response=(self._client.cache_get if cached else self._client.get)(url,params=params,timeout=timeout)
            elif method=='POST':response=self._client.post(url,params=params,body=body,timeout=timeout)
            else:raise WireFixtureRefused('Unsupported fixture method')
            self.session.check();response.raise_for_status();return response.json()
        except Exception:
            self.session.check()
            raise
    def report(self):
        remaining=self.session.check()
        return {'schema':'ATLAS_SDK_WIRE_FIXTURE_V1','mode':'SYNTHETIC_REPLAY','sdk_version':VERSION,'source_sha256':PIN,
                'attempt_n':len(self.session.events),'remaining':remaining,'events':copy.deepcopy(self.session.events),
                'virtual_backoffs':list(self.backoffs),'cache_operations':dict(self.cache_calls),
                'virtual_deadline_elapsed':self.session.deadline.elapsed if self.session.deadline is not None else None,
                'real_backend_verified':False,'account_wide_budget_verified':False,'source_authenticated':False,
                'network_authorized':False,'startup_authorized':False,'recovery_authorized':False,'trading_authorized':False}
