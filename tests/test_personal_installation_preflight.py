"""Native installation inventory is deliberately not an authorization oracle."""
from scripts.observation_runtime.personal_installation_preflight import inspect_native_personal_installation


def test_missing_parent_is_a_blocker(tmp_path):
    result = inspect_native_personal_installation(custody_parent=tmp_path / "missing")
    assert "CUSTODY_PARENT_MISSING" in result["blockers"]
    assert "PERSONAL_PARENT_MISSING" in result["blockers"]
    assert result["forward_financial_write_authorized"] is False


def test_parent_present_but_personal_missing(tmp_path):
    result = inspect_native_personal_installation(custody_parent=tmp_path)
    assert result["custody_parent_exists"] is True
    assert result["personal_parent_exists"] is False
    assert "PERSONAL_PARENT_MISSING" in result["blockers"]


def test_even_existing_personal_parent_never_proves_activation(tmp_path):
    (tmp_path / "PersonalPaper").mkdir()
    result = inspect_native_personal_installation(custody_parent=tmp_path)
    assert result["personal_parent_exists"] is True
    assert "PERSONAL_PARENT_MISSING" not in result["blockers"]
    assert "NATIVE_OPERATOR_ACTIVATION_UNVERIFIED" in result["blockers"]
    assert result["native_activation_record_verified"] is False
    assert result["operator_lease_verified"] is False
    assert result["forward_financial_write_authorized"] is False


def test_junction_custody_parent_is_not_trusted(tmp_path, monkeypatch):
    from pathlib import Path
    actual = Path.is_junction
    parent = tmp_path / "custody"
    (parent / "PersonalPaper").mkdir(parents=True)
    monkeypatch.setattr(Path, "is_junction", lambda self: self == parent or actual(self))
    result = inspect_native_personal_installation(custody_parent=parent)
    assert result["custody_parent_exists"] is False
    assert result["personal_parent_exists"] is False
    assert "CUSTODY_PARENT_MISSING" in result["blockers"]
    assert result["forward_financial_write_authorized"] is False

def test_junction_personal_parent_is_not_trusted(tmp_path, monkeypatch):
    from pathlib import Path
    actual = Path.is_junction
    personal = tmp_path / "PersonalPaper"
    personal.mkdir()
    monkeypatch.setattr(Path, "is_junction", lambda self: self == personal or actual(self))
    result = inspect_native_personal_installation(custody_parent=tmp_path)
    assert result["custody_parent_exists"] is True
    assert result["personal_parent_exists"] is False
    assert "PERSONAL_PARENT_MISSING" in result["blockers"]
    assert result["forward_financial_write_authorized"] is False
