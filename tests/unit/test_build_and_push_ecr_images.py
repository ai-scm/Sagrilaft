"""Publisher contract: AWS and Docker are always replaced, no network or images."""
from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import build_and_push_ecr_images as publisher

REAL_RUN = subprocess.run
REAL_OUTPUT = subprocess.check_output

SHA = "a" * 40
ACCOUNT = "123456789012"
REGION = "us-east-1"
DIGEST = "sha256:" + "b" * 64
CONFIG = {"VITE_BACKEND_URL": "https://api.test", "VITE_PORTAL_INTERNO_URL": "https://portal.test",
          "VITE_KEYCLOAK_URL": "https://auth.test", "FRONTEND_URL": "https://form.test"}


@pytest.fixture(autouse=True)
def block_processes(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected process: AWS/Docker must be simulated")
    monkeypatch.setattr(publisher.subprocess, "run", blocked)
    monkeypatch.setattr(publisher.subprocess, "check_output", blocked)


class FakeEcr:
    def __init__(self):
        self.images = {}
        self.account = ACCOUNT
        self.mutable = False

    def call(self, *args):
        assert args == ("sts", "get-caller-identity")
        return {"Account": self.account}

    def immutable(self, repo):
        publisher.require(not self.mutable, "IMMUTABLE required")

    def digest(self, repo, tag):
        assert tag == SHA
        return self.images.get(repo)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setattr(publisher, "LOCK_DIRECTORY", tmp_path)
    api = FakeEcr()
    calls = []
    options = publisher.builds(CONFIG)

    def run(command, cwd=None):
        calls.append(command)
        if command[:2] == ["docker", "push"]:
            repo = command[2].split("/")[-1].split(":")[0]
            api.images[repo] = DIGEST

    @contextmanager
    def snapshot(tag):
        assert tag == SHA
        yield tmp_path

    def output(command):
        assert command[:3] == ["docker", "image", "inspect"]
        uri = command[3].rsplit(":", 1)[0]
        return json.dumps([f"{uri}@{DIGEST}"])

    monkeypatch.setattr(publisher, "run", run)
    monkeypatch.setattr(publisher, "output", output)
    monkeypatch.setattr(publisher, "source_snapshot", snapshot)
    monkeypatch.setattr(publisher, "login_ecr", lambda *a: calls.append(["login"]))
    path = tmp_path / "manifest.json"

    def publish(approved=None):
        return publisher.publish("staging", ACCOUNT, REGION, SHA, options, path, approved, api)

    return api, calls, options, path, publish


def approved_manifest(options):
    registry = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com"
    return {"version": 1, "environment": "staging", "account": ACCOUNT, "region": REGION,
            "tag": SHA, "platform": publisher.PLATFORM, "complete": True,
            "images": {name: {"repository": f"{registry}/sagrilaft-staging-{name}", "digest": DIGEST,
                               "inputsHash": publisher.inputs_hash(SHA, options[name])}
                       for name in publisher.COMPONENTS}}


def seed(api):
    api.images = {f"sagrilaft-staging-{n}": DIGEST for n in publisher.COMPONENTS}


def test_publish_four_sha_images_and_manifest(rig):
    api, calls, options, path, publish = rig
    result = publish()
    assert json.loads(path.read_text()) == result
    assert result["complete"] is True
    assert result["digests"] == {name: DIGEST for name in publisher.COMPONENTS}
    builds = [c for c in calls if c[:2] == ["docker", "build"]]
    pushes = [c for c in calls if c[:2] == ["docker", "push"]]
    assert len(builds) == len(pushes) == 4
    assert all(c.count("-t") == 1 and c[-1].endswith(":" + SHA) for c in builds)
    assert all(c[-1].endswith(":" + SHA) for c in pushes)
    assert not any("latest" in arg for c in calls for arg in c)
    assert all(record["status"] == "published" for record in result["images"].values())


def test_approved_reuse_requires_no_docker(rig):
    api, calls, options, path, publish = rig
    seed(api)
    result = publish(approved_manifest(options))
    assert result["complete"] and calls == []
    assert all(record["status"] == "reused" for record in result["images"].values())


def test_resume_partial_builds_only_missing(rig):
    api, calls, options, path, publish = rig
    approved = approved_manifest(options)
    approved["complete"] = False
    approved["images"] = {"backend": approved["images"]["backend"]}
    api.images["sagrilaft-staging-backend"] = DIGEST
    result = publish(approved)
    assert result["complete"]
    assert len([c for c in calls if c[:2] == ["docker", "push"]]) == 3


@pytest.mark.parametrize("problem", ["mutable", "account", "unapproved", "digest", "config", "repository", "deleted"])
def test_preflight_stops_before_build(rig, problem):
    api, calls, options, path, publish = rig
    approved = None
    if problem == "mutable":
        api.mutable = True
    elif problem == "account":
        api.account = "000000000000"
    else:
        seed(api)
        if problem != "unapproved":
            approved = approved_manifest(options)
        if problem == "digest":
            approved["images"]["backend"]["digest"] = "sha256:" + "c" * 64
        if problem == "config":
            options["backend"] += ["--build-arg", "CHANGED=true"]
        if problem == "repository":
            approved["images"]["backend"]["repository"] = "another/repo"
        if problem == "deleted":
            api.images.clear()
    with pytest.raises(publisher.PrecondicionError):
        publish(approved)
    assert calls == []
    assert json.loads(path.read_text())["complete"] is False


@pytest.mark.parametrize("field", ["environment", "account", "region", "tag", "platform", "version"])
def test_reuse_metadata_must_match(rig, field):
    api, calls, options, path, publish = rig
    approved = approved_manifest(options)
    approved[field] = "different"
    with pytest.raises(publisher.PrecondicionError):
        publish(approved)
    assert not path.exists() and not calls


def test_existing_manifest_is_never_overwritten(rig):
    _, calls, _, path, publish = rig
    path.write_text("original")
    with pytest.raises(FileExistsError):
        publish()
    assert path.read_text() == "original" and calls == []


def test_partial_failure_preserves_confirmed_digests(rig, monkeypatch):
    api, calls, options, path, publish = rig
    original = publisher.run
    def run(command, cwd=None):
        if command[:2] == ["docker", "push"] and "formulario-publico" in command[-1]:
            raise subprocess.CalledProcessError(1, command)
        original(command, cwd)
    monkeypatch.setattr(publisher, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        publish()
    evidence = json.loads(path.read_text())
    assert not evidence["complete"]
    assert list(evidence["images"]) == ["backend"]
    assert evidence["images"]["backend"]["digest"] == DIGEST


def test_remote_digest_must_match_pushed_image(rig, monkeypatch):
    _, _, _, path, publish = rig
    monkeypatch.setattr(publisher, "output", lambda _: "[]")
    with pytest.raises(publisher.PrecondicionError, match="digest remoto"):
        publish()
    assert not json.loads(path.read_text())["complete"]


def test_concurrent_publication_is_not_adopted(rig, monkeypatch):
    api, calls, options, path, publish = rig
    monkeypatch.setattr(publisher, "login_ecr", lambda *a: seed(api))
    with pytest.raises(publisher.PrecondicionError, match="concurrente"):
        publish()
    assert not any(c[:2] == ["docker", "build"] for c in calls)


def test_final_digest_is_rechecked(rig, monkeypatch):
    api, calls, options, path, publish = rig
    seed(api)
    count = 0
    def digest(repo, tag):
        nonlocal count
        count += 1
        return DIGEST if count <= 4 else "sha256:" + "c" * 64
    monkeypatch.setattr(api, "digest", digest)
    with pytest.raises(publisher.PrecondicionError, match="cambió"):
        publish(approved_manifest(options))
    assert not json.loads(path.read_text())["complete"]


@pytest.mark.parametrize("tag,dirty,stages", [("latest", "", ""), ("abcdef0", "", ""),
    ("b" * 40, "", ""), (SHA, " M backend/main.py", ""),
    (SHA, "?? untracked", ""), (SHA, "", "160000 abc 0\tbackend/submodule")])
def test_invalid_source_rejected(monkeypatch, tag, dirty, stages):
    def output(command):
        return SHA if "rev-parse" in command else dirty if "status" in command else stages
    monkeypatch.setattr(publisher, "output", output)
    with pytest.raises(publisher.PrecondicionError):
        publisher.validate_source(tag)


def test_clean_source_defaults_to_full_head(monkeypatch):
    monkeypatch.setattr(publisher, "output", lambda c: SHA if "rev-parse" in c else "")
    assert publisher.validate_source(None) == SHA


@pytest.mark.parametrize("code", ["AccessDeniedException", "RepositoryNotFoundException", "ThrottlingException", "ImageNotFoundException"])
def test_only_image_not_found_means_absent(monkeypatch, code):
    monkeypatch.setattr(publisher.subprocess, "run", lambda *a, **kw:
        subprocess.CompletedProcess(a, 1, "", f"An error occurred ({code}) when calling DescribeImages"))
    api = publisher.Ecr(REGION)
    if code == "ImageNotFoundException":
        assert api.digest("repo", SHA) is None
    else:
        with pytest.raises(publisher.PrecondicionError):
            api.digest("repo", SHA)


@pytest.mark.parametrize("mutability", ["MUTABLE", "IMMUTABLE_WITH_EXCLUSION", "MUTABLE_WITH_EXCLUSION"])
def test_exclusion_modes_are_rejected(monkeypatch, mutability):
    api = publisher.Ecr(REGION)
    monkeypatch.setattr(api, "call", lambda *a: {"repositories": [{"imageTagMutability": mutability}]})
    with pytest.raises(publisher.PrecondicionError):
        api.immutable("repo")


def test_build_arguments_preserve_spaces_and_hash_configuration():
    config = dict(CONFIG, VITE_RAZON_SOCIAL="Empresa con espacios")
    options = publisher.builds(config)
    assert "VITE_RAZON_SOCIAL=Empresa con espacios" in options["formulario-publico"]
    assert publisher.inputs_hash(SHA, options["formulario-publico"]) != publisher.inputs_hash(SHA, publisher.builds(CONFIG)["formulario-publico"])
    assert all(o[:2] == ["--platform", "linux/amd64"] for o in options.values())


def test_missing_configuration_fails_before_publication():
    with pytest.raises(publisher.PrecondicionError):
        publisher.builds({})


def test_workflow_uses_shared_publisher_and_preserves_partial_evidence():
    workflow = (publisher.ROOT / ".github/workflows/ci.yml").read_text()
    assert "scripts/build_and_push_ecr_images.py" in workflow
    assert ":latest" not in workflow
    assert "docker push" not in workflow and "docker build" not in workflow
    assert "if: always()" in workflow and "actions/upload-artifact@v4" in workflow
    assert '--tag "$IMAGE_TAG"' in workflow and "${{ github.sha }}" in workflow


def test_snapshot_contains_only_committed_inputs(tmp_path, monkeypatch):
    # Only git is permitted; all other subprocesses remain prohibited.
    def git_run(command, **kwargs):
        assert command[0] == "git"
        return REAL_RUN(command, **kwargs)
    def git_output(command, **kwargs):
        assert command[0] == "git"
        return REAL_OUTPUT(command, **kwargs)
    monkeypatch.setattr(publisher.subprocess, "run", git_run)
    monkeypatch.setattr(publisher.subprocess, "check_output", git_output)
    monkeypatch.setattr(publisher, "ROOT", tmp_path)
    for name in ("backend", "frontend", "keycloak"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "tracked file").write_text("committed")
    (tmp_path / ".gitignore").write_text(".env.local\n")
    (tmp_path / "frontend/.env.local").write_text("ignored configuration")
    publisher.run(["git", "init", "-q"])
    publisher.run(["git", "add", "."])
    publisher.run(["git", "-c", "user.name=Local Test", "-c", "user.email=test@example.invalid",
                   "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"])
    sha = publisher.validate_source(None)
    with publisher.source_snapshot(sha) as snapshot:
        assert (snapshot / "frontend/tracked file").read_text() == "committed"
        assert not (snapshot / "frontend/.env.local").exists()
        assert not (snapshot / ".git").exists()
    assert not snapshot.exists()


def test_cli_environment_uses_shared_publisher(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["publisher", "--environment", "prod", "--account", ACCOUNT,
        "--region", REGION, "--from-environment", "--tag", SHA, "--manifest", str(tmp_path / "result.json")])
    monkeypatch.setattr(publisher, "validate_source", lambda tag: tag)
    monkeypatch.setattr(publisher.os, "umask", lambda _: None)
    for key, val in CONFIG.items():
        monkeypatch.setenv(key, val)
    monkeypatch.setattr(publisher, "publish", lambda *a: calls.append(a))
    assert publisher.main() == 0
    assert calls[0][:4] == ("prod", ACCOUNT, REGION, SHA)
    assert set(calls[0][4]) == set(publisher.COMPONENTS)


@pytest.mark.parametrize("stage", ["build", "push", "inspect"])
def test_concurrent_local_publish_cannot_replace_tag_or_record_digest(rig, monkeypatch, stage):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    api, calls, options, path, publish = rig
    entered, release = Event(), Event()
    original_run, original_output = publisher.run, publisher.output

    def pause():
        entered.set()
        assert release.wait(5), "Test synchronization timed out"

    def run(command, cwd=None):
        # Pause before fake push writes the remote digest, or after fake build.
        if command[:2] == ["docker", "push"] and stage == "push" and not entered.is_set():
            pause()
        original_run(command, cwd)
        if command[:2] == ["docker", "build"] and stage == "build" and not entered.is_set():
            pause()

    def output(command):
        if stage == "inspect" and not entered.is_set():
            pause()
        return original_output(command)

    monkeypatch.setattr(publisher, "run", run)
    monkeypatch.setattr(publisher, "output", output)
    other_options = publisher.builds(dict(CONFIG, VITE_RAZON_SOCIAL="Other build configuration"))
    other_path = path.with_name("other.json")
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(publish)
        try:
            assert entered.wait(5)
            previous_calls = list(calls)
            # During inspect one image exists remotely; explicitly acknowledge it
            # so this contender reaches the lock for the other missing images.
            approved = None
            if stage == "inspect":
                approved = approved_manifest(other_options)
                approved["images"] = {"backend": approved["images"]["backend"]}
            with pytest.raises(publisher.PrecondicionError, match="lock"):
                publisher.publish("staging", ACCOUNT, REGION, SHA, other_options, other_path, approved, api)
            assert calls == previous_calls  # No second build, push or login.
            assert json.loads(other_path.read_text())["complete"] is False
        finally:
            release.set()
        result = first.result(timeout=5)
    assert result["complete"]
    assert result["images"]["formulario-publico"]["inputsHash"] == publisher.inputs_hash(SHA, options["formulario-publico"])
    assert len([c for c in calls if c[:2] == ["docker", "push"]]) == 4


def test_lock_is_shared_between_processes_and_released_on_error(tmp_path, monkeypatch):
    import multiprocessing
    monkeypatch.setattr(publisher, "LOCK_DIRECTORY", tmp_path)
    context = multiprocessing.get_context("fork")
    receive, send = context.Pipe(duplex=False)

    def contender():
        try:
            with publisher.publication_lock("registry", SHA):
                send.send("unexpected entry")
        except publisher.PrecondicionError:
            send.send("blocked")
        finally:
            send.close()

    with pytest.raises(RuntimeError):
        with publisher.publication_lock("registry", SHA):
            child = context.Process(target=contender)
            child.start()
            try:
                assert receive.poll(5)
                assert receive.recv() == "blocked"
                child.join(5)
                assert child.exitcode == 0
            finally:
                if child.is_alive():
                    child.terminate()
                    child.join()
            raise RuntimeError("simulated publication failure")
    with publisher.publication_lock("registry", SHA):
        pass  # Lock released; persistent inode does not mean stale lock.
    assert len(list(tmp_path.glob("*.lock"))) == 1


def test_build_child_inherits_lock_descriptor(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(publisher, "LOCK_DIRECTORY", tmp_path)
    calls = []
    def fake_run(command, **kwargs):
        assert command == ["docker", "build", "simulated"]
        descriptors = kwargs["pass_fds"]
        assert len(descriptors) == 1
        os.fstat(descriptors[0])  # Valid descriptor forwarded; no subprocess runs.
        calls.append(descriptors)
    monkeypatch.setattr(publisher.subprocess, "run", fake_run)
    with publisher.publication_lock("registry", SHA):
        publisher.run(["docker", "build", "simulated"])
    assert len(calls) == 1
    assert publisher.lock_descriptors() == ()


@pytest.mark.parametrize("origin", ["", "https://api.test"])
def test_backend_origin_empty_or_absolute_is_preserved(origin):
    options = publisher.builds(dict(CONFIG, VITE_BACKEND_URL=origin))
    for component in ("formulario-publico", "portal-interno"):
        assert f"VITE_BACKEND_URL={origin}" in options[component]
        assert "VITE_BACKEND_URL=/api" not in options[component]


@pytest.mark.parametrize("value", [None, "   "])
def test_missing_or_whitespace_backend_origin_is_rejected(value):
    config = dict(CONFIG)
    if value is None:
        del config["VITE_BACKEND_URL"]
    else:
        config["VITE_BACKEND_URL"] = value
    with pytest.raises(publisher.PrecondicionError, match="VITE_BACKEND_URL"):
        publisher.builds(config)


def test_env_file_preserves_explicit_empty_origin(tmp_path):
    path = tmp_path / "build.env"
    path.write_text('VITE_BACKEND_URL=""\n')
    config = dict(CONFIG, **publisher.parse_env(path))
    assert "VITE_BACKEND_URL=" in publisher.builds(config)["formulario-publico"]


def test_relative_origin_changes_manifest_input_hash():
    empty = publisher.builds(dict(CONFIG, VITE_BACKEND_URL=""))
    absolute = publisher.builds(CONFIG)
    for component in ("formulario-publico", "portal-interno"):
        assert publisher.inputs_hash(SHA, empty[component]) != publisher.inputs_hash(SHA, absolute[component])


@pytest.mark.parametrize("value", [None, 123])
def test_invalid_backend_url_is_not_silently_relative(value):
    with pytest.raises(publisher.PrecondicionError, match="VITE_BACKEND_URL"):
        publisher.builds(dict(CONFIG, VITE_BACKEND_URL=value))
