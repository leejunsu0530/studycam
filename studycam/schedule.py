"""Persistent local data for StudyCam."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

DEFAULT_DATA: dict[str, Any] = {
    "tasks": {}, "subjects": [], "schedule": [], "started_on": date.today().isoformat(), "study_seconds": {},
    "settings": {"study_minutes": 50, "break_minutes": 10, "capture_seconds": 30, "speed": 20, "camera_resolution": "1280x720", "storage_dir": str(Path.home() / ".studycam" / "media"), "capture_dir": str(Path.home() / ".studycam" / "captures"), "auto_cleanup_captures": True, "alarm_enabled": True, "alarm_volume": 70, "completed_color": "#dce8ff", "failed_color": "#ffd9d9", "start_maximized": False, "pomodoro_with_camera": False, "prevent_home_close": False, "prevent_studio_close": False, "timestamp_format": "HH:MM", "timestamp_background_color": "#0a0a0a", "timestamp_text_color": "#ffffff", "timestamp_font": "simplex", "timestamp_size": 100, "day_lock_hour": 12, "youtube_auto_upload": False, "youtube_client_secret": "", "youtube_title_template": "StudyCam {date}", "youtube_privacy": "private"},
    "videos": {}, "daily_videos": {}, "youtube_uploads": {},
}


class StudyStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".studycam" / "studycam.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            merged = deepcopy(DEFAULT_DATA)
            merged.update(saved)
            merged["settings"] = {**DEFAULT_DATA["settings"], **saved.get("settings", {})}
            if saved.get("settings", {}).get("prevent_window_close"):
                merged["settings"]["prevent_home_close"] = True
                merged["settings"]["prevent_studio_close"] = True
            for tasks in merged["tasks"].values():
                tasks[:] = [task for task in tasks if task.get("system") != "daily_study_time"]
            return merged
        except (OSError, json.JSONDecodeError):
            return deepcopy(DEFAULT_DATA)

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def key(day: date) -> str: return day.isoformat()

    def tasks_for(self, day: date) -> list[dict[str, Any]]: return self.data["tasks"].setdefault(self.key(day), [])

    def add_task(self, day: date, subject: str, text: str, kind: str = "복습") -> None:
        self.tasks_for(day).append({"subject": subject.strip() or "과목", "text": text.strip(), "kind": kind, "done": False})
        self.save()

    def update_tasks(self, day: date, tasks: list[dict[str, Any]]) -> None:
        self.data["tasks"][self.key(day)] = tasks
        self.save()

    def completed(self, day: date) -> bool:
        tasks = self.data["tasks"].get(self.key(day), [])
        return bool(tasks) and all(task.get("done") for task in tasks)

    def is_day_locked(self, day: date, now: datetime | None = None) -> bool:
        """A day's planner locks at the configured hour on the following day."""
        now = now or datetime.now()
        hour = int(self.data["settings"]["day_lock_hour"])
        return now >= datetime.combine(day + timedelta(days=1), time(hour=hour))

    def study_seconds_for(self, day: date) -> int:
        return int(self.data["study_seconds"].get(self.key(day), 0))

    def add_study_seconds(self, day: date, seconds: int) -> None:
        if seconds <= 0:
            return
        key = self.key(day)
        self.data["study_seconds"][key] = self.study_seconds_for(day) + seconds
        self.save()

    def streak(self, until: date | None = None) -> int:
        cursor, count = until or date.today(), 0
        from datetime import timedelta
        while self.completed(cursor):
            count += 1
            cursor -= timedelta(days=1)
        return count

    def save_settings(self, **settings: Any) -> None:
        """Persist complete settings while preserving migration defaults."""
        self.data["settings"] = {**DEFAULT_DATA["settings"], **settings}
        self.save()
