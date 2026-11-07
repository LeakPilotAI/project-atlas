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