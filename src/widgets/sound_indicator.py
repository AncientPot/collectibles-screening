from PySide6.QtWidgets import QHBoxLayout, QWidget

from src.utils.set_layout import set_layout
from src.widgets.topbar.auto_fit import AutoFitComboBox

ANY_SOUND = "任意音频"


class SoundComboBox(AutoFitComboBox):
    """声音类别下拉框（弹窗首帧加固见 AutoFitComboBox）"""


class SoundIndicator(QWidget):
    """声音类别选择栏（宽度与其他下拉框一致：按最长选项自适应）"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QHBoxLayout(self))
        self.category_combo_box = SoundComboBox()
        self.category_combo_box.addItem(ANY_SOUND)
        layout.addWidget(self.category_combo_box)
        self._harden_popup()

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
        self._harden_popup()

    def select_category(self, category: str):
        """比对结果自动选中该类别（不锁定，用户仍可改选）"""
        if self.category_combo_box.findText(category) < 0:
            self.category_combo_box.addItem(category)
        self.category_combo_box.setCurrentText(category)
        self._harden_popup()

    def _harden_popup(self, *_):
        """弹出列表按行数给最小高度，杜绝偶发的空列表渲染"""
        row_height = self.category_combo_box.view().sizeHintForRow(0)
        if row_height > 0:
            self.category_combo_box.view().setMinimumHeight(
                row_height * self.category_combo_box.count())
