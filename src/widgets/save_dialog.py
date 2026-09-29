from PySide6.QtWidgets import QComboBox, QDialogButtonBox, QFormLayout

from src.widgets.top_aligned_dialog import TopAlignedDialog


class SaveDialog(TopAlignedDialog):
    """保存采集音频对话框：选择该音频对应的声音类别名称"""

    def __init__(self, parent=None, categories: list[str] | None = None,
                 default: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("保存采集音频")
        self._setup_ui(categories or [], default)
        self._setup_geometry()

    def _setup_ui(self, categories: list[str], default: str | None):
        """组装ui"""
        self.category_combo_box = QComboBox()
        self.category_combo_box.addItems(categories)
        if default is not None and self.category_combo_box.findText(default) >= 0:
            self.category_combo_box.setCurrentText(default)
        else:
            # 无默认值时保持未选中，避免停在第一项造成误存
            self.category_combo_box.setCurrentIndex(-1)
        buttons = QDialogButtonBox()
        ok_button = buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        ok_button.setEnabled(self.category_combo_box.currentIndex() >= 0)
        self.category_combo_box.currentTextChanged.connect(
            lambda _: ok_button.setEnabled(self.category_combo_box.currentIndex() >= 0)
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QFormLayout(self)
        layout.addRow("音频名称:", self.category_combo_box)
        layout.addRow(buttons)

    @property
    def category_name(self) -> str:
        return self.category_combo_box.currentText().strip()
