from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_stop_batch_does_not_claim_financial_flatness():
    batch = (ROOT / "ATLAS-STOP.bat").read_text(encoding="utf-8").lower()
    assert "not yet connected to certified paper flattening" in batch
    assert "do not assume paper positions were closed" in batch
    assert "atlas is stopped" not in batch
    assert "if errorlevel 1" in batch
    assert "exit /b 1" in batch


def test_desktop_stop_batch_preserves_legacy_refusal_and_genesis():
    batch = (ROOT / "ATLAS-STOP.bat").read_text(encoding="utf-8").lower()
    assert "atlas-stop.ps1" in batch
    assert "genesis shutdown will be attempted" in batch
    assert "protected shutdown script returned success" in batch
