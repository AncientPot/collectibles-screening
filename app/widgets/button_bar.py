"""顶部工具栏:筛选下拉、试听播放与设置入口。"""

from PySide6.QtCore import QEvent, QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QKeyEvent, QStandardItemModel
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QPushButton

from app.config import AppConfig
from app.data_store import DataStore
from app.utils.hotkey import HotkeyManager
from app.utils.set_layout import set_layout
from app.widgets.settings_dialog import SettingsDialog

FILTER_ALL = "全部"
# 类别下拉首项显示为"神秘货物",选中即不过滤
CATEGORY_ALL = "神秘货物"
# 置顶切换动作,默认热键见 AppConfig
ACTION_TOPMOST = "topmost"
# 播放动作,默认热键见 AppConfig
ACTION_PLAY = "play"
# 声音切换动作及其固定热键(上下方向键,不提供设置)
ACTION_SOUND_UP = "sound_up"
ACTION_SOUND_DOWN = "sound_down"
DEFAULT_SOUND_UP_HOTKEY = "up"
DEFAULT_SOUND_DOWN_HOTKEY = "down"
# 设置界面中的快捷键描述
HOTKEY_LABELS = {ACTION_PLAY: "播放快捷键", ACTION_TOPMOST: "置顶快捷键"}


class ButtonBar(QFrame):
    """主窗口顶部工具栏。"""

    # 类别、格式、声音三个筛选条件;空字符串表示不过滤
    filter_changed = Signal(str, str, str)
    # 热键按下,请求主窗口切换置顶/置底
    toggle_topmost = Signal()

    def __init__(self, store: DataStore, config: AppConfig | None = None) -> None:
        """初始化工具栏控件并连接信号。

        Args:
            store: 数据层。
            config: 运行配置(音量与可设置快捷键),缺省时读取 data/config.json。
        """
        super().__init__()
        # 创建对象
        self._store = store
        self._config = config if config is not None else AppConfig()
        self.category_combo = QComboBox()
        self.format_combo = QComboBox()
        self.sound_combo = QComboBox()
        self.settings_button = QPushButton("设置")
        self.sound_effect = QSoundEffect()
        self.sound_effect.setVolume(self._config.volume)
        self.hotkey_manager = HotkeyManager()
        self._hotkey_actions = {
            ACTION_PLAY: self.play_sound,
            ACTION_TOPMOST: self.toggle_topmost.emit,
            ACTION_SOUND_UP: self.switch_sound_up,
            ACTION_SOUND_DOWN: self.switch_sound_down,
        }
        # 设置控件
        self._setup_widgets()
        # 设置布局
        self._setup_layout()
        # 设置槽
        self._setup_slots()

    def _setup_widgets(self) -> None:
        """填充下拉选项、按持久化配置注册热键并创建设置界面。"""
        self._fill_combos()
        self.hotkey_manager.register(ACTION_PLAY, self._config.hotkey(ACTION_PLAY))
        self.hotkey_manager.register(ACTION_TOPMOST, self._config.hotkey(ACTION_TOPMOST))
        self.hotkey_manager.register(ACTION_SOUND_UP, DEFAULT_SOUND_UP_HOTKEY)
        self.hotkey_manager.register(ACTION_SOUND_DOWN, DEFAULT_SOUND_DOWN_HOTKEY)
        self.settings_dialog = SettingsDialog(
            self.hotkey_manager,
            self._store,
            self._config,
            HOTKEY_LABELS,
            parent=self,
        )
        # 拦截输入控件自身的上下方向键处理,方向键仅保留全局热键切换声音一条路径
        for widget in (
            self.category_combo,
            self.format_combo,
            self.sound_combo,
            self.settings_dialog.volume_spin,
        ):
            widget.installEventFilter(self)

    def _fill_combos(self) -> None:
        """按数据层当前内容填充三个下拉选项。"""
        self.category_combo.addItem(CATEGORY_ALL, FILTER_ALL)
        for name in self._store.categories():
            self.category_combo.addItem(name, name)
        self.format_combo.addItem(FILTER_ALL, FILTER_ALL)
        for name in self._store.formats():
            self.format_combo.addItem(name, name)
        self.sound_combo.addItem(FILTER_ALL, FILTER_ALL)
        model = self.sound_combo.model()
        assert isinstance(model, QStandardItemModel)
        last_group = ""
        for name, label, group in self._store.sounds():
            if group and group != last_group:
                # 新分组前插入标题行,禁用不可选
                self.sound_combo.addItem(f"── {group} ──")
                header = model.item(self.sound_combo.count() - 1)
                if header is not None:
                    header.setEnabled(False)
            last_group = group
            self.sound_combo.addItem(label, name)

    def reload_options(self) -> None:
        """数据热更新后重建下拉选项,保留仍然有效的选择。

        无效选择回退为"全部",并发出筛选信号刷新内容区。
        """
        combos = (self.category_combo, self.format_combo, self.sound_combo)
        wanted = [combo.currentData() for combo in combos]
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
        self._fill_combos()
        for combo, data in zip(combos, wanted, strict=True):
            index = combo.findData(data) if data is not None else 0
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)
        self.filter_changed.emit(*self.current_filter())

    def _setup_layout(self) -> None:
        """横向排列各控件。"""
        layout = set_layout(QHBoxLayout(self))
        layout.addWidget(self.category_combo)
        layout.addWidget(self.format_combo)
        layout.addWidget(self.sound_combo)
        layout.addWidget(self.settings_button)
        layout.addStretch()

    def _setup_slots(self) -> None:
        """连接控件与热键信号。"""
        self.category_combo.currentTextChanged.connect(self.emit_filter_changed)
        self.format_combo.currentTextChanged.connect(self.emit_filter_changed)
        self.sound_combo.currentTextChanged.connect(self.emit_filter_changed)
        self.settings_button.clicked.connect(self.open_settings)
        self.settings_dialog.volume_spin.valueChanged.connect(self.set_volume)
        self.hotkey_manager.hotkey_pressed.connect(self.trigger_hotkey)

    def current_filter(self) -> tuple[str, str, str]:
        """读取三个下拉列表的当前条件;"全部"转为空字符串表示不过滤。

        Returns:
            (类别, 格式, 声音) 三元组,未选择时对应位置为空字符串。
        """

        def to_condition(combo: QComboBox) -> str:
            data = combo.currentData()
            return "" if data in (None, FILTER_ALL) else str(data)

        return (
            to_condition(self.category_combo),
            to_condition(self.format_combo),
            to_condition(self.sound_combo),
        )

    @Slot(str)
    def emit_filter_changed(self, _text: str) -> None:
        """任一筛选条件变化时,发出当前筛选条件。"""
        self.filter_changed.emit(*self.current_filter())

    @Slot()
    def play_sound(self) -> None:
        """播放声音下拉列表中选中的声音,音量取设置界面输入框数值;声音为全部时不播放。"""
        _, _, sound = self.current_filter()
        path = self._store.sound_file(sound)
        if path is None:
            return
        self.sound_effect.setSource(QUrl.fromLocalFile(str(path)))
        self.sound_effect.play()

    @Slot(float)
    def set_volume(self, value: float) -> None:
        """按设置界面输入框数值实时调整播放音量并持久化。"""
        self.sound_effect.setVolume(value)
        self._config.set_volume(value)

    @Slot()
    def open_settings(self) -> None:
        """打开设置界面。"""
        self.settings_dialog.exec()

    @Slot(str)
    def trigger_hotkey(self, action: str) -> None:
        """热键触发:分发到对应动作。

        Args:
            action: 动作标识。
        """
        handler = self._hotkey_actions.get(action)
        if handler is not None:
            handler()

    @Slot()
    def switch_sound_up(self) -> None:
        """切换到上一个声音选项。"""
        self._switch_sound(-1)

    @Slot()
    def switch_sound_down(self) -> None:
        """切换到下一个声音选项。"""
        self._switch_sound(1)

    def _switch_sound(self, step: int) -> None:
        """按步数切换声音下拉选项,循环滚动并跳过分组标题。

        Args:
            step: 正数为下一个,负数为上一个。
        """
        combo = self.sound_combo
        if combo.count() == 0:
            return
        index = combo.currentIndex()
        for _ in range(combo.count()):
            index = (index + step) % combo.count()
            # 分组标题不携带数据,跳过
            if combo.itemData(index) is not None:
                break
        combo.setCurrentIndex(index)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """拦截输入控件上的上下方向键,方向键仅保留全局热键切换声音一条路径。

        类别、格式、声音下拉与音量框持有焦点时,Qt 默认会用上下方向键
        改变自身取值;此处将其屏蔽。下拉列表展开时的方向键导航不受影响。

        Args:
            obj: 安装了本过滤器的控件。
            event: 控件收到的事件。

        Returns:
            True 表示拦截该事件,False 交还默认处理。
        """
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)
        ):
            combo = obj if isinstance(obj, QComboBox) else None
            if combo is None or not combo.view().isVisible():
                return True
        return super().eventFilter(obj, event)
