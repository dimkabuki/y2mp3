"""Explicit playlist expansion and quality prompts before concurrent execution."""

from collections.abc import Callable
from typing import Any

from .diagnostics import LOG, failure_message, redact
from .downloader import Downloader, reject_unsupported
from .formats import default_resolution, resolutions, select_format
from .input_parser import validate_url
from .models import Cancelled, Job, Mode, State, UnsupportedMedia


def entry_url(entry: dict[str, Any]) -> str:
    value = entry.get("webpage_url") or entry.get("url") or ""
    if not value.startswith(("http://", "https://")) and entry.get("ie_key") == "Youtube":
        value = f"https://www.youtube.com/watch?v={entry.get('id') or value}"
    return validate_url(value)


def plan_jobs(
    urls: list[str],
    mode: Mode,
    engine: Downloader,
    choose: Callable[[Job, list[int], int], int],
    notice: Callable[[str], None] = lambda text: None,
) -> list[Job]:
    jobs: list[Job] = []

    def failed(url: str, exc: Exception, **context: Any) -> None:
        job = Job(len(jobs) + 1, url, mode, **context)
        job.state = State.SKIPPED if isinstance(exc, UnsupportedMedia) else State.FAILED
        job.message = str(exc) if isinstance(exc, UnsupportedMedia) else failure_message(exc)
        jobs.append(job)
        LOG.debug("planning failure: %s", redact(exc))

    def visit(info: dict[str, Any] | None, url: str, depth: int = 0, **context: Any) -> None:
        if info is None:
            failed(url, UnsupportedMedia("This playlist entry is unavailable."), **context)
            return
        if info.get("_type") in {"playlist", "multi_video"} or "entries" in info:
            if depth >= 5:
                failed(
                    url, UnsupportedMedia("Nested playlist depth exceeds v0.1 support."), **context
                )
                return
            entries = list(info.get("entries") or [])
            title = str(info.get("title") or "Playlist")
            notice(f"Playlist: {title} — {len(entries)} entries")
            if not entries:
                failed(url, ValueError("Empty playlist."), **context)
                return
            for index, entry in enumerate(entries, 1):
                playlist_context = dict(
                    playlist=title,
                    playlist_id=str(info.get("id") or "playlist"),
                    playlist_index=(entry or {}).get("playlist_index") or index,
                    playlist_size=len(entries),
                )
                try:
                    child_url = entry_url(entry) if entry else url
                    visit(entry, child_url, depth + 1, **playlist_context)
                except (Cancelled, KeyboardInterrupt):
                    raise
                except Exception as exc:
                    failed(url, exc, **playlist_context)
            return
        job = Job(len(jobs) + 1, url, mode, **context)
        jobs.append(job)
        try:
            reject_unsupported(info)
            notice(f"[{job.number}] Inspecting {info.get('title') or 'media'}")
            # Full metadata from a top-level individual can be reused for planning.
            metadata = (
                info
                if info.get("formats") and info.get("_type", "video") == "video"
                else engine.inspect(url)
            )
            reject_unsupported(metadata)
            job.title = str(metadata.get("title") or "Untitled")
            job.media_id = str(metadata.get("id") or "unknown")
            if mode == Mode.VIDEO:
                formats = metadata.get("formats") or []
                heights = resolutions(formats)
                job.resolution = choose(job, heights, default_resolution(heights))
                job.choice = select_format(formats, job.resolution)
            job.state = State.QUEUED
        except (Cancelled, KeyboardInterrupt):
            raise
        except Exception as exc:
            job.state = State.SKIPPED if isinstance(exc, UnsupportedMedia) else State.FAILED
            job.message = str(exc) if isinstance(exc, UnsupportedMedia) else failure_message(exc)
            LOG.debug("metadata failure: %s", redact(exc))

    for url in urls:
        try:
            visit(engine.expand(url), url)
        except (Cancelled, KeyboardInterrupt):
            raise
        except Exception as exc:
            failed(url, exc)
    return jobs
