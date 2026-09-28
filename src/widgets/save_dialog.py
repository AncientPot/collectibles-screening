from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout


class SaveDialog(QDialog):
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
