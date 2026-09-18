"""Regression tests for Termux-specific Debian archive compatibility."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "packaging/validate_deb.py"


@pytest.mark.skipif(
    shutil.which("dpkg-deb") is None or shutil.which("ar") is None,
    reason="requires dpkg-deb and ar",
)
def test_validator_rejects_gzip_debian_members(tmp_path):
    control = tmp_path / "stage/DEBIAN"
    control.mkdir(parents=True)
    (control / "control").write_text(
        "Package: y2mp3\nVersion: 0.1.1\nArchitecture: all\n"
        "Maintainer: Test <test@example.invalid>\nDescription: Compression fixture\n"
    )
    package = tmp_path / "gzip.deb"
    subprocess.run(
        [
            "dpkg-deb",
            "--root-owner-group",
            "--uniform-compression",
            "-Zgzip",
            "--build",
            str(tmp_path / "stage"),
            str(package),
        ],
        check=True,
        capture_output=True,
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(package), "0.1.1"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Termux requires" in result.stderr
    assert "control.tar.gz" in result.stderr
