"""主窗口冒烟测试:验证组件装配与热键信号接线。"""

from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.widgets.content_area import MIN_CONTENT_HEIGHT


def test_main_window_assembly(qapp: QApplication, fake_keyboard: dict[str, Any]) -> None:
    """主窗口装配真实数据,热键触发一次后窗口进入置顶状态。"""
    window = MainWindow()
    assert window.windowTitle() == "听声鉴宝"
    assert window.content_area.count_label.text() == "共 180 件"
    # 默认热键 "-" 经工具栏转发到主窗口,切换置顶标志并同步状态显示
    fake_keyboard["hotkeys"]["left"]()
    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert window.content_area.topmost_label.text() == "置顶:是"


def test_data_hot_reload_wiring(qapp: QApplication, fake_keyboard: dict[str, Any]) -> None:
    """数据变动经防抖定时器触发热加载;数据未变时重载亦不报错。"""
    window = MainWindow()
    window._schedule_reload()
    assert window._reload_timer.isActive()
    window._reload_data()
    assert window.content_area.count_label.text() == "共 180 件"


def test_window_opens_at_top_left(qapp: QApplication, fake_keyboard: dict[str, Any]) -> None:
    """窗口启动默认位于屏幕左上角。"""
    window = MainWindow()
    window.show()
    assert window.pos() == QPoint(0, 0)


def test_window_height_fits_all_items(qapp: QApplication, fake_keyboard: dict[str, Any]) -> None:
    """窗口高度随筛选结果自适应,恰好完整展示所有物品。"""

    def needed(target: MainWindow) -> int:
        content = target.content_area
        return content.flow_layout.heightForWidth(content.scroll_area.viewport().width())

    window = MainWindow()
    window.show()
    qapp.processEvents()
    assert needed(window) <= window.content_area.scroll_area.viewport().height()
    # 筛选后物品减少:高度收缩,且仍完整展示
    tall = window.height()
    window.top_bar.category_combo.setCurrentText("收藏品")
    qapp.processEvents()
    assert window.content_area.count_label.text() == "共 52 件"
    assert needed(window) <= window.content_area.scroll_area.viewport().height()
    assert window.height() < tall

    # 单件物品:高度恰好内容所需(不低于内容下限),不被滚动区默认最小尺寸顶住
    window.content_area.refresh(sound="双颈鲁特琴声")
    qapp.processEvents()
    area = window.content_area
    assert area.flow_layout.count() == 1
    assert max(needed(window), MIN_CONTENT_HEIGHT) == area.scroll_area.viewport().height()

    # 空结果后再切回:视口不塌缩,自适应仍精确无偏差
    window.content_area.refresh(category="工具", sound="金手镯声")
    qapp.processEvents()
    assert window.content_area.flow_layout.count() == 0
    assert window.content_area.scroll_area.viewport().height() >= MIN_CONTENT_HEIGHT
    window.content_area.refresh()
    qapp.processEvents()
    assert needed(window) == window.content_area.scroll_area.viewport().height()

    # 连续快速切换声音(事件循环未及时处理布局)不应塌缩或覆盖
    cached_extra = window.content_area._extra_height  # noqa: SLF001 验证缓存被复用
    assert cached_extra is not None
    for _ in range(4):
        window.top_bar.switch_sound_down()
    qapp.processEvents()
    area = window.content_area
    assert area._extra_height == cached_extra  # noqa: SLF001
    fit = max(needed(window), MIN_CONTENT_HEIGHT)
    assert area.scroll_area.viewport().height() == fit
    assert window.height() == cached_extra + fit
