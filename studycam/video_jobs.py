"""Recoverable, serial background processing of daily video merges."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .cam import CameraService


class DailyVideoJobs(QObject):
    finished = Signal(str, object, object, str)
    updated = Signal()
    failed_notice = Signal(str, str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.active = False
        self.failed = set()
        self.finished.connect(self._finished)
        self.store.data.setdefault("pending_merges", {})

    def enqueue(self, key):
        videos = list(self.store.data["videos"].get(key, []))
        if not videos:
            return
        self.store.data["pending_merges"][key] = videos
        self.failed.discard(key)
        self.store.save()
        self.resume()

    def resume(self):
        if self.active:
            return
        pending = self.store.data["pending_merges"]
        key = next((key for key in pending if key not in self.failed), None)
        if key is None:
            return
        self.active = True
        videos = list(pending[key])
        settings = self.store.data["settings"]
        directory = Path(settings["storage_dir"])
        capture = Path(settings["capture_dir"])
        threading.Thread(target=self._merge, args=(key, videos, directory, capture), daemon=False).start()

    def _merge(self, key, videos, directory, capture):
        output = directory / ("daily_" + key.replace("-", "") + ".mp4")
        temporary = directory / ("daily_" + key.replace("-", "") + ".pending.mp4")
        error = ""
        try:
            if not all(Path(path).is_file() for path in videos):
                raise FileNotFoundError("A source video is missing")
            camera = CameraService(capture, directory)
            if not camera.combine_videos([Path(path) for path in videos], temporary):
                raise RuntimeError("Could not create the daily video")
            temporary.replace(output)
        except Exception as exc:
            error = str(exc)
        try:
            self.finished.emit(key, videos, str(output), error)
        except RuntimeError:
            # The GUI has exited. The persisted job is retried next time.
            pass

    def _finished(self, key, videos, output, error):
        self.active = False
        pending = self.store.data["pending_merges"]
        if error:
            self.failed.add(key)
            self.failed_notice.emit(key, error)
        else:
            self.store.data["daily_videos"][key] = output
            if pending.get(key) == videos:
                pending.pop(key, None)
            self.store.save()
            self.updated.emit()
        self.resume()
