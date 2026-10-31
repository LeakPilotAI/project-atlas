"""Build a deterministic, explicitly inventoried source candidate without Git writes.

No runtime state, credentials, virtualenvs, backups or diagnostic sandboxes are
included. This is packaging/verification only, never deployment or activation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ROOTS = ("backend/app/", "scripts/", "tests/", "docs/", "frontend/offline/")
COMPANIONS = {"backend/app/static/vendor/lightweight-charts.LICENSE"}
EXTENSIONS = {".py", ".ps1", ".psm1", ".js", ".cjs", ".mjs", ".html", ".css", ".json", ".md"}

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).splitlines()

def source_path(root: Path, name: str) -> Path:
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
            or PurePosixPath(name).as_posix() != name
            or any(part.endswith(('.', ' ')) or any(ord(c)<32 or c in '<>"|?*' for c in part)
                or re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]',part.split('.')[0].rstrip(' .'),re.IGNORECASE)
                for part in name.split('/'))):
        raise ValueError(f"Unsafe source path: {name}")
    return root / name


def windows_namespace(names):
    """One unambiguous file/directory spelling under the Windows-local policy."""
    seen={}
    for name in names:
        source_path(Path('.'),name)
        parts=PurePosixPath(name).parts
        for length in range(1,len(parts)+1):
            path='/'.join(parts[:length]);role='file' if length==len(parts) else 'directory';key=path.casefold()
            if key in seen and seen[key]!=(path,role):raise ValueError('Windows namespace alias or file/directory conflict')
            seen[key]=path,role


def new_destination(destination):
    """Create only a new artifact child; never adopt or repair an existing root."""
    destination=Path(destination).absolute()
    for parent in destination.parents:
        if parent.exists() or parent.is_symlink():
            info=parent.lstat()
            if not stat.S_ISDIR(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('Unsafe artifact destination ancestor')
    destination.mkdir(parents=True,exist_ok=False)
    return destination


def source_bytes(root: Path, name: str, *, maximum_bytes: int | None = None) -> bytes:
    """Read one regular, singly linked source through its verified open handle.

    No administrator/same-account mutation exclusion or directory lock is claimed.
    Windows path/handle ctime representations are compared only within their own
    API; exact device/inode/type/link/size/mtime matching still precedes reads.
    Identity checks precede content access; concurrent in-place writes are detected
    when ordinary size/time/identity metadata changes, not cryptographically barred.
    """
    path = source_path(root, name)
    for parent in [root, *path.parents]:
        if parent == root or parent.is_relative_to(root):
            metadata = parent.lstat()
            if (not stat.S_ISDIR(metadata.st_mode)
                    or getattr(metadata, "st_file_attributes", 0) & 0x400):
                raise ValueError(f"Unsafe source identity: {name}")
    expected = path.lstat()
    if maximum_bytes is not None and expected.st_size > maximum_bytes:
        raise ValueError("Source exceeds explicit read bound")
    if (not stat.S_ISREG(expected.st_mode) or expected.st_nlink != 1
            or getattr(expected, "st_file_attributes", 0) & 0x400):
        raise ValueError(f"Unsafe source identity: {name}")
    def identity(value):
        return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
                value.st_size, value.st_mtime_ns)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if identity(opened) != identity(expected):
            fields = ("device", "inode", "mode", "links", "size", "mtime")
            changed = [field for field, a, b in zip(fields, identity(opened), identity(expected), strict=True) if a != b]
            raise ValueError(f"Source identity changed: {name} ({changed})")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            content = stream.read() if maximum_bytes is None else stream.read(maximum_bytes + 1)
            if maximum_bytes is not None and len(content) > maximum_bytes:
                raise ValueError("Source exceeds explicit read bound")
            if (identity(os.fstat(stream.fileno())) != identity(opened)
                    or os.fstat(stream.fileno()).st_ctime_ns != opened.st_ctime_ns):
                raise ValueError(f"Source identity changed: {name}")
        current = path.lstat()
        if identity(current) != identity(expected) or current.st_ctime_ns != expected.st_ctime_ns:
            raise ValueError(f"Source identity changed: {name}")
        return content
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def build(destination: Path) -> str:
    destination.mkdir(parents=True, exist_ok=False)
    tracked = set(git("ls-files"))
    untracked = set(git("ls-files", "--others", "--exclude-standard", *[x[:-1] for x in ROOTS]))
    extras = {p for p in untracked if p.startswith(ROOTS) and Path(p).suffix in EXTENSIONS}
    extras.update(COMPANIONS)
    extras.add("scripts/build_release_candidate.py")
    selected = sorted(tracked | extras)
    windows_namespace(selected)
    for name in selected:
        source_path(ROOT, name)
    entries = []
    contents = {}
    for name in selected:
        path = source_path(ROOT, name)
        if not path.is_file():
            raise ValueError(f"Required candidate file missing: {name}")
        if (path.name == ".env" or "data" in path.relative_to(ROOT).parts
                or "__pycache__" in path.parts or path.suffix == ".bak"):
            raise ValueError(f"Unsafe release input: {name}")
        content = source_bytes(ROOT, name)
        contents[name] = content
        entries.append({"path": name, "sha256": hashlib.sha256(content).hexdigest(),
                        "bytes": len(content), "git_status": "tracked" if name in tracked else "untracked",
                        "role": "runtime" if name.startswith(("backend/app/", "scripts/windows/", "deploy/")) else "support"})
    manifest = {"contract": "R7E46O_SOURCE_V1", "branch": git("branch", "--show-current")[0],
                "head": git("rev-parse", "HEAD")[0], "activation_approved": False, "files": entries}
    return _write_candidate(destination,manifest,contents)


def _write_candidate(destination,manifest,contents):
    contents["release-manifest.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    packages = sorted({f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()})
    contents["requirements-observed.txt"] = ("\n".join(packages) + "\n").encode()
    output = destination / "atlas-source.zip"
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(contents.items()):
            item = zipfile.ZipInfo(name, date_time=(2026, 10, 16, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, content)
    (destination / "release-manifest.json").write_bytes(contents["release-manifest.json"])
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    (destination / "archive.sha256").write_text(digest + "\n", encoding="ascii")
    return digest


def build_selected(destination: Path, *, selection: dict, expected_inventory_sha256: str) -> str:
    """Package an explicit reviewed subset; no untracked input or deployment.

    Hashes bind the supplied selection, not operator/security approval. The
    original broad source-review build remains separately supported.
    """
    if (type(selection) is not dict or set(selection)!={'schema','source_commit','inventory_digest','files'}
            or selection['schema']!='ATLAS_SOURCE_SELECTION_V1'
            or type(expected_inventory_sha256) is not str or not re.fullmatch('[0-9a-f]{64}',expected_inventory_sha256)
            or type(selection['source_commit']) is not str or not re.fullmatch('[0-9a-f]{40}',selection['source_commit'])
            or type(selection['files']) is not list or not 0<len(selection['files'])<=2048):
        raise ValueError('Explicit bounded source selection required')
    selection=dict(selection)
    rows=selection['files']
    encoded=json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if (len(encoded)>1024*1024 or hashlib.sha256(encoded).hexdigest()!=expected_inventory_sha256
            or selection['inventory_digest']!=expected_inventory_sha256):raise ValueError('Selected inventory digest mismatch')
    rows=json.loads(encoded)  # Freeze caller-owned rows before reading sources.
    if git('rev-parse','HEAD')!=[selection['source_commit']]:raise ValueError('Selected source commit mismatch')
    tracked=set(git('ls-files'));names=[];total=0
    for row in rows:
        if (type(row) is not dict or set(row)!={'path','bytes','sha256'} or type(row['path']) is not str
                or type(row['bytes']) is not int or not 0<=row['bytes']<=16*1024*1024
                or type(row['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',row['sha256'])):
            raise ValueError('Invalid selected source entry')
        name=row['path'];source_path(ROOT,name)
        if (name not in tracked or name in names or not name.startswith(ROOTS)
                or any(part in ('data','__pycache__') for part in PurePosixPath(name).parts)
                or Path(name).name=='.env' or Path(name).suffix=='.bak'):
            raise ValueError('Selected source must be explicit safe tracked input')
        total+=row['bytes'];names.append(name)
    if total>128*1024*1024 or names!=sorted(names):raise ValueError('Selected inventory order or capacity')
    windows_namespace([*names,'release-manifest.json','requirements-observed.txt'])
    # Selected runtime equality, not a blanket clean-tree waiver. Unrelated
    # edits remain untouched and are neither packaged nor silently committed.
    for offset in range(0,len(names),64):
        if git('diff','--name-only','HEAD','--',*names[offset:offset+64]):
            raise ValueError('Uncommitted selected source refused')
    contents={};entries=[]
    for row in rows:
        content=source_bytes(ROOT,row['path'],maximum_bytes=row['bytes'])
        if len(content)!=row['bytes'] or hashlib.sha256(content).hexdigest()!=row['sha256']:
            raise ValueError('Selected source contents changed')
        contents[row['path']]=content
        entries.append({**row,'git_status':'tracked','role':'runtime' if row['path'].startswith(
            ('backend/app/','scripts/windows/','scripts/observation_runtime/','scripts/volume_inspector/')) else 'support'})
    if git('rev-parse','HEAD')!=[selection['source_commit']]:raise ValueError('Selected source changed during build')
    manifest={'contract':'R7E46O_SOURCE_V1','branch':git('branch','--show-current')[0],
        'head':selection['source_commit'],'activation_approved':False,'files':entries}
    destination=new_destination(destination)
    pin=_write_candidate(destination,manifest,contents)
    verify_candidate(destination/'atlas-source.zip',expected_sha256=pin)
    return pin

def verify_candidate(archive: Path, *, expected_sha256: str) -> dict:
    """Bounded supplied-byte consistency only; no extraction, execution or trust grant."""
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Explicit retained archive SHA256 required")
    archive = Path(archive).absolute()
    raw = source_bytes(archive.parent, archive.name, maximum_bytes=64 * 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Archive SHA256 mismatch")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate manifest JSON key")
            result[key] = value
        return result
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        members = bundle.infolist()
        if not 2 <= len(members) <= 5000:
            raise ValueError("Bounded archive member count required")
        windows_namespace([m.filename for m in members])
        seen = set()
        total = 0
        for member in members:
            source_path(Path("."), member.filename)
            if member.filename in seen or member.is_dir() or member.flag_bits & 1:
                raise ValueError("Duplicate/directory/encrypted archive member refused")
            mode = member.external_attr >> 16
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise ValueError("Non-regular archive member refused")
            if member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                raise ValueError("Unsupported archive compression")
            if member.file_size > 16 * 1024 * 1024:
                raise ValueError("Archive entry exceeds bound")
            total += member.file_size
            if total > 128 * 1024 * 1024:
                raise ValueError("Decoded archive exceeds bound")
            seen.add(member.filename)
        if "release-manifest.json" not in seen or "requirements-observed.txt" not in seen:
            raise ValueError("Required archive companions missing")
        if bundle.getinfo("release-manifest.json").file_size > 1024 * 1024:
            raise ValueError("Manifest exceeds bound")
        manifest = json.loads(bundle.read("release-manifest.json"), object_pairs_hook=unique_object)
        if (type(manifest) is not dict or set(manifest) != {"contract", "branch", "head", "activation_approved", "files"}
                or manifest["contract"] != "R7E46O_SOURCE_V1" or manifest["activation_approved"] is not False
                or any(not isinstance(manifest[k], str) or not manifest[k].strip() for k in ("branch", "head"))
                or type(manifest["files"]) is not list):
            raise ValueError("Invalid non-activating source manifest")
        declared = {"release-manifest.json", "requirements-observed.txt"}
        for entry in manifest["files"]:
            if (type(entry) is not dict or set(entry) != {"path", "sha256", "bytes", "git_status", "role"}
                    or type(entry["path"]) is not str or entry["path"] in declared
                    or type(entry["bytes"]) is not int or not 0 <= entry["bytes"] <= 16 * 1024 * 1024
                    or not isinstance(entry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
                    or entry["git_status"] not in ("tracked", "untracked") or entry["role"] not in ("runtime", "support")):
                raise ValueError("Invalid or duplicate source declaration")
            source_path(Path("."), entry["path"])
            if entry["path"] not in seen or bundle.getinfo(entry["path"]).file_size != entry["bytes"]:
                raise ValueError("Missing source or length mismatch")
            content = bundle.read(entry["path"])
            if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                raise ValueError("Source hash mismatch")
            declared.add(entry["path"])
        if seen != declared:
            raise ValueError("Undeclared archive members")
        # Read the bounded observed-dependency companion too, validating its ZIP CRC.
        bundle.read("requirements-observed.txt")
    return {"schema": "ATLAS_SOURCE_CANDIDATE_VERIFICATION_V1", "archive_sha256": expected_sha256,
            "source_files": len(manifest["files"]), "supplied_bytes_consistent": True,
            "source_authenticated": False, "installation_verified": False, "activation_approved": False}


def verify_staged_candidate(stage: Path, archive: Path, *, expected_sha256: str) -> dict:
    """Read-only portable staging consistency, never native installed acceptance.

    No extraction/repair, release selection, process execution or ACL operation.
    A partial staging tree remains evidence and never triggers a blind retry.
    """
    verified=verify_candidate(archive,expected_sha256=expected_sha256)
    archive=Path(archive).absolute()
    raw=source_bytes(archive.parent,archive.name,maximum_bytes=64*1024*1024)
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('Archive changed before stage verification')
    stage=Path(stage).absolute()
    for parent in (stage,*stage.parents):
        info=parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('Unsafe staged directory')
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        expected_files=set(bundle.namelist());expected_dirs={'.'}
        for name in expected_files:
            expected_dirs.update(str(p) for p in PurePosixPath(name).parents)
        files=set();directories={'.'};count=0;total=0
        for parent,dirs,names in os.walk(stage,followlinks=False):
            for leaf in dirs+names:
                path=Path(parent)/leaf;relative=path.relative_to(stage).as_posix();source_path(stage,relative)
                info=path.lstat();count+=1
                if count>8192 or getattr(info,'st_file_attributes',0)&0x400:
                    raise ValueError('Staged namespace or capacity refused')
                if stat.S_ISDIR(info.st_mode):
                    if relative not in expected_dirs:raise ValueError('Unexpected staged directory')
                    directories.add(relative)
                elif stat.S_ISREG(info.st_mode):
                    if relative not in expected_files:raise ValueError('Unexpected staged file')
                    maximum=bundle.getinfo(relative).file_size
                    content=source_bytes(stage,relative,maximum_bytes=maximum)
                    if content!=bundle.read(relative):raise ValueError('Staged file content mismatch')
                    total+=len(content);files.add(relative)
                    if total>128*1024*1024:raise ValueError('Staged byte capacity')
                else:raise ValueError('Staged nonregular file')
        if files!=expected_files or directories!=expected_dirs:raise ValueError('Incomplete staged source tree')
    return {**verified,'schema':'ATLAS_SOURCE_STAGE_CONSISTENCY_V1','source_stage_consistent':True,
        'staged_files':len(files),'staged_bytes':total,'native_identity_acl_verified':False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, nargs="?", help="New source-candidate output directory")
    parser.add_argument("--verify", type=Path, metavar="ARCHIVE", help="Verify an existing archive without extracting")
    parser.add_argument("--expected-sha256", metavar="SHA256", help="Separately retained lowercase archive SHA256")
    parser.add_argument('--selection',type=Path,help='Explicit tracked-only source selection JSON; no deployment')
    parser.add_argument('--expected-inventory-sha256',help='Separately retained selected file-list SHA256')
    args = parser.parse_args(argv)
    if (args.destination is None) == (args.verify is None):
        parser.error("Choose exactly one build destination or --verify archive")
    if args.verify is None and args.expected_sha256 is not None:
        parser.error("--expected-sha256 requires --verify")
    if args.verify is not None and (args.expected_sha256 is None or not re.fullmatch(r"[0-9a-f]{64}", args.expected_sha256)):
        parser.error("--verify requires an explicit lowercase --expected-sha256")
    if ((args.selection is None)!=(args.expected_inventory_sha256 is None)
            or args.selection is not None and args.verify is not None
            or args.expected_inventory_sha256 is not None and not re.fullmatch('[0-9a-f]{64}',args.expected_inventory_sha256)):
        parser.error('Selection requires build destination and explicit lowercase inventory SHA256')
    try:
        if args.verify is not None:
            print(json.dumps(verify_candidate(args.verify, expected_sha256=args.expected_sha256), sort_keys=True))
        elif args.selection is not None:
            selection_path=args.selection.absolute()
            def selected_object(pairs):
                value={}
                for key,item in pairs:
                    if key in value:raise ValueError('Duplicate selection JSON key')
                    value[key]=item
                return value
            selection=json.loads(source_bytes(selection_path.parent,selection_path.name,maximum_bytes=1024*1024),object_pairs_hook=selected_object)
            print(build_selected(args.destination,selection=selection,expected_inventory_sha256=args.expected_inventory_sha256))
        else:
            print(build(args.destination))
    except (ValueError, OSError, zipfile.BadZipFile, EOFError, zlib.error) as error:
        print(json.dumps({"schema": "ATLAS_SOURCE_CANDIDATE_REFUSAL_V1", "status": "REFUSED",
                          "operation": "VERIFY" if args.verify is not None else "BUILD",
                          "error_type": type(error).__name__, "activation_approved": False}, sort_keys=True), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
