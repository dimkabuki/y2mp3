"""UI-independent job models."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Mode(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"


class State(str, Enum):
    INSPECTING = "Inspecting metadata"
    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    PROCESSING = "Processing"
    MERGING = "Merging"
    CONVERTING = "Converting to MP3"
    TRANSCODING = "Transcoding to MP4"
    REMUXING = "Preparing MP4"
    COMPLETED = "Completed"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    CANCELLED = "Cancelled"


@dataclass(frozen=True)
class FormatChoice:
    selector: str
    transcode: bool


@dataclass
class Job:
    number: int
    url: str
    mode: Mode
    title: str = ""
    media_id: str = "unknown"
    playlist: str | None = None
    playlist_id: str = ""
    playlist_index: int | None = None
    playlist_size: int = 0
    resolution: int | None = None
    choice: FormatChoice | None = None
    state: State = State.INSPECTING
    message: str = ""
    output: Path | None = None


class UnsupportedMedia(Exception):
    """A requested item cannot be handled by this version."""


class Cancelled(Exception):
    """Cooperative cancellation; keep resumable partial downloads."""


def exit_code(jobs: list[Job]) -> int:
    if any(job.state == State.CANCELLED for job in jobs):
        return 130
    return 0 if jobs and all(job.state == State.COMPLETED for job in jobs) else 1
