"""Fail closed on invalid metadata, layout, symlinks, or native payloads."""

import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PREFIX = "data/data/com.termux/files/usr/"
MAGIC = (b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe")


def validate(package: Path, version: str) -> None:
    members = subprocess.check_output(["ar", "t", str(package)], text=True).splitlines()
    expected_members = ["debian-binary", "control.tar.xz", "data.tar.xz"]
    if members != expected_members:
        raise ValueError(
            f"Invalid Debian archive members; Termux requires {expected_members}, found {members}."
        )
    info = subprocess.check_output(["dpkg-deb", "--field", str(package)], text=True)
    fields = dict(
        line.split(": ", 1)
        for line in info.splitlines()
        if ": " in line and not line.startswith(" ")
    )
    for key, expected in {
        "Package": "y2mp3",
        "Version": version,
        "Architecture": "all",
        "Homepage": "https://github.com/dimkabuki/y2mp3",
    }.items():
        if fields.get(key) != expected:
            raise ValueError(f"Invalid {key}: {fields.get(key)}")
    deps = {part.strip() for part in fields.get("Depends", "").split(",")}
    if deps != {"python-yt-dlp", "yt-dlp-ejs", "deno", "ffmpeg"}:
        raise ValueError("Incorrect or version-pinned runtime dependencies.")
    with tempfile.TemporaryDirectory() as temp:
        archive = Path(temp) / "payload.tar"
        with archive.open("wb") as out:
            subprocess.run(["dpkg-deb", "--fsys-tarfile", str(package)], stdout=out, check=True)
        with tarfile.open(archive) as tar:
            files = {}
            for member in tar:
                name = member.name.removeprefix("./")
                if member.isdir():
                    continue
                if not member.isfile() or not name.startswith(PREFIX) or ".." in Path(name).parts:
                    raise ValueError(f"Invalid installed path/type: {name}")
                contents = tar.extractfile(member).read()
                if (
                    name.endswith((".so", ".dll", ".dylib", ".exe", ".pyc"))
                    or ".so." in name
                    or contents.startswith(MAGIC)
                ):
                    raise ValueError(f"Native/compiled payload: {name}")
                if contents.startswith(b"#!") and not contents.splitlines()[0].startswith(
                    b"#!/data/data/com.termux/files/usr/bin/"
                ):
                    # Non-executable Python source can carry a harmless host shebang.
                    if member.mode & 0o111:
                        raise ValueError(f"Host launcher found: {name}")
                files[name] = (member, contents)
            required = [
                "bin/y2mp3",
                "lib/y2mp3/app/y2mp3/__main__.py",
                "lib/y2mp3/app/y2mp3/__init__.py",
                "lib/y2mp3/vendor/rich/__init__.py",
            ]
            for name in required:
                if PREFIX + name not in files:
                    raise ValueError(f"Missing {name}")
            module = files[PREFIX + "lib/y2mp3/app/y2mp3/__init__.py"][1]
            if f'__version__ = "{version}"'.encode() not in module:
                raise ValueError("Bundled Python version differs from Debian version.")
            launcher, contents = files[PREFIX + "bin/y2mp3"]
            if not launcher.mode & 0o111 or not contents.startswith(
                b"#!/data/data/com.termux/files/usr/bin/sh\n"
            ):
                raise ValueError("Invalid Termux launcher.")
    print(
        f"Validated {package.name}: version {version}, xz members, "
        "Termux prefix, pure-Python payload"
    )


if __name__ == "__main__":
    validate(Path(sys.argv[1]), sys.argv[2])
