"""Camera session and time-lapse assembly."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2


class CameraService:
    """Keeps the webcam open only while a recording session is active."""

    def __init__(self, directory: Path | None = None, camera_index: int = 0, resolution: tuple[int, int] | None = None) -> None:
        self.directory = directory or Path.home() / ".studycam" / "captures"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.camera_index = camera_index
        self.resolution = resolution
        self.cap: cv2.VideoCapture | None = None

    def start(self) -> bool:
        if self.cap is not None and self.cap.isOpened():
            return True
        self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if self.resolution:
            width, height = self.resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
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

    def active_resolution(self) -> tuple[int, int] | None:
        """Return the resolution the camera actually accepted, if it is open."""
        if self.cap is None or not self.cap.isOpened():
            return None
        return (round(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)), round(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

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
        return self.make_timelapse_with_timestamp(images, speed)

    def make_timelapse_with_timestamp(self, images: list[Path], speed: int = 20, timestamp_format: str = "HH:MM") -> Path | None:
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
                    self._draw_timestamp(frame, path, timestamp_format)
                    writer.write(cv2.resize(frame, (width, height)))
        finally:
            writer.release()
        return output

    @staticmethod
    def _draw_timestamp(frame, path: Path, timestamp_format: str) -> None:
        try:
            captured = datetime.strptime(path.stem, "%Y%m%d_%H%M%S_%f")
        except ValueError:
            captured = datetime.now()
        CameraService.draw_timestamp(frame, captured, timestamp_format)

    @staticmethod
    def draw_timestamp(frame, captured: datetime, timestamp_format: str) -> None:
        """Draw the same clean timestamp used in the preview and final video."""
        if timestamp_format == "HH:MM:SS":
            label = captured.strftime("%H:%M:%S")
        elif timestamp_format == "12H":
            label = f"{'AM' if captured.hour < 12 else 'PM'} {(captured.hour - 1) % 12 + 1}:{captured:%M}"
        else:
            label = captured.strftime("%H:%M")
        _, width = frame.shape[:2]
        scale = max(0.8, width / 1150)
        thickness = max(1, round(scale * 1.5))
        (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        padding_x = max(14, round(width * 0.02))
        padding_y = max(12, round(width * 0.015))
        outer_margin = max(14, round(width * 0.02))
        left = width - text_width - padding_x * 2 - outer_margin
        top = outer_margin
        right = width - outer_margin
        bottom = top + text_height + padding_y * 2
        overlay = frame.copy()
        cv2.rectangle(overlay, (left, top), (right, bottom), (10, 10, 10), -1)
        cv2.addWeighted(overlay, 0.68, frame, 0.32, 0, frame)
        # The baseline places the visible glyphs exactly in the padded rectangle.
        cv2.putText(frame, label, (left + padding_x, bottom - padding_y), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    def combine_videos(self, videos: list[Path], output: Path) -> Path | None:
        """Combine same-day time-lapses into one video, preserving stamped frames."""
        valid = [video for video in videos if video.exists()]
        if not valid:
            return None
        first = cv2.VideoCapture(str(valid[0])); ok, frame = first.read()
        fps = first.get(cv2.CAP_PROP_FPS) or 20
        first.release()
        if not ok:
            return None
        height, width = frame.shape[:2]
        writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        try:
            for video in valid:
                capture = cv2.VideoCapture(str(video))
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    writer.write(cv2.resize(frame, (width, height)))
                capture.release()
        finally:
            writer.release()
        return output if output.exists() else None
