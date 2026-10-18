"""流式布局:子项按自身大小从左到右排列,宽度不够时自动换行。"""

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget


class FlowLayout(QLayout):
    """流式布局:子项按自身大小从左到右排列,宽度不够时自动换行。"""

    def __init__(self, parent: QWidget | None = None, spacing: int = 8) -> None:
        """初始化布局。

        Args:
            parent: 父控件。
            spacing: 子项水平和垂直间距。
        """
        super().__init__(parent)
        self.setSpacing(spacing)
        self.item_list: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:
        """添加子项。

        Args:
            item: 布局项。
        """
        self.item_list.append(item)

    def count(self) -> int:
        """子项数量。"""
        return len(self.item_list)

    def itemAt(self, index: int) -> QLayoutItem | None:
        """按索引取子项。

        Args:
            index: 索引,越界返回 None。
        """
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        """按索引移除并返回子项。

        Args:
            index: 索引,越界返回 None。
        """
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        """流式布局不希望在水平或垂直方向独占扩展空间。"""
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        """高度依赖宽度。"""
        return True

    def heightForWidth(self, width: int) -> int:
        """计算给定宽度下布局所需高度。

        Args:
            width: 可用宽度。

        Returns:
            所需高度。
        """
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        """布置所有子项。"""
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        """推荐尺寸,取最小尺寸。"""
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        """最小尺寸:最大子项最小尺寸加两倍间距。"""
        size = QSize()
        for item in self.item_list:
            widget = item.widget()
            hint = widget.minimumSizeHint() if widget is not None else item.minimumSize()
            size = size.expandedTo(hint)
        size += QSize(2 * self.spacing(), 2 * self.spacing())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        """从左到右排布子项,宽度不够时换行。

        尺寸取控件自身的 sizeHint:新建尚未显示的控件,其布局项的
        sizeHint 为 (0,0),会导致高度计算与自适应偏小。

        Args:
            rect: 可用区域。
            test_only: 为 True 时只计算高度,不移动子项。

        Returns:
            布局所需高度。
        """
        spacing = self.spacing()
        x, y = rect.x(), rect.y()
        line_height = 0
        for item in self.item_list:
            widget = item.widget()
            hint = widget.sizeHint() if widget is not None else item.sizeHint()
            next_x = x + hint.width() + spacing
            if next_x - spacing > rect.right() and line_height > 0:
                x = rect.x()
                y += line_height + spacing
                next_x = x + hint.width() + spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y()
