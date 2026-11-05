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


def assess_observed_branch(review, observation):
    """An observed host branch can prove refusal, never native compatibility.

    The caller preserves genuine read-only host observations and byte pins.
    Matching a different runtime's bytes is explicitly labelled inference;
    this function cannot claim that the target process was executed.
    """
    need(type(review) is dict and review.get('schema') == 'AIP06_ASYNC_SOURCE_REVIEW_V1'
         and review.get('native_execution') is False and review.get('compatible') is False,
         'ORIGINAL_SOURCE_ASYNC_REVIEW_REQUIRED')
    need(type(observation) is dict and observation.get('schema') == 'AIP06_READONLY_HOST_ASYNC_BRANCH_V1'
         and type(observation.get('has_builtin_socketpair')) is bool
         and observation.get('socket_created') is False and observation.get('loop_created') is False
         and observation.get('target_runtime_executed') is False,
         'READONLY_BRANCH_OBSERVATION_NOT_EXECUTION_AUTHORITY')
    refusal = (observation['has_builtin_socketpair'] is False and review.get('default_proactor') is True
               and review.get('self_socketpair') is True and review.get('fallback_binds_tcp') is True)
    return {'schema': 'AIP06_ASYNC_BRANCH_ASSESSMENT_V1', 'compatible': False, 'native_acceptance': False,
            'target_runtime_executed': False,
            'status': 'BLOCKED_OBSERVED_HOST_TCP_FALLBACK_REQUIRES_FORBIDDEN_BIND_CONNECT' if refusal
                      else 'BLOCKED_NATIVE_BRANCH_NOT_QUALIFIED',
            'target_byte_match': observation.get('target_byte_match') is True,
            'target_branch': 'INFERRED_FROM_MATCHING_BYTES_NOT_EXECUTED' if observation.get('target_byte_match') is True
                             else 'UNKNOWN_UNEXECUTED',
            'required': 'Approved transport/environment decision; do not exempt loopback or weaken the guard.'}
