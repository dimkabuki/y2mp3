"""Storage checks and collision-safe publication."""

import hashlib
import os
import re
import shutil
import unicodedata
from pathlib import Path

from .models import Job, Mode


class StorageError(Exception):
    pass


def storage_root(override: Path | None = None, home: Path | None = None) -> Path:
    if override is not None:
        root = override.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
    else:
        downloads = (home or Path.home()) / "storage" / "downloads"
        if not downloads.is_dir():
            raise StorageError(
                "Shared storage is unavailable. Run termux-setup-storage "
                "and approve Android storage access."
            )
        root = downloads / "y2mp3"
        root.mkdir(exist_ok=True)
    if not os.access(root, os.W_OK):
        raise StorageError(
            "The output directory is not writable. Check Android storage permissions."
        )
    return root


def safe_name(value: str, limit: int = 100) -> str:
    value = unicodedata.normalize("NFC", value)
    value = "".join("_" if unicodedata.category(c).startswith("C") else c for c in value)
    value = re.sub(r'[<>:"/\\|?*]', "_", value).strip(" .")
    value = value.encode("utf-8")[:limit].decode("utf-8", errors="ignore").strip(" .")
    return value or "untitled"


def output_path(root: Path, job: Job) -> Path:
    directory = root / job.mode.value
    prefix = ""
    if job.playlist is not None:
        directory /= f"{safe_name(job.playlist)} [{safe_name(job.playlist_id, 32)}]"
        width = max(3, len(str(job.playlist_size)))
        prefix = f"{job.playlist_index or 1:0{width}d} - "
    extension = "mp3" if job.mode == Mode.AUDIO else "mp4"
    return directory / f"{prefix}{safe_name(job.title)} [{safe_name(job.media_id, 40)}].{extension}"


def workspace(root: Path, job: Job) -> Path:
    identity = (
        f"{job.number}|{job.url}|{job.mode.value}|{job.resolution}|"
        f"{job.playlist_id}|{job.playlist_index}"
    )
    key = hashlib.sha256(identity.encode()).hexdigest()[:24]
    path = root / ".partial" / key
    path.mkdir(parents=True, exist_ok=True)
    return path


def publish(source: Path, target: Path) -> Path:
    """Exclusive creation also protects duplicates across workers/processes."""
    target.parent.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        candidate = (
            target if index == 1 else target.with_name(f"{target.stem} ({index}){target.suffix}")
        )
        try:
            destination = candidate.open("xb")
        except FileExistsError:
            index += 1
            continue
        try:
            with destination, source.open("rb") as original:
                shutil.copyfileobj(original, destination)
            return candidate
        except BaseException:
            candidate.unlink(missing_ok=True)
            raise
