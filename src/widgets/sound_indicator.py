from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from src.utils.set_layout import set_layout

ANY_SOUND = "任意声音"


class SoundIndicator(QWidget):
    """声音类别选择栏"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QHBoxLayout(self))
        self.category_combo_box = QComboBox()
        self.category_combo_box.addItem(ANY_SOUND)
        layout.addWidget(self.category_combo_box)

    @property
    def current_category(self) -> str:
        return self.category_combo_box.currentText()

    def set_categories(self, categories: list[str]):
        """填充声音类别选项，保留当前选择"""
        previous = self.current_category
        self.category_combo_box.blockSignals(True)
        self.category_combo_box.clear()
        self.category_combo_box.addItem(ANY_SOUND)
        self.category_combo_box.addItems(categories)
        restored = previous if self.category_combo_box.findText(previous) >= 0 else ANY_SOUND
        self.category_combo_box.setCurrentText(restored)
        self.category_combo_box.blockSignals(False)

    def select_category(self, category: str):
        """比对结果自动选中该类别（不锁定，用户仍可改选）"""
        if self.category_combo_box.findText(category) < 0:
            self.category_combo_box.addItem(category)
        self.category_combo_box.setCurrentText(category)
