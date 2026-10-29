"""Explicit, bounded free-data GET transport and cache. Never trading authority."""
import hashlib
import json
import os
import re
import stat
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

_NETWORK_LOCK = threading.Lock()
_LAST_NETWORK_ATTEMPT = 0.0

class ResearchRefused(ValueError):
    pass


def utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ResearchRefused('RESEARCH_AUTHORED_UTC_REQUIRED')
    return value.astimezone(UTC)


def decode(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            if k in result: raise ResearchRefused('RESEARCH_DUPLICATE_JSON')
            result[k] = v
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError) as exc:
        raise ResearchRefused('RESEARCH_JSON_REFUSED') from exc


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ResearchRefused('RESEARCH_REDIRECT_REFUSED')


class FreeResearchClient:
    """One shared owner per cache/provider budget; no retries or implicit IO.

    Injected fetchers are tests only. Operational use uses the fixed TLS GET
    transport. Cache receipts label acquisition, not independent source custody.
    """
    def __init__(self, *, cache_root, now, sec_user_agent=None, credentials=None,
                 max_attempts=12, seconds=60, fetch=None, monotonic=time.monotonic, sleep=time.sleep):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 200 or type(seconds) is not int or not 1 <= seconds <= 300:
            raise ResearchRefused('RESEARCH_BUDGET_REQUIRED')
        self.root, self.now = Path(cache_root), now
        self.sec_agent, self.credentials = sec_user_agent, credentials
        self.fetch, self.mono, self.sleep = fetch or self._get, monotonic, sleep
        self.deadline, self.max_attempts = monotonic()+seconds, max_attempts
        self.attempted, self.lock, self.last = 0, threading.RLock(), None
        self.domain = 'SYNTHETIC' if fetch is not None else 'TLS_PUBLIC_PROVIDER'
        if fetch is None:
            try: relative=self.root.absolute().relative_to(Path('D:/Work/Project Atlas/logs'))
            except ValueError: raise ResearchRefused('RESEARCH_D_LOCAL_CACHE_REQUIRED') from None
            if not relative.parts or relative.parts[0] not in ('research','diagnostics'):
                raise ResearchRefused('RESEARCH_D_LOCAL_CACHE_REQUIRED')
            if relative.parts[0]=='diagnostics' and (len(relative.parts)<2 or not relative.parts[1].startswith('qd-free-research-')):
                raise ResearchRefused('RESEARCH_D_LOCAL_CACHE_REQUIRED')
        self._ports = self.fetch,self.mono,self.sleep,self.now,self.credentials,self.sec_agent,self.root,self.domain

    @staticmethod
    def _get(url, headers, timeout, maximum):
        global _LAST_NETWORK_ATTEMPT
        deadline = time.monotonic()+timeout
        if not _NETWORK_LOCK.acquire(timeout=timeout): raise ResearchRefused('RESEARCH_RATE_QUEUE_TIMEOUT')
        try:
            wait=max(0,.5-(time.monotonic()-_LAST_NETWORK_ATTEMPT))
            if time.monotonic()+wait>=deadline: raise ResearchRefused('RESEARCH_RATE_QUEUE_TIMEOUT')
            time.sleep(wait); _LAST_NETWORK_ATTEMPT=time.monotonic()
            with build_opener(_NoRedirect()).open(Request(url, headers=headers, method='GET'), timeout=deadline-time.monotonic()) as response:
                if response.status != 200: raise ResearchRefused('RESEARCH_HTTP_REFUSED')
                chunks=[];size=0
                while True:
                    if time.monotonic()>=deadline: raise ResearchRefused('RESEARCH_TIME_BUDGET')
                    part=response.read1(min(65536,maximum+1-size))
                    if time.monotonic()>=deadline: raise ResearchRefused('RESEARCH_TIME_BUDGET')
                    if not part:return b''.join(chunks)
                    chunks.append(part);size+=len(part)
                    if size>maximum:raise ResearchRefused('RESEARCH_RESPONSE_CAPACITY')
        except HTTPError as exc:
            raise ResearchRefused('RESEARCH_HTTP_'+str(exc.code)) from None
        except (URLError, OSError):
            raise ResearchRefused('RESEARCH_NETWORK_REFUSED') from None
        finally:
            _NETWORK_LOCK.release()

    def _scope(self, url):
        u = urlsplit(url)
        if u.scheme != 'https' or u.username or u.password or u.port or u.fragment:
            raise ResearchRefused('RESEARCH_ENDPOINT_REFUSED')
        if ((u.hostname == 'data.sec.gov' and re.fullmatch(r'/api/xbrl/companyfacts/CIK\d{10}\.json', u.path)
             or u.hostname == 'www.sec.gov' and u.path == '/files/company_tickers.json') and not u.query):
            if (type(self.sec_agent) is not str or len(self.sec_agent) > 200
                    or not re.fullmatch(r'ProjectAtlas/1\.0 [A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', self.sec_agent)):
                raise ResearchRefused('SEC_REAL_CONTACT_USER_AGENT_REQUIRED')
            domain=self.sec_agent.rsplit('@',1)[1].lower()
            if self.domain!='SYNTHETIC' and (domain in ('example.com','example.org','example.net') or domain.endswith(('.invalid','.test','.example'))):
                raise ResearchRefused('SEC_REAL_CONTACT_USER_AGENT_REQUIRED')
            return 'SEC_EDGAR', {'User-Agent': self.sec_agent, 'Accept': 'application/json'}
        calendar = u.hostname == 'paper-api.alpaca.markets' and u.path == '/v2/calendar'
        allowed = (calendar or u.hostname == 'data.alpaca.markets' and re.fullmatch(r'/v2/stocks/[A-Z][A-Z0-9.-]{0,14}/bars', u.path)
                   or u.hostname == 'paper-api.alpaca.markets' and re.fullmatch(r'/v2/assets/[A-Z][A-Z0-9.-]{0,14}', u.path) and not u.query)
        if not allowed or self.credentials is None:
            raise ResearchRefused('RESEARCH_ENDPOINT_OR_CREDENTIALS_REFUSED')
        if calendar:
            from urllib.parse import parse_qs
            q = parse_qs(u.query, strict_parsing=True)
            if set(q) != {'start','end'} or any(len(v)!=1 or not re.fullmatch(r'\d{4}-\d\d-\d\d',v[0]) for v in q.values()):
                raise ResearchRefused('ALPACA_CALENDAR_QUERY_REFUSED')
        if u.hostname == 'data.alpaca.markets':
            from urllib.parse import parse_qs
            q = parse_qs(u.query, strict_parsing=True)
            if (set(q)-{'feed','timeframe','start','end','limit','adjustment','sort','page_token'}
                    or any(len(v) != 1 for v in q.values()) or q.get('feed') != ['iex']
                    or q.get('timeframe') != ['1Day'] or q.get('adjustment') not in (['raw'], ['all'])
                    or not q.get('limit', [''])[0].isdigit() or not 1 <= int(q['limit'][0]) <= 1000):
                raise ResearchRefused('ALPACA_FREE_RESEARCH_QUERY_REFUSED')
        return 'ALPACA_BASIC_IEX', {'APCA-API-KEY-ID': self.credentials.key,
                                  'APCA-API-SECRET-KEY': self.credentials.secret, 'Accept': 'application/json'}

    def _inventory(self):
        if any(p.is_symlink() or p.is_junction() for p in (self.root, *self.root.parents)):
            raise ResearchRefused('RESEARCH_CACHE_REPARSE_REFUSED')
        if not self.root.exists(): return
        files = list(self.root.iterdir())
        if any(p.name.endswith('.pending') for p in files): raise ResearchRefused('RESEARCH_CACHE_INCOMPLETE')
        if (len(files) > 128 or any(p.is_symlink() or p.is_junction() or not stat.S_ISREG(p.lstat().st_mode)
                                  or p.lstat().st_nlink != 1 or not re.fullmatch('[0-9a-f]{64}\\.json',p.name) for p in files)
                or sum(p.stat().st_size for p in files) > 64*1024*1024):
            raise ResearchRefused('RESEARCH_CACHE_CAPACITY')

    def get(self, url, *, ttl, maximum=16*1024*1024):
        with self.lock:
            if (any(a is not b for a,b in zip((self.fetch,self.mono,self.sleep,self.now,self.credentials),self._ports[:5],strict=True))
                    or (self.sec_agent,self.root,self.domain)!=self._ports[5:]):
                raise ResearchRefused('RESEARCH_TRANSPORT_COMPONENT_CHANGED')
            if self.mono()>=self.deadline: raise ResearchRefused('RESEARCH_TIME_BUDGET')
            provider, headers = self._scope(url)  # Even cached data cannot evade scope.
            if type(ttl) is not int or not 0 <= ttl <= 86400 or not 1 <= maximum <= 16*1024*1024:
                raise ResearchRefused('RESEARCH_CACHE_POLICY')
            stamp = utc(self.now()); self._inventory()
            key = hashlib.sha256(url.encode()).hexdigest()
            target = self.root/(key+'.json')
            if target.exists():
                packet = decode(target.read_bytes())
                if (packet.get('schema') != 'FREE_RESEARCH_CACHE_V1' or packet.get('url') != url
                        or packet.get('provider') != provider or packet.get('domain') != self.domain):
                    raise ResearchRefused('RESEARCH_CACHE_SCOPE')
                raw = packet['raw'].encode()
                age = (stamp-utc(datetime.fromisoformat(packet['retrieved_at']))).total_seconds()
                if len(raw) > maximum or hashlib.sha256(raw).hexdigest() != packet.get('sha256') or age < 0:
                    raise ResearchRefused('RESEARCH_CACHE_CORRUPT_OR_FUTURE')
                if age <= ttl:
                    if self.mono()>=self.deadline: raise ResearchRefused('RESEARCH_TIME_BUDGET')
                    return decode(raw), {k:v for k,v in packet.items() if k != 'raw'}
            if self.mono() >= self.deadline or self.attempted >= self.max_attempts:
                raise ResearchRefused('RESEARCH_ATTEMPT_OR_TIME_BUDGET')
            wait = max(0, .5-(self.mono()-self.last)) if self.last is not None else 0
            if self.mono()+wait+1 >= self.deadline: raise ResearchRefused('RESEARCH_TIME_BUDGET')
            self.sleep(wait)  # At most two attempts/second, below SEC's aggregate 10/s ceiling.
            self.attempted += 1; self.last = self.mono()
            raw = self.fetch(url, headers, min(10, self.deadline-self.mono()), maximum)
            if self.mono()>=self.deadline: raise ResearchRefused('RESEARCH_TIME_BUDGET')
            if type(raw) is not bytes or len(raw) > maximum: raise ResearchRefused('RESEARCH_RESPONSE_CAPACITY')
            value = decode(raw)
            received = utc(self.now())
            if received < stamp: raise ResearchRefused('RESEARCH_COLLECTION_CLOCK_ROLLBACK')
            packet = {'schema':'FREE_RESEARCH_CACHE_V1','provider':provider,'url':url,'domain':self.domain,
                      'retrieved_at':received.isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'raw':raw.decode()}
            encoded = json.dumps(packet, sort_keys=True).encode()
            if self.root.exists():
                entries = list(self.root.iterdir())
                if len(entries)+(not target.exists())+1 > 128 or sum(p.stat().st_size for p in entries)+len(encoded) > 64*1024*1024:
                    raise ResearchRefused('RESEARCH_CACHE_CAPACITY')
            self.root.mkdir(parents=True, exist_ok=True); self._inventory()
            temporary = self.root/(key+'.pending')
            with temporary.open('xb') as stream:
                stream.write(encoded); stream.flush(); os.fsync(stream.fileno())
            if self.mono()>=self.deadline: raise ResearchRefused('RESEARCH_TIME_BUDGET')
            os.replace(temporary, target)
            self._inventory()
            return value, {k:v for k,v in packet.items() if k != 'raw'}
