"""Exercise the mandatory updater on temporary roadmaps, never the real roadmap."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts/windows/Atlas-Roadmap-Checkpoint.ps1"
STRATEGY = "ATLAS PERMANENT FUTURE STRATEGY V1 - MARKET INTELLIGENCE OS"
RECOVERY = "ATLAS PERMANENT EXECUTION AND CONVERSATION RECOVERY CONTRACT V1"


def update(roadmap, checkpoint):
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(UPDATER), "-RoadmapPath", str(roadmap), "-CheckpointFile", str(checkpoint)],
        capture_output=True, text=True, timeout=20, check=False,
    )


def test_updater_preserves_history_and_replaces_only_managed_checkpoint(tmp_path):
    roadmap = tmp_path / "roadmap.txt"
    original = f"{STRATEGY}\n{RECOVERY}\nPhase 1–7 historical evidence retained\n"
    roadmap.write_text(original, encoding="utf-8")
    checkpoint = tmp_path / "checkpoint.txt"
    for milestone in ("FIRST", "R7E46M"):
        checkpoint.write_text(
            f"Milestone: {milestone}\nStatus: ISOLATED\nEvidence: fixtures\nNext action: no activation",
            encoding="utf-8",
        )
        result = update(roadmap, checkpoint)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "ATLAS ROADMAP CHECKPOINT VERIFIED" in result.stdout
    updated = roadmap.read_text(encoding="utf-8")
    assert updated.startswith(original.rstrip())
    assert "Milestone: R7E46M" in updated and "Milestone: FIRST" not in updated
    assert len(list(tmp_path.glob("roadmap.txt.checkpoint-*.bak"))) == 2


@pytest.mark.parametrize("content", ["", "Milestone: incomplete",
    "Milestone: M\nStatus: X\nEvidence: X\nNext action: X\n=== ATLAS MANAGED CURRENT CHECKPOINT V1 ==="])
def test_invalid_checkpoint_cannot_modify_history(tmp_path, content):
    roadmap = tmp_path / "roadmap.txt"
    roadmap.write_text(f"{STRATEGY}\n{RECOVERY}\nretain", encoding="utf-8")
    original = roadmap.read_bytes()
    checkpoint = tmp_path / "checkpoint.txt"
    checkpoint.write_text(content, encoding="utf-8")
    result = update(roadmap, checkpoint)
    assert result.returncode != 0
    assert roadmap.read_bytes() == original


@pytest.mark.parametrize("size,accepted", [(31000, True), (60001, False)])
def test_bounded_checkpoint_history_capacity(tmp_path, size, accepted):
    roadmap = tmp_path / "roadmap.txt"
    prefix_bytes = f"{STRATEGY}\n{RECOVERY}\nretain historical bytes\n".encode()
    original = (prefix_bytes + b"=== ATLAS MANAGED CURRENT CHECKPOINT V1 ===\nold\n"
                b"=== END ATLAS MANAGED CURRENT CHECKPOINT V1 ===\nretained suffix\n")
    roadmap.write_bytes(original)
    checkpoint = tmp_path / "checkpoint.txt"
    prefix = "Milestone: recovery\nStatus: offline\nEvidence: fixtures\nNext action: independent review\n"
    checkpoint.write_text(prefix + "x" * (size - len(prefix)), encoding="utf-8")
    result = update(roadmap, checkpoint)
    assert (result.returncode == 0) == accepted, result.stdout + result.stderr
    if accepted:
        assert roadmap.read_bytes().startswith(prefix_bytes)
        assert roadmap.read_bytes().endswith(b"\nretained suffix\n")
        assert next(tmp_path.glob("roadmap.txt.checkpoint-*.bak")).read_bytes() == original
    else:
        assert roadmap.read_bytes() == original
