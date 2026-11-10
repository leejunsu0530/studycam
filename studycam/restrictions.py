"""Focus-period restrictions: local browser rules and explicitly selected apps."""
from __future__ import annotations

import ctypes
import json
import ntpath
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PySide6.QtCore import QObject, QTimer

PORT = 48736
PROTECTED = {"explorer.exe", "dwm.exe", "csrss.exe", "winlogon.exe",
             "services.exe", "svchost.exe", "systemsettings.exe", "taskmgr.exe",
             "studycam.exe", "python.exe", "pythonw.exe"}


def close_selected_windows(paths):
    """Ask only windows belonging to selected executables to close, never kill."""
    if sys.platform != "win32" or not paths:
        return
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    selected = {ntpath.normcase(ntpath.normpath(path)) for path in paths}
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]

    @callback_type
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value or pid.value == os.getpid():
            return True
        handle = kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return True
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(buffer))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                path = ntpath.normcase(ntpath.normpath(buffer.value))
                if ntpath.basename(path) not in PROTECTED and path in selected:
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)
        finally:
            kernel32.CloseHandle(handle)
        return True

    user32.EnumWindows(visit, 0)


class FocusRestrictions(QObject):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.active = False
        self.rules = []
        self.server = None
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.check_apps)

    def start(self):
        self.rules = list(self.store.data.get("restriction_rules", []))
        self.active = True
        self.timer.start()
        self.check_apps()
        if any(rule.get("kind") == "site" for rule in self.rules) and self.server is None:
            owner = self

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path != "/rules":
                        self.send_error(404)
                        return
                    data = json.dumps({"active": owner.active, "rules": [
                        rule for rule in owner.rules if rule.get("kind") == "site"
                    ]}).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

                def log_message(self, *args):
                    pass

            self.server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
            self.server.daemon_threads = True
            threading.Thread(target=self.server.serve_forever, daemon=True).start()
    def stop(self):
        self.active = False
        self.timer.stop()

    def check_apps(self):
        if self.active:
            paths = [path for rule in self.rules if rule.get("kind") == "app"
                     for path in rule.get("patterns", [])]
            close_selected_windows(paths)
