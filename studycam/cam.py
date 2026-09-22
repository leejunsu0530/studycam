import sys
import os
from pathlib import Path
import cv2
import rich
from ._console import console


class Camera:
    def __init__(
        self,
        photo_path: str | Path
    ) -> None:
        """
        - 카메라 루프에 대한 제어
        - 찍은 사진에 대한 제어 및 관리
        - 스레드 처리 주의

        - 카메라만 다루는 만큼 전체적인 파일들의 경로는 여기서 관리하지 않음.
        """
        self.photo_path = Path(photo_path)

    def save_photo(self):
        pass
