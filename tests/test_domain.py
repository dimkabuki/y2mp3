from io import StringIO

import pytest
from rich.console import Console

from y2mp3.cli import select
from y2mp3.diagnostics import redact
from y2mp3.downloader import reject_unsupported
from y2mp3.formats import default_resolution, resolutions, select_format
from y2mp3.input_parser import parse_urls
from y2mp3.models import Job, Mode, State, UnsupportedMedia, exit_code
from y2mp3.orchestration import worker_count
from y2mp3.paths import StorageError, output_path, publish, safe_name, storage_root, workspace
from y2mp3.progress import Progress


def fmt(name, height=None, video="avc1", audio="none", fps=30, **extra):
    return dict(format_id=name, height=height, vcodec=video, acodec=audio, fps=fps, **extra)


@pytest.mark.parametrize("separator", [",", " ", "\n", ",\n  "])
def test_url_order_and_duplicates(separator):
    assert parse_urls(
        separator.join(["https://a.test/1", "http://b.test/2", "https://a.test/1"])
    ) == ["https://a.test/1", "http://b.test/2", "https://a.test/1"]


@pytest.mark.parametrize(
    "value",
    [
        "",
        " \n, ",
        "ftp://a.test/x",
        "file:///etc/passwd",
        "https://",
        "https://user:password@a.test/x",
        "https://[broken",
        "https://a.test:bad",
    ],
)
def test_invalid_urls(value):
    with pytest.raises(ValueError):
        parse_urls(value)


def test_resolution_policy_and_deduplication():
    formats = [
        fmt("1", 720),
        fmt("2", 1080),
        fmt("3", 1080),
        fmt("4", 2160),
        fmt("drm", 4320, has_drm=True),
    ]
    assert resolutions(formats) == [2160, 1080, 720]
    assert default_resolution(resolutions(formats)) == 1080
    assert default_resolution([2160, 720]) == 720
    assert default_resolution([480, 2160]) == 2160
    with pytest.raises(ValueError):
        default_resolution([])


def test_compatible_streams_preferred_over_higher_fps_vp9():
    formats = [
        fmt("avc", 1080),
        fmt("vp9", 1080, "vp9", fps=60),
        fmt("aac", video="none", audio="mp4a.40.2", abr=128),
        fmt("opus", video="none", audio="opus", abr=160),
    ]
    choice = select_format(formats, 1080)
    assert choice.selector == "avc+aac"
    assert not choice.transcode


def test_sdr_preferred_and_transcoding_required():
    formats = [
        fmt("hdr", 1080, "avc1", "aac", dynamic_range="HDR10"),
        fmt("sdr", 1080, "vp9", "opus", dynamic_range="SDR"),
    ]
    choice = select_format(formats, 1080)
    assert choice.selector == "sdr"
    assert choice.transcode


def test_best_fps_and_muxed_formats():
    choice = select_format([fmt("30", 720, audio="aac"), fmt("60", 720, audio="aac", fps=60)], 720)
    assert choice.selector == "60"
    assert not choice.transcode
    with pytest.raises(ValueError):
        select_format([fmt("30", 720)], 1080)


def test_storage_requires_setup(tmp_path):
    with pytest.raises(StorageError, match="termux-setup-storage"):
        storage_root(home=tmp_path)
    downloads = tmp_path / "storage/downloads"
    downloads.mkdir(parents=True)
    assert storage_root(home=tmp_path) == downloads / "y2mp3"
    assert storage_root(tmp_path / "custom") == tmp_path / "custom"


@pytest.mark.parametrize("mode,extension", [(Mode.AUDIO, "mp3"), (Mode.VIDEO, "mp4")])
def test_playlist_paths_unicode_and_traversal(tmp_path, mode, extension):
    job = Job(
        1,
        "https://x.test",
        mode,
        title="Песня/楽曲\x1b",
        media_id="id",
        playlist="../Album",
        playlist_id="PL1",
        playlist_index=2,
        playlist_size=1234,
    )
    target = output_path(tmp_path, job)
    assert target.suffix == f".{extension}"
    assert target.name.startswith("0002 - Песня_楽曲_")
    assert target.parent.parent == tmp_path / mode.value
    assert len(safe_name("😀" * 200).encode()) <= 100
    assert "/" not in safe_name("../x")
    job.playlist = None
    assert output_path(tmp_path, job).parent == tmp_path / mode.value


def test_publish_never_overwrites_and_duplicates_are_distinct(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"new")
    target = tmp_path / "video" / "name.mp4"
    target.parent.mkdir()
    target.write_bytes(b"old")
    result = publish(source, target)
    assert target.read_bytes() == b"old"
    assert result.read_bytes() == b"new"
    assert result.name == "name (2).mp4"
    first = Job(1, "https://x.test", Mode.AUDIO)
    second = Job(2, "https://x.test", Mode.AUDIO)
    assert workspace(tmp_path, first) != workspace(tmp_path, second)
    assert workspace(tmp_path, first) == workspace(tmp_path, first)


@pytest.mark.parametrize(
    "text,total,expected", [("", 5, 2), ("", 1, 1), ("8", 3, 3), ("1", 5, 1), ("", 0, 0)]
)
def test_worker_defaults_and_bounds(text, total, expected):
    assert worker_count(text, total) == expected


@pytest.mark.parametrize("text", ["0", "-1", "x", "1.5"])
def test_worker_invalid(text):
    with pytest.raises(ValueError):
        worker_count(text, 3)


@pytest.mark.parametrize(
    "state,expected",
    [(State.COMPLETED, 0), (State.FAILED, 1), (State.SKIPPED, 1), (State.CANCELLED, 130)],
)
def test_exit_status(state, expected):
    assert exit_code([Job(1, "https://x.test", Mode.AUDIO, state=state)]) == expected


@pytest.mark.parametrize(
    "info",
    [
        {"is_live": True},
        {"live_status": "is_upcoming"},
        {"live_status": "post_live"},
        {"availability": "private"},
        {"has_drm": True},
    ],
)
def test_unsupported(info):
    with pytest.raises(UnsupportedMedia):
        reject_unsupported(info)


def test_archived_stream_accepted():
    reject_unsupported({"is_live": False, "live_status": "was_live"})


def test_progress_finishing_download_is_not_completion():
    progress = Progress()
    progress.download(
        1,
        {
            "status": "downloading",
            "downloaded_bytes": 25,
            "total_bytes": 100,
            "speed": 20,
            "eta": 4,
        },
    )
    snapshot = progress.snapshots()[1]
    assert snapshot.total == 100 and snapshot.downloaded == 25
    progress.download(1, {"status": "finished"})
    assert progress.snapshots()[1].state == State.PROCESSING
    progress.postprocess(1, {"status": "started", "postprocessor": "Merger"})
    assert progress.snapshots()[1].state == State.MERGING
    progress.postprocess(1, {"status": "finished", "postprocessor": "Merger"})
    assert progress.snapshots()[1].state != State.COMPLETED


def test_default_mode_and_invalid_prompt(monkeypatch):
    answers = iter(["oops", "", "2"])
    console = Console(file=StringIO())
    monkeypatch.setattr(console, "input", lambda prompt: next(answers))
    assert select(console, "Mode", ["Audio", "Video"]) == 0
    assert select(console, "Mode", ["Audio", "Video"]) == 1


def test_diagnostics_redact_urls_and_tokens():
    assert "secret" not in redact("https://user:secret@example.test?a=secret")
    assert "abcdef" not in redact("Authorization: Bearer token=abcdef")
