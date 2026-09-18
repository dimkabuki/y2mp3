"""Exercise release safeguards with real Git/deb/checksums and a fake GitHub CLI."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("dpkg-deb") is None, reason="requires dpkg-deb")

SCRIPT = Path(__file__).resolve().parents[1] / "packaging/publish_release.sh"


def command(root, *args):
    return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.DEVNULL).strip()


@pytest.fixture
def release(tmp_path):
    command(tmp_path, "git", "init", "-b", "main")
    command(tmp_path, "git", "config", "user.name", "Release test")
    command(tmp_path, "git", "config", "user.email", "test@example.invalid")
    command(tmp_path, "git", "commit", "--allow-empty", "-m", "Tested commit")
    sha = command(tmp_path, "git", "rev-parse", "HEAD")
    control = tmp_path / "payload/DEBIAN"
    control.mkdir(parents=True)
    (control / "control").write_text(
        "Package: y2mp3\nVersion: 0.1.0\nArchitecture: all\n"
        "Maintainer: Test <test@example.invalid>\nDescription: Release fixture\n"
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    command(tmp_path, "dpkg-deb", "--build", "payload", "dist/y2mp3.deb")
    digest = hashlib.sha256((dist / "y2mp3.deb").read_bytes()).hexdigest()
    (dist / "SHA256SUMS").write_text(f"{digest}  y2mp3.deb\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "with open(os.environ['GH_CALL_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:3] == ['release', 'view']:\n"
        "    sys.exit(0 if os.environ.get('EXISTING_RELEASE') else 1)\n"
        "if sys.argv[1] == 'api' and os.environ.get('TAG_CREATE_FAIL'):\n"
        "    sys.exit(1)\n"
    )
    gh.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "GH_CALL_LOG": str(tmp_path / "gh-calls.jsonl"),
        "GH_REPO": "example/y2mp3",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": sha,
        "DEFAULT_BRANCH": "main",
        "RELEASE_ACTION": "Publish release",
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md"),
    }
    return tmp_path, env


def invoke(release):
    root, env = release
    result = subprocess.run(
        ["bash", str(SCRIPT)], cwd=root, env=env, capture_output=True, text=True
    )
    log = Path(env["GH_CALL_LOG"])
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


def test_manual_release_creates_tag_at_tested_commit_and_direct_asset(release):
    root, env = release
    result, calls = invoke(release)
    assert result.returncode == 0, result.stderr
    create_tag = next(call for call in calls if call[0] == "api")
    assert "ref=refs/tags/v0.1.0" in create_tag
    assert f"sha={env['GITHUB_SHA']}" in create_tag
    assert calls[-1][:3] == ["release", "create", "v0.1.0"]
    assert "--verify-tag" in calls[-1]
    assert calls[-1][-2:] == ["./dist/y2mp3.deb", "./dist/SHA256SUMS"]
    assert "/releases/download/v0.1.0/y2mp3.deb" in (root / "summary.md").read_text()


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("RELEASE_ACTION", "Build only", "Publishing was not selected"),
        ("GITHUB_REF", "refs/heads/feature", "Publish from the default branch"),
        ("GITHUB_SHA", "0" * 40, "Checkout differs"),
        ("GITHUB_EVENT_NAME", "pull_request", "Unsupported release event"),
    ],
)
def test_invalid_invocation_never_contacts_github(release, key, value, message):
    release[1][key] = value
    result, calls = invoke(release)
    assert result.returncode != 0 and message in result.stderr
    assert not calls


def test_corrupt_package_never_contacts_github(release):
    with (release[0] / "dist/y2mp3.deb").open("ab") as stream:
        stream.write(b"modified")
    result, calls = invoke(release)
    assert result.returncode != 0
    assert not calls


def test_existing_release_is_never_replaced(release):
    release[1]["EXISTING_RELEASE"] = "1"
    result, calls = invoke(release)
    assert result.returncode != 0 and "already exists" in result.stderr
    assert len(calls) == 1 and calls[0][:2] == ["release", "view"]


def test_existing_tag_for_another_commit_is_never_moved(release):
    root, _ = release
    command(root, "git", "tag", "v0.1.0")
    command(root, "git", "commit", "--allow-empty", "-m", "Later commit")
    release[1]["GITHUB_SHA"] = command(root, "git", "rev-parse", "HEAD")
    result, calls = invoke(release)
    assert result.returncode != 0 and "Tag points to another commit" in result.stderr
    assert not calls


@pytest.mark.parametrize("event", ["workflow_dispatch", "push"])
def test_existing_matching_annotated_tag_can_be_published(release, event):
    root, env = release
    command(root, "git", "tag", "-a", "v0.1.0", "-m", "Release")
    env["GITHUB_EVENT_NAME"] = event
    if event == "push":
        env["GITHUB_REF"] = "refs/tags/v0.1.0"
    result, calls = invoke(release)
    assert result.returncode == 0, result.stderr
    assert all(call[0] != "api" for call in calls)
    assert calls[-1][:3] == ["release", "create", "v0.1.0"]


def test_tag_creation_failure_prevents_release_creation(release):
    release[1]["TAG_CREATE_FAIL"] = "1"
    result, calls = invoke(release)
    assert result.returncode != 0
    assert not any(call[:2] == ["release", "create"] for call in calls)


def test_pushed_tag_version_must_match_package(release):
    release[1].update(GITHUB_EVENT_NAME="push", GITHUB_REF="refs/tags/v0.2.0")
    result, calls = invoke(release)
    assert result.returncode != 0 and "Tag and package versions differ" in result.stderr
    assert not calls
