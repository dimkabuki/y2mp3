"""Assemble text/Python assets only. Never execute target Android programs."""

import argparse
import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from validate_deb import validate

ROOT = Path(__file__).resolve().parents[1]
PREFIX = Path("data/data/com.termux/files/usr")


def project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text()
    version = re.search(r'^version = "([^"]+)"', text, re.MULTILINE).group(1)
    module = (ROOT / "src/y2mp3/__init__.py").read_text()
    if f'__version__ = "{version}"' not in module:
        raise ValueError("Python project and module versions differ.")
    return version


def run(*args: str) -> None:
    subprocess.run(list(args), check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=project_version())
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    version = args.version.removeprefix("v")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version) or version != project_version():
        raise ValueError("Release version must match pyproject.toml and __version__ (X.Y.Z).")
    maintainer = os.environ.get(
        "Y2MP3_MAINTAINER", (ROOT / "packaging/maintainer.txt").read_text().strip()
    )
    if not re.fullmatch(r"[^<>\r\n]+ <[^<>\s]+@[^<>\s]+>", maintainer):
        raise ValueError("Provide a valid maintainer Name <email>.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="y2mp3-build-") as temp:
        work = Path(temp)
        stage = work / "stage"
        install = stage / PREFIX
        app = install / "lib/y2mp3/app/y2mp3"
        app.parent.mkdir(parents=True)
        shutil.copytree(
            ROOT / "src/y2mp3", app, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
        wheels = work / "wheels"
        run(
            sys.executable,
            "-m",
            "pip",
            "download",
            "--only-binary=:all:",
            "--no-deps",
            "--require-hashes",
            "-r",
            str(ROOT / "packaging/vendor-requirements.txt"),
            "-d",
            str(wheels),
        )
        for wheel in wheels.glob("*.whl"):
            if not wheel.name.endswith("-none-any.whl"):
                raise ValueError(f"Not a pure-Python wheel: {wheel.name}")
            with zipfile.ZipFile(wheel) as archive:
                if any(
                    name.endswith((".so", ".dll", ".dylib", ".exe")) for name in archive.namelist()
                ):
                    raise ValueError(f"Native payload in {wheel.name}")
        vendor = install / "lib/y2mp3/vendor"
        run(
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheels),
            "--no-deps",
            "--no-compile",
            "--require-hashes",
            "--target",
            str(vendor),
            "-r",
            str(ROOT / "packaging/vendor-requirements.txt"),
        )
        shutil.rmtree(vendor / "bin", ignore_errors=True)
        installed = {
            d.metadata["Name"].lower().replace("_", "-")
            for d in importlib.metadata.distributions(path=[str(vendor)])
        }
        if installed != {"rich", "markdown-it-py", "mdurl", "pygments"}:
            raise ValueError("Unexpected bundled dependency set.")
        launcher = install / "bin/y2mp3"
        launcher.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "packaging/y2mp3-launcher", launcher)
        launcher.chmod(0o755)
        docs = install / "share/doc/y2mp3"
        docs.mkdir(parents=True)
        for filename in ("README.md", "LICENSE"):
            shutil.copyfile(ROOT / filename, docs / filename)
        control = stage / "DEBIAN"
        control.mkdir()
        (control / "control").write_text(
            (ROOT / "packaging/control.in")
            .read_text()
            .format(version=version, maintainer=maintainer)
        )
        shutil.copyfile(ROOT / "packaging/postinst", control / "postinst")
        (control / "postinst").chmod(0o755)
        # Stable file permissions independent of the caller's umask.
        for path in stage.rglob("*"):
            path.chmod(
                0o755 if path.is_dir() or path in {launcher, control / "postinst"} else 0o644
            )
        output = args.output_dir / "y2mp3.deb"
        built_output = work / "y2mp3.deb"
        # Termux's APT reader expects the Debian control and data members in xz format.
        run(
            "dpkg-deb",
            "--root-owner-group",
            "--uniform-compression",
            "-Zxz",
            "--build",
            str(stage),
            str(built_output),
        )
        validate(built_output, version)
        shutil.copyfile(built_output, output)
        print(output)


if __name__ == "__main__":
    main()
