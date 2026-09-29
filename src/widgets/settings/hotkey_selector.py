import threading

import keyboard
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from src.utils.set_layout import set_layout


class HotkeySelector(QWidget):
    """快捷键选择框：只读显示当前键，录制按钮捕获下一次按键（Esc 取消）。
    录制期间通过 on_capture_start/on_capture_end 挂起/恢复全局热键，
    避免按下的新键同时触发当前绑定的热键动作。"""

    _captured = Signal(str)
    capture_started = Signal()
    capture_ended = Signal()

    def __init__(self, hotkey: str, parent=None,
                 on_capture_start=None, on_capture_end=None):
        super().__init__(parent)
        self._previous_hotkey = hotkey
        self._capturing = False
        self._on_capture_start = on_capture_start
        self._on_capture_end = on_capture_end
        self._setup_ui(hotkey)
        self._captured.connect(self._on_captured)

    def _setup_ui(self, hotkey: str):
        """组装ui"""
        self.hotkey_edit = QLineEdit(hotkey)
        self.hotkey_edit.setReadOnly(True)
        self.record_button = QPushButton("录制")
        self.record_button.clicked.connect(self._on_record_clicked)
        layout = set_layout(QHBoxLayout(self))
        layout.addWidget(self.hotkey_edit)
        layout.addWidget(self.record_button)

    @property
    def hotkey(self) -> str:
        return self.hotkey_edit.text()

    @property
    def is_capturing(self) -> bool:
        """是否正在等待按键录制。不能用按钮可用性推断：两个录制框互斥
        时按钮也会被禁用，但并未在录制，cancel 须跳过这种被动禁用。"""
        return self._capturing

    def cancel(self):
        """结束未完成的录制并恢复原键显示（对话框关闭/确认时调用）"""
        if self.is_capturing:
            self._on_captured("")

    def _on_record_clicked(self, *_):
        """开始录制快捷键，等待用户下一次按键；先挂起全局热键"""
        self._previous_hotkey = self.hotkey_edit.text()
        self._capturing = True
        self.record_button.setEnabled(False)
        self.hotkey_edit.setText("请按键（Esc 取消）...")
        if self._on_capture_start is not None:
            self._on_capture_start()
        self.capture_started.emit()
        threading.Thread(target=self._capture_hotkey, daemon=True).start()

    def _capture_hotkey(self):
        """在 keyboard 钩子线程外捕获按键，经信号转回界面线程；Esc 或异常视为取消"""
        try:
            hotkey = keyboard.read_hotkey(suppress=False)
        except Exception:
            hotkey = ""
        self._captured.emit(hotkey if hotkey != "esc" else "")

    def _on_captured(self, hotkey: str):
        self._capturing = False
        if self._on_capture_end is not None:
            self._on_capture_end()
        self.capture_ended.emit()
        self.record_button.setEnabled(True)
        self.hotkey_edit.setText(hotkey if hotkey else self._previous_hotkey)
