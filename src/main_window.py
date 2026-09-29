from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from src.core.filter_controller import FilterController
from src.core.listen_controller import ListenController
from src.core.save_controller import SaveController
from src.utils.set_layout import set_layout
from src.widgets.content_area import ContentArea
from src.widgets.top_bar import TopBar

class MainWindow(QWidget):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("暗区突围无限-听声鉴宝")
        self._setup_geometry()
        self._setup_ui()
        self.set_topmost(True)  # 启动即置顶最上层

    def _setup_ui(self):
        """组装ui"""
        self.top_bar = TopBar()
        self.content_area = ContentArea()
        self.filter_controller = FilterController(self.top_bar, self.content_area)
        self.listen_controller = ListenController(self.top_bar)
        self.save_controller = SaveController(self.top_bar, self.listen_controller.matcher)
        self.listen_controller.match_completed.connect(self._on_match_completed)
        self.top_bar.sound_indicator.set_categories(self.listen_controller.matcher.categories)
        # 类别名（最多5字）长于初始占位项，填充后重算统一宽度避免截断
        self.top_bar.unify_combo_widths()
        self._create_main_layout()

    def _on_match_completed(self, category: str, probability: float):
        """比对完成：自动选中该类别并在监听右侧显示相似度（类别仍可手动改选）"""
        if category:
            self.top_bar.sound_indicator.select_category(category)
            self.top_bar.probability_label.setText("%.0f%%" % (probability * 100))
        elif probability < 0:
            self.top_bar.probability_label.setText("比对失败")
        else:
            self.top_bar.probability_label.setText("未检测到有效声音")

    def _create_main_layout(self):
        """创建主布局"""
        layout = set_layout(QVBoxLayout(self))
        layout.addWidget(self.top_bar, 0)
        layout.addWidget(self.content_area, 1)

    def _setup_geometry(self):
        """设置窗口位置和大小"""
        size = QApplication.primaryScreen().size()
        w, h = int(6 * size.width() / 13), int(size.height() / 6)
        self.setGeometry(0, 0, w, h)
        self.setFixedSize(w, h)

    def is_topmost(self) -> bool:
        return bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

    def set_topmost(self, topmost: bool):
        """切换窗口置顶显示；取消置顶时沉到最底层"""
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, topmost)
        self.show()
        if topmost:
            self.raise_()
            self.activateWindow()
        else:
            self.lower()
