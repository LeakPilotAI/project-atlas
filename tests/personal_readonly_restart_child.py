"""Self-exiting synthetic native restart reader. Never an operational entry."""
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path
from threading import Timer

from app.investment.quality_dips_candidate_evidence import CandidateEvidenceAdapter
from app.services.paper_financial_replay import digest, number, strict
from app.services.personal_current_pins import PersonalCurrentPins
from app.services.personal_native_coordination import PersonalNativeCoordination
from app.services.personal_publication_custody import PersonalPublicationCustody
from app.services.quality_dips_autonomous_integration import AutonomousCoordinationRead
from app.services.quality_dips_autonomous_paper import AutonomousPaper
from app.services.quality_dips_operational_presentation import OperationalAutonomousSelectedRead

from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_financial_authority import (
    NativePersonalFinancialReadAuthority,
)
from scripts.observation_runtime.personal_local_authority import NativePersonalOperatorAuthority
from scripts.observation_runtime.personal_paper_inception import (
    NativePersonalInitialReadback,
    PersonalInceptionBootstrap,
)
from scripts.observation_runtime.personal_runtime_current import PersonalNativeReadAuthority
from scripts.observation_runtime.personal_writer_ownership import NativePersonalWriterOwnership
from scripts.observation_runtime.quality_dips_read_service import observe_self


class NoFinancialPermission:
    def verify(self, *args, **kwargs): raise ValueError('READ_ONLY_FIXTURE_NO_FINANCIAL_AUTHORITY')
    def verify_current(self, *args, **kwargs): raise ValueError('READ_ONLY_FIXTURE_NO_MARKET_AUTHORITY')
    def lease(self, *args, **kwargs): raise ValueError('READ_ONLY_FIXTURE_NO_PUBLICATION_AUTHORITY')


def main():
    raw=sys.stdin.buffer.read(65537)
    if len(raw)>65536: raise ValueError('FIXTURE_INPUT_CAPACITY')
    value=strict(raw.decode())
    root=Path(value['root'])
    repo=Path(__file__).resolve().parents[1]
    if (root.parent.parent != repo/'logs/diagnostics' or not root.parent.name.startswith('qd-personal-pipeline-')
            or any(p.is_symlink() or p.is_junction() for p in (root,*root.parents))):
        raise ValueError('EXPLICIT_SYNTHETIC_ROOT_REQUIRED')
    enrollment=value['personal_enrollment']
    native,manifest=enrollment['native_enrollment'],enrollment['parameters']
    if any(Path(item['path']) != root/role for role,item in native['resources'].items()):
        raise ValueError('FIXTURE_RESOURCE_ESCAPE')
    clock=lambda:value['now']
    # Explicit synthetic operator action for this disposable test only. This
    # class override cannot be installed as genuine native activation evidence.
    operator=object.__new__(NativePersonalOperatorAuthority)
    operator.enrollment,operator.clock=copy.deepcopy(native),clock
    def action(name):
        if name!='READ_ONLY': raise ValueError('SYNTHETIC_READER_NO_WRITE_GRANT')
        return {'schema':'SYNTHETIC_READ_ONLY_TEST_ACTION','action':name}
    operator.activation=action
    refused=False
    try: NativePersonalWriterOwnership(enrollment=native,authority=operator)
    except ValueError: refused=True
    if not refused: raise ValueError('RESTART_WRITER_REBIND_NOT_REFUSED')
    images=NativePersonalCoordinationImages(root=native['resources']['coordination']['path'],
        native_root=native['resources']['coordination']['native_id'],enrollment_digest=digest(native))
    handles=[images]
    try:
        ledger=PersonalNativeCoordination(manifest=manifest,images=images,path=root/'coordination/memory-only')
        owner=NativePersonalWriterOwnership(enrollment=native,authority=operator,ledger=ledger,read_only=True)
        handles.append(owner)
        source=PersonalCurrentPins(ledger=ledger,name='source',clock=clock)
        reports=PersonalCurrentPins(ledger=ledger,name='reports',clock=clock)
        authority=NativePersonalFinancialReadAuthority(operator=operator,ownership=owner,source=source)
        spec=importlib.util.spec_from_file_location('readonly_restart_codec',repo/'scripts/volume_inspector/operational_autonomous_store.py')
        codec=importlib.util.module_from_spec(spec);spec.loader.exec_module(codec)
        spec=importlib.util.spec_from_file_location('readonly_restart_report',repo/'scripts/volume_inspector/financial_reporting.py')
        report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)
        projection=report.ProjectionTarget(native['resources']['projection']['path'],native['resources']['projection']['native_id'])
        handles.append(projection)
        native_reader=codec.OperationalAutonomousReader(enrollment=native,trust=source,authority=authority,
                                                        clock=clock,projection=projection)
        bootstrap=PersonalInceptionBootstrap(enrollment=enrollment,publication=PersonalPublicationCustody(ledger),
                    issuer=NoFinancialPermission(),clock=clock,readback=NativePersonalInitialReadback())
        source_pin=source.current()
        read_enrollment={'schema':'QD_AUTO_OP_READ_ENROLLMENT_V1','account_id':native['account_id'],'epoch':native['epoch'],
            'manifest_digest':digest(manifest),'policy_digest':native['policy_digest'],'inception':source_pin['inception'],
            **{r+'_root':native['resources'][r]['native_id'] for r in ('source','projection','report')}}
        read_authority=PersonalNativeReadAuthority(bootstrap=bootstrap,source=source,reports=reports,
                                                   ownership=owner,enrollment=read_enrollment)
        refused_data=NoFinancialPermission()
        engine=AutonomousPaper(ledger=ledger,clock=clock,session_authority=refused_data,source_authority=refused_data,
                candidates=CandidateEvidenceAdapter(ranking_authority=refused_data,execution_authority=refused_data))
        reader=OperationalAutonomousSelectedRead(enrollment=read_enrollment,authority=read_authority,clock=clock,
                    port=native_reader,coordination=AutonomousCoordinationRead(engine))
        payload=reader.read_committed(native['account_id'],native['epoch'])
        assert reader.verify(payload,account_id=native['account_id'],epoch=native['epoch'],now=clock())['verified']
        assert number(payload['state']['cash'])==number('1015.9136')
        assert all(number(p['remaining'])==0 and number(p['remaining_entry_costs'])==0 for p in payload['state']['positions'].values())
        assert engine.grant is None and operator.enrollment==native
        print(json.dumps({'synthetic_only':True,'read_only_restart':True,'writer_rebind_refused':refused,
            'process':observe_self(),'cash':payload['state']['cash'],'source_revision':payload['source_revision'],
            'state_digest':digest(payload['state']),'account_and_epoch_distinct':native['account_id']!=native['epoch']}))
    finally:
        for item in reversed(handles): item.close()


if __name__=='__main__':
    watchdog=Timer(30,lambda:os._exit(70));watchdog.daemon=True;watchdog.start()
    try:
        if sys.argv[1:]==['--ready-before-input']:
            # Imports are ready, but no account/root/authority has been opened.
            # A retained read-only service can wait for post-Stop input.
            print(json.dumps({'reader_ready':True,'process':observe_self()}),flush=True)
        elif sys.argv[1:]:
            raise ValueError('SYNTHETIC_READER_MODE_REFUSED')
        main()
    finally: watchdog.cancel()
