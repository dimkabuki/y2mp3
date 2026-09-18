"""Exercise real FFmpeg and yt-dlp against generated, local-only media."""

from copy import deepcopy
from threading import Event, Timer

import pytest
from yt_dlp import YoutubeDL

from y2mp3.downloader import Downloader
from y2mp3.media import normalize, probe, run_process, stream_types
from y2mp3.models import Cancelled, FormatChoice, Job, Mode, State
from y2mp3.orchestration import run_jobs
from y2mp3.progress import Progress


@pytest.fixture
def synthetic(tmp_path):
    def create(name, video=None, audio="aac", bitrate=None):
        path = tmp_path / name
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]
        if video:
            command += ["-f", "lavfi", "-i", "color=c=blue:s=160x120:r=10"]
        if audio:
            command += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100"]
        command += ["-t", "0.4"]
        if video:
            command += ["-c:v", video, "-pix_fmt", "yuv420p", "-threads", "1"]
        if audio:
            command += ["-c:a", audio]
        if bitrate:
            command += ["-b:a", bitrate]
        run_process(command + [str(path)], Event())
        return path

    return create


def test_mp3_source_is_reencoded_to_192kbps(synthetic):
    original = synthetic("quiet.mp3", audio="libmp3lame", bitrate="64k")
    result = normalize(original, Mode.AUDIO, Event(), Progress(), 1)
    assert result.suffix == ".mp3"
    streams = probe(result, Event())["streams"]
    assert int(streams[0]["bit_rate"]) == 192000


def test_h264_aac_is_remuxed_without_reencoding(synthetic):
    original = synthetic("compatible.mkv", video="libx264")
    progress = Progress()
    result = normalize(original, Mode.VIDEO, Event(), progress, 1)
    assert result.suffix == ".mp4"
    assert progress.snapshots()[1].state == State.REMUXING

    # Compare decoded video frame hashes as an independent check for unchanged picture data.
    def frames(path):
        return run_process(
            ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v", "-f", "framemd5", "-"],
            Event(),
        ).splitlines()[-4:]

    assert frames(original) == frames(result)


def test_vp9_opus_is_transcoded_to_h264_aac(synthetic):
    original = synthetic("incompatible.webm", video="libvpx-vp9", audio="libopus")
    progress = Progress()
    result = normalize(original, Mode.VIDEO, Event(), progress, 1)
    video, audio = stream_types(probe(result, Event()))
    assert video[0]["codec_name"] == "h264"
    assert video[0]["pix_fmt"] == "yuv420p"
    assert audio[0]["codec_name"] == "aac"
    assert progress.snapshots()[1].state == State.TRANSCODING


def test_video_without_audio_is_valid(synthetic):
    source = synthetic("silent.mp4", video="libx264", audio=None)
    result = normalize(source, Mode.VIDEO, Event(), Progress(), 1)
    video, audio = stream_types(probe(result, Event()))
    assert video and not audio


def test_cancellation_terminates_running_subprocess():
    import sys

    stop = Event()
    timer = Timer(0.2, stop.set)
    timer.start()
    try:
        with pytest.raises(Cancelled):
            run_process([sys.executable, "-c", "import time; time.sleep(30)"], stop)
    finally:
        timer.cancel()


def local_factory(info):
    class LocalYDL(YoutubeDL):
        def __init__(self, params):
            # File URLs are enabled ONLY by this test adapter; production rejects them.
            super().__init__(params | {"enable_file_urls": True})

        def extract_info(self, url, download=True):
            return self.process_ie_result(deepcopy(info), download=download)

    return LocalYDL


def test_real_ytdlp_audio_adapter_and_postprocessor_path(synthetic, tmp_path):
    original = synthetic("original.wav", audio="pcm_s16le")
    info = dict(
        id="audio1",
        title="Local sample",
        extractor="test",
        webpage_url="https://example.test/1",
        url=original.as_uri(),
        ext="wav",
        vcodec="none",
        acodec="pcm_s16le",
    )
    stop, progress = Event(), Progress()
    engine = Downloader(stop, progress, local_factory(info))
    job = Job(
        1,
        "https://example.test/1",
        Mode.AUDIO,
        title="Local sample",
        media_id="audio1",
        state=State.QUEUED,
    )
    assert (
        run_jobs([job], 1, lambda j: engine.download(j, tmp_path / "output"), stop, progress) == 0
    )
    assert job.output.is_file() and job.output.suffix == ".mp3"
    assert progress.snapshots()[1].state == State.COMPLETED


def test_real_ytdlp_separate_stream_merge(synthetic, tmp_path):
    video = synthetic("video.mp4", video="libx264", audio=None)
    audio = synthetic("audio.m4a")
    info = dict(
        id="video1",
        title="Merge sample",
        extractor="test",
        formats=[
            dict(
                format_id="v",
                url=video.as_uri(),
                ext="mp4",
                vcodec="avc1",
                acodec="none",
                height=120,
            ),
            dict(format_id="a", url=audio.as_uri(), ext="m4a", vcodec="none", acodec="mp4a.40.2"),
        ],
    )
    stop, progress = Event(), Progress()
    engine = Downloader(stop, progress, local_factory(info))
    job = Job(
        1,
        "https://example.test/1",
        Mode.VIDEO,
        title="Merge sample",
        media_id="video1",
        resolution=120,
        choice=FormatChoice("v+a", False),
    )
    result = engine.download(job, tmp_path / "output")
    assert result.suffix == ".mp4"
    videos, audios = stream_types(probe(result, stop))
    assert videos[0]["codec_name"] == "h264" and audios[0]["codec_name"] == "aac"


def test_failed_conversion_never_publishes(synthetic, tmp_path, monkeypatch):
    original = synthetic("source.wav", audio="pcm_s16le")
    info = dict(
        id="bad",
        title="Bad",
        extractor="test",
        url=original.as_uri(),
        ext="wav",
        vcodec="none",
        acodec="pcm_s16le",
    )
    stop, progress = Event(), Progress()
    engine = Downloader(stop, progress, local_factory(info))
    job = Job(1, "https://example.test/1", Mode.AUDIO, state=State.QUEUED)

    def fail(*args):
        raise RuntimeError("FFmpeg failed")

    monkeypatch.setattr("y2mp3.downloader.normalize", fail)
    root = tmp_path / "output"
    assert run_jobs([job], 1, lambda j: engine.download(j, root), stop, progress) == 1
    assert job.output is None and not (root / "audio").exists()
    assert list((root / ".partial").rglob("source.wav"))


def test_real_ytdlp_flat_playlist_keeps_live_entry():
    info = dict(
        _type="playlist",
        id="pl",
        title="Playlist",
        extractor="test",
        extractor_key="Test",
        entries=[
            dict(_type="url", url="https://example.test/live", id="live", is_live=True),
            dict(_type="url", url="https://example.test/good", id="good"),
        ],
    )
    engine = Downloader(Event(), Progress(), local_factory(info))
    expanded = engine.expand("https://example.test/playlist")
    assert [entry["id"] for entry in expanded["entries"]] == ["live", "good"]


def test_resume_after_postprocessing_failure_uses_downloaded_source(
    synthetic, tmp_path, monkeypatch
):
    source = synthetic("resume.wav", audio="pcm_s16le")
    info = dict(
        id="resume",
        title="Resume sample",
        extractor="test",
        url=source.as_uri(),
        ext="wav",
        vcodec="none",
        acodec="pcm_s16le",
    )
    stop, progress = Event(), Progress()
    engine = Downloader(stop, progress, local_factory(info))
    job = Job(1, "https://example.test/resume", Mode.AUDIO, media_id="resume", title="Resume")
    root = tmp_path / "output%with-template-characters"
    with monkeypatch.context() as patch:

        def fail(*args):
            raise RuntimeError("Simulated conversion error")

        patch.setattr("y2mp3.downloader.normalize", fail)
        with pytest.raises(RuntimeError, match="Simulated"):
            engine.download(job, root)
    # Remove the remote source: completing the second attempt proves reuse of the local download.
    source.unlink()
    result = engine.download(job, root)
    assert result.is_file() and result.suffix == ".mp3"
