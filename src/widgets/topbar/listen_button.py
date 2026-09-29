from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from src.utils.set_layout import set_layout

NORMAL_COLOR = "#4CAF50"   # 常态绿
ACTIVE_COLOR = "#DC143C"   # 进行中红


class ListenButton(QWidget):
    """监听按钮"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QHBoxLayout(self))
        self.button = QPushButton("监听")
        self.button.setCheckable(True)
        self.button.setStyleSheet("color: %s;" % NORMAL_COLOR)
        layout.addWidget(self.button)

    def set_listening(self, listening: bool):
        """切换监听按钮的显示状态"""
        if listening:
            self.button.setText("正在监听")
            self.button.setStyleSheet("color: %s;" % ACTIVE_COLOR)
        else:
            self.button.setText("监听")
            self.button.setStyleSheet("color: %s;" % NORMAL_COLOR)
