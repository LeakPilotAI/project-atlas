"""Personal PAPER policy/composition. No provisioning,providers or automatic start.

Operator approval is LOCAL_OPERATOR authority,not historical strict-gate approval.
Existing FS1-FS3/V3-V5 technical contracts are reused without fixture conversion.
"""
from contextlib import contextmanager

from app.services.paper_financial_replay import body, digest, strict
from app.services.quality_dips_autonomous_binding import EnrolledAutonomousRuntime
from app.services.quality_dips_autonomous_enrollment import (
    AutonomousNativeEnrollment,
    validate_enrollment,
)
from app.services.quality_dips_operational_runtime import (
    OperationalFinancialBinding,
    OperationalRuntime,
)

PROFILE='PERSONAL_PAPER_ONLY_V1'
CHECKS=('SIMULATION_ONLY','ACCOUNT_ISOLATION','RISK_LIMITS','FINANCIAL_INTEGRITY','NATIVE_RESOURCES',
        'WRITER_OWNERSHIP','CLOCK_CONTINUITY','DATA_REFUSAL_CONTROLS','CAPACITY_WITH_STOP_RESERVES')
PERSONAL_GATES=('P-B1','P-C1','P-D1','P-E1')


def validate_policy(value):
    p=strict(body(value))
    if (p.get('schema')!='ATLAS_PERSONAL_PAPER_RELEASE_POLICY_V1' or p.get('profile_id')!=PROFILE
            or p.get('policy_approved') is not True or p.get('runtime_consumable') is not True
            or p.get('status')!='APPROVED_SOURCE_INTEGRATION_ONLY'
            or p.get('operator_model')!='SOLE_LOCAL_OPERATOR' or p.get('deployment')!='D_ONLY_EXISTING_WINDOWS_ACCOUNT'
            or p.get('startup_authorized') is not False or p.get('activation_authorized') is not False
            or p.get('financial_publication_authorized') is not False or p.get('provider_activation_authorized') is not False
            or p.get('historical_gate_promotions')!=0
            or p.get('vps_cloud_new_windows_account_allowed') is not False or p.get('genesis_access_allowed') is not False
            or p.get('preserve_original_frontend') is not True):raise ValueError('PERSONAL_APPROVED_POLICY_REQUIRED_NO_ACTIVATION_IMPLIED')
    a=p['authority'];s=p['account_separation'];q=p['accounts']['QUALITY_DIPS'];h=p['accounts']['HYPERLIQUID']
    if (a['release_decision']!='SOLE_OPERATOR' or a.get('technical_refusals_not_overrideable_by_start') is not True or any(a[k] is not False for k in ('external_reviewer_required','external_issuer_required','independent_custodian_required','per_trade_confirmation'))
            or any(s[k] is not False for k in ('transfers','cash_netting','assume_usdc_equals_usd','synthetic_counterpart_for_uninitialized_lane','legacy_adoption','historical_positions_assumed_closed'))
            or (q['currency'],q['opening_balance'],q['max_entry_notional'],q['max_open_positions'],q['long_only'],q['scale_in'])!=('SIMULATED_USD','1000','100',1,True,False)
            or (h['currency'],h['opening_balance'],h['max_risk_per_trade'],h['max_open_positions'],h['session_stop_R'])!=('SIMULATED_USDC','1000','1',3,'-3')
            or q['universe']!='ELIGIBLE_EXISTING_QD_RANKED_STOCKS_ETFS' or q['fractional']!='ONLY_WHEN_SUPPORTED'
            or type(h['max_open_positions']) is not int or h['universe']!=['BTC','ETH','SOL']
            or type(q['max_open_positions']) is not int or q['long_only'] is not True or q['scale_in'] is not False
            or q['fee_bps_per_side']!='2' or q['slippage_bps_per_side']!='2'
            or set(p['prohibited_capabilities'])!={'REAL_ORDER_EXECUTION','REAL_CAPITAL_ENROLLMENT','WITHDRAWAL','TRANSFER','WALLET_SIGNING','PAPER_TO_LIVE_PROMOTION','LIVE_TOGGLE','LIVE_ORDER_SDK_OR_DORMANT_ROUTE'}):raise ValueError('PERSONAL_SAFETY_POLICY_CHANGED')
    return p


def _components(value):
    if type(value) is dict:return ('mapping',tuple((k,_components(v)) for k,v in sorted(value.items())))
    if type(value) in (str,int,bool,float,type(None)):return (type(value).__name__,value)
    if type(value) in (list,tuple):return (type(value).__name__,tuple(_components(v) for v in value))
    return ('port',id(value))


class PersonalOperatorInstallation:
    """One local activation record + actual technical facts;no reviewer roles.

    reader is the explicitly installed handle-bound LOCAL_OPERATOR record port.
    identity/technical read actual local evidence. None has a default installation.
    Policy approval alone supplies neither this record nor a running session.
    """
    def __init__(self,*,policy,reader,identity,technical,clock,components,release_digest,accounts):
        if any(x is None for x in (reader,identity,technical,clock,components,release_digest,accounts)):raise ValueError('PERSONAL_LOCAL_ACTIVATION_DEPENDENCIES_REQUIRED')
        self.policy=validate_policy(policy);self._policy=body(self.policy)
        self.reader,self.identity,self.technical,self.clock=reader,identity,technical,clock
        self.release,self.accounts=release_digest,strict(body(accounts));self.revoked=False
        if (type(self.release) is not str or len(self.release)!=64 or any(c not in '0123456789abcdef' for c in self.release)
                or not self.accounts or any(type(v) is not str or len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for v in self.accounts.values())):raise ValueError('PERSONAL_RELEASE_ACCOUNT_DIGESTS_REQUIRED')
        self._scope=body({'release':self.release,'accounts':self.accounts})
        self._expected_components=_components(components)
        self._ports=(reader,identity,technical,clock)
    def revoke(self):self.revoked=True
    def _read(self,request):
        if (self.revoked or body(self.policy)!=self._policy or body({'release':self.release,'accounts':self.accounts})!=self._scope
                or any(a is not b for a,b in zip((self.reader,self.identity,self.technical,self.clock),self._ports,strict=True))):raise ValueError('PERSONAL_ACTIVATION_REVOKED_OR_CHANGED')
        now=self.clock();value=strict(body(self.reader.read()))
        fields={'schema','profile','origin','activation_id','operator_id','policy_digest','release_digest','accounts','issued_at','expires_at','actions'}
        if (type(now) is not int or set(value)!=fields or value['schema']!='ATLAS_PERSONAL_ACTIVATION_V1'
                or value['profile']!=PROFILE or value['origin']!='LOCAL_OPERATOR'
                or not isinstance(value['activation_id'],str) or not value['activation_id']
                or type(value['operator_id']) is not str or not value['operator_id'] or value['operator_id']!=self.identity.current_operator()
                or value['policy_digest']!=digest(self.policy) or value['release_digest']!=self.release
                or value['accounts']!=self.accounts or not self.accounts
                or set(self.accounts)-{'QUALITY_DIPS','HYPERLIQUID'}
                or any(type(value[k]) is not int for k in ('issued_at','expires_at'))
                or not value['issued_at']<=now<value['expires_at']<=value['issued_at']+1800
                or type(value['actions']) is not list or len(value['actions'])!=len(set(value['actions']))
                or set(value['actions'])-{'READ_ONLY','AUTO_PAPER','SHUTDOWN_FLATTEN','EMERGENCY_STOP','INITIALIZE_SIMULATED_ACCOUNTS','CONNECT_APPROVED_DATA'}
                or request.get('action','AUTO_PAPER') not in value['actions']):raise ValueError('PERSONAL_EXPLICIT_ACTIVATION_REQUIRED')
        facts=strict(body(self.technical.inspect(request)))
        if set(facts)!=set(CHECKS) or any(x is not True for x in facts.values()):raise ValueError('PERSONAL_TECHNICAL_CHECKS_FAILED')
        return value,now
    @contextmanager
    def lease(self,request):
        request=strict(body(request));value,start=self._read(request);owner=self
        proof={'schema':'ATLAS_PERSONAL_INSTALLATION_V1','domain':'PERSONAL_LOCAL_OPERATOR','profile':PROFILE,
            'binding':digest(request),'policy_digest':digest(self.policy),'activation_id':value['activation_id'],
            'gates':dict.fromkeys(PERSONAL_GATES,'OPERATOR_AND_TECHNICAL_CHECKS_PASSED')}
        sealed=body(proof)
        class Lease:
            snapshot=proof
            def check(self,snapshot):
                current,end=owner._read(request)
                return body(snapshot)==sealed and body(proof)==sealed and current==value and start<=end<value['expires_at']
            def check_components(self,ports):return _components(ports)==owner._expected_components
        lease=Lease();yield lease
        if not lease.check(proof):raise ValueError('PERSONAL_ACTIVATION_CHANGED')


class PersonalNativeEnrollment(AutonomousNativeEnrollment):
    # Underlying AUTO enrollment identifies the financial calculation/resource
    # protocol. Release authority is explicitly PERSONAL,never strict B1 ACCEPTED.
    acceptance_schema='ATLAS_PERSONAL_NATIVE_ACCEPTANCE_V1'
    acceptance_profile=PROFILE
    gate_names=PERSONAL_GATES
    gate_status='OPERATOR_AND_TECHNICAL_CHECKS_PASSED'


class PersonalNativeAcceptance:
    """Local operator activation expressed in distinct personal proof tags."""
    def __init__(self,installation):self.installation=installation
    @contextmanager
    def lease(self,request,now):
        i=self.installation;e=validate_enrollment(request['enrollment'])
        if request['scope']!='LOCAL_ENROLLED' or i.accounts.get('QUALITY_DIPS')!=digest(e):raise ValueError('PERSONAL_NATIVE_ACCOUNT_SCOPE')
        outer={'schema':'ATLAS_PERSONAL_NATIVE_ADMISSION_V1','request':request}
        with i.lease(outer) as lease:
            original=checked_personal_installation(lease,outer)
            activation,stamp=i._read(outer)
            if now!=stamp or request['grant']['expires_at']>activation['expires_at']:raise ValueError('PERSONAL_SESSION_OUTSIDE_ACTIVATION')
            proof={'schema':'ATLAS_PERSONAL_NATIVE_ACCEPTANCE_V1','request_digest':digest(request),'scope':'LOCAL_ENROLLED',
                'acceptance_id':e['acceptance_id'],'profile':PROFILE,'gates':dict.fromkeys(PERSONAL_GATES,'OPERATOR_AND_TECHNICAL_CHECKS_PASSED'),
                'revoked':False,'issued_at':now,'expires_at':min(now+30,activation['expires_at'])}
            sealed=body(proof)
            class Accepted:
                snapshot=proof
                def check(self,p,end):return body(p)==sealed and body(proof)==sealed and now<=end<=proof['expires_at'] and lease.check(original)
            yield Accepted()


class PersonalFinancialBinding(OperationalFinancialBinding):
    def cut(self):return {**super().cut(),'execution_domain':'PERSONAL_PAPER'}


def checked_personal_installation(lease,request):
    p=strict(body(lease.snapshot))
    if (set(p)!={'schema','domain','profile','binding','policy_digest','activation_id','gates'}
            or p['schema']!='ATLAS_PERSONAL_INSTALLATION_V1' or p['domain']!='PERSONAL_LOCAL_OPERATOR'
            or p['profile']!=PROFILE or p['binding']!=digest(request)
            or p['gates']!=dict.fromkeys(PERSONAL_GATES,'OPERATOR_AND_TECHNICAL_CHECKS_PASSED')
            or lease.check(p) is not True):raise ValueError('PERSONAL_INSTALLATION_REFUSED')
    return p


class PersonalEnrolledRuntime(EnrolledAutonomousRuntime):
    financial_types=(PersonalFinancialBinding,)
    execution_domain='PERSONAL_PAPER'
    @contextmanager
    def _action(self,*,readonly=False):
        try:
            if self.admission.acceptance is not self._personal_acceptance:raise ValueError('PERSONAL_AUTHORITY_SUBSTITUTION')
            request=self.installation_request()
            with self.installation.lease(request) as lease:
                proof=checked_personal_installation(lease,request)
                if not lease.check_components(self.installation_components()):raise ValueError('PERSONAL_COMPONENT_SUBSTITUTION')
                with super()._action(readonly=readonly):yield
                if not lease.check(proof) or not lease.check_components(self.installation_components()):raise ValueError('PERSONAL_INSTALLATION_CHANGED')
        except BaseException:
            if not readonly:
                self.failed=True;self.runtime._incomplete()
            raise


def compose_personal_qd(*,policy=None,enrollment=None,runtime_dependencies=None,native_dependencies=None,store=None,native_reader=None,installation=None):
    """Construct existing V3-V5 components only;does not start or initialize them."""
    if any(x is None for x in (policy,enrollment,runtime_dependencies,native_dependencies,store,native_reader,installation)):raise ValueError('PERSONAL_EXPLICIT_ACTIVATION_DEPENDENCIES_REQUIRED')
    p=validate_policy(policy);e=validate_enrollment(enrollment)
    if type(installation) is not PersonalOperatorInstallation or body(installation.policy)!=body(p):raise ValueError('PERSONAL_OPERATOR_INSTALLATION_REQUIRED')
    if installation.accounts.get('QUALITY_DIPS')!=digest(e) or installation.release!=e['release_digest']:raise ValueError('PERSONAL_ACCOUNT_RELEASE_BINDING')
    def request():return {'schema':'ATLAS_PERSONAL_QD_COMPOSITION_V1','profile':PROFILE,'policy_digest':digest(p),'enrollment':e,'source_pin':store.trust.current(),'report_pin':runtime_dependencies['reports'].archive.trust.current()}
    if set(native_dependencies)!={'custody','clock','ownership','sessions'}:raise ValueError('PERSONAL_TECHNICAL_PORTS_ONLY_NO_REVIEWER')
    ports={'runtime':dict(runtime_dependencies),'native':dict(native_dependencies),'store':store,'reader':native_reader}
    with installation.lease(request()) as lease:
        proof=checked_personal_installation(lease,request())
        if not lease.check_components(ports):raise ValueError('PERSONAL_COMPONENT_SUBSTITUTION')
        r=OperationalRuntime(**runtime_dependencies)
        financial=PersonalFinancialBinding(enrollment=e,runtime=r,store=store,native_reader=native_reader,release_digest=e['release_digest'])
        acceptance=PersonalNativeAcceptance(installation)
        admission=PersonalNativeEnrollment(enrollment=e,native=financial,acceptance=acceptance,**native_dependencies)
        delegate=r.engine.publication;r.engine.publication=financial
        try:
            result=PersonalEnrolledRuntime(runtime=r,admission=admission,financial=financial)
            result.installation=installation;result.installation_request=request;result._personal_acceptance=acceptance
            result.installation_components=lambda:{'runtime':{k:getattr(r,k) for k in runtime_dependencies},'native':{k:getattr(admission,k) for k in native_dependencies},'store':store,'reader':native_reader}
            if not lease.check(proof):raise ValueError('PERSONAL_INSTALLATION_CHANGED')
            return result
        except BaseException:r.engine.publication=delegate;raise


def compose_personal_unified(*,policy=None,lanes=None,portfolio=None,clock=None,installation=None):
    from app.services.unified_paper_runtime import UnifiedPaperRuntime
    if any(x is None for x in (policy,lanes,portfolio,clock,installation)):raise ValueError('PERSONAL_UNIFIED_ACTIVATION_REQUIRED')
    p=validate_policy(policy)
    if type(installation) is not PersonalOperatorInstallation or body(installation.policy)!=body(p) or set(installation.accounts)!={'QUALITY_DIPS','HYPERLIQUID'}:raise ValueError('PERSONAL_COMPLETE_REAL_ACCOUNTS_REQUIRED')
    from app.services.perp_operational_contract import validate_enrollment as validate_perp
    from app.services.unified_native_writer import CanonicalWriterLane
    from app.services.unified_portfolio_custody import UnifiedPortfolioCustody
    if (type(portfolio) is not UnifiedPortfolioCustody or type(lanes) is not dict
            or set(lanes)!={'QUALITY_DIPS','HYPERLIQUID'} or set(portfolio.writers)!=set(lanes)):
        raise ValueError('PERSONAL_ACTUAL_UNIFIED_LANES_REQUIRED')
    for lane,writer in portfolio.writers.items():
        if type(lanes[lane]) is not CanonicalWriterLane or lanes[lane].writer is not writer:raise ValueError('PERSONAL_UNIFIED_WRITER_SUBSTITUTION')
        native=(validate_enrollment if lane=='QUALITY_DIPS' else validate_perp)(writer.store.enrollment)
        if (digest(native)!=installation.accounts[lane] or native['release_digest']!=installation.release
                or native['inception_digest']!=digest(writer.manifest)):
            raise ValueError('PERSONAL_UNIFIED_ACCOUNT_RELEASE_SUBSTITUTION')
    ports={'lanes':lanes,'portfolio':portfolio,'clock':clock}
    with installation.lease({'schema':'ATLAS_PERSONAL_UNIFIED_COMPOSITION_V1','profile':PROFILE}) as lease:
        checked_personal_installation(lease,{'schema':'ATLAS_PERSONAL_UNIFIED_COMPOSITION_V1','profile':PROFILE})
        if not lease.check_components(ports):raise ValueError('PERSONAL_UNIFIED_COMPONENT_SUBSTITUTION')
        return UnifiedPaperRuntime(lanes=lanes,portfolio=portfolio,clock=clock,installation=installation)
