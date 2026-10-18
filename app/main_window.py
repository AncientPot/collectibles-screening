"""主窗口:组装工具栏与内容区,并管理窗口层级切换。"""

import sys

from PySide6.QtCore import QFileSystemWatcher, Qt, QTimer, Slot
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.data_store import DataStore
from app.utils.set_layout import set_layout
from app.widgets.button_bar import ButtonBar
from app.widgets.content_area import ContentArea

if sys.platform == "win32":
    import ctypes

    _HWND_BOTTOM = ctypes.c_void_p(1)
    _SWP_NOSIZE = 0x0001
    _SWP_NOMOVE = 0x0002
    _set_window_pos = ctypes.WinDLL("user32").SetWindowPos
    _set_window_pos.argtypes = (
        ctypes.c_void_p,  # hwnd
        ctypes.c_void_p,  # hWndInsertAfter
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,  # x, y, cx, cy
        ctypes.c_uint,  # flags
    )
    _set_window_pos.restype = ctypes.c_bool


class MainWindow(QWidget):
    """主窗口。"""

    def __init__(self) -> None:
        """初始化主窗口:创建子组件并连接信号。"""
        super().__init__()
        # 创建对象
        self.store = DataStore()
        self.top_bar = ButtonBar(self.store)
        self.content_area = ContentArea(self.store)
        self._topmost = False
        # 设置布局(先于窗口尺寸,保证能按内容计算最小值)
        self._setup_layout()
        # 设置窗口
        self._setup_windows()
        # 设置槽
        self._setup_slots()
        # 监听数据目录变动,自动热加载 json 与音频文件
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(400)
        self._reload_timer.timeout.connect(self._reload_data)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.addPath(str(self.store.data_dir / "json_map"))
        self._watcher.directoryChanged.connect(self._schedule_reload)
        self._sync_audio_watches()

    def _sync_audio_watches(self) -> None:
        """同步音频目录监听:根目录与各声音同名子目录。

        新增声音目录后自动纳入监听,保证向任意子目录添加 wav 也能热刷新分组。
        """
        wanted = {str(self.store.audio_dir)}
        wanted.update(str(path) for path in self.store.audio_dir.iterdir() if path.is_dir())
        current = set(self._watcher.directories())
        for path in current - wanted - {str(self.store.data_dir / "json_map")}:
            self._watcher.removePath(path)
        for path in wanted - current:
            self._watcher.addPath(path)

    def _schedule_reload(self) -> None:
        """数据目录有变动,防抖后统一热加载。"""
        self._reload_timer.start()

    @Slot()
    def _reload_data(self) -> None:
        """重载数据并重建下拉选项与设置界面的物品列表。

        数据暂不合法(如编辑到一半)时保留旧数据,等待下次文件变动重试;
        音频文件不参与缓存,重建选项即可刷新"暂无声音"分组与试听。
        """
        if self.store.reload():
            self.top_bar.reload_options()
            self.top_bar.settings_dialog.reload_items()
        self._sync_audio_watches()

    def _setup_windows(self) -> None:
        """设置窗口标题,默认以最小尺寸打开并位于屏幕左上角。"""
        self.setWindowTitle("听声鉴宝")
        self.resize(self.minimumSizeHint())
        self.move(0, 0)

    def _setup_layout(self) -> None:
        """设置主布局:工具栏在上,内容区在下。"""
        layout = set_layout(QVBoxLayout(self))
        layout.addWidget(self.top_bar, 0)
        layout.addWidget(self.content_area, 1)

    def _setup_slots(self) -> None:
        """连接工具栏信号。"""
        self.top_bar.filter_changed.connect(self.content_area.refresh)
        self.top_bar.toggle_topmost.connect(self._toggle_topmost)

    def showEvent(self, event: QShowEvent) -> None:
        """显示时按当前物品数量自适应窗口高度。

        Args:
            event: 显示事件。
        """
        super().showEvent(event)
        self.content_area.fit_window_height()

    @Slot()
    def _toggle_topmost(self) -> None:
        """热键切换窗口层级:置顶 <-> 最底层。"""
        self._topmost = not self._topmost
        self.content_area.set_topmost(self._topmost)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._topmost)
        self.show()
        if not self._topmost and sys.platform == "win32":
            # HWND_BOTTOM + SWP_NOSIZE | SWP_NOMOVE:仅改变层级,不动窗口
            _set_window_pos(int(self.winId()), _HWND_BOTTOM, 0, 0, 0, 0, _SWP_NOSIZE | _SWP_NOMOVE)
