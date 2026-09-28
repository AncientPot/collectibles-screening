from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from src.utils.set_layout import set_layout


class SettingsButton(QWidget):
    """设置按钮"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QHBoxLayout(self))
        self.button = QPushButton("设置")
        layout.addWidget(self.button)
