"""布局工具:统一设置边距和间距。"""

from PySide6.QtWidgets import QBoxLayout


def set_layout(
    layout: QBoxLayout,
    left: int = 0,
    top: int = 0,
    right: int = 0,
    bottom: int = 0,
    spacing: int = 0,
) -> QBoxLayout:
    """统一设置布局的边距和间距。

    Args:
        layout: 布局对象。
        left: 左边距。
        top: 上边距。
        right: 右边距。
        bottom: 下边距。
        spacing: 间距。

    Returns:
        传入的布局对象,便于链式使用。
    """
    layout.setContentsMargins(left, top, right, bottom)
    layout.setSpacing(spacing)
    return layout
