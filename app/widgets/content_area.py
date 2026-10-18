"""主窗口内容区:以流式网格显示筛选出的物品。"""

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.data_store import DataStore
from app.utils.set_layout import set_layout
from app.widgets.flow_layout import FlowLayout

QUALITY_COLORS = {"红": "#d32f2f", "金": "#b8860b", "紫": "#8e24aa"}
# 品质显示顺序:红在前,其次金,最后紫;未知品质排末尾
QUALITY_ORDER = {"红": 0, "金": 1, "紫": 2}
# 空结果时保留的最小内容区高度;视口塌缩会让窗口高度中的固定部分
# (工具栏、计数行等)被测小,导致下一次自适应偏低
MIN_CONTENT_HEIGHT = 24


class ContentArea(QFrame):
    """主窗口内容区,以流式网格显示筛选出的物品名称,颜色为对应品质。"""

    def __init__(self, store: DataStore) -> None:
        """初始化内容区并显示全部物品。

        Args:
            store: 数据层。
        """
        super().__init__()
        # 创建对象
        self._store = store
        self.count_label = QLabel()
        self.topmost_label = QLabel("置顶:否")
        self.hint_label = QLabel("仅包含紫色品质以上常见容易混淆的物品")
        self.scroll_area = QScrollArea()
        self.name_container = QWidget()
        self.flow_layout = FlowLayout(spacing=8)
        # 窗口高度中固定部分(工具栏、计数行等)的缓存,见 _fixed_extra_height
        self._extra_height: int | None = None
        # 设置控件
        self._setup_widgets()
        # 设置布局
        self._setup_layout()
        # 初始显示全部物品
        self.refresh()

    def _setup_widgets(self) -> None:
        """设置滚动区与提示样式。

        窗口高度会随物品数量自适应到恰好完整展示,关闭滚动条,
        也避免滚动条出现/消失导致的内容宽度抖动。
        """
        self.hint_label.setStyleSheet("color: gray;")
        self.topmost_label.setStyleSheet("color: gray;")
        self.name_container.setLayout(self.flow_layout)
        self.scroll_area.setWidget(self.name_container)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _setup_layout(self) -> None:
        """顶部为计数与提示,下方为可滚动的名称网格。"""
        layout = set_layout(QVBoxLayout(self), left=4, top=4, right=4, bottom=4)
        top_row = set_layout(QHBoxLayout(), spacing=12)
        top_row.addWidget(self.count_label)
        top_row.addWidget(self.topmost_label)
        top_row.addWidget(self.hint_label)
        top_row.addStretch()
        layout.addLayout(top_row)
        layout.addWidget(self.scroll_area, 1)

    @Slot(str, str, str)
    def refresh(self, category: str = "", format_: str = "", sound: str = "") -> None:
        """按筛选条件刷新物品名称网格。

        Args:
            category: 类别名,空字符串表示不过滤。
            format_: 格式名,空字符串表示不过滤。
            sound: 声音名,空字符串表示不过滤。
        """
        items = self._store.filter_items(category, format_, sound)
        items.sort(key=lambda pair: QUALITY_ORDER.get(pair[1].quality, len(QUALITY_ORDER)))
        self.count_label.setText(f"共 {len(items)} 件")
        self._clear_names()
        for name, info in items:
            label = QLabel(name)
            if info.quality in QUALITY_COLORS:
                label.setStyleSheet(f"color: {QUALITY_COLORS[info.quality]};")
            self.flow_layout.addWidget(label)
        # 新建标签的尺寸提示需经事件循环解析,延后一拍再按内容自适应高度
        QTimer.singleShot(0, self.fit_window_height)

    def fit_window_height(self) -> None:
        """把窗口高度调整为恰好完整展示当前所有物品,宽度保持不变。

        内容高度下限为 MIN_CONTENT_HEIGHT(空结果也保留),防止视口塌缩;
        最小高度同步设为内容所需,既解除滚动区默认最小尺寸的下限,
        也避免滚动条关闭后被手动缩小到裁剪物品。
        尚未显示(如初始化阶段)时跳过,由主窗口显示时统一触发。
        """
        if not self.isVisible():
            return
        window = self.window()
        viewport = self.scroll_area.viewport()
        needed = max(self.flow_layout.heightForWidth(viewport.width()), MIN_CONTENT_HEIGHT)
        height = self._fixed_extra_height(window) + needed
        window.setMinimumHeight(height)
        window.resize(window.width(), height)

    def _fixed_extra_height(self, window: QWidget) -> int:
        """测量并缓存窗口高度中不属于滚动视口的固定部分。

        工具栏、计数行、边距等在运行期不会变化,测量一次后复用。
        连续切换声音时,上一次窗口缩放的子布局可能尚未同步到视口,
        若每次现场测量"窗口高 - 视口高"会得到偏小甚至为负的旧值,
        导致窗口塌缩、控件互相覆盖。

        Args:
            window: 主窗口。

        Returns:
            固定部分的高度(像素),不为负。
        """
        extra = self._extra_height
        if extra is None:
            layout = window.layout()
            if layout is not None:
                layout.activate()
            extra = max(window.height() - self.scroll_area.viewport().height(), 0)
            self._extra_height = extra
        return extra

    @Slot(bool)
    def set_topmost(self, topmost: bool) -> None:
        """更新当前置顶状态显示。

        Args:
            topmost: 是否处于窗口置顶状态。
        """
        self.topmost_label.setText("置顶:是" if topmost else "置顶:否")

    def _clear_names(self) -> None:
        """清空已显示的名称标签。"""
        while (item := self.flow_layout.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
