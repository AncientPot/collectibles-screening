from PySide6.QtWidgets import QHBoxLayout, QWidget

from src.utils.set_layout import set_layout
from src.widgets.topbar.auto_fit import AutoFitComboBox


class FormatSelector(QWidget):
    """格式选择栏"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QHBoxLayout(self))
        self.combo_box = AutoFitComboBox()
        self.combo_box.addItems(["任意格式", "1x2", "1x3", "2x2", "2x3"])
        layout.addWidget(self.combo_box)
