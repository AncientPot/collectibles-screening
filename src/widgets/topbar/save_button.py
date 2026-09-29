from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from src.utils.set_layout import set_layout


class SaveButton(QWidget):
    """保存按钮"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QHBoxLayout(self))
        self.button = QPushButton("保存学习")
        layout.addWidget(self.button)
