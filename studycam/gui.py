"""PySide6 interface for StudyCam."""
from __future__ import annotations

import ctypes
import math
import struct
import sys
import time
import wave
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QTimer, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QImage, QPixmap, QTextCharFormat
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (QApplication, QCalendarWidget, QComboBox, QDialog,
    QAbstractSpinBox, QCheckBox, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .cam import CameraService
from .schedule import StudyStore

APP_STYLE = """
QWidget { font-family: 'Malgun Gothic'; font-size: 13px; color: #213547; }
QMainWindow,QDialog { background:#f6f8fb; } QPushButton { background:#5068e8;color:white;border:0;border-radius:8px;padding:9px 14px;font-weight:600; }
QPushButton:hover { background:#6d81f1; } QPushButton:disabled { background:#e8ebf2;color:#9ca6b7;border:1px solid #dde2eb; }
QPushButton[secondary='true'] { background:white;color:#5068e8;border:1px solid #cdd5ff; } QPushButton[secondary='true']:hover { background:#edf1ff;color:#3048c7;border-color:#8da0ff; }
QPushButton[secondary='true']:disabled { background:#e8ebf2;color:#9ca6b7;border:1px solid #dde2eb; }
QPushButton[danger='true'] { background:#dc2626;color:white;border:0; } QPushButton[danger='true']:hover { background:#ef4444;color:white; }
QFrame[card='true'] { background:white;border:1px solid #e4e8f0;border-radius:12px; }
QListWidget,QTableWidget { background:white;border:1px solid #e4e8f0;border-radius:8px; }
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox { background:#ffffff;color:#213547;border:1px solid #cfd6e3;border-radius:6px;padding:5px;selection-background-color:#dce5ff;selection-color:#213547; }
QLineEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus { background:#ffffff;border:2px solid #5068e8; }
QComboBox QAbstractItemView { background:#ffffff;color:#213547;selection-background-color:#dce5ff;selection-color:#213547;border:1px solid #cfd6e3; }
QTableWidget::item:selected { background:#dce5ff;color:#213547;border:1px solid #5068e8; }
QCheckBox { color:#213547;spacing:7px; } QCheckBox:hover { color:#5068e8; } QCheckBox::indicator { width:16px;height:16px;border:1px solid #71809a;border-radius:4px;background:#ffffff; } QCheckBox::indicator:hover { border:2px solid #5068e8;background:#edf1ff; } QCheckBox::indicator:checked { background:#5068e8;border-color:#5068e8; }
QCheckBox:disabled { color:#a9b0bc; } QCheckBox::indicator:disabled { border-color:#cbd1db;background:#edf0f4; } QCheckBox::indicator:checked:disabled { background:#b9c1ce;border-color:#b9c1ce; }
QHeaderView::section { background:#eff2ff;border:0;padding:7px;font-weight:600; }
QCalendarWidget QWidget,QCalendarWidget QTableView { background:#273246;color:#f7f9ff; }
QCalendarWidget QToolButton { color:#fff;background:#364563;border-radius:6px;padding:6px; }
QCalendarWidget QAbstractItemView { selection-background-color:#5068e8;selection-color:#fff;color:#fff;background:#273246;gridline-color:#4b5a75; }
"""

def qdate(day: date) -> QDate: return QDate(day.year, day.month, day.day)
def pydate(day: QDate) -> date: return date(day.year(), day.month(), day.day())
def secondary(text: str) -> QPushButton:
    button = QPushButton(text); button.setProperty("secondary", True); return button

def set_danger(button: QPushButton, active: bool) -> None:
    button.setProperty("danger", active); button.style().unpolish(button); button.style().polish(button)

def can_close_window(parent: QWidget, store: StudyStore, setting: str) -> bool:
    """Respect the close-lock setting and ask before closing an app window."""
    if store.data["settings"][setting]:
        QMessageBox.information(parent, "창 닫기 방지", "설정에서 창 닫기 방지가 켜져 있어 창을 닫을 수 없습니다.")
        return False
    return QMessageBox.question(
        parent, "창 닫기", "정말 창을 닫으시겠습니까?",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
    ) == QMessageBox.Yes

def keep_awake(active: bool) -> None:
    """Ask Windows not to suspend an active study session or turn off its display."""
    if sys.platform == "win32":
        flags = 0x80000000 | (0x00000001 | 0x00000002 if active else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)

def format_seconds(seconds: int) -> str:
    return f"{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}"

def app_icon() -> QIcon:
    """Return the bundled icon both from source and from a PyInstaller build."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return QIcon(str(root / "assets" / "studycam.ico"))

def ensure_alarm_tone(directory: Path) -> Path:
    """Create a small bundled-at-runtime WAV tone without an external asset."""
    directory.mkdir(parents=True, exist_ok=True); tone = directory / "studycam_alarm.wav"
    if tone.exists(): return tone
    rate, duration = 44100, 0.42
    samples = bytearray()
    for index in range(int(rate * duration)):
        envelope = min(1.0, index / 800) * min(1.0, (rate * duration - index) / 1200)
        value = int(0.42 * 32767 * envelope * math.sin(2 * math.pi * 880 * index / rate))
        samples.extend(struct.pack("<h", value))
    with wave.open(str(tone), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(rate); output.writeframes(samples)
    return tone


class SettingsDialog(QDialog):
    def __init__(self, store: StudyStore, parent=None):
        super().__init__(parent); self.store = store; self.setWindowTitle("공부 및 촬영 설정")
        form = QFormLayout(self); s = store.data["settings"]
        self.study, self.rest, self.speed = (QSpinBox() for _ in range(3))
        for box, value, maximum in ((self.study,s["study_minutes"],360),(self.rest,s["break_minutes"],180),(self.speed,s["speed"],120)):
            box.setRange(1, maximum); box.setValue(value)
        self.capture=QDoubleSpinBox(); self.capture.setRange(0.1,3600); self.capture.setSingleStep(0.1); self.capture.setDecimals(1); self.capture.setValue(float(s["capture_seconds"]))
        self.storage_dir=QLineEdit(s["storage_dir"]); self.storage_dir.setReadOnly(True)
        self.alarm_enabled=QCheckBox("집중·휴식 전환 시 알람음 재생"); self.alarm_enabled.setChecked(s["alarm_enabled"])
        self.alarm_volume=QSpinBox(); self.alarm_volume.setRange(0,100); self.alarm_volume.setSuffix("%"); self.alarm_volume.setValue(s["alarm_volume"])
        self.start_maximized=QCheckBox("다음 앱 실행 시 창 최대화"); self.start_maximized.setChecked(s["start_maximized"])
        self.pomodoro_with_camera=QCheckBox("촬영 시작 시 뽀모도로도 자동 시작"); self.pomodoro_with_camera.setChecked(s["pomodoro_with_camera"])
        self.prevent_home_close=QCheckBox("캘린더 창 닫기 방지"); self.prevent_home_close.setChecked(s["prevent_home_close"])
        self.prevent_studio_close=QCheckBox("카메라 창 닫기 방지"); self.prevent_studio_close.setChecked(s["prevent_studio_close"])
        self.completed_color=QLineEdit(s["completed_color"]); self.completed_color.setPlaceholderText("#dce8ff")
        self.failed_color=QLineEdit(s["failed_color"]); self.failed_color.setPlaceholderText("#ffd9d9")
        choose, open_dir = secondary("폴더 선택"), secondary("폴더 열기"); choose.clicked.connect(self.choose_folder); open_dir.clicked.connect(self.open_folder)
        folder=QHBoxLayout(); folder.addWidget(self.storage_dir,1); folder.addWidget(choose); folder.addWidget(open_dir)
        form.addRow("집중 시간 (분)",self.study); form.addRow("휴식 시간 (분)",self.rest); form.addRow("사진 촬영 간격 (초)",self.capture); form.addRow("타임랩스 FPS / 배속",self.speed); form.addRow("영상·촬영본 저장 폴더",folder); form.addRow("알람",self.alarm_enabled); form.addRow("알람 음량",self.alarm_volume); form.addRow("목표 완료일 색상 (HEX)",self.completed_color); form.addRow("목표 미완료일 색상 (HEX)",self.failed_color); form.addRow("창 시작 옵션",self.start_maximized); form.addRow("촬영·타이머 연동",self.pomodoro_with_camera); form.addRow("창 닫기",self.prevent_home_close); form.addRow("",self.prevent_studio_close)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def choose_folder(self):
        selected=QFileDialog.getExistingDirectory(self,"저장 폴더 선택",self.storage_dir.text())
        if selected: self.storage_dir.setText(selected)
    def open_folder(self):
        folder=Path(self.storage_dir.text()); folder.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
    def save(self):
        folder=Path(self.storage_dir.text()); folder.mkdir(parents=True,exist_ok=True)
        completed, failed = self.completed_color.text().strip(), self.failed_color.text().strip()
        if not QColor(completed).isValid() or not QColor(failed).isValid():
            QMessageBox.warning(self,"색상 코드 확인","색상은 #RRGGBB 형식의 올바른 HEX 코드여야 합니다."); return
        self.store.save_settings(self.study.value(),self.rest.value(),self.capture.value(),self.speed.value(),str(folder),self.alarm_enabled.isChecked(),self.alarm_volume.value(),completed,failed,self.start_maximized.isChecked(),self.pomodoro_with_camera.isChecked(),self.prevent_home_close.isChecked(),self.prevent_studio_close.isChecked()); self.accept()


class ScheduleDialog(QDialog):
    DAYS=["월","화","수","목","금","토","일"]
    def __init__(self,store:StudyStore,parent=None):
        super().__init__(parent); self.store=store; self.setWindowTitle("과목 및 주간 시간표"); self.resize(650,520)
        outer=QVBoxLayout(self); scroll=QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll); content=QWidget(); scroll.setWidget(content)
        layout=QVBoxLayout(content); layout.addWidget(QLabel("1. 과목 목록을 만든 뒤  2. 각 과목의 수업 요일과 시간을 등록하세요."))
        subject_row=QHBoxLayout(); self.subjects=QListWidget(); self.subjects.addItems(store.data["subjects"]); self.new_subject=QLineEdit(); self.new_subject.setPlaceholderText("새 과목명")
        add_subject=QPushButton("과목 추가"); remove_subject=secondary("선택 과목 삭제"); add_subject.clicked.connect(self.add_subject); remove_subject.clicked.connect(self.remove_subject)
        subject_box=QVBoxLayout(); subject_box.addWidget(QLabel("과목 목록")); subject_box.addWidget(self.subjects); actions=QHBoxLayout(); actions.addWidget(self.new_subject); actions.addWidget(add_subject); actions.addWidget(remove_subject); subject_box.addLayout(actions); subject_row.addLayout(subject_box,1); layout.addLayout(subject_row)
        layout.addWidget(QLabel("수업 시간")); self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(["과목","요일","시작","종료"]); self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table)
        row=QHBoxLayout(); add=QPushButton("수업 추가"); remove=secondary("선택 수업 삭제"); add.clicked.connect(self.add_row); remove.clicked.connect(self.remove_row); row.addWidget(add); row.addWidget(remove); row.addStretch(); layout.addLayout(row)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        for item in store.data["schedule"]: self.add_row(item)
    def add_subject(self):
        name=self.new_subject.text().strip()
        if name and name not in [self.subjects.item(i).text() for i in range(self.subjects.count())]: self.subjects.addItem(name); self.new_subject.clear()
    def remove_subject(self):
        row=self.subjects.currentRow()
        if row>=0: self.subjects.takeItem(row); self.refresh_subject_choices()
    def subject_names(self): return [self.subjects.item(i).text() for i in range(self.subjects.count())]
    def refresh_subject_choices(self):
        names=self.subject_names()
        for row in range(self.table.rowCount()):
            combo=self.table.cellWidget(row,0); current=combo.currentText(); combo.clear(); combo.addItems(names); combo.setCurrentText(current)
    def add_row(self,item:dict|None=None):
        row=self.table.rowCount(); self.table.insertRow(row); subject=QComboBox(); subject.addItems(self.subject_names()); subject.setCurrentText((item or {}).get("subject","")); day=QComboBox(); day.addItems(self.DAYS); day.setCurrentIndex((item or {}).get("weekday",0)); self.table.setCellWidget(row,0,subject); self.table.setCellWidget(row,1,day)
        self.table.setItem(row,2,QTableWidgetItem((item or {}).get("start","09:00"))); self.table.setItem(row,3,QTableWidgetItem((item or {}).get("end","10:00")))
    def remove_row(self):
        if self.table.currentRow()>=0: self.table.removeRow(self.table.currentRow())
    def save(self):
        names=self.subject_names(); result=[]
        for row in range(self.table.rowCount()):
            subject=self.table.cellWidget(row,0).currentText()
            if subject in names: result.append({"subject":subject,"weekday":self.table.cellWidget(row,1).currentIndex(),"start":self.table.item(row,2).text(),"end":self.table.item(row,3).text()})
        self.store.data["subjects"]=names; self.store.data["schedule"]=result; self.store.save(); self.accept()


class Planner(QWidget):
    def __init__(self,store:StudyStore,day:date,refresh_calendar,parent=None):
        super().__init__(parent); self.store,self.day,self.refresh_calendar=store,day,refresh_calendar; self.loading=False
        layout=QVBoxLayout(self); layout.setContentsMargins(18,18,18,18); self.title=QLabel(); self.title.setStyleSheet("font-size:19px;font-weight:700;"); layout.addWidget(self.title)
        self.list=QListWidget(); layout.addWidget(self.list)
        inputs=QHBoxLayout(); self.subject=QComboBox(); self.subject.setEditable(True); self.refresh_subjects(); self.subject.activated.connect(self.select_subject); self.goal=QLineEdit(); self.goal.setPlaceholderText("목표 (예: p13~30까지 복습하기)"); self.kind=QComboBox(); self.kind.addItems(["복습","예습","자율"]); self.add=QPushButton("목표 추가")
        inputs.addWidget(self.subject); inputs.addWidget(self.goal,1); inputs.addWidget(self.kind); inputs.addWidget(self.add); layout.addLayout(inputs)
        actions=QHBoxLayout(); self.recommend_button=secondary("시간표에서 추천 만들기"); self.edit=secondary("선택 목표 수정"); self.delete=secondary("선택 목표 삭제"); actions.addWidget(self.recommend_button); actions.addWidget(self.edit); actions.addWidget(self.delete); actions.addStretch(); layout.addLayout(actions)
        self.add.clicked.connect(self.add_task); self.goal.returnPressed.connect(self.add_task); self.delete.clicked.connect(self.delete_task); self.edit.clicked.connect(self.edit_task); self.recommend_button.clicked.connect(self.recommend); self.reload()
    def refresh_subjects(self):
        current=self.subject.currentText() if hasattr(self,"subject") else ""; self.subject.clear(); self.subject.addItems(self.store.data["subjects"]); self.subject.addItem("직접 입력"); self.subject.setCurrentText(current)
    def select_subject(self, _):
        if self.subject.currentText()=="직접 입력": self.subject.lineEdit().clear(); self.subject.lineEdit().setFocus()
    def editable(self): return self.day >= date.today()
    def reload(self):
        self.loading=True; self.title.setText(f"{self.day:%Y년 %m월 %d일} 스터디 플래너"); self.list.clear(); can_check=self.editable()
        for index, task in enumerate(self.store.tasks_for(self.day)):
            item=QListWidgetItem(); checkbox=QCheckBox(f"[{task['kind']}] {task['subject']} — {task['text']}")
            checkbox.setChecked(task.get("done", False)); checkbox.setEnabled(can_check and not task.get("system"))
            checkbox.toggled.connect(lambda checked, task_index=index: self.set_done(task_index, checked))
            item.setSizeHint(checkbox.sizeHint()); self.list.addItem(item); self.list.setItemWidget(item, checkbox)
        if not can_check: self.title.setText(self.title.text()+"  (지난 날짜: 완료 상태 변경 불가)")
        self.loading=False
    def add_task(self):
        subject=self.subject.currentText().strip()
        if subject=="직접 입력": subject="과목"
        if self.goal.text().strip(): self.store.add_task(self.day,subject,self.goal.text(),self.kind.currentText()); self.goal.clear(); self.reload(); self.refresh_calendar()
    def set_done(self, task_index, checked):
        if self.loading or not self.editable(): return
        tasks=self.store.tasks_for(self.day)
        if task_index >= len(tasks) or tasks[task_index].get("system"): return
        tasks[task_index]["done"]=checked
        self.store.update_tasks(self.day,tasks); self.refresh_calendar()
    def delete_task(self):
        row=self.list.currentRow()
        if row>=0:
            tasks=self.store.tasks_for(self.day)
            if tasks[row].get("system"): QMessageBox.information(self,"수정 불가","총 공부 시간 목표는 자동으로 관리됩니다."); return
            tasks.pop(row); self.store.update_tasks(self.day,tasks); self.reload(); self.refresh_calendar()
    def edit_task(self):
        row=self.list.currentRow()
        if row<0: QMessageBox.information(self,"목표 수정","수정할 목표를 선택하세요."); return
        tasks=self.store.tasks_for(self.day); task=tasks[row]
        if task.get("system"): QMessageBox.information(self,"수정 불가","총 공부 시간 목표는 자동으로 관리됩니다."); return
        dialog=QDialog(self); dialog.setWindowTitle("공부 목표 수정"); form=QFormLayout(dialog); subject=QLineEdit(task["subject"]); text=QLineEdit(task["text"]); kind=QComboBox(); kind.addItems(["복습","예습","자율"]); kind.setCurrentText(task["kind"]); form.addRow("과목",subject); form.addRow("목표",text); form.addRow("구분",kind); buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec() and text.text().strip():
            task.update({"subject":subject.text().strip() or "과목", "text":text.text().strip(), "kind":kind.currentText()}); self.store.update_tasks(self.day,tasks); self.reload(); self.refresh_calendar()
    def recommend(self):
        existing={(t["subject"],t["kind"]) for t in self.store.tasks_for(self.day)}; additions=[]; previous=self.day-timedelta(days=1)
        for item in self.store.data["schedule"]:
            if item["weekday"]==previous.weekday() and (item["subject"],"복습") not in existing: additions.append((item["subject"],"어제 수업 내용 복습하기","복습"))
            if item["weekday"]==self.day.weekday() and (item["subject"],"예습") not in existing: additions.append((item["subject"],"오늘 수업 내용 예습하기","예습"))
        for subject,text,kind in additions: self.store.add_task(self.day,subject,text,kind)
        self.reload(); self.refresh_calendar()


class PlannerViewer(QDialog):
    def __init__(self,store:StudyStore,day:date,parent=None):
        super().__init__(parent); self.setWindowTitle("스터디 플래너 보기"); self.resize(560,460); layout=QVBoxLayout(self); title=QLabel(f"{day:%Y년 %m월 %d일} 스터디 플래너"); title.setStyleSheet("font-size:19px;font-weight:700;"); layout.addWidget(title)
        tasks=store.tasks_for(day)
        layout.addWidget(QLabel("등록된 공부 목표가 없습니다.") if not tasks else QLabel(""))
        for task in tasks:
            label=QLabel(f"{'✓ 완료' if task.get('done') else '○ 미완료'}   [{task['kind']}] {task['subject']} — {task['text']}"); label.setWordWrap(True); label.setStyleSheet("padding:10px;background:white;border:1px solid #e4e8f0;border-radius:7px;"); layout.addWidget(label)
        layout.addStretch(); buttons=QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(self.reject); buttons.accepted.connect(self.accept); layout.addWidget(buttons)


class ClockWindow(QMainWindow):
    """A distraction-free display that mirrors the active study session."""
    def __init__(self, studio):
        super().__init__(studio); self.studio=studio; self.scale=1.0; self.setWindowTitle("StudyCam 큰 시계"); self.resize(620,360)
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root); controls=QHBoxLayout(); controls.addStretch(); smaller=secondary("−"); larger=secondary("+"); smaller.setFixedWidth(42); larger.setFixedWidth(42); controls.addWidget(smaller); controls.addWidget(larger); layout.addLayout(controls); layout.setAlignment(Qt.AlignCenter)
        self.now=QLabel(); self.pomodoro=QLabel(); self.daily=QLabel()
        for label in (self.now,self.pomodoro,self.daily): label.setAlignment(Qt.AlignCenter); layout.addWidget(label)
        smaller.clicked.connect(lambda: self.change_scale(-0.1)); larger.clicked.connect(lambda: self.change_scale(0.1)); self.timer=QTimer(self); self.timer.setInterval(250); self.timer.timeout.connect(self.refresh); self.timer.start(); self.refresh()
    def change_scale(self, amount): self.scale=max(0.6,min(2.2,self.scale+amount)); self.refresh()
    def refresh(self):
        self.now.setText(time.strftime("%H:%M:%S")); self.pomodoro.setText(self.studio.timer_label.text()); self.daily.setText(f"{self.studio.session_prefix.text()} {self.studio.session_label.text()}")
        self.now.setStyleSheet(f"font-size:{round(42*self.scale)}px;font-weight:700;"); self.pomodoro.setStyleSheet(f"font-size:{round(64*self.scale)}px;font-weight:800;color:{self.studio.timer_color};"); self.daily.setStyleSheet(f"font-size:{round(30*self.scale)}px;font-weight:700;color:#5068e8;")
    def closeEvent(self,event): event.accept()


class StudioWindow(QMainWindow):
    def __init__(self,store:StudyStore,chosen_day:date,refresh_home):
        super().__init__(); self.store,self.refresh_home,self.day=store,refresh_home,chosen_day; self.camera=self.new_camera(); self.images=[]; self.recording=False; self.in_break=False; self.remaining=0; self.current_frame=None; self.preview_hidden=False; self.last_tick_at=None; self.blink_count=0; self.clock_window=None; self.session_target_seconds=0; self.session_elapsed_seconds=0; self.lock_until_session_target=False; self.timer_color="#3446b8"; self.alarm=QSoundEffect(self); self.configure_alarm()
        self.setWindowTitle("StudyCam — 스터디 캠"); self.setWindowIcon(app_icon()); self.resize(1180,760); root=QWidget(); self.setCentralWidget(root); outer=QVBoxLayout(root)
        top=QHBoxLayout(); self.timer_label=QLabel(); self.timer_label.setStyleSheet("font-size:55px;font-weight:800;color:#3446b8;"); self.session_prefix=QLabel(); self.session_prefix.setStyleSheet("font-size:18px;font-weight:700;color:#5068e8;"); self.session_label=QLabel(); self.session_label.setStyleSheet("font-size:18px;font-weight:800;color:#3446b8;border:2px solid #5068e8;border-radius:6px;padding:4px 7px;"); self.state_label=QLabel("촬영을 시작하면 카메라가 켜집니다."); settings=secondary("설정"); clock_view=secondary("큰 시계"); session_settings=secondary("이번 공부 목표 설정"); top.addWidget(self.timer_label); top.addWidget(self.session_prefix); top.addWidget(self.session_label); top.addWidget(self.state_label); top.addStretch(); top.addWidget(session_settings); top.addWidget(clock_view); top.addWidget(settings); outer.addLayout(top)
        splitter=QSplitter(); outer.addWidget(splitter,1); left=QWidget(); left_layout=QVBoxLayout(left); self.preview=QLabel("카메라 미리보기"); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumSize(520,390); self.preview.setStyleSheet("background:#202536;color:#dce3ff;border-radius:12px;font-size:16px;"); left_layout.addWidget(self.preview)
        controls=QHBoxLayout(); self.record_button=QPushButton("촬영 시작"); self.preview_button=secondary("미리보기 숨기기"); self.pomodoro_button=secondary("뽀모도로 시작"); self.finish=secondary("영상 만들기"); controls.addWidget(self.record_button); controls.addWidget(self.preview_button); controls.addWidget(self.pomodoro_button); controls.addWidget(self.finish); left_layout.addLayout(controls); splitter.addWidget(left); self.planner=Planner(store,chosen_day,refresh_home); splitter.addWidget(self.planner); splitter.setSizes([650,450])
        self.capture_timer,self.preview_timer,self.clock,self.blink_timer=QTimer(self),QTimer(self),QTimer(self),QTimer(self); self.preview_timer.setInterval(100); self.clock.setInterval(1000); self.blink_timer.setInterval(300); self.capture_timer.timeout.connect(self.capture); self.preview_timer.timeout.connect(self.update_preview); self.clock.timeout.connect(self.tick); self.blink_timer.timeout.connect(self.blink_timer_label); self.record_button.clicked.connect(self.toggle_recording); self.preview_button.clicked.connect(self.toggle_preview); self.pomodoro_button.clicked.connect(self.toggle_pomodoro); self.finish.clicked.connect(self.finish_video); settings.clicked.connect(self.open_settings); clock_view.clicked.connect(self.open_clock_window); session_settings.clicked.connect(self.configure_session_goal); self.set_phase(False)
    def new_camera(self): return CameraService(Path(self.store.data["settings"]["storage_dir"]))
    def configure_alarm(self):
        settings=self.store.data["settings"]; tone=ensure_alarm_tone(Path(settings["storage_dir"])); self.alarm.setSource(QUrl.fromLocalFile(str(tone))); self.alarm.setVolume(settings["alarm_volume"] / 100)
    def play_alarm(self):
        if self.store.data["settings"]["alarm_enabled"]: self.alarm.play()
    def open_settings(self):
        if SettingsDialog(self.store,self).exec():
            if not self.recording: self.camera.stop(); self.camera=self.new_camera()
            self.configure_alarm()
            self.set_phase(self.in_break)
            self.planner.reload(); self.refresh_home()
    def open_clock_window(self):
        if self.clock_window and self.clock_window.isVisible(): self.clock_window.raise_(); self.clock_window.activateWindow(); return
        self.clock_window=ClockWindow(self); self.clock_window.show()
    def configure_session_goal(self):
        dialog=QDialog(self); dialog.setWindowTitle("이번 공부 총 목표 시간"); form=QFormLayout(dialog); hours=QSpinBox(); hours.setRange(0,24); hours.setSingleStep(1); hours.setButtonSymbols(QAbstractSpinBox.UpDownArrows); hours.setSuffix("시간"); minutes=QSpinBox(); minutes.setRange(0,59); minutes.setSingleStep(1); minutes.setButtonSymbols(QAbstractSpinBox.UpDownArrows); minutes.setSuffix("분"); total_minutes=self.session_target_seconds//60; hours.setValue(total_minutes//60); minutes.setValue(total_minutes%60); lock=QCheckBox("목표 시간을 채우기 전에는 카메라 창 닫기 방지"); lock.setChecked(self.lock_until_session_target); form.addRow("목표 시간",hours); form.addRow("",minutes); form.addRow("창 닫기",lock); active_goal=self.session_target_seconds and self.session_elapsed_seconds < self.session_target_seconds
        if active_goal:
            hours.setEnabled(False); minutes.setEnabled(False); lock.setEnabled(False); form.addRow(QLabel("진행 중인 이번 공부 목표는 수정할 수 없습니다.")); buttons=QDialogButtonBox(QDialogButtonBox.Close); buttons.rejected.connect(dialog.reject); buttons.accepted.connect(dialog.accept); form.addRow(buttons); dialog.exec(); return
        form.addRow(QLabel("집중 구간만 목표 시간에 포함됩니다. 시간과 분이 모두 0이면 사용하지 않습니다.")); buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec():
            self.session_target_seconds=(hours.value()*60+minutes.value())*60; self.session_elapsed_seconds=0; self.lock_until_session_target=lock.isChecked(); self.sync_session_goal(); self.update_clock(); self.planner.reload(); self.refresh_home()
    def sync_session_goal(self):
        tasks=self.store.tasks_for(self.day); tasks[:]=[task for task in tasks if task.get("system")!="session_study_time"]
        if self.session_target_seconds:
            tasks.append({"system":"session_study_time","subject":"이번 공부 총 목표 시간","kind":"자율","text":f"{format_seconds(self.session_elapsed_seconds)} / {format_seconds(self.session_target_seconds)} 공부하기","done":self.session_elapsed_seconds>=self.session_target_seconds})
        self.store.update_tasks(self.day,tasks)
    def toggle_preview(self):
        self.preview_hidden=not self.preview_hidden; self.preview_button.setText("미리보기 보이기" if self.preview_hidden else "미리보기 숨기기")
        if self.preview_hidden: self.preview.setPixmap(QPixmap()); self.preview.setText("카메라는 계속 촬영 중입니다.")
        else: self.preview.setText(""); self.update_preview()
    def toggle_recording(self):
        self.recording=not self.recording; self.record_button.setText("촬영 중지" if self.recording else "촬영 시작"); set_danger(self.record_button,self.recording)
        if self.recording and not self.in_break:
            if not self.camera.start(): self.recording=False; self.record_button.setText("촬영 시작"); set_danger(self.record_button,False); self.state_label.setText("카메라를 찾을 수 없습니다. 카메라 연결·권한을 확인하세요."); return
            self.preview_timer.start(); self.update_preview(); self.capture_timer.start(int(self.store.data["settings"]["capture_seconds"]*1000)); self.state_label.setText("공부 중: 카메라를 유지하며 설정 간격으로 저장합니다.")
            if self.store.data["settings"]["pomodoro_with_camera"] and not self.clock.isActive(): self.set_phase(False); self.start_pomodoro()
        elif not self.recording: self.finalize_recording(True)
        self.update_awake_state()
    def toggle_pomodoro(self):
        if self.clock.isActive(): self.clock.stop(); self.last_tick_at=None; self.pomodoro_button.setText("뽀모도로 시작"); set_danger(self.pomodoro_button,False)
        else: self.set_phase(False); self.start_pomodoro()
        self.update_awake_state()
    def start_pomodoro(self):
        self.last_tick_at=time.time(); self.clock.start(); self.pomodoro_button.setText("뽀모도로 중지"); set_danger(self.pomodoro_button,True); self.update_awake_state()
    def update_awake_state(self): keep_awake(self.recording or self.clock.isActive())
    def set_phase(self,break_time,announce=False):
        self.in_break=break_time; self.remaining=self.store.data["settings"]["break_minutes" if break_time else "study_minutes"]*60; self.update_clock()
        if break_time: self.capture_timer.stop(); self.preview_timer.stop(); self.camera.stop()
        elif self.recording and self.camera.start(): self.preview_timer.start(); self.capture_timer.start(int(self.store.data["settings"]["capture_seconds"]*1000))
        if announce: self.play_alarm(); self.start_blink()
    def tick(self):
        now=time.time(); elapsed=max(1, int(now-(self.last_tick_at or now))); self.last_tick_at=now
        if not self.in_break:
            self.store.add_study_seconds(date.today(), elapsed)
            if self.session_target_seconds:
                self.session_elapsed_seconds=min(self.session_target_seconds,self.session_elapsed_seconds+elapsed); self.sync_session_goal(); self.planner.reload()
            self.refresh_home()
        self.remaining-=elapsed
        if self.remaining<=0: self.set_phase(not self.in_break,announce=True)
        self.update_clock()
    def update_clock(self):
        self.timer_label.setText(f"{'휴식' if self.in_break else '집중'} {self.remaining//60:02}:{self.remaining%60:02}")
        self.session_prefix.setText("이번 공부 목표:" if not self.session_target_seconds else "이번 공부 남은 시간:")
        self.session_label.setText("사용 안 함" if not self.session_target_seconds else format_seconds(max(0, self.session_target_seconds-self.session_elapsed_seconds)))
    def start_blink(self): self.blink_count=0; self.blink_timer.start()
    def blink_timer_label(self):
        self.blink_count+=1; self.timer_color="#ffffff" if self.blink_count % 2 else "#3446b8"; self.timer_label.setStyleSheet(f"font-size:55px;font-weight:800;color:{self.timer_color};")
        if self.blink_count >= 6: self.blink_timer.stop(); self.timer_color="#3446b8"; self.timer_label.setStyleSheet("font-size:55px;font-weight:800;color:#3446b8;")
    def capture(self):
        image=self.camera.save_frame(self.current_frame)
        if image: self.images.append(image)
    def update_preview(self):
        frame=self.camera.read()
        if frame is None: return
        import cv2
        frame=cv2.flip(frame,1); self.current_frame=frame.copy()
        if self.preview_hidden: return
        height,width,channels=frame.shape; image=QImage(frame.data,width,height,channels*width,QImage.Format_BGR888); self.preview.setPixmap(QPixmap.fromImage(image).scaled(self.preview.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def finish_video(self): self.recording=False; self.record_button.setText("촬영 시작"); set_danger(self.record_button,False); self.finalize_recording(True); self.update_awake_state()
    def finalize_recording(self,announce=False):
        self.capture_timer.stop(); self.preview_timer.stop(); self.camera.stop(); video=self.camera.make_timelapse(self.images,self.store.data["settings"]["speed"])
        if not video:
            if announce: QMessageBox.information(self,"영상 만들기","저장된 사진이 없어 영상을 만들 수 없습니다.")
            return
        self.store.data["videos"].setdefault(self.store.key(self.day),[]).append(str(video)); self.store.save(); self.images.clear(); self.current_frame=None
        if announce: QMessageBox.information(self,"영상 완성",f"타임랩스가 자동 저장되었습니다.\n{video}")
    def closeEvent(self,event):
        if self.lock_until_session_target and self.session_target_seconds and self.session_elapsed_seconds < self.session_target_seconds:
            QMessageBox.information(self,"이번 공부 목표 진행 중", "설정한 이번 공부 총 목표 시간을 채운 뒤 카메라 창을 닫을 수 있습니다."); event.ignore(); return
        if not can_close_window(self, self.store, "prevent_studio_close"): event.ignore(); return
        self.recording=False; self.clock.stop(); self.last_tick_at=None; set_danger(self.record_button,False); set_danger(self.pomodoro_button,False); self.update_awake_state(); self.finalize_recording(); self.refresh_home(); event.accept()


class HomePage(QWidget):
    def __init__(self,store:StudyStore):
        super().__init__(); self.store=store; self.selected_day=date.today(); self.studio=None; layout=QVBoxLayout(self); layout.setContentsMargins(42,30,42,34)
        header=QHBoxLayout(); title=QLabel("StudyCam"); title.setStyleSheet("font-size:30px;font-weight:800;color:#3446b8;"); self.streak_label=QLabel(); self.streak_label.setStyleSheet("font-size:21px;font-weight:800;color:#2563eb;"); self.streak_time_label=QLabel(); self.streak_time_label.setStyleSheet("font-size:18px;font-weight:800;color:white;background:#2563eb;padding:6px 10px;border-radius:7px;"); streak_row=QHBoxLayout(); streak_row.setSpacing(10); streak_row.addWidget(self.streak_label); streak_row.addWidget(self.streak_time_label); start=QPushButton("스터디 캠 실행하기"); settings=secondary("설정"); today=secondary("오늘"); header.addWidget(title); header.addSpacing(20); header.addLayout(streak_row); header.addStretch(); header.addWidget(today); header.addWidget(settings); header.addWidget(start); layout.addLayout(header); layout.addWidget(QLabel("날짜를 선택하면 그날의 목표와 만들어진 공부 영상을 확인할 수 있습니다."))
        weekly=QFrame(); weekly.setProperty("card",True); weekly_layout=QVBoxLayout(weekly); weekly_layout.addWidget(QLabel("이번 주 요일별 공부 시간")); week_row=QHBoxLayout(); self.week_labels=[]
        for weekday in ("월","화","수","목","금","토","일"):
            label=QLabel(weekday); label.setAlignment(Qt.AlignCenter); label.setMinimumHeight(48); label.setStyleSheet("background:#edf1ff;border-radius:7px;font-weight:700;"); self.week_labels.append(label); week_row.addWidget(label)
        weekly_layout.addLayout(week_row); layout.addWidget(weekly)
        card=QFrame(); card.setProperty("card",True); card_layout=QVBoxLayout(card); self.calendar=QCalendarWidget(); self.calendar.setGridVisible(True); self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader); self.calendar.setMinimumHeight(510); card_layout.addWidget(self.calendar); layout.addWidget(card,1)
        bottom=QHBoxLayout(); self.detail=QLabel(); planner=secondary("선택한 날짜의 플래너 열기"); schedule=secondary("과목·시간표 설정"); self.videos_button=secondary("선택 날짜 영상 열기"); bottom.addWidget(self.detail); bottom.addStretch(); bottom.addWidget(self.videos_button); bottom.addWidget(schedule); bottom.addWidget(planner); layout.addLayout(bottom)
        start.clicked.connect(self.open_studio); planner.clicked.connect(self.open_planner); schedule.clicked.connect(self.open_schedule); self.videos_button.clicked.connect(self.open_video); settings.clicked.connect(self.open_settings); today.clicked.connect(self.go_today); self.calendar.selectionChanged.connect(self.select_day); self.calendar.setSelectedDate(qdate(self.selected_day)); self.refresh()
    def refresh(self):
        streak=self.store.streak(); self.streak_label.setText(f"{streak}일째 공부 목표 달성 중!"); total=0
        for offset in range(streak): total+=self.store.study_seconds_for(date.today()-timedelta(days=offset))
        self.streak_time_label.setText(f"연속 달성 기간 공부시간 누계: {format_seconds(total)}"); monday=date.today()-timedelta(days=date.today().weekday())
        for offset,label in enumerate(self.week_labels): label.setText(f"{'월화수목금토일'[offset]}\n{format_seconds(self.store.study_seconds_for(monday+timedelta(days=offset)))}")
        settings=self.store.data["settings"]; completed=QTextCharFormat(); completed.setBackground(QColor(settings["completed_color"])); completed.setForeground(QColor("#1f3ea8")); failed=QTextCharFormat(); failed.setBackground(QColor(settings["failed_color"])); failed.setForeground(QColor("#a41525")); year,month=self.calendar.yearShown(),self.calendar.monthShown()
        for n in range(1,QDate(year,month,1).daysInMonth()+1): self.calendar.setDateTextFormat(QDate(year,month,n),QTextCharFormat())
        for key in self.store.data["tasks"]:
            day=date.fromisoformat(key)
            if self.store.completed(day): self.calendar.setDateTextFormat(qdate(day),completed)
        started=date.fromisoformat(self.store.data["started_on"])
        cursor=started
        while cursor < date.today():
            if not self.store.completed(cursor): self.calendar.setDateTextFormat(qdate(cursor),failed)
            cursor += timedelta(days=1)
        self.select_day()
    def select_day(self):
        self.selected_day=pydate(self.calendar.selectedDate()); tasks=self.store.tasks_for(self.selected_day); videos=self.store.data["videos"].get(self.store.key(self.selected_day),[]); has_video=bool(videos); self.videos_button.setEnabled(has_video); self.videos_button.setProperty("secondary",not has_video); self.videos_button.style().unpolish(self.videos_button); self.videos_button.style().polish(self.videos_button); self.detail.setText(f"{self.selected_day:%m월 %d일}: 목표 {len(tasks)}개 · 완료 {sum(t.get('done',False) for t in tasks)}개 · 영상 {len(videos)}개")
    def open_schedule(self):
        if ScheduleDialog(self.store,self).exec(): self.refresh()
    def open_settings(self):
        if SettingsDialog(self.store,self).exec(): self.refresh()
    def go_today(self):
        today=QDate.currentDate(); self.calendar.setCurrentPage(today.year(),today.month()); self.calendar.setSelectedDate(today)
    def open_studio(self):
        if self.studio and self.studio.isVisible(): self.studio.raise_(); self.studio.activateWindow(); return
        self.studio=StudioWindow(self.store,self.selected_day,self.refresh); self.studio.show()
    def open_planner(self): PlannerViewer(self.store,self.selected_day,self).exec()
    def open_video(self):
        videos=self.store.data["videos"].get(self.store.key(self.selected_day),[])
        if not videos: QMessageBox.information(self,"공부 영상","이 날짜에 생성된 공부 영상이 없습니다."); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(videos[-1]))


class HomeWindow(QMainWindow):
    def __init__(self, store: StudyStore):
        super().__init__(); self.store = store

    def closeEvent(self, event):
        if can_close_window(self, self.store, "prevent_home_close"): event.accept()
        else: event.ignore()

def main():
    app=QApplication(sys.argv); app.setApplicationName("StudyCam"); app.setWindowIcon(app_icon()); app.setStyleSheet(APP_STYLE); store=StudyStore(); window=HomeWindow(store); window.setWindowTitle("StudyCam"); window.setWindowIcon(app_icon()); window.resize(980,720); window.setCentralWidget(HomePage(store)); (window.showMaximized() if store.data["settings"]["start_maximized"] else window.show()); sys.exit(app.exec())

if __name__ == "__main__": main()
