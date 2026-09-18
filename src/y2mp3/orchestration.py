"""Bounded in-flight work, failure isolation, and cooperative cancellation."""

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from threading import Event

from .diagnostics import LOG, failure_message, redact
from .models import Cancelled, Job, State, UnsupportedMedia, exit_code
from .progress import Progress


def worker_count(text: str, total: int) -> int:
    if total <= 0:
        return 0
    try:
        value = int(text) if text.strip() else min(2, total)
    except ValueError as exc:
        raise ValueError("Enter a positive whole number.") from exc
    if value <= 0:
        raise ValueError("Enter a positive whole number.")
    return min(value, total)


def run_jobs(
    jobs: list[Job],
    workers: int,
    download: Callable,
    stop: Event,
    progress: Progress,
    refresh: Callable[[], None] = lambda: None,
) -> int:
    pending = iter(job for job in jobs if job.state == State.QUEUED)

    def execute(job: Job) -> None:
        try:
            if stop.is_set():
                raise Cancelled()
            job.output = download(job)
            job.state = State.COMPLETED
        except (Cancelled, KeyboardInterrupt):
            job.state = State.CANCELLED
        except UnsupportedMedia as exc:
            job.state, job.message = State.SKIPPED, str(exc)
        except Exception as exc:
            job.state, job.message = State.FAILED, failure_message(exc)
            LOG.debug("job %s failed: %s", job.number, redact(exc))
        progress.state(job.number, job.state)

    if workers < 1:
        return exit_code(jobs)
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="y2mp3")
    active: set = set()
    try:
        for _ in range(workers):
            job = next(pending, None)
            if job is not None:
                active.add(pool.submit(execute, job))
        while active:
            done, active = wait(active, timeout=0.1, return_when=FIRST_COMPLETED)
            for future in done:
                future.result()
                if not stop.is_set():
                    job = next(pending, None)
                    if job is not None:
                        active.add(pool.submit(execute, job))
            refresh()
    except KeyboardInterrupt:
        stop.set()
    finally:
        # Hooks stop downloads, explicit FFmpeg subprocesses poll the event. In-flight
        # yt-dlp metadata/merge calls may need to return before workers can finish.
        pool.shutdown(wait=True, cancel_futures=True)
        if stop.is_set():
            for job in jobs:
                if job.state in {State.QUEUED, State.INSPECTING}:
                    job.state = State.CANCELLED
                    progress.state(job.number, State.CANCELLED)
        refresh()
    return 130 if stop.is_set() else exit_code(jobs)
