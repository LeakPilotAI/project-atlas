"""Explicit synthetic authority models; never operational enrollment/approval."""

import copy
import importlib.util
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.paper_financial_replay import body, digest
from test_quality_dips_operational_contract import fixture as schema_fixture

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "enrollment_bootstrap",
    ROOT / "scripts/observation_runtime/quality_dips_enrollment_bootstrap.py",
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def setup():
    x = schema_fixture()
    n = SimpleNamespace(
        x=x,
        now=100,
        approved=True,
        pinned=True,
        read_accepted=True,
        read_calls=0,
        phase="UNPUBLISHED",
    )
    snapshot = x.cap.read_committed("synthetic-account", "synthetic-epoch")

    def readback():
        n.read_calls += 1
        return copy.deepcopy(snapshot)

    def admitted(action):
        if not n.read_accepted:
            raise ValueError("READ_SERVICE_NOT_ACCEPTED")
        return action()

    n.composition = SimpleNamespace(
        operational=True,
        enrollment=copy.deepcopy(x.e),
        preflight=readback,
        admitted=admitted,
    )

    @contextmanager
    def issuer(scope, now):
        yield SimpleNamespace(
            check=lambda value, t: (
                n.approved and body(value) == body(n.scope) and 100 <= t <= 130
            )
        )

    @contextmanager
    def publication(scope, now):
        assert body(scope) == body(n.scope)
        witness = copy.deepcopy(n.witness)
        yield SimpleNamespace(
            snapshot=witness,
            check=lambda value, t: n.pinned and body(value) == body(n.witness),
        )

    n.issuer, n.publication = (
        SimpleNamespace(lease=issuer),
        SimpleNamespace(lease=publication),
    )
    n.args = {
        "enrollment": x.e,
        "release": {
            "schema": "QD_OP_ENROLLMENT_RELEASE_V1",
            "sha256": "e" * 64,
            "executable": "D:\\Synthetic\\python.exe",
        },
        "issuer": n.issuer,
        "publication": n.publication,
        "clock": lambda: n.now,
        "composition": n.composition,
    }
    n.bootstrap = m.EnrollmentBootstrap(**n.args)
    n.scope = n.bootstrap._scope()
    n.witness = {
        "schema": "QD_OP_PUBLICATION_WITNESS_V1",
        "intent_digest": digest(n.scope),
        "operation_id": n.scope["operation_id"],
        "state": "UNPUBLISHED",
        "ack_id": None,
        "current_digest": None,
        "resources_digest": n.scope["resources_digest"],
        "acknowledged_at": None,
    }
    n.snapshot = snapshot
    return n


def acknowledge(n):
    n.witness.update(
        state="ACKNOWLEDGED",
        ack_id="SYNTHETIC_NOT_AUTHORITY",
        current_digest=digest(n.x.b["current"]),
        acknowledged_at=100,
    )


def test_intent_is_stable_readonly_and_performs_no_publication():
    n = setup()
    before = body(n.witness)
    a = n.bootstrap.prepare()
    b = m.EnrollmentBootstrap(**n.args).prepare()
    assert a == b and a["capabilities"] == ["READ_ONLY"] and n.read_calls == 0
    assert body(n.witness) == before and a["operation_id"].startswith("qd-enrollment:")
    assert not any(
        hasattr(n.bootstrap, name)
        for name in ("publish", "write", "initialize", "repair", "recover", "start")
    )


@pytest.mark.parametrize(
    "field", ["enrollment", "release", "issuer", "publication", "clock", "composition"]
)
def test_missing_dependencies_fail_before_read(field):
    n = setup()
    args = {**n.args, field: None}
    with pytest.raises(ValueError):
        m.EnrollmentBootstrap(**args)
    assert n.read_calls == 0


@pytest.mark.parametrize("phase", ["PENDING", "UNKNOWN", "FAILED", "ACKNOWLEDGED"])
def test_no_replay_from_nonnew_publication(phase):
    n = setup()
    if phase == "ACKNOWLEDGED":
        acknowledge(n)
    else:
        n.witness["state"] = phase
    with pytest.raises(ValueError, match="NO_PUBLICATION_REPLAY"):
        n.bootstrap.prepare()
    assert n.read_calls == 0


@pytest.mark.parametrize("phase", ["UNPUBLISHED", "PENDING", "UNKNOWN", "FAILED"])
def test_no_read_or_launch_for_incomplete_publication(phase):
    n = setup()
    n.witness["state"] = phase
    with pytest.raises(ValueError, match="INCOMPLETE_OR_UNKNOWN"):
        n.bootstrap.launch_plan()
    assert n.read_calls == 0


def test_durable_ack_readback_idempotent_no_reenrollment():
    n = setup()
    acknowledge(n)
    first = n.bootstrap.verify_publication()
    assert m.EnrollmentBootstrap(**n.args).verify_publication() == first
    plan = n.bootstrap.launch_plan()
    assert plan["capabilities"] == ["READ_ONLY"] and plan["expires_at"] == 130
    assert (
        first["commands_enabled"] is False
        and first["operational_startup_authorized"] is False
    )
    with pytest.raises(ValueError):
        n.bootstrap.prepare()


@pytest.mark.parametrize(
    "damage",
    [
        "issuer",
        "custody",
        "clock",
        "account",
        "resource",
        "rollback",
        "ack",
        "future",
        "scope",
        "test_schema",
    ],
)
def test_unaccepted_or_corrupt_evidence_refuses(damage):
    n = setup()
    acknowledge(n)
    if damage == "issuer":
        n.approved = False
    if damage == "custody":
        n.pinned = False
    if damage == "clock":
        n.now = 131
    if damage == "account":
        n.snapshot["account_id"] = "foreign"
    if damage == "resource":
        n.snapshot["source_identity"]["pin_digest"] = "d" * 64
    if damage == "rollback":
        n.witness["current_digest"] = "f" * 64
    if damage == "ack":
        n.witness["ack_id"] = None
    if damage == "future":
        n.witness["acknowledged_at"] = 101
    if damage == "scope":
        n.witness["resources_digest"] = "f" * 64
    if damage == "test_schema":
        n.witness["schema"] = "FS2_TEST_PIN_V1"
    if damage in ("account", "resource"):
        n.composition.preflight = lambda: copy.deepcopy(n.snapshot)
    with pytest.raises((ValueError, TypeError)):
        n.bootstrap.launch_plan()


def test_wrong_enrolled_resource_scope_refuses():
    n = setup()
    wrong = copy.deepcopy(n.x.e)
    wrong["resources"]["source"]["native_root"] = [1, 2, 999]
    with pytest.raises(ValueError, match="COMPOSITION_REQUIRED"):
        m.EnrollmentBootstrap(**{**n.args, "enrollment": wrong})


@pytest.mark.parametrize(
    "damage",
    ["existing_positions", "nonzero_revision", "cash", "issuer_lost", "clock_back"],
)
def test_readback_or_authority_loss_never_acknowledges(damage):
    n = setup()
    acknowledge(n)
    if damage == "existing_positions":
        n.snapshot["state"]["positions"] = {"legacy": {}}
    if damage == "nonzero_revision":
        n.snapshot["source_revision"] = 1
    if damage == "cash":
        n.snapshot["state"]["cash"] = "999"

    def read():
        if damage == "issuer_lost":
            n.approved = False
        if damage == "clock_back":
            n.now = 99
        return copy.deepcopy(n.snapshot)

    n.composition.preflight = read
    with pytest.raises(ValueError):
        n.bootstrap.verify_publication()


@pytest.mark.parametrize("phase", ["PENDING", "UNKNOWN", "ACKNOWLEDGED"])
def test_test_witness_survives_abrupt_child_and_bootstrap_restart(tmp_path, phase):
    # Disposable control receipt only; no financial records or production issuer.
    n = setup()
    file = tmp_path / "synthetic-witness.json"
    code = "import os,sys;f=open(sys.argv[1],'w');f.write(sys.argv[2]);f.flush();os.fsync(f.fileno());os._exit(71)"
    acknowledge(n)
    n.witness["state"] = phase
    result = subprocess.run(
        [sys.executable, "-c", code, str(file), json.dumps(n.witness)],
        check=False,
        timeout=15,
    )
    assert result.returncode == 71
    n.witness = json.loads(
        file.read_text()
    )  # Test-authority model only, not enrollment.
    restarted = m.EnrollmentBootstrap(**n.args)
    if phase == "ACKNOWLEDGED":
        assert restarted.verify_publication()["source_revision"] == 0
    else:
        with pytest.raises(ValueError):
            restarted.verify_publication()
    with pytest.raises(ValueError):
        restarted.prepare()


def test_existing_desktop_and_new_cli_still_refuse(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "backend")
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "scripts/observation_runtime/quality_dips_enrollment_bootstrap.py"
            ),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode != 0 and "REFUSED" in result.stderr
    module = (ROOT / "scripts/windows/Atlas-SelectedPaper-ReadOnly.psm1").read_text()
    assert "SELECTED_READ_NOT_ENROLLED" in module
    assert (
        "AcceptedSelectedReadBridge = $null"
        in (ROOT / "scripts/windows/Atlas-Background-Controls.ps1").read_text()
    )


@pytest.mark.skipif(os.name != "nt", reason="NOT EXECUTED: Windows PowerShell required")
@pytest.mark.parametrize("damage", ["missing", "authority", "stale", "default"])
def test_windows_launcher_refuses_before_factory(tmp_path, damage):
    script = tmp_path / "test.ps1"
    plan = {
        "schema": "QD_OP_ENROLLED_LAUNCH_PLAN_V1",
        "operation_id": "qd-enrollment:" + "a" * 64,
        "account_id": "synthetic-account",
        "epoch": "synthetic-epoch",
        "enrollment_digest": "b" * 64,
        "policy_digest": "c" * 64,
        "release_digest": "d" * 64,
        "publication_digest": "e" * 64,
        "executable": "D:\\Synthetic\\python.exe",
        "issued_at": 100,
        "expires_at": 130,
        "capabilities": ["READ_ONLY"],
    }
    source = f"""$ErrorActionPreference='Stop'
$launcher='{(ROOT / "scripts/windows/Atlas-SelectedPaper-EnrolledLauncher.ps1").as_posix()}'
$script:calls=0
try{{
if('{damage}' -eq 'default'){{& $launcher}}else{{
. $launcher -SourceLoadOnly
$p='{json.dumps(plan)}'|ConvertFrom-Json
$clock={{100}};if('{damage}' -eq 'stale'){{$clock={{131}}}}
$authorize={{param($phase,$plan,$context,$now) $false}}
if('{damage}' -eq 'missing'){{New-AtlasEnrolledReadBridge}}else{{New-AtlasEnrolledReadBridge -AcceptedPlan $p -TrustedClock $clock -Authorize $authorize -AcceptedChildFactory {{$script:calls++;throw 'FACTORY_CALLED'}}}}
}}
throw 'DID_NOT_REFUSE'
}}catch{{if($_.Exception.Message -match 'FACTORY_CALLED|DID_NOT_REFUSE'){{throw}}}}
if($script:calls -ne 0){{throw 'FACTORY_CALLED'}}
Write-Output 'REFUSED_BEFORE_FACTORY'
"""
    script.write_text(source)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-File", str(script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "REFUSED_BEFORE_FACTORY" in result.stdout


def test_read_service_acceptance_needed_even_for_intent():
    n = setup()
    n.read_accepted = False
    with pytest.raises(ValueError, match="READ_SERVICE"):
        n.bootstrap.prepare()
    assert n.read_calls == 0


def test_release_change_does_not_create_new_enrollment_identity():
    n = setup()
    release = {**n.args["release"], "sha256": "f" * 64}
    different = m.EnrollmentBootstrap(**{**n.args, "release": release})
    assert different._scope()["operation_id"] == n.scope["operation_id"]
    assert digest(different._scope()) != digest(n.scope)
    with pytest.raises(ValueError, match="ISSUER"):
        different.prepare()


def test_alternate_stream_executable_refused():
    n = setup()
    with pytest.raises(ValueError):
        m.EnrollmentBootstrap(
            **{
                **n.args,
                "release": {
                    **n.args["release"],
                    "executable": "D:\\Synthetic\\python.exe:other.exe",
                },
            }
        )


@pytest.mark.skipif(os.name != "nt", reason="NOT EXECUTED: Windows required")
@pytest.mark.parametrize("mode", ["ok", "retain_refused", "identity_refused"])
def test_enrolled_launcher_retains_exact_child_and_gracefully_closes(tmp_path, mode):
    # Protocol-only child. No financial files, HTTP, provider or worker startup.
    child = tmp_path / "owned.py"
    child.write_text(
        "import sys,json\nfor line in sys.stdin:\n r=json.loads(line)\n assert r['action']=='CLOSE'\n print(json.dumps({'schema':'QD_OP_BRIDGE_RESPONSE_V1','sequence':r['sequence'],'status':'OK','ready':None}),flush=True)\n break\n"
    )
    script = tmp_path / "owned.ps1"
    script.write_text(r"""param($Repo,$Program,$Executable,$Mode)
$ErrorActionPreference='Stop'
. (Join-Path $Repo 'scripts/windows/Atlas-SelectedPaper-EnrolledLauncher.ps1') -SourceLoadOnly
$plan=[pscustomobject]@{schema='QD_OP_ENROLLED_LAUNCH_PLAN_V1';operation_id=('qd-enrollment:'+('a'*64));account_id='synthetic-account';epoch='synthetic-epoch';enrollment_digest=('b'*64);policy_digest=('c'*64);release_digest=('d'*64);publication_digest=('e'*64);executable=$Executable;issued_at=100;expires_at=130;capabilities=@('READ_ONLY')}
$script:owned=$null
$factory={param($accepted)
 $p=New-Object System.Diagnostics.Process
 $p.StartInfo.FileName=$Executable;$p.StartInfo.Arguments='"'+$Program+'"'
 $p.StartInfo.UseShellExecute=$false;$p.StartInfo.CreateNoWindow=$true
 $p.StartInfo.RedirectStandardInput=$true;$p.StartInfo.RedirectStandardOutput=$true
 [void]$p.Start();$script:owned=$p
 $context=[pscustomobject]@{schema='QD_OP_BRIDGE_CONTEXT_V1';host_id=('a'*32);account_id='synthetic-account';epoch='synthetic-epoch';enrollment_digest=('b'*64);process=[pscustomobject]@{pid=$p.Id;creation_filetime=$p.StartTime.ToUniversalTime().ToFileTimeUtc();image=$p.MainModule.FileName}}
 if($Mode -eq 'identity_refused'){$context.process.pid++}
 return [pscustomobject]@{Process=$p;Context=$context}
}
$authorize={param($phase,$accepted,$context,$now)
 if($accepted.account_id -cne 'synthetic-account' -or $accepted.enrollment_digest -cne ('b'*64)){return $false}
 return -not ($Mode -eq 'retain_refused' -and $phase -eq 'RETAIN')
}
try {
 try {
  $bridge=New-AtlasEnrolledReadBridge -AcceptedPlan $plan -Authorize $authorize -TrustedClock {100} -AcceptedChildFactory $factory
  if($Mode -ne 'ok'){throw 'EXPECTED_REFUSAL'}
  if(-not $bridge.close_read_only_session($null)){throw 'close failed'}
  if(-not $bridge.close_read_only_session($null)){throw 'repeat close failed'}
 } catch {
  if($Mode -eq 'ok' -or $_.Exception.Message -match 'EXPECTED_REFUSAL'){throw}
  if($Mode -eq 'identity_refused' -and $_.Exception.Data['RetainedUnverifiedProcess'] -ne $script:owned){throw 'ownership lost'}
  if($Mode -eq 'retain_refused' -and -not $script:owned.HasExited){throw 'owned refusal did not close'}
 }
 Write-Output 'ENROLLED_TEST_OWNED_PASS'
} finally {
 if($null -ne $script:owned -and -not $script:owned.HasExited){
  # Test harness owns this exact retained process independently of launcher.
  $script:owned.StandardInput.Close()
  if(-not $script:owned.WaitForExit(12000)){throw 'owned fixture did not exit; retained, no kill'}
 }
}
""")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(script),
            str(ROOT),
            str(child),
            sys._base_executable,
            mode,
        ],
        capture_output=True,
        text=True,
        timeout=35,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ENROLLED_TEST_OWNED_PASS" in result.stdout
