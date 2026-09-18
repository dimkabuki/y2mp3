"""The only adapter importing yt-dlp. No CLI output parsing or private APIs."""

import shutil
from pathlib import Path
from threading import Event
from typing import Any

from yt_dlp import YoutubeDL
from yt_dlp.postprocessor import PostProcessor

from .diagnostics import EngineLogger
from .input_parser import validate_url
from .media import check_cancel, normalize
from .models import Job, Mode, UnsupportedMedia
from .paths import output_path, publish, workspace
from .progress import Progress


def reject_unsupported(info: dict[str, Any], *, incomplete: bool = False) -> None:
    if info.get("is_live") or info.get("live_status") in {"is_live", "is_upcoming", "post_live"}:
        raise UnsupportedMedia(
            "Live, scheduled, or still-processing streams are not supported in v0.1."
        )
    if info.get("availability") in {"private", "premium_only", "subscriber_only", "needs_auth"}:
        raise UnsupportedMedia("Only public media is supported in v0.1.")
    if info.get("has_drm"):
        raise UnsupportedMedia("DRM-protected media is not supported.")


class CapturePathPP(PostProcessor):
    def __init__(self, downloader: YoutubeDL) -> None:
        super().__init__(downloader)
        self.path: Path | None = None

    def run(self, info: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
        self.path = Path(info["filepath"])
        return [], info


class Downloader:
    def __init__(self, stop: Event, progress: Progress, factory: Any = YoutubeDL) -> None:
        self.stop = stop
        self.progress = progress
        self.factory = factory

    def options(self) -> dict[str, Any]:
        return {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "logger": EngineLogger(),
            "noplaylist": True,
            "socket_timeout": 20,
            "retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": False,
            "js_runtimes": {"deno": {}},
            "remote_components": [],
            "match_filter": self.filter,
        }

    def filter(self, info: dict[str, Any], *, incomplete: bool = False) -> None:
        check_cancel(self.stop)
        # Preserve flat playlist entries, including unsupported ones, for per-item reporting.
        if not incomplete:
            reject_unsupported(info)

    def expand(self, url: str) -> dict[str, Any]:
        check_cancel(self.stop)
        options = self.options() | {"extract_flat": "in_playlist", "ignoreerrors": True}
        with self.factory(options) as engine:
            info = engine.extract_info(url, download=False)
        if not info:
            raise ValueError("No public media was found.")
        return info

    def inspect(self, url: str) -> dict[str, Any]:
        check_cancel(self.stop)
        with self.factory(self.options()) as engine:
            info = engine.extract_info(url, download=False)
        if not info or info.get("_type") in {"playlist", "multi_video"}:
            raise ValueError("An individual media item could not be resolved.")
        reject_unsupported(info)
        return info

    def download(self, job: Job, root: Path) -> Path:
        check_cancel(self.stop)
        work = workspace(root, job)

        def hook(data: dict[str, Any]) -> None:
            check_cancel(self.stop)
            self.progress.download(job.number, data)

        def pp_hook(data: dict[str, Any]) -> None:
            check_cancel(self.stop)
            self.progress.postprocess(job.number, data)

        options = self.options() | {
            "format": "bestaudio/best" if job.mode == Mode.AUDIO else job.choice.selector,
            "outtmpl": str(work / "source.%(ext)s")
            .replace("%", "%%")
            .replace("%%(ext)s", "%(ext)s"),
            "continuedl": True,
            "overwrites": False,
            "merge_output_format": "mkv",
            "progress_hooks": [hook],
            "postprocessor_hooks": [pp_hook],
        }
        with self.factory(options) as engine:
            capture = CapturePathPP(engine)
            engine.add_post_processor(capture, when="after_move")
            info = engine.extract_info(validate_url(job.url), download=True)
        if not info or capture.path is None or not capture.path.is_file():
            raise RuntimeError("Download did not produce a media file.")
        check_cancel(self.stop)
        ready = normalize(capture.path, job.mode, self.stop, self.progress, job.number)
        check_cancel(self.stop)
        result = publish(ready, output_path(root, job))
        shutil.rmtree(work, ignore_errors=True)
        return result
