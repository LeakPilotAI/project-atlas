import json
from pathlib import Path

PACKAGE=Path("frontend/package.json")
LOCK=Path("frontend/package-lock.json")

def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def test_e119_next_is_patched_without_react_change():
    package=_json(PACKAGE)
    assert package["dependencies"]["next"] == "16.4.0"
    assert package["dependencies"]["react"] == "19.2.4"
    assert package["dependencies"]["react-dom"] == "19.2.4"

def test_e119_eslint_config_tracks_next_release():
    package=_json(PACKAGE)
    assert package["devDependencies"]["eslint-config-next"] == "16.4.0"

def test_e119_lock_matches_patched_next():
    lock=_json(LOCK)
    root=lock["packages"][""]
    assert root["dependencies"]["next"] == "16.4.0"
    assert lock["packages"]["node_modules/next"]["version"] == "16.4.0"

def test_e119_vulnerable_production_transitives_are_patched():
    lock=_json(LOCK)
    assert lock["packages"]["node_modules/nanoid"]["version"] >= "3.3.18"
    assert lock["packages"]["node_modules/source-map-js"]["version"] >= "1.2.2"
    assert lock["packages"]["node_modules/sharp"]["version"] >= "0.35.5"

def test_e119_framework_remains_runtime_dependency():
    package=_json(PACKAGE)
    assert "next" in package["dependencies"]
    assert "next" not in package["devDependencies"]
