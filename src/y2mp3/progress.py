"""Thread-safe progress snapshots; terminal rendering happens on the main thread."""

from dataclasses import dataclass, replace
from threading import Lock
from typing import Any

from .models import State


@dataclass
class Snapshot:
    state: State = State.QUEUED
    downloaded: int = 0
    total: int | None = None
    speed: float | None = None
    eta: float | None = None


class Progress:
    def __init__(self) -> None:
        self._lock = Lock()
        self._items: dict[int, Snapshot] = {}

    def state(self, number: int, state: State) -> None:
        with self._lock:
            self._items[number] = Snapshot(state=state)

    def download(self, number: int, data: dict[str, Any]) -> None:
        state = {
            "downloading": State.DOWNLOADING,
            "finished": State.PROCESSING,
            "error": State.FAILED,
        }.get(data.get("status"))
        if state is None:
            return
        with self._lock:
            self._items[number] = Snapshot(
                state,
                data.get("downloaded_bytes") or 0,
                data.get("total_bytes") or data.get("total_bytes_estimate"),
                data.get("speed"),
                data.get("eta"),
            )

    def postprocess(self, number: int, data: dict[str, Any]) -> None:
        if data.get("status") not in {"started", "processing"}:
            return
        name = data.get("postprocessor", "")
        state = State.MERGING if "Merger" in name else State.PROCESSING
        self.state(number, state)

    def snapshots(self) -> dict[int, Snapshot]:
        with self._lock:
            return {number: replace(value) for number, value in self._items.items()}
