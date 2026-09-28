from PySide6.QtWidgets import QListWidget, QListWidgetItem, QListView, QVBoxLayout, QWidget

from src.utils.set_layout import set_layout

class ContentArea(QWidget):
    """物品展示区"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setWrapping(True)
        self.list_widget.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_widget.setMovement(QListView.Movement.Static)
        self.list_widget.setSpacing(6)
        layout = set_layout(QVBoxLayout(self))
        layout.addWidget(self.list_widget)

    def show_items(self, items):
        """按（名称, 颜色）列表刷新展示"""
        self.list_widget.clear()
        for name, color in items:
            item = QListWidgetItem(name)
            item.setForeground(color)
            self.list_widget.addItem(item)
