"""Deterministic selection from public yt-dlp format metadata."""

from collections.abc import Iterable
from typing import Any

from .models import FormatChoice


def is_video(fmt: dict[str, Any]) -> bool:
    return (
        fmt.get("vcodec") not in (None, "none")
        and bool(fmt.get("height"))
        and bool(fmt.get("format_id"))
        and not fmt.get("has_drm")
    )


def resolutions(formats: Iterable[dict[str, Any]]) -> list[int]:
    return sorted({int(f["height"]) for f in formats if is_video(f)}, reverse=True)


def default_resolution(heights: list[int]) -> int:
    if not heights:
        raise ValueError("No usable video streams are available.")
    return next((h for h in (1080, 720) if h in heights), max(heights))


def avc(codec: str | None) -> bool:
    return bool(codec and codec.lower().startswith(("avc", "h264")))


def aac(codec: str | None) -> bool:
    return bool(codec and codec.lower().startswith(("mp4a", "aac")))


def rank(fmt: dict[str, Any]) -> tuple[float, float]:
    return float(fmt.get("fps") or 0), float(fmt.get("tbr") or fmt.get("abr") or 0)


def select_format(formats: list[dict[str, Any]], height: int) -> FormatChoice:
    videos = [f for f in formats if is_video(f) and int(f["height"]) == height]
    if not videos:
        raise ValueError("The selected resolution is unavailable.")
    sdr = [f for f in videos if f.get("dynamic_range") in (None, "SDR")]
    videos = sdr or videos
    audios = [
        f
        for f in formats
        if f.get("vcodec") == "none"
        and f.get("acodec") not in (None, "none")
        and f.get("format_id")
        and not f.get("has_drm")
    ]
    compatible_audio = [f for f in audios if aac(f.get("acodec"))]
    compatible_video = [
        f
        for f in videos
        if avc(f.get("vcodec"))
        and (aac(f.get("acodec")) or (f.get("acodec") == "none" and compatible_audio))
    ]
    video = max(compatible_video or videos, key=rank)
    chosen = [video]
    if video.get("acodec") in (None, "none") and audios:
        chosen.append(
            max(compatible_audio or audios, key=lambda f: float(f.get("abr") or f.get("tbr") or 0))
        )
    # Video-only sources are supported; no artificial audio is added.
    transcode = not avc(video.get("vcodec")) or any(
        f.get("acodec") not in (None, "none") and not aac(f.get("acodec")) for f in chosen
    )
    return FormatChoice("+".join(str(f["format_id"]) for f in chosen), transcode)
