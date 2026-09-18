"""Explicit, cancellable FFmpeg conversion and final media validation."""

import json
import subprocess
from pathlib import Path
from threading import Event
from typing import Any

from .models import Cancelled, Mode, State
from .progress import Progress


def check_cancel(stop: Event) -> None:
    if stop.is_set():
        raise Cancelled("Interrupted")


def run_process(args: list[str], stop: Event, timeout: float | None = None) -> str:
    import time

    check_cancel(stop)
    started = time.monotonic()
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        while True:
            check_cancel(stop)
            if timeout is not None and time.monotonic() - started > timeout:
                raise RuntimeError("Media inspection timed out.")
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise RuntimeError(f"{Path(args[0]).name} failed: {stderr[-2000:]}")
        return stdout
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


def probe(path: Path, stop: Event) -> dict[str, Any]:
    return json.loads(
        run_process(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            stop,
            timeout=30,
        )
    )


def stream_types(info: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    streams = info.get("streams", [])
    return (
        [
            s
            for s in streams
            if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")
        ],
        [s for s in streams if s.get("codec_type") == "audio"],
    )


def normalize(source: Path, mode: Mode, stop: Event, progress: Progress, number: int) -> Path:
    videos, audios = stream_types(probe(source, stop))
    target = source.parent / ("ready.mp3" if mode == Mode.AUDIO else "ready.mp4")
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
    if mode == Mode.AUDIO:
        if not audios:
            raise ValueError("No usable audio stream.")
        progress.state(number, State.CONVERTING)
        args += ["-map", "0:a:0", "-vn", "-c:a", "libmp3lame", "-b:a", "192k"]
    else:
        if not videos:
            raise ValueError("No video stream.")
        copy_video = videos[0].get("codec_name") == "h264" and videos[0].get("pix_fmt") == "yuv420p"
        copy_audio = not audios or audios[0].get("codec_name") == "aac"
        progress.state(number, State.REMUXING if copy_video and copy_audio else State.TRANSCODING)
        args += ["-map", "0:V:0", "-map", "0:a:0?", "-c:v", "copy" if copy_video else "libx264"]
        if not copy_video:
            args += [
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            ]
        args += ["-c:a", "copy" if copy_audio else "aac"]
        if not copy_audio:
            args += ["-b:a", "192k"]
        args += ["-movflags", "+faststart"]
    args += ["-map_metadata", "-1", str(target)]
    run_process(args, stop)
    check_cancel(stop)
    final = probe(target, stop)
    final_videos, final_audios = stream_types(final)
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError("The final output is missing or empty.")
    if mode == Mode.AUDIO:
        if (
            not final_audios
            or final_audios[0].get("codec_name") != "mp3"
            or int(final_audios[0].get("bit_rate", 0)) != 192000
        ):
            raise RuntimeError("Final MP3 did not pass bitrate verification.")
    elif (
        not final_videos
        or final_videos[0].get("codec_name") != "h264"
        or any(s.get("codec_name") != "aac" for s in final_audios)
    ):
        raise RuntimeError("Final MP4 did not pass codec verification.")
    return target
