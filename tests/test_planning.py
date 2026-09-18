from threading import Event

from y2mp3.models import Mode, State
from y2mp3.planning import plan_jobs


def metadata(key):
    return {
        "id": key,
        "title": f"Title {key}",
        "formats": [
            {"format_id": "720", "height": 720, "vcodec": "avc1", "acodec": "aac"},
            {"format_id": "1080", "height": 1080, "vcodec": "avc1", "acodec": "aac"},
        ],
    }


class FakeEngine:
    def __init__(self):
        self.inspected = []
        self.stop = Event()

    def expand(self, url):
        if url.endswith("/playlist"):
            return {
                "_type": "playlist",
                "id": "PL",
                "title": "Album",
                "entries": [
                    {"_type": "url", "url": "https://example.test/1"},
                    None,
                    {"_type": "url", "url": "https://example.test/live"},
                    {"_type": "url", "url": "https://example.test/bad"},
                    {"_type": "url", "url": "https://example.test/2"},
                ],
            }
        if url.endswith("/empty"):
            return {"_type": "playlist", "entries": []}
        return metadata(url.rsplit("/", 1)[-1])

    def inspect(self, url):
        self.inspected.append(url)
        if url.endswith("/bad"):
            raise RuntimeError("Unavailable")
        info = metadata(url.rsplit("/", 1)[-1])
        if url.endswith("/live"):
            info["is_live"] = True
        return info


def test_mixed_playlist_expansion_prompts_and_order():
    engine = FakeEngine()
    prompts = []

    def choose(job, heights, default):
        prompts.append((job.number, job.media_id, default))
        return 720

    jobs = plan_jobs(
        ["https://example.test/start", "https://example.test/playlist", "https://example.test/end"],
        Mode.VIDEO,
        engine,
        choose,
    )
    assert len(jobs) == 7
    assert [(j.media_id, j.resolution) for j in jobs if j.state == State.QUEUED] == [
        ("start", 720),
        ("1", 720),
        ("2", 720),
        ("end", 720),
    ]
    assert prompts == [(1, "start", 1080), (2, "1", 1080), (6, "2", 1080), (7, "end", 1080)]
    assert [j.playlist_index for j in jobs[1:6]] == [1, 2, 3, 4, 5]
    assert jobs[2].state == State.SKIPPED
    assert jobs[3].state == State.SKIPPED
    assert jobs[4].state == State.FAILED


def test_audio_never_prompts_and_empty_playlist_does_not_stop_inputs():
    def unexpected(*args):
        raise AssertionError("Audio should not ask for quality")

    jobs = plan_jobs(
        ["https://example.test/empty", "https://example.test/playlist", "https://example.test/end"],
        Mode.AUDIO,
        FakeEngine(),
        unexpected,
    )
    assert jobs[0].state == State.FAILED
    assert jobs[-1].state == State.QUEUED
    assert sum(j.state == State.QUEUED for j in jobs) == 3


def test_flat_youtube_ids_resolve_to_watch_urls():
    from y2mp3.planning import entry_url

    assert (
        entry_url({"id": "abc123", "url": "abc123", "ie_key": "Youtube"})
        == "https://www.youtube.com/watch?v=abc123"
    )
