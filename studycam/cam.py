"""Camera session and time-lapse assembly."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2


class CameraService:
    """Keeps the webcam open only while a recording session is active."""

    def __init__(self, directory: Path | None = None, camera_index: int = 0) -> None:
        self.directory = directory or Path.home() / ".studycam" / "captures"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.camera_index = camera_index
        self.cap: cv2.VideoCapture | None = None

    def start(self) -> bool:
        if self.cap is not None and self.cap.isOpened():
            return True
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FPS, 10)
        if self.cap.isOpened():
            return True
        self.stop()
        return False

    def read(self):
        """Read one frame. Call this at a modest rate (10 FPS in the UI)."""
        if self.cap is None or not self.cap.isOpened():
            return None
        ok, frame = self.cap.read()
        return frame if ok else None

    def save_frame(self, frame) -> Path | None:
        if frame is None:
            return None
        path = self.directory / f"{datetime.now():%Y%m%d_%H%M%S_%f}.jpg"
        return path if cv2.imwrite(str(path), frame) else None

    def stop(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def make_timelapse(self, images: list[Path], speed: int = 20) -> Path | None:
        valid = [path for path in images if path.exists()]
        if not valid:
            return None
        first = cv2.imread(str(valid[0]))
        if first is None:
            return None
        height, width = first.shape[:2]
        output = self.directory / f"study_{datetime.now():%Y%m%d_%H%M%S}.mp4"
        writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), max(1, speed), (width, height))
        try:
            for path in valid:
                frame = cv2.imread(str(path))
                if frame is not None:
                    writer.write(cv2.resize(frame, (width, height)))
        finally:
            writer.release()
        return output
