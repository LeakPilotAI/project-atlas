from pathlib import Path

READY = Path("scripts/windows/Atlas-Ready.ps1")
LAUNCH = Path("scripts/windows/Atlas-Launch.ps1")

def _ready():
    return READY.read_text(encoding="utf-8")

def test_e122_readiness_requires_postgres_and_redis_health():
    text = _ready()
    assert "'atlas-postgres'" in text
    assert "'atlas-redis'" in text
    assert ".health -eq 'healthy'" in text
    assert "$allHealthy = $allHealthy -and $checks['atlas-postgres'] -and $checks['atlas-redis']" in text

def test_e122_readiness_container_probe_is_read_only():
    text = _ready().lower()
    assert "docker inspect" in text
    assert "docker start" not in text
    assert "docker stop" not in text
    assert "docker rm" not in text
    assert "docker compose up" not in text

def test_e122_readiness_artifact_records_container_and_last_check_context():
    text = _ready()
    assert "$result.last_checks = $checks" in text
    assert "$result.container_health = $containers" in text
    assert "ConvertTo-Json -Depth 6" in text
    assert "launcher-ready.json" in text

def test_e122_readiness_failure_has_actionable_non_mutating_recovery_guidance():
    text = _ready()
    assert "ATLAS-STOP.bat" in text
    assert "inspect logs and Docker Desktop" in text
    assert "This readiness check does not mutate runtime state." in text

def test_e122_launcher_no_longer_recommends_wrong_main_branch_pull():
    text = LAUNCH.read_text(encoding="utf-8")
    assert "git pull origin main" not in text
    assert "Pull-And-Ready.ps1 after closing Atlas" in text

def test_e122_existing_http_readiness_surfaces_remain_required():
    text = _ready()
    for path in ("/health", "/api/research", "/api/command-center/summary", "/diagnostics/paper-reconciliation"):
        assert path in text
    assert "required=3" in text
