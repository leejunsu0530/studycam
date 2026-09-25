"""PySide6 user interface for StudyCam."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPixmap, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication, QCalendarWidget, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .cam import CameraService
from .schedule import StudyStore


APP_STYLE = """
QWidget { font-family: 'Malgun Gothic'; font-size: 13px; color: #213547; }
QMainWindow, QDialog { background: #f6f8fb; }
QPushButton { background: #5068e8; color: white; border: 0; border-radius: 8px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { background: #4057d4; }
QPushButton[secondary='true'] { background: white; color: #5068e8; border: 1px solid #cdd5ff; }
QFrame[card='true'] { background: white; border: 1px solid #e4e8f0; border-radius: 12px; }
QListWidget, QTableWidget { background: white; border: 1px solid #e4e8f0; border-radius: 8px; }
QHeaderView::section { background: #eff2ff; border: 0; padding: 7px; font-weight: 600; }
QCalendarWidget QWidget { background: #273246; color: #f7f9ff; }
QCalendarWidget QToolButton { color: #ffffff; background: #364563; border-radius: 6px; padding: 6px; }
QCalendarWidget QAbstractItemView { selection-background-color: #5068e8; selection-color: #ffffff; color: #ffffff; background: #273246; }
QCalendarWidget QTableView { color: #ffffff; background: #273246; gridline-color: #4b5a75; }
"""


def qdate(day: date) -> QDate:
    return QDate(day.year, day.month, day.day)


def pydate(day: QDate) -> date:
    return date(day.year(), day.month(), day.day())


def secondary(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("secondary", True)
    return button


class SettingsDialog(QDialog):
    def __init__(self, store: StudyStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("공부 및 촬영 설정")
        form = QFormLayout(self)
        s = store.data["settings"]
        self.study, self.rest, self.speed = (QSpinBox() for _ in range(3))
        for box, value, maximum in ((self.study, s["study_minutes"], 360), (self.rest, s["break_minutes"], 180), (self.speed, s["speed"], 120)):
            box.setRange(1, maximum); box.setValue(value)
        self.capture = QDoubleSpinBox(); self.capture.setRange(0.1, 3600); self.capture.setSingleStep(0.1); self.capture.setDecimals(1); self.capture.setValue(float(s["capture_seconds"]))
        form.addRow("집중 시간 (분)", self.study)
        form.addRow("휴식 시간 (분)", self.rest)
        form.addRow("사진 촬영 간격 (초)", self.capture)
        form.addRow("타임랩스 FPS / 배속", self.speed)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def save(self) -> None:
        self.store.save_settings(self.study.value(), self.rest.value(), self.capture.value(), self.speed.value())
        self.accept()


class ScheduleDialog(QDialog):
    DAYS = ["월", "화", "수", "목", "금", "토", "일"]
    def __init__(self, store: StudyStore, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.store = store
        self.setWindowTitle("주간 시간표"); self.resize(560, 360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("수업을 등록하면 오늘의 복습·예습 과목 추천에 반영됩니다."))
        self.table = QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(["요일", "과목", "시작", "종료"])
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table)
        row = QHBoxLayout(); add = QPushButton("수업 추가"); remove = secondary("선택 삭제")
        add.clicked.connect(self.add_row); remove.clicked.connect(lambda: self.table.removeRow(self.table.currentRow()) if self.table.currentRow() >= 0 else None)
        row.addWidget(add); row.addWidget(remove); row.addStretch(); layout.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        for item in store.data["schedule"]: self.add_row(item)

    def add_row(self, item: dict | None = None) -> None:
        row = self.table.rowCount(); self.table.insertRow(row)
        day = QComboBox(); day.addItems(self.DAYS); day.setCurrentIndex((item or {}).get("weekday", 0))
        self.table.setCellWidget(row, 0, day)
        for col, key, default in ((1, "subject", "과목"), (2, "start", "09:00"), (3, "end", "10:00")):
            self.table.setItem(row, col, QTableWidgetItem((item or {}).get(key, default)))

    def save(self) -> None:
        result = []
        for row in range(self.table.rowCount()):
            subject = self.table.item(row, 1).text().strip() if self.table.item(row, 1) else ""
            if subject:
                result.append({"weekday": self.table.cellWidget(row, 0).currentIndex(), "subject": subject, "start": self.table.item(row, 2).text(), "end": self.table.item(row, 3).text()})
        self.store.data["schedule"] = result; self.store.save(); self.accept()


class Planner(QWidget):
    def __init__(self, store: StudyStore, day: date, refresh_calendar, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.store, self.day, self.refresh_calendar = store, day, refresh_calendar
        layout = QVBoxLayout(self); layout.setContentsMargins(18, 18, 18, 18)
        self.title = QLabel(); self.title.setStyleSheet("font-size: 19px; font-weight: 700;"); layout.addWidget(self.title)
        self.list = QListWidget(); layout.addWidget(self.list)
        inputs = QHBoxLayout(); self.subject = QLineEdit(); self.subject.setPlaceholderText("과목 (예: 물리1)")
        self.goal = QLineEdit(); self.goal.setPlaceholderText("목표 (예: p13~30까지 복습하기)")
        self.kind = QComboBox(); self.kind.addItems(["복습", "예습", "자율"]); add = QPushButton("목표 추가")
        inputs.addWidget(self.subject); inputs.addWidget(self.goal, 1); inputs.addWidget(self.kind); inputs.addWidget(add); layout.addLayout(inputs)
        actions = QHBoxLayout(); recommend = secondary("시간표에서 추천 만들기"); delete = secondary("선택 목표 삭제")
        actions.addWidget(recommend); actions.addWidget(delete); actions.addStretch(); layout.addLayout(actions)
        add.clicked.connect(self.add_task); self.goal.returnPressed.connect(self.add_task); delete.clicked.connect(self.delete_task); recommend.clicked.connect(self.recommend)
        self.reload()

    def set_day(self, day: date) -> None:
        self.day = day; self.reload()

    def reload(self) -> None:
        self.title.setText(f"{self.day:%Y년 %m월 %d일} 스터디 플래너")
        self.list.clear()
        for index, task in enumerate(self.store.tasks_for(self.day)):
            item = QListWidgetItem(f"[{task['kind']}] {task['subject']} — {task['text']}")
            item.setData(Qt.UserRole, index); item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if task.get("done") else Qt.Unchecked); self.list.addItem(item)
        self.list.itemChanged.connect(self.save_checks, Qt.UniqueConnection)

    def add_task(self) -> None:
        if not self.goal.text().strip(): return
        self.store.add_task(self.day, self.subject.text(), self.goal.text(), self.kind.currentText())
        self.subject.clear(); self.goal.clear(); self.reload(); self.refresh_calendar()

    def save_checks(self, _: QListWidgetItem) -> None:
        tasks = self.store.tasks_for(self.day)
        for row in range(self.list.count()): tasks[row]["done"] = self.list.item(row).checkState() == Qt.Checked
        self.store.update_tasks(self.day, tasks); self.refresh_calendar()

    def delete_task(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            tasks = self.store.tasks_for(self.day); tasks.pop(row); self.store.update_tasks(self.day, tasks); self.reload(); self.refresh_calendar()

    def recommend(self) -> None:
        existing = {(t["subject"], t["kind"]) for t in self.store.tasks_for(self.day)}
        additions = []
        previous = self.day - timedelta(days=1)
        for entry in self.store.data["schedule"]:
            if entry["weekday"] == previous.weekday() and (entry["subject"], "복습") not in existing:
                additions.append((entry["subject"], "어제 수업 내용 복습하기", "복습"))
            if entry["weekday"] == self.day.weekday() and (entry["subject"], "예습") not in existing:
                additions.append((entry["subject"], "오늘 수업 내용 예습하기", "예습"))
        for subject, text, kind in additions: self.store.add_task(self.day, subject, text, kind)
        self.reload(); self.refresh_calendar()


class PlannerViewer(QDialog):
    """A read-only planner used when opening a day from the calendar."""
    def __init__(self, store: StudyStore, day: date, parent: QWidget | None = None) -> None:
        super().__init__(parent); self.setWindowTitle("스터디 플래너 보기"); self.resize(560, 460)
        layout = QVBoxLayout(self)
        title = QLabel(f"{day:%Y년 %m월 %d일} 스터디 플래너"); title.setStyleSheet("font-size: 19px; font-weight: 700;"); layout.addWidget(title)
        tasks = store.tasks_for(day)
        if not tasks:
            layout.addWidget(QLabel("등록된 공부 목표가 없습니다."))
        else:
            for task in tasks:
                done = "✓ 완료" if task.get("done") else "○ 미완료"
                label = QLabel(f"{done}   [{task['kind']}] {task['subject']} — {task['text']}")
                label.setWordWrap(True); label.setStyleSheet("padding: 10px; background: white; border: 1px solid #e4e8f0; border-radius: 7px;"); layout.addWidget(label)
        videos = store.data["videos"].get(store.key(day), [])
        layout.addSpacing(8); layout.addWidget(QLabel(f"생성된 공부 영상: {len(videos)}개")); layout.addStretch()
        close = QDialogButtonBox(QDialogButtonBox.Close); close.rejected.connect(self.reject); close.accepted.connect(self.accept); layout.addWidget(close)


class StudioWindow(QMainWindow):
    def __init__(self, store: StudyStore, chosen_day: date, refresh_home) -> None:
        super().__init__(); self.store, self.refresh_home = store, refresh_home; self.day = chosen_day
        self.camera = CameraService(); self.images: list[Path] = []; self.recording = False; self.in_break = False; self.remaining = 0; self.current_frame = None
        self.setWindowTitle("StudyCam — 스터디 캠"); self.resize(1180, 760)
        root = QWidget(); self.setCentralWidget(root); outer = QVBoxLayout(root)
        top = QHBoxLayout(); self.timer_label = QLabel("준비 완료"); self.timer_label.setStyleSheet("font-size: 22px; font-weight: 700;")
        self.state_label = QLabel("촬영 중에는 카메라를 유지하고 10 FPS로 미리보기를 갱신합니다."); settings = secondary("타이머·촬영 설정")
        top.addWidget(self.timer_label); top.addWidget(self.state_label); top.addStretch(); top.addWidget(settings); outer.addLayout(top)
        splitter = QSplitter(); outer.addWidget(splitter, 1)
        left = QWidget(); left_layout = QVBoxLayout(left); self.preview = QLabel("카메라 미리보기\n(촬영 시작 후 첫 사진이 표시됩니다)"); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumSize(520, 390); self.preview.setStyleSheet("background: #202536; color: #dce3ff; border-radius: 12px; font-size: 16px;"); left_layout.addWidget(self.preview)
        controls = QHBoxLayout(); self.record_button = QPushButton("촬영 시작"); self.pomodoro_button = secondary("뽀모도로 시작"); finish = secondary("영상 만들기")
        controls.addWidget(self.record_button); controls.addWidget(self.pomodoro_button); controls.addWidget(finish); left_layout.addLayout(controls); splitter.addWidget(left)
        self.planner = Planner(store, chosen_day, refresh_home); splitter.addWidget(self.planner); splitter.setSizes([650, 450])
        self.capture_timer, self.preview_timer, self.clock = QTimer(self), QTimer(self), QTimer(self); self.preview_timer.setInterval(100); self.clock.setInterval(1000)
        self.record_button.clicked.connect(self.toggle_recording); self.pomodoro_button.clicked.connect(self.toggle_pomodoro); finish.clicked.connect(self.finish_video); settings.clicked.connect(self.open_settings)
        self.capture_timer.timeout.connect(self.capture); self.preview_timer.timeout.connect(self.update_preview); self.clock.timeout.connect(self.tick)
        self.set_phase(False)

    def open_settings(self) -> None:
        if SettingsDialog(self.store, self).exec(): self.set_phase(self.in_break)

    def toggle_recording(self) -> None:
        self.recording = not self.recording
        self.record_button.setText("촬영 중지" if self.recording else "촬영 시작")
        if self.recording and not self.in_break:
            if not self.camera.start():
                self.recording = False; self.record_button.setText("촬영 시작"); self.state_label.setText("카메라를 찾을 수 없습니다. 카메라 연결·권한을 확인하세요."); return
            self.preview_timer.start(); self.update_preview(); self.capture_timer.start(int(self.store.data["settings"]["capture_seconds"] * 1000))
            self.state_label.setText("공부 중: 카메라를 유지하며 설정한 간격으로 사진을 저장합니다.")
        elif not self.recording:
            self.finalize_recording(announce=True)

    def toggle_pomodoro(self) -> None:
        if self.clock.isActive():
            self.clock.stop(); self.pomodoro_button.setText("뽀모도로 시작"); self.timer_label.setText("뽀모도로 일시정지")
        else:
            self.set_phase(False); self.clock.start(); self.pomodoro_button.setText("뽀모도로 일시정지")

    def set_phase(self, break_time: bool) -> None:
        self.in_break = break_time
        minutes = self.store.data["settings"]["break_minutes" if break_time else "study_minutes"]
        self.remaining = minutes * 60; self.update_clock()
        if break_time:
            self.capture_timer.stop(); self.preview_timer.stop(); self.camera.stop()
        elif self.recording:
            if self.camera.start():
                self.preview_timer.start(); self.capture_timer.start(int(self.store.data["settings"]["capture_seconds"] * 1000))

    def tick(self) -> None:
        self.remaining -= 1
        if self.remaining <= 0: self.set_phase(not self.in_break)
        self.update_clock()

    def update_clock(self) -> None:
        phase = "휴식" if self.in_break else "집중"
        self.timer_label.setText(f"{phase} {self.remaining // 60:02}:{self.remaining % 60:02}")
        if self.in_break: self.state_label.setText("휴식 중: 배터리 보호를 위해 촬영하지 않습니다.")

    def capture(self) -> None:
        image = self.camera.save_frame(self.current_frame)
        if image:
            self.images.append(image)

    def update_preview(self) -> None:
        frame = self.camera.read()
        if frame is None:
            return
        self.current_frame = frame.copy()
        height, width, channels = frame.shape
        image = QImage(frame.data, width, height, channels * width, QImage.Format_BGR888)
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def finish_video(self) -> None:
        self.recording = False; self.record_button.setText("촬영 시작"); self.finalize_recording(announce=True)

    def finalize_recording(self, announce: bool = False) -> None:
        """Release the webcam and save one video for the current session."""
        self.capture_timer.stop(); self.preview_timer.stop(); self.camera.stop()
        video = self.camera.make_timelapse(self.images, self.store.data["settings"]["speed"])
        if not video:
            if announce: QMessageBox.information(self, "영상 만들기", "저장된 사진이 없어 영상을 만들 수 없습니다.")
            return
        key = self.store.key(self.day); self.store.data["videos"].setdefault(key, []).append(str(video)); self.store.save()
        self.images.clear(); self.current_frame = None
        if announce: QMessageBox.information(self, "영상 완성", f"타임랩스가 자동 저장되었습니다.\n{video}")

    def closeEvent(self, event) -> None:
        self.recording = False; self.clock.stop(); self.finalize_recording(); self.refresh_home(); event.accept()


class HomePage(QWidget):
    def __init__(self, store: StudyStore) -> None:
        super().__init__(); self.store = store; self.selected_day = date.today(); self.studio: StudioWindow | None = None
        layout = QVBoxLayout(self); layout.setContentsMargins(42, 30, 42, 34)
        header = QHBoxLayout(); title = QLabel("StudyCam"); title.setStyleSheet("font-size: 30px; font-weight: 800; color: #3446b8;")
        self.streak_label = QLabel(); self.streak_label.setStyleSheet("font-size: 16px; font-weight: 600;"); start = QPushButton("스터디 캠 실행하기")
        header.addWidget(title); header.addSpacing(20); header.addWidget(self.streak_label); header.addStretch(); header.addWidget(start); layout.addLayout(header)
        subtitle = QLabel("날짜를 선택하면 그날의 목표와 만들어진 공부 영상을 확인할 수 있습니다."); subtitle.setStyleSheet("color: #6b7280;"); layout.addWidget(subtitle)
        card = QFrame(); card.setProperty("card", True); card_layout = QVBoxLayout(card); self.calendar = QCalendarWidget(); self.calendar.setGridVisible(True); self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader); self.calendar.setMinimumHeight(510); card_layout.addWidget(self.calendar); layout.addWidget(card, 1)
        bottom = QHBoxLayout(); self.detail = QLabel(); planner = secondary("선택한 날짜의 플래너 열기"); schedule = secondary("주간 시간표 설정"); videos = secondary("선택 날짜 영상 열기")
        bottom.addWidget(self.detail); bottom.addStretch(); bottom.addWidget(videos); bottom.addWidget(schedule); bottom.addWidget(planner); layout.addLayout(bottom)
        start.clicked.connect(self.open_studio); planner.clicked.connect(self.open_planner); schedule.clicked.connect(self.open_schedule); videos.clicked.connect(self.open_video); self.calendar.selectionChanged.connect(self.select_day)
        self.calendar.setSelectedDate(qdate(self.selected_day)); self.refresh()

    def refresh(self) -> None:
        self.streak_label.setText(f"{self.store.streak()}일째 공부 목표 달성 중!")
        fmt = QTextCharFormat(); fmt.setBackground(QColor("#dce8ff")); fmt.setForeground(QColor("#1f3ea8"))
        today_fmt = QTextCharFormat(); today_fmt.setBackground(QColor("#f7d781")); today_fmt.setFontWeight(700)
        year = self.calendar.yearShown(); month = self.calendar.monthShown()
        for day_num in range(1, QDate(year, month, 1).daysInMonth() + 1): self.calendar.setDateTextFormat(QDate(year, month, day_num), QTextCharFormat())
        for key in self.store.data["tasks"]:
            day = date.fromisoformat(key)
            if self.store.completed(day): self.calendar.setDateTextFormat(qdate(day), fmt)
        self.calendar.setDateTextFormat(QDate.currentDate(), today_fmt)
        self.select_day()

    def select_day(self) -> None:
        self.selected_day = pydate(self.calendar.selectedDate()); tasks = self.store.tasks_for(self.selected_day); videos = self.store.data["videos"].get(self.store.key(self.selected_day), [])
        self.detail.setText(f"{self.selected_day:%m월 %d일}: 목표 {len(tasks)}개 · 완료 {sum(t.get('done', False) for t in tasks)}개 · 영상 {len(videos)}개")

    def open_schedule(self) -> None:
        if ScheduleDialog(self.store, self).exec(): self.refresh()

    def open_studio(self) -> None:
        if self.studio and self.studio.isVisible(): self.studio.raise_(); self.studio.activateWindow(); return
        self.studio = StudioWindow(self.store, self.selected_day, self.refresh); self.studio.show()

    def open_planner(self) -> None:
        PlannerViewer(self.store, self.selected_day, self).exec()

    def open_video(self) -> None:
        videos = self.store.data["videos"].get(self.store.key(self.selected_day), [])
        if not videos:
            QMessageBox.information(self, "공부 영상", "이 날짜에 생성된 공부 영상이 없습니다.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(videos[-1]))


def main() -> None:
    app = QApplication(sys.argv); app.setApplicationName("StudyCam"); app.setStyleSheet(APP_STYLE)
    window = QMainWindow(); window.setWindowTitle("StudyCam"); window.resize(980, 720); window.setCentralWidget(HomePage(StudyStore())); window.show()
    sys.exit(app.exec())


if __name__ == "__main__": main()
