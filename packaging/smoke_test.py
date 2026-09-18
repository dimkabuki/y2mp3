"""Verify an extracted .deb with host Python, without claiming Android validation."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from validate_deb import validate


def smoke_test(package: Path, version: str) -> None:
    package = package.resolve()
    validate(package, version)
    with tempfile.TemporaryDirectory(prefix="y2mp3-smoke-") as directory:
        root = Path(directory)
        payload = root / "payload"
        subprocess.run(["dpkg-deb", "-x", str(package), str(payload)], check=True)
        base = payload / "data/data/com.termux/files/usr/lib/y2mp3"
        env = os.environ | {
            "PYTHONPATH": f"{base / 'app'}{os.pathsep}{base / 'vendor'}",
            "HOME": str(root / "home"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        Path(env["HOME"]).mkdir()
        # Import origins ensure this tests the package payload, not an editable checkout.
        check = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "import y2mp3, rich; print(y2mp3.__file__); print(rich.__file__)",
            ],
            env=env,
            cwd=root,
            text=True,
        )
        if str(base / "app") not in check or str(base / "vendor") not in check:
            raise RuntimeError("Imports escaped the extracted package payload.")
        result = subprocess.check_output(
            [sys.executable, "-m", "y2mp3", "--version"], env=env, cwd=root, text=True
        )
        if result.strip() != f"y2mp3 {version}":
            raise RuntimeError("Wrong packaged version.")
        subprocess.run(
            [sys.executable, "-m", "y2mp3", "--help"],
            env=env,
            cwd=root,
            check=True,
            capture_output=True,
        )
        missing_storage = subprocess.run(
            [sys.executable, "-m", "y2mp3"], env=env, cwd=root, capture_output=True, text=True
        )
        if missing_storage.returncode != 2 or "termux-setup-storage" not in missing_storage.stdout:
            raise RuntimeError("Packaged application did not report missing storage.")
    print("Package smoke test passed: imports, --version, --help, storage guard. Android untested.")


if __name__ == "__main__":
    smoke_test(Path(sys.argv[1]), sys.argv[2])
