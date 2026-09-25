"""Camera capture and time-lapse assembly. The camera is opened only per capture."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2


class CameraService:
    def __init__(self, directory: Path | None = None, camera_index: int = 0) -> None:
        self.directory = directory or Path.home() / ".studycam" / "captures"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.camera_index = camera_index

    def capture(self) -> Path | None:
        """Take a single frame and immediately release the webcam."""
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        try:
            if not cap.isOpened():
                return None
            ok, frame = cap.read()
            if not ok:
                return None
            path = self.directory / f"{datetime.now():%Y%m%d_%H%M%S_%f}.jpg"
            cv2.imwrite(str(path), frame)
            return path
        finally:
            cap.release()

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
