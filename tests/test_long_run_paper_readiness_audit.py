from pathlib import Path
def test_long_run_audit_preserves_native_lifecycle_no_go():
    root=Path(__file__).resolve().parents[1]
    audit=(root/"docs/ATLAS_LONG_RUN_PAPER_READINESS_AUDIT.md").read_text(encoding="utf-8-sig")
    start=(root/"scripts/windows/Atlas-Launch.ps1").read_text(encoding="utf-8-sig")
    stop=(root/"scripts/windows/Atlas-Stop.ps1").read_text(encoding="utf-8-sig")
    assert "Status: NO-GO / NOT ACCEPTED" in audit
    assert "ATLAS_LEGACY_LIFECYCLE_BLOCKED" in start
    assert "ATLAS_LEGACY_LIFECYCLE_BLOCKED" in stop
    assert "Generate shareable PDF" in audit
    for gate in ("B1/C1/D1/E1","multi-week","Genesis","PAPER"):
        assert gate in audit
