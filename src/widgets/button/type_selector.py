from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from src.utils.set_layout import set_layout


class TypeSelector(QWidget):
    """类别选择栏"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QHBoxLayout(self))
        self.combo_box = QComboBox()
        self.combo_box.addItems([
            "神秘货物",
            "建筑材料", "能源物品", "生活物品",
            "工具", "收藏品", "电子产品", "仪器仪表", "军用杂物", "医疗杂物", "纸制品",
        ])
        layout.addWidget(self.combo_box)
