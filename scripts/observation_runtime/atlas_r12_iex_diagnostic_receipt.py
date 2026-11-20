"""Create-once, sanitized ALPACA IEX observation receipt. DIAGNOSTIC ONLY.

Takes only a fully admitted successful bounded data-only probe. Does not open
credentials, contact Alpaca, write native QD custody, admit financial rights,
or record raw quote prices. An unkeyed SHA-256 is integrity, NOT provider proof.
"""
import hashlib
import json
import os
import re
from pathlib import Path

ROOT=Path(r'D:\Work\Project Atlas')
RECORDS_DIR=ROOT/'logs/diagnostics/atlas-iex-data-only-observations'
ID=re.compile(r'[0-9a-f]{32}\Z')
SYMBOL=re.compile(r'[A-Z][A-Z0-9.-]{0,14}\Z')
SCHEMA='ATLAS_R12_IEX_DATA_ONLY_DIAGNOSTIC_RECEIPT_V1'


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),
                       ensure_ascii=True,allow_nan=False)+'\n').encode('ascii')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def admit_packet(packet,requested,operation_id):
    from scripts.observation_runtime.atlas_r12_alpaca_source_admission import validate_bounded_iex_probe
    if type(operation_id) is not str or ID.fullmatch(operation_id) is None:
        raise ValueError('IEX_DIAGNOSTIC_EXACT_OPERATION_ID_REQUIRED')
    if (type(requested) is not list or not 1<=len(requested)<=10
        or len(set(requested))!=len(requested)
        or any(type(x) is not str or SYMBOL.fullmatch(x) is None for x in requested)):
        raise ValueError('IEX_DIAGNOSTIC_BOUNDED_REQUESTED_SYMBOLS_REQUIRED')
    if type(packet) is not dict:
        raise ValueError('IEX_DIAGNOSTIC_BOUNDED_PACKET_REQUIRED')
    validated=validate_bounded_iex_probe(packet)
    if (packet.get('status')!='BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY'
        or packet.get('single_exchange_not_nbbo') is not True
        or packet.get('continuous_executable_prices_verified') is not False
        or packet.get('provider_rights_independently_accepted') is not False
        or type(packet.get('observed_symbols')) is not list
        or not packet['observed_symbols']
        or packet['observed_symbols']!=sorted(set(packet['observed_symbols']))
        or not set(packet['observed_symbols'])<=set(requested)
        or type(packet.get('callback_quote_count')) is not int
        or not 0<packet['callback_quote_count']<=packet['quote_count']
        or validated.get('paper_execution_authorized') is not False
        or validated.get('provider_data_rights_accepted') is not False):
        raise ValueError('IEX_DIAGNOSTIC_SUCCESS_BUT_UNVERIFIED_SCOPE')
    body={'schema':'ATLAS_R12_IEX_DATA_ONLY_DIAGNOSTIC_BODY_V1',
          'operation_id':operation_id,
            'provider':'ALPACA','feed':'IEX',
            'feed_scope':'SINGLE_EXCHANGE_NOT_NBBO',
            'requested_symbols':list(requested),
            'observed_symbols':list(packet['observed_symbols']),
            'callback_quote_count':packet['callback_quote_count'],
            'provider_quote_count':packet['quote_count'],
            'authenticated_observed':True,
            'exact_subscription_ack_observed':True,
            'fresh_quote_callback_observed':True,
            'connection_closed':True,
            'wall_clock_or_financial_ntp_certified':False,
            'provider_event_signature_verified':False,
            'individual_rights_accepted':False,
            'continuous_executable_prices_verified':False,
            'native_forward_source_published':False,
            'financial_account_created':False,
            'paper_execution_authorized':False,
            'live_order_authorized':False,
            'startup_authorized':False}
    if 'per_symbol_quote_diagnostics' in packet:
        from scripts.observation_runtime.alpaca_iex_probe import _admit_symbol_diagnostics
        validated_stats=_admit_symbol_diagnostics(
            {'per_symbol_quote_diagnostics':packet['per_symbol_quote_diagnostics'],
             'quote_count':packet['quote_count']},requested,
            set(packet['observed_symbols']),packet['callback_quote_count'])
        if validated_stats != packet['per_symbol_quote_diagnostics']:
            raise ValueError('IEX_DIAGNOSTIC_INVALID_SYMBOL_TELEMETRY')
        body['per_symbol_quote_diagnostics']=validated_stats
    return body


def _path(operation_id,root):
    if type(operation_id) is not str or ID.fullmatch(operation_id) is None:
        raise ValueError('IEX_DIAGNOSTIC_EXACT_OPERATION_ID_REQUIRED')
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('IEX_DIAGNOSTIC_OWNED_DIRECTORY_REQUIRED')
    return root/('receipt-'+operation_id+'.json')


def read_receipt(operation_id,*,root=None):
    path=_path(operation_id,RECORDS_DIR if root is None else root)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>8192:
        raise ValueError('IEX_DIAGNOSTIC_NATIVE_READBACK_REFUSED')
    try:
        content=path.read_bytes()
        row=json.loads(content)
        if (type(row) is not dict or set(row)!={'schema','body','body_sha256'}
            or row['schema']!=SCHEMA
            or type(row['body']) is not dict
            or row['body'].get('operation_id')!=operation_id
            or row['body'].get('schema')!='ATLAS_R12_IEX_DATA_ONLY_DIAGNOSTIC_BODY_V1'
            or type(row['body_sha256']) is not str
            or row['body_sha256']!=digest(row['body'])
            or content!=canonical(row)
            or any(row['body'].get(x) is not False for x in (
                'wall_clock_or_financial_ntp_certified','provider_event_signature_verified',
                'individual_rights_accepted','continuous_executable_prices_verified',
                'native_forward_source_published','financial_account_created',
                'paper_execution_authorized','live_order_authorized','startup_authorized'))):
            raise ValueError('IEX_DIAGNOSTIC_RECEIPT_INTEGRITY_OR_SCOPE_CHANGED')
        # Validate count/symbol scope again, not merely a self-authored SHA.
        body=row['body']
        packet={'schema':'ATLAS_IEX_BOUNDED_DATA_ONLY_PROBE_V1',
                'status':'BOUNDED_FRESH_IEX_OBSERVED_NOT_FINANCIAL_AUTHORITY',
                'authenticated':body.get('authenticated_observed'),
                'subscribed':body.get('exact_subscription_ack_observed'),
                'quote_count':body.get('provider_quote_count'),
                'fresh_quote_observed_during_connection':body.get('fresh_quote_callback_observed'),
                'observed_symbols':body.get('observed_symbols'),
                'callback_quote_count':body.get('callback_quote_count'),
                'connection_closed':body.get('connection_closed'),
                'single_exchange_not_nbbo':True,
                'continuous_executable_prices_verified':False,
                'provider_rights_independently_accepted':False,
                'paper_fill_authorized':False,'live_order_authorized':False}
        if 'per_symbol_quote_diagnostics' in body:
            packet['per_symbol_quote_diagnostics'] = body['per_symbol_quote_diagnostics']
        if body.get('provider')!='ALPACA' or body.get('feed')!='IEX' or body.get('feed_scope')!='SINGLE_EXCHANGE_NOT_NBBO':
            raise ValueError('IEX_DIAGNOSTIC_RECEIPT_PROVIDER_CHANGED')
        if admit_packet(packet,body.get('requested_symbols'),operation_id)!=body:
            raise ValueError('IEX_DIAGNOSTIC_RECEIPT_NONCANONICAL_BODY')
        return {'status':'DIAGNOSTIC_DATA_ONLY_RECEIPT_VERIFIED_NOT_FINANCIAL_AUTHORITY',
                'operation_id':operation_id,'body_sha256':row['body_sha256'],
                'observed_symbols':body['observed_symbols'],
                'callback_quote_count':body['callback_quote_count'],
                'paper_execution_authorized':False,
                'native_forward_source_published':False}
    except (UnicodeError,json.JSONDecodeError,KeyError,TypeError):
        raise ValueError('IEX_DIAGNOSTIC_RECEIPT_MALFORMED') from None


def write_receipt(packet,requested,operation_id,*,root=None):
    dest=_path(operation_id,RECORDS_DIR if root is None else root)
    body=admit_packet(packet,requested,operation_id)
    row={'schema':SCHEMA,'body':body,'body_sha256':digest(body)}
    data=canonical(row)
    if len(data)>8192:
        raise ValueError('IEX_DIAGNOSTIC_RECEIPT_SIZE_REFUSED')
    # Create once: an existing or partial record is never overwritten or
    # silently adopted after a crash; the operator must inspect it.
    with dest.open('xb') as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    verified=read_receipt(operation_id,root=dest.parent)
    if verified['body_sha256']!=row['body_sha256']:
        raise ValueError('IEX_DIAGNOSTIC_DURABLE_RECEIPT_CHANGED')
    return verified
