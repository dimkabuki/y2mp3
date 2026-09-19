"""Phone-friendly numbered prompts and compact live progress."""

import argparse
import logging
import shutil
from collections import Counter
from pathlib import Path
from threading import Event

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from .diagnostics import LOG, redact
from .downloader import Downloader
from .input_parser import parse_urls
from .models import Cancelled, Job, Mode, State, exit_code
from .orchestration import run_jobs, worker_count
from .paths import StorageError, storage_root
from .planning import plan_jobs
from .progress import Progress


def select(console: Console, heading: str, options: list[str], default: int = 0) -> int:
    console.print(heading, markup=False)
    for index, option in enumerate(options):
        console.print(
            f"  {index + 1}. {option}" + (" (default)" if index == default else ""), markup=False
        )
    while True:
        value = console.input("> ").strip()
        if not value:
            return default
        if value.isdecimal() and 1 <= int(value) <= len(options):
            return int(value) - 1
        console.print(f"Choose a number from 1 to {len(options)}.", markup=False)


def ask_urls(console: Console) -> list[str]:
    while True:
        console.print(
            "Paste URLs separated by commas, spaces, or new lines.\n"
            "Submit an empty line when finished."
        )
        lines = []
        while True:
            line = console.input("> ")
            if not line.strip():
                break
            lines.append(line)
        try:
            return parse_urls("\n".join(lines))
        except ValueError as exc:
            console.print(str(exc), style="red", markup=False)


def choose_quality(console: Console, job: Job, heights: list[int], default: int) -> int:
    index = select(
        console,
        f"Video {job.number}: {job.title}",
        [f"{h}p" for h in heights],
        heights.index(default),
    )
    return heights[index]


def render(jobs: list[Job], progress: Progress, width: int) -> Table:
    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(ratio=1)
    snapshots = progress.snapshots()
    for job in jobs:
        snapshot = snapshots.get(job.number)
        state = snapshot.state if snapshot else job.state
        if state in {State.COMPLETED, State.FAILED, State.SKIPPED, State.CANCELLED}:
            continue
        title = job.title or "Media item"
        line = Text(f"[{job.number}/{len(jobs)}] {title}", overflow="ellipsis", no_wrap=True)
        table.add_row(line)
        status = state.value
        if snapshot and state == State.DOWNLOADING:
            done = snapshot.downloaded / 1048576
            if snapshot.total:
                percent = min(100, 100 * snapshot.downloaded / snapshot.total)
                status += f" {percent:.0f}% {done:.1f}/{snapshot.total / 1048576:.1f} MiB"
            else:
                status += f" {done:.1f} MiB"
            if snapshot.speed:
                status += f" {snapshot.speed / 1048576:.1f} MiB/s"
            if snapshot.eta is not None:
                status += f" ETA {int(snapshot.eta)}s"
        table.add_row(Text(status, style="cyan"))
    counts = Counter(job.state for job in jobs)
    table.add_row(
        Text(
            f"Completed {counts[State.COMPLETED]}/{len(jobs)} · "
            f"Failed {counts[State.FAILED]} · Skipped {counts[State.SKIPPED]}"
        )
    )
    return table


def summary(console: Console, jobs: list[Job]) -> None:
    counts = Counter(job.state for job in jobs)
    console.print("\nSummary", style="bold")
    console.print(
        f"Successful: {counts[State.COMPLETED]}  Failed: {counts[State.FAILED]}  "
        f"Skipped: {counts[State.SKIPPED]}  Cancelled: {counts[State.CANCELLED]}"
    )
    for job in jobs:
        console.print(
            f"[{job.number}] {job.state.value}: {job.output or job.title or 'Media item'}",
            markup=False,
            highlight=False,
        )
        if job.message:
            console.print(f"  {job.message}", markup=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="y2mp3", description="Interactive public audio/video downloads for Termux."
    )
    parser.add_argument("--version", action="version", version=f"y2mp3 {__version__}")
    parser.add_argument(
        "--output-dir", type=Path, help="Output root (for desktop development or custom storage)."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Write redacted diagnostics to stderr."
    )
    args = parser.parse_args(argv)
    console = Console(highlight=False)
    stop = Event()
    jobs: list[Job] = []
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    LOG.addHandler(handler)
    LOG.setLevel(logging.DEBUG if args.verbose else logging.CRITICAL)
    LOG.propagate = False
    try:
        root = storage_root(args.output_dir)
        missing = [name for name in ("ffmpeg", "ffprobe", "deno") if shutil.which(name) is None]
        if missing:
            raise StorageError(
                f"Missing required tools: {', '.join(missing)}. In Termux, run: "
                "pkg install ffmpeg deno python-yt-dlp yt-dlp-ejs"
            )
        console.print(Panel("y2mp3\nDownload audio or video", expand=False))
        mode = [Mode.AUDIO, Mode.VIDEO][
            select(console, "What would you like to download?", ["Audio", "Video"])
        ]
        urls = ask_urls(console)
        progress = Progress()
        engine = Downloader(stop, progress)
        jobs = plan_jobs(
            urls,
            mode,
            engine,
            lambda job, heights, default: choose_quality(console, job, heights, default),
            lambda text: console.print(text, markup=False),
        )
        queued = sum(job.state == State.QUEUED for job in jobs)
        if queued:
            parallel = select(console, "Processing mode:", ["Sequential", "Parallel"])
            workers = 1
            if parallel:
                while True:
                    try:
                        workers = worker_count(
                            console.input(
                                f"Workers [default {min(2, queued)}, maximum {queued}]: "
                            ),
                            queued,
                        )
                        break
                    except ValueError as exc:
                        console.print(str(exc), markup=False)
            # All prompts have ended before Live or any worker thread starts.
            with Live(
                console=console, auto_refresh=False, transient=True, vertical_overflow="ellipsis"
            ) as live:

                def refresh() -> None:
                    live.update(render(jobs, progress, console.width), refresh=True)

                refresh()
                result = run_jobs(
                    jobs, workers, lambda job: engine.download(job, root), stop, progress, refresh
                )
        else:
            result = exit_code(jobs)
        summary(console, jobs)
        return result
    except (KeyboardInterrupt, Cancelled):
        stop.set()
        console.print(
            "\nInterrupted. Partial downloads are retained; "
            "repeat the same inputs and quality to resume."
        )
        return 130
    except EOFError:
        console.print("\nInput ended before planning was complete.")
        return 2
    except (StorageError, OSError) as exc:
        console.print(str(exc), style="red", markup=False)
        return 2
    except Exception as exc:
        LOG.debug("startup failure: %s", redact(exc))
        console.print("Unable to start. Use --verbose for diagnostics.", style="red")
        return 2
    finally:
        LOG.removeHandler(handler)
        handler.close()
