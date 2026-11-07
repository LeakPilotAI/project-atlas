"""Exact two-command race admission; no creation, PID selection or adoption."""

import copy
import hashlib
import ntpath

from app.services.paper_financial_replay import body, digest, strict
from scripts.observation_runtime.aip06_harness import BASE, need


class RaceRoles:
    def __init__(self, port, commands):
        port.guard.check()
        need(type(commands) in (tuple,list) and len(commands)==2,
             'EXACT_TWO_RACE_COMMANDS')
        target=ntpath.join(ntpath.dirname(ntpath.dirname(BASE)), 'tests', 'perp_order_crash_child.py')
        need(all(port.controller.profile['targets'].get(role)==target for role in ('race_one','race_two')),
             'EXACT_SHARED_RACE_SOURCE_PROFILE')
        port.controller.verify_source(target)
        self.port,self.owner=port,port.guard.owner
        self.entries={};self.used=set();self.failed=False
        for role,argv in zip(('race_one','race_two'),commands):
            need(type(argv) in (tuple,list) and len(argv)==7
                 and all(type(v) is str for v in argv)
                 and list(argv[:4])==[port.executable,'-B',target,'--config']
                 and list(argv[5:])==['--phase','none'], 'EXACT_RACE_COMMAND_SHAPE')
            path=argv[4];port.guard.validate_path(path)
            need(path in port.guard.owned_files,'RACE_CONFIG_NOT_CREATED_BY_THIS_GUARD')
            native=port.io.inspect(path);raw=port.io.read_bytes(path,maximum_bytes=65536)
            need(native is not None and native['kind']=='file' and native['reparse'] is False
                 and native['links']==1 and native['id']==port.guard.file_identities[path],
                 'RACE_CONFIG_NATIVE_IDENTITY')
            value=strict(raw.decode('utf8'))
            need(type(value) is dict and all(type(value.get(k)) is str for k in ('ready','barrier','confinement','root')),
                 'RACE_CONFIG_CONTROL_PATHS')
            for key in ('ready','barrier','root'):port.guard.validate_path(value[key],create=key in ('ready','barrier'))
            self.entries[role]={'argv':tuple(argv),'path':path,'identity':copy.deepcopy(native),
                                'sha256':hashlib.sha256(raw).hexdigest(),'value':value}
        a,b=self.entries.values()
        need(a['path']!=b['path'] and a['identity']['id']!=b['identity']['id']
             and a['value']['ready']!=b['value']['ready']
             and body({k:v for k,v in a['value'].items() if k!='ready'})
                 ==body({k:v for k,v in b['value'].items() if k!='ready'}),
             'RACE_DISTINCT_IDENTITIES_SAME_ORIGINAL_OPERATION')
        self.receipt=digest({'owner':self.owner,'commands':self.entries})

    def claim(self, argv):
        try:return self._claim(argv)
        except BaseException:
            self.failed=True
            raise

    def _claim(self,argv):
        p=self.port;p.guard.check()
        need(not self.failed and p.guard.owner==self.owner,'RACE_OWNER_OR_PRIOR_REFUSAL')
        matches=[name for name,row in self.entries.items() if row['argv']==tuple(argv)]
        need(len(matches)==1 and matches[0] not in self.used,'RACE_UNDECLARED_OR_REUSED_COMMAND')
        role=matches[0];row=self.entries[role]
        need(not any(s.name==role for s in p.sessions)
             and role not in p.guard.ownership.prepared,'RACE_ROLE_ALREADY_RESERVED')
        p.guard.validate_path(row['path'])
        need(p.io.inspect(row['path'])==row['identity']
             and hashlib.sha256(p.io.read_bytes(row['path'],maximum_bytes=65536)).hexdigest()==row['sha256'],
             'RACE_CONFIG_CHANGED_AFTER_DECLARATION')
        self.used.add(role)  # A failed later launch never silently recycles it.
        return role


def declare_pair(port, commands):
    need(getattr(port,'race_roles',None) is None
         and not any(s.name in ('race_one','race_two') for s in port.sessions),
         'RACE_PAIR_ONCE_BEFORE_CREATION')
    result=RaceRoles(port,commands);port.race_roles=result
    return {'owner':result.owner,'receipt':result.receipt,'roles':['race_one','race_two'],
            'processes_created':False,'native_acceptance':False}
