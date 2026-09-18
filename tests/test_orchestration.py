from pathlib import Path
from threading import Barrier, Event, Lock

from y2mp3.models import Cancelled, Job, Mode, State
from y2mp3.orchestration import run_jobs
from y2mp3.progress import Progress


def queued(count):
    return [
        Job(i, f"https://example.test/{i}", Mode.AUDIO, state=State.QUEUED)
        for i in range(1, count + 1)
    ]


def test_five_jobs_two_workers_and_failure_isolation():
    jobs = queued(5)
    lock = Lock()
    barrier = Barrier(2)
    current = peak = 0
    seen = []

    def download(job):
        nonlocal current, peak
        with lock:
            current += 1
            peak = max(peak, current)
            seen.append(job.number)
        try:
            if job.number <= 2:
                barrier.wait(timeout=3)
            if job.number == 2:
                raise RuntimeError("Network failure")
            return Path(f"{job.number}.mp3")
        finally:
            with lock:
                current -= 1

    assert run_jobs(jobs, 2, download, Event(), Progress()) == 1
    assert sorted(seen) == [1, 2, 3, 4, 5]
    assert peak == 2
    assert jobs[1].state == State.FAILED
    assert sum(j.state == State.COMPLETED for j in jobs) == 4


def test_cancel_does_not_start_more_jobs():
    jobs = queued(5)
    stop = Event()
    seen = []

    def download(job):
        seen.append(job.number)
        stop.set()
        raise Cancelled()

    assert run_jobs(jobs, 1, download, stop, Progress()) == 130
    assert seen == [1]
    assert all(j.state == State.CANCELLED for j in jobs)


def test_keyboard_interrupt_stops_active_workers_and_keeps_completed():
    jobs = queued(3)
    stop = Event()
    started = Event()

    def download(job):
        started.set()
        while not stop.wait(0.01):
            pass
        raise Cancelled()

    def refresh():
        if not stop.is_set():
            assert started.wait(1)
            raise KeyboardInterrupt

    assert run_jobs(jobs, 1, download, stop, Progress(), refresh) == 130
    assert all(j.state == State.CANCELLED for j in jobs)
