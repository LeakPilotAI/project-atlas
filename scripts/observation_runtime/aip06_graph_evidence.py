"""Authenticated root-ledger graph receipts, never process-adoption authority.

Only the parent Broker emits these after original-handle/native Job verification.
An inherited consumer supplements the receipt with its own current handle and
raw Job roster. Scalars in an uncorrelated message cannot install this proof.
"""
from app.services.paper_financial_replay import body
from scripts.observation_runtime.aip06_harness import SCOPE_HASH, need
from scripts.observation_runtime.aip06_ipc import MAX_IPC_NS
from scripts.observation_runtime.launch_ownership import identity


def validate_graph_evidence(value, wire, now):
    need(type(value) is dict and set(value)=={'schema','scope','peer','nonce','rows','at_ns','source_head'}
         and value['schema']=='AIP06_RETAINED_GRAPH_V1' and value['scope']==SCOPE_HASH
         and body(value['peer'])==body(wire['child']) and value['nonce']==wire['nonce']
         and type(value['at_ns']) is int and 0<=now-value['at_ns']<=MAX_IPC_NS
         and type(value['source_head']) is str and len(value['source_head'])==64
         and set(value['source_head'])<=set('0123456789abcdef')
         and type(value['rows']) is list and len(value['rows'])<8,'GRAPH_RECEIPT_SCOPE_OR_FRESHNESS')
    known={wire['child']['pid']:wire['child']}
    pending=list(value['rows'])
    while pending:
        progressed=False
        for row in pending[:]:
            need(type(row) is dict and set(row)==set(wire['child']), 'GRAPH_EXACT_NATIVE_ROW')
            checked=dict(row);checked['file_id']=tuple(checked['file_id'])
            identity(checked)
            need(type(row['parent_pid']) is int and type(row['command_line']) is str
                 and row['command_line'] and row['pid'] not in known,'GRAPH_DUPLICATE_OR_INVALID_BIRTH')
            if row['parent_pid'] in known:
                need(row['created']>=known[row['parent_pid']]['created'],'GRAPH_ANCESTRY_LIFETIME')
                known[row['pid']]=row;pending.remove(row);progressed=True
        need(progressed,'GRAPH_MISSING_PARENT_OR_CYCLE')
    return value['rows']
