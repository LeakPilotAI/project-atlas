"""Static compatibility inventory must never promote an unaccepted reader."""
from types import SimpleNamespace
from app.services.quality_dips_autonomous_authority_inspection import inspect_financial_authority_adapters
from app.services.quality_dips_autonomous_publication_port import BoundAutonomousFinancialPublication


def test_no_installed_operational_authorities_are_assumed():
    result = inspect_financial_authority_adapters()
    assert result['status'] == 'SOURCE_INSPECTION_NOT_ACCEPTANCE'
    assert result['startup_authorized'] is False
    assert result['operational_evidence_verified'] is False
    assert [x['role'] for x in result['ports']] == ['publication', 'custody_ack', 'financial_replay']
    assert all(not x['interface_present'] for x in result['ports'])


def test_method_names_do_not_prove_independent_authority():
    fake = SimpleNamespace(lease=lambda *a, **kw: None, verify=lambda *a, **kw: True)
    result = inspect_financial_authority_adapters(publication=fake, custody_ack=fake,
                                                   financial_replay=fake)
    assert all(x['interface_present'] for x in result['ports'])
    assert all(x['independent_authority_accepted'] is False for x in result['ports'])
    assert result['startup_authorized'] is False


def test_existing_native_reader_signatures_are_not_v4_lease_ports():
    import importlib.util
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    for name, path, cls in (
        ('qd_op_reader', 'operational_financial_read.py', 'NativeOperationalReadPort'),
        ('fs3_reader', 'financial_read_port.py', 'NativeFinancialReadPort'),
        ('v4_reader', 'autonomous_enrollment_read.py', 'BoundNativeEnrollmentEvidence'),
    ):
        spec = importlib.util.spec_from_file_location(name, repo / 'scripts/volume_inspector' / path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        reader = getattr(module, cls)
        assert not callable(getattr(reader, 'lease', None)), name
        assert not callable(getattr(reader, 'verify_cut', None)), name
