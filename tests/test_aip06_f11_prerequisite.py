"""F11 source prerequisite is not a substitute for native load acceptance."""
from scripts.observation_runtime.aip06_acceptance_plan import schedule


def test_f11_readback_prerequisite_is_selected_without_false_acceptance():
    row = next(row for row in schedule() if row["id"] == "F11")
    assert row["prerequisite_case"] == (
        "tests/test_unified_source_capacity_native.py::"
        "test_native_store_capacity_readbacks_are_consistent_without_mocked_headroom")
    assert row["prerequisite_status"] == "SOURCE_CASE_IDENTIFIED_NATIVE_EXECUTION_PENDING"
    assert row["source_case"] is None
    assert row["status"] == "NATIVE_CASE_BINDING_PENDING"

def test_f11_real_write_prerequisite_does_not_complete_saturation():
    row = next(row for row in schedule() if row['id'] == 'F11')
    assert row['real_write_prerequisite_case'] == (
        'tests/test_unified_source_capacity_native.py::'
        'test_native_capacity_changes_after_real_disposable_orders_and_stops')
    assert row['real_write_prerequisite_status'] == 'SOURCE_CASE_IDENTIFIED_NATIVE_EXECUTION_PENDING'
    assert row['source_case'] is None


def test_f11_native_write_saturation_source_exists_but_remains_unbound():
    row = next(row for row in schedule() if row['id'] == 'F11')
    assert row['saturation_source_case'] == (
        'tests/test_unified_source_capacity_native.py::'
        'test_native_global_capacity_saturation_refuses_entry_and_preserves_stop')
    assert row['saturation_source_status'] == (
        'SOURCE_IMPLEMENTED_GUARDED_NATIVE_EXECUTION_PENDING')
    assert row['source_case'] is None
    assert row['status'] == 'NATIVE_CASE_BINDING_PENDING'
