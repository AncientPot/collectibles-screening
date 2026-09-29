from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from src.utils.set_layout import set_layout


class PlayButton(QWidget):
    """播放按钮：播放当前声音类别对应的基准音频"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QHBoxLayout(self))
        self.button = QPushButton("播放")
        layout.addWidget(self.button)
