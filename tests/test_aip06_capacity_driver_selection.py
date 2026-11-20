"""Offline driver source-selection regression; no guarded native launch."""
import ast
from pathlib import Path


def test_native_capacity_module_is_explicitly_selected_for_async_plugin():
    path = Path(__file__).parents[1] / "scripts/observation_runtime/aip06_test_driver.py"
    tree = ast.parse(path.read_text(encoding="utf8"))
    selection = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == "SELECTION"
                             for target in node.targets))
    selected = ast.literal_eval(selection)
    assert selected["tests/test_unified_source_capacity_native.py"] == "P"
    driver = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "run_reviewed_tests")
    source = ast.get_source_segment(path.read_text(encoding="utf8"), driver)
    assert '"tests/test_unified_source_capacity_native.py"' in source
    assert '"pytest_asyncio.plugin"' in source
    assert "require_fixture(\"native-pytest-driver\")" in source
