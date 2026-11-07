"""Explicit source-only support packaging. Never creates an operational path."""
import copy
import json
import zipfile
from pathlib import Path

from scripts.build_release_candidate import source_bytes
from scripts.release_selection import encoded
from scripts.support_deployment import (
    APP,
    EXCLUSIONS,
    LIMITS,
    SOURCES,
    sha,
    validate_manifest,
)


def build(*, output, historical_manifest, application, domain="WINDOWS_LOCAL", fixture=None, accepted_parents=None):
    output = Path(output).absolute(); repo = Path(__file__).resolve().parents[1]
    if (not output.is_relative_to(repo / "logs/diagnostics") or output.exists()
            or any(p.is_symlink() or p.is_junction() for p in (output.parent, *output.parents))):
        raise ValueError("EXACT_NEW_SUPPORT_PACKAGE_OUTPUT_REQUIRED")
    old = json.loads(Path(historical_manifest).read_bytes())
    payload = {name: source_bytes(repo, name, maximum_bytes=262144).replace(b'\r\n', b'\n') for name in sorted(SOURCES)}
    package = copy.deepcopy(old)
    package.update(schema="QD_NONFINANCIAL_LAUNCHER_SUPPORT_V2", source_base_commit="fdfb9a7fd9c63f067f37e5fdd39784dac5d09b1e",
                   support_sources=[{"path": n, "bytes": len(raw), "sha256": sha(raw)} for n, raw in payload.items()],
                   missing_from_frozen_application=sorted(SOURCES))
    app=APP if accepted_parents is None else application['release']
    package['application_release']=app
    if accepted_parents is not None:
        import re
        if (type(app) is not str or not re.fullmatch('[0-9a-f]{40}',app)
                or Path(application['receipt']) != repo/'logs/diagnostics'/('qd-unselected-release-'+app+'.json')):
            raise ValueError('EXACT_RECOVERY_APPLICATION_RECEIPT_REQUIRED')
        receipt_path=Path(application['receipt'])
        raw=source_bytes(receipt_path.parent,receipt_path.name,maximum_bytes=8*1024**2)
        receipt=json.loads(raw)
        if (sha(raw)!=application['receipt_sha256'] or receipt['source_commit']!=app
                or receipt['release_path']!=application['root'] or receipt['artifact_digest']!=application['artifact_digest']):
            raise ValueError('RECOVERY_APPLICATION_RECEIPT_PIN_MISMATCH')
        actual={r['path'].replace('\\','/'):r['sha256'] for r in receipt['files']}
        required=package['required_installed_application_sources']
        if any(r['path'] not in actual for r in required):
            raise ValueError('RECOVERY_INSTALLED_APPLICATION_DEPENDENCY_MISSING')
        package['required_installed_application_sources']=[{'path':r['path'],'sha256':actual[r['path']]} for r in required]
        package['application_archive_sha256']=receipt['archive_sha256']
        package['missing_from_frozen_application']=sorted(n for n,data in payload.items() if actual.get(n)!=sha(data))
    # Historical source-only authority flags deliberately remain false.
    payload["support-manifest.json"] = encoded(package)
    h = sha(payload["support-manifest.json"])
    base = Path("D:/AtlasRuntime") if domain == "WINDOWS_LOCAL" else Path(fixture)
    output.mkdir()
    archive = output / "support-source.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for name, raw in sorted(payload.items()):
            item = zipfile.ZipInfo(name, date_time=(2026, 10, 31, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED; item.external_attr = 0o100600 << 16
            z.writestr(item, raw)
    manifest = {"schema": "QD_SUPPORT_DEPLOYMENT_V1" if accepted_parents is None else 'QD_SUPPORT_DEPLOYMENT_V2', "domain": domain, "status": "REVIEW_INVENTORY_NOT_PERMISSION",
                "support_manifest_sha256": h, "archive_sha256": sha(archive.read_bytes()),
                "destination": str(base / "launchers" / h), "control": str(base / "support-installations" / h),
                "selection": str(base / "selection"), "new_parents": [str(base / "launchers"), str(base / "support-installations")],
                "files": [{"path": n, "bytes": len(v), "sha256": sha(v)} for n, v in sorted(payload.items())],
                "directories": sorted({"."} | {p.as_posix() for n in payload for p in Path(n).parents}),
                "application": application, "limits": LIMITS, "exclusions": EXCLUSIONS,
                "runtime": {"python": str(base / "releases" / app / "python/python.exe"), "version": [3, 12], "bits": 64,
                            "app_receipt_inventory": True, "providers": False, "financial_writers": False, "workspace_fallback": False},
                "receipt_schema": "QD_SUPPORT_INSTALL_RECEIPT_V1"}
    if accepted_parents is not None:manifest['accepted_parents']=copy.deepcopy(accepted_parents)
    validate_manifest(manifest)
    (output / "deployment.json").write_bytes(encoded(manifest))
    return {"manifest": manifest, "manifest_sha256": sha(encoded(manifest)), "archive": archive, "support": package}
