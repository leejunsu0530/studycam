import sys
import os
import threading
import time
from pathlib import Path
import cv2
import rich
from ._console import console


class Camera:
    def __init__(
            self,
            photo_path: str | Path,
            index: int = 0,
            fps: int = 30,
    ) -> None:
        """
        - 카메라 루프에 대한 제어
        - 찍은 사진에 대한 제어 및 관리
        - 스레드 처리 주의
        - 카메라 드라이버가 지원하는 해상도와 fps를 지정해야 함ㄴ

        - 카메라만 다루는 만큼 전체적인 파일들의 경로는 여기서 관리하지 않음.
        """
        self.cap = cv2.VideoCapture(index)

        if not self.cap.isOpened():
            raise RuntimeError("카메라를 열 수 없습니다.")

        self.fps = fps

        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            daemon=True,
        )
        self._thread.start()

    def _capture_loop(self):
        interval = 1 / self.fps

        while self._running:
            start = time.perf_counter()

            ret, frame = self.cap.read()

            if ret:
                with self._lock:
                    self._frame = frame

            elapsed = time.perf_counter() - start
            time.sleep(max(0, interval - elapsed))

    def read(self):
        with self._lock:
            if self._frame is None:
                return None

            return self._frame.copy()

    def stop(self):
        self._running = False

        if self._thread is not None:
            self._thread.join()

        self.cap.release()
