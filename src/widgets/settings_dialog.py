import threading

import keyboard
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from src.utils.set_layout import set_layout


class HotkeySelector(QWidget):
    """快捷键选择框：只读显示当前键，录制按钮捕获下一次按键（Esc 取消）"""

    _captured = Signal(str)

    def __init__(self, hotkey: str, parent=None):
        super().__init__(parent)
        self._previous_hotkey = hotkey
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

    def _on_record_clicked(self, *_):
        """开始录制快捷键，等待用户下一次按键"""
        self._previous_hotkey = self.hotkey_edit.text()
        self.record_button.setEnabled(False)
        self.hotkey_edit.setText("请按键（Esc 取消）...")
        threading.Thread(target=self._capture_hotkey, daemon=True).start()

    def _capture_hotkey(self):
        """在 keyboard 钩子线程外捕获按键，经信号转回界面线程；Esc 视为取消"""
        hotkey = keyboard.read_hotkey(suppress=False)
        self._captured.emit(hotkey if hotkey != "esc" else "")

    def _on_captured(self, hotkey: str):
        self.record_button.setEnabled(True)
        self.hotkey_edit.setText(hotkey if hotkey else self._previous_hotkey)


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None, max_seconds: int = 5,
                 hotkey: str = "num +", visibility_hotkey: str = "-", play_volume: float = 1.0):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self._setup_ui(max_seconds, hotkey, visibility_hotkey, play_volume)
        self._setup_geometry()

    def _setup_ui(self, max_seconds: int, hotkey: str, visibility_hotkey: str, play_volume: float):
        """组装ui"""
        self.max_seconds_spin_box = QSpinBox()
        self.max_seconds_spin_box.setRange(1, 3600)
        self.max_seconds_spin_box.setValue(max_seconds)
        self.play_volume_spin_box = QDoubleSpinBox()
        self.play_volume_spin_box.setRange(0.1, 100.0)
        self.play_volume_spin_box.setDecimals(1)
        self.play_volume_spin_box.setSingleStep(0.5)
        self.play_volume_spin_box.setValue(play_volume)
        self.hotkey_selector = HotkeySelector(hotkey)
        self.visibility_hotkey_selector = HotkeySelector(visibility_hotkey)
        self.rebuild_button = QPushButton("重建保底模板")
        self.rebuild_status_label = QLabel()
        buttons = QDialogButtonBox()
        buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        action_layout = QHBoxLayout()
        action_layout.addWidget(self.rebuild_button)
        action_layout.addWidget(self.rebuild_status_label, 1)
        action_layout.addWidget(buttons)
        layout = QFormLayout(self)
        layout.addRow("最长监听时长(秒):", self.max_seconds_spin_box)
        layout.addRow("播放音量(倍, 1.0=原始):", self.play_volume_spin_box)
        layout.addRow("监听快捷键:", self.hotkey_selector)
        layout.addRow("置顶快捷键:", self.visibility_hotkey_selector)
        layout.addRow(action_layout)

    def on_rebuild_progress(self, done: int, total: int, category: str):
        """保底模板采集进度更新"""
        self.rebuild_status_label.setText("采集 %s (%d/%d)..." % (category, done, total))

    def on_rebuild_finished(self, ok: bool):
        """保底模板重建结束"""
        self.rebuild_button.setEnabled(True)
        self.rebuild_status_label.setText("已完成" if ok else "失败，详见控制台输出")

    def _setup_geometry(self):
        """宽度设为主界面一半（不小于表单最小宽度）"""
        parent = self.parentWidget()
        window = parent.window() if parent else None
        if window is not None:
            self.resize(int(window.width() / 2), self.height())

    def showEvent(self, event):
        """显示后水平居中于主界面，顶边上移与主界面顶边对齐"""
        super().showEvent(event)
        parent = self.parentWidget()
        window = parent.window() if parent else None
        if window is not None:
            center_x = window.geometry().center().x()
            self.move(center_x - self.width() // 2, window.frameGeometry().top())

    @property
    def max_seconds(self) -> int:
        return self.max_seconds_spin_box.value()

    @property
    def play_volume(self) -> float:
        return self.play_volume_spin_box.value()

    @property
    def hotkey(self) -> str:
        return self.hotkey_selector.hotkey

    @property
    def visibility_hotkey(self) -> str:
        return self.visibility_hotkey_selector.hotkey
