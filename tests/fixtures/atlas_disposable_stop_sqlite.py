"""Test fixture: real production Stop SQLite ledger with disposable Windows IPC.

No real Atlas financial runtime/account, provider or trade. Isolated pytest path
only, synthetic session ID, deterministic two-lane nonfinancial receipt.
"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.services.paper_stop_receipt_ledger import PaperStopReceiptLedger

SESSION='test-disposable-two-lane-session'
MODE='SHUTDOWN_FLATTEN'


def verify_receipt(value):
    if (type(value) is not dict or value.get('schema')!='QD_CONTROL_STOP_V1'
       or value.get('phase')!='FINISHED'
       or type(value.get('outcome')) is not dict
       or value['outcome'].get('schema')!='QD_AUTO_SHUTDOWN_V1'
       or value['outcome'].get('mode')!=MODE
       or value['outcome'].get('status')!='FLATTENED'
       or value['outcome'].get('position_state')!='FLAT'
       or value['outcome'].get('process_shutdown')!='VERIFIED_EXIT'
       or value.get('disposable_positions_before')!={'QUALITY_DIPS':5,'HYPERLIQUID':3}
       or value.get('disposable_positions_after')!={'QUALITY_DIPS':0,'HYPERLIQUID':0}
       or type(value['outcome'].get('lanes')) is not dict
       or set(value['outcome']['lanes'])!={'QUALITY_DIPS','HYPERLIQUID'}
       or any(v!={'state':'ACKNOWLEDGED_FLAT_AND_DRAINED'}
              for v in value['outcome']['lanes'].values())):
        raise ValueError('DISPOSABLE_NATIVE_STOP_TWO_LANE_FLATNESS_REFUSED')
    return value


def operate(action,db_file,receipt_path):
    db_file=Path(db_file)
    receipt_path=Path(receipt_path)
    if (db_file.suffix!='.sqlite' or not db_file.parent.is_dir() or
        db_file.is_symlink() or receipt_path.is_symlink() or
        db_file.name!='disposable-stop-ledger.sqlite' or
        receipt_path.name!='disposable-flatten-receipt.json' or
        db_file.parent!=receipt_path.parent):
        raise ValueError('DISPOSABLE_STOP_ISOLATED_PATHS_REQUIRED')
    if action=='reserve':
        if db_file.exists():
            raise ValueError('DISPOSABLE_STOP_LEDGER_CREATE_ONCE_REQUIRED')
        result=PaperStopReceiptLedger(db_file).reserve_fresh(SESSION,MODE)
        if result!={'state':'PENDING','mode':MODE,'receipt':None}:
            raise ValueError('DISPOSABLE_STOP_FRESH_INTENT_REQUIRED')
        return
    if not db_file.is_file():
        raise ValueError('DISPOSABLE_STOP_LEDGER_MISSING')
    ledger=PaperStopReceiptLedger(db_file)
    if action=='finish':
        if ledger.inspect_session(SESSION)!={'state':'PENDING','mode':MODE,'receipt':None}:
            raise ValueError('DISPOSABLE_STOP_PENDING_INTENT_REQUIRED')
        receipt=verify_receipt(json.loads(receipt_path.read_text(encoding='utf-8')))
        ledger.finish(SESSION,MODE,receipt)
        return
    if action=='verify':
        if not receipt_path.is_file():
            raise ValueError('DISPOSABLE_STOP_RECEIPT_MISSING')
        expected=verify_receipt(json.loads(receipt_path.read_text(encoding='utf-8')))
        row=ledger.inspect_session(SESSION)
        if row!={'state':'FINISHED','mode':MODE,'receipt':expected}:
            raise ValueError('DISPOSABLE_STOP_DURABLE_SQLITE_RECEIPT_CHANGED')
        recovered=PaperStopReceiptLedger(db_file).recover(SESSION,MODE)
        if recovered!={'state':'RECEIPT_RECORDED','mode':MODE,'receipt':expected}:
            raise ValueError('DISPOSABLE_STOP_DURABLE_REOPEN_REFUSED')
        return
    raise ValueError('DISPOSABLE_STOP_UNKNOWN_ACTION')


if __name__=='__main__':
    if len(sys.argv)!=4:
        raise SystemExit('DISPOSABLE_STOP_EXACT_ARGUMENTS_REQUIRED')
    operate(sys.argv[1],sys.argv[2],sys.argv[3])
