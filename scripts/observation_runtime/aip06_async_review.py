"""Static default-loop review, never creates a loop, socket or native proof."""

import ast
import hashlib

from scripts.observation_runtime.aip06_harness import need


def review_sources(*, socket_source, proactor_source, policy_source):
    sources={'socket':socket_source,'proactor_events':proactor_source,'windows_events':policy_source}
    need(all(type(v) is bytes and 0<len(v)<=1024**2 for v in sources.values()),'BOUNDED_STDLIB_REVIEW_BYTES')
    trees={k:ast.parse(v.decode('utf-8-sig')) for k,v in sources.items()}
    def call(tree,owner,name):
        return any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)
                   and isinstance(n.func.value,ast.Name) and n.func.value.id==owner
                   and n.func.attr==name for n in ast.walk(tree))
    fallback=next((n for n in trees['socket'].body if isinstance(n,ast.FunctionDef)
                   and n.name=='_fallback_socketpair'),None)
    tcp_fallback=fallback is not None and all(call(fallback,owner,name) for owner,name in
                                              (('lsock','bind'),('lsock','listen'),('csock','connect')))
    default=any(isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='DefaultEventLoopPolicy' for t in n.targets)
                and isinstance(n.value,ast.Name) and n.value.id=='WindowsProactorEventLoopPolicy'
                for n in trees['windows_events'].body)
    self_pair=call(trees['proactor_events'],'socket','socketpair')
    return {'schema':'AIP06_ASYNC_SOURCE_REVIEW_V1','source_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in sources.items()},
            'default_proactor':default,'self_socketpair':self_pair,'fallback_binds_tcp':tcp_fallback,
            'runtime_socketpair_branch':'UNEXECUTED','native_execution':False,'compatible':False,
            'status':'BLOCKED_DEFAULT_LOOP_SOCKETPAIR_NOT_QUALIFIED' if default and self_pair and tcp_fallback
                     else 'BLOCKED_UNREVIEWED_STDLIB_SHAPE',
            'required':'Separately scoped native branch/owned-resource evidence or reviewed compliant design; no guard exemption.'}


def require_compatible(review):
    need(type(review) is dict and review.get('schema')=='AIP06_ASYNC_SOURCE_REVIEW_V1'
         and review.get('native_execution') is False and review.get('compatible') is False,
         'ASYNC_REVIEW_NOT_NATIVE_AUTHORITY')
    raise ValueError('ASYNC_COMPATIBILITY_REQUIRES_SEPARATE_EVIDENCE')
