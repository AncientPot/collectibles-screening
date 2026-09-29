from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
)

from src.core.audio_matcher import DEFAULT_SAVE_CAP
from src.widgets.settings.help_dialog import HelpDialog
from src.widgets.settings.hotkey_selector import HotkeySelector
from src.widgets.settings.save_viewer import SaveViewerDialog
from src.widgets.top_aligned_dialog import TopAlignedDialog
from src.widgets.topbar.listen_button import ACTIVE_COLOR, NORMAL_COLOR


class SettingsDialog(TopAlignedDialog):
    """设置对话框：网格布局，参数两列排布并利用横向空间"""

    def __init__(self, parent=None, max_seconds: int = 5,
                 hotkey: str = "num +", visibility_hotkey: str = "-", play_volume: float = 5.0,
                 save_weight: float = 0.5, categories: list[str] | None = None,
                 save_caps: dict[str, int] | None = None, on_save_files_changed=None,
                 suspend_hotkeys=None, resume_hotkeys=None, templates_ready: bool = True):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self._on_save_files_changed = on_save_files_changed
        self._setup_ui(max_seconds, hotkey, visibility_hotkey, play_volume,
                       save_weight, categories or [], save_caps or {},
                       suspend_hotkeys, resume_hotkeys, templates_ready)
        self._setup_geometry()

    def _setup_ui(self, max_seconds: int, hotkey: str, visibility_hotkey: str, play_volume: float,
                  save_weight: float, categories: list[str], save_caps: dict[str, int],
                  suspend_hotkeys, resume_hotkeys, templates_ready: bool):
        """组装ui"""
        self.max_seconds_spin_box = QSpinBox()
        self.max_seconds_spin_box.setRange(1, 3600)
        self.max_seconds_spin_box.setValue(max_seconds)
        self.play_volume_spin_box = QDoubleSpinBox()
        self.play_volume_spin_box.setRange(0.1, 100.0)
        self.play_volume_spin_box.setDecimals(1)
        self.play_volume_spin_box.setSingleStep(0.5)
        self.play_volume_spin_box.setValue(play_volume)
        self.save_weight_spin_box = QDoubleSpinBox()
        self.save_weight_spin_box.setRange(0.0, 1.0)
        self.save_weight_spin_box.setDecimals(1)
        self.save_weight_spin_box.setSingleStep(0.1)
        self.save_weight_spin_box.setValue(save_weight)
        self.hotkey_selector = HotkeySelector(hotkey,
                                              on_capture_start=suspend_hotkeys,
                                              on_capture_end=resume_hotkeys)
        self.visibility_hotkey_selector = HotkeySelector(visibility_hotkey,
                                                         on_capture_start=suspend_hotkeys,
                                                         on_capture_end=resume_hotkeys)
        # 同一时间只允许一个录制框工作，避免并发捕获把两个热键录成同一个键
        for a, b in ((self.hotkey_selector, self.visibility_hotkey_selector),
                     (self.visibility_hotkey_selector, self.hotkey_selector)):
            a.capture_started.connect(lambda other=b: other.record_button.setEnabled(False))
            a.capture_ended.connect(lambda other=b: other.record_button.setEnabled(True))
        # 学习音频上限：下拉选类别，输入框改该类上限，菜单实时显示各类当前值
        self._caps: dict[str, int] = {}
        self.category_combo_box = QComboBox()
        for category in categories:
            value = int(save_caps.get(category, DEFAULT_SAVE_CAP))
            self._caps[category] = value
            self.category_combo_box.addItem("%s（%d）" % (category, value), category)
        self.cap_spin_box = QSpinBox()
        self.cap_spin_box.setRange(1, 99)
        self.category_combo_box.currentIndexChanged.connect(self._on_category_selected)
        self.cap_spin_box.valueChanged.connect(self._on_cap_changed)
        if categories:
            self.cap_spin_box.setValue(self._caps[categories[0]])
        caps_row = QHBoxLayout()
        caps_row.addWidget(self.category_combo_box)
        caps_row.addWidget(self.cap_spin_box)
        # 未构建过模板时引导构建，构建完成后变为重构
        self.rebuild_button = QPushButton("构建输出模板" if not templates_ready else "重构输出模板")
        self.rebuild_button.setStyleSheet("color: %s;" % NORMAL_COLOR)
        self.rebuild_status_label = QLabel()
        self.help_button = QPushButton("说明")
        self.help_button.clicked.connect(self._show_help)
        self.view_save_button = QPushButton("查看音频")
        self.view_save_button.clicked.connect(self._show_save_viewer)
        buttons = QDialogButtonBox()
        buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        grid = QGridLayout(self)
        grid.setHorizontalSpacing(12)
        grid.addWidget(QLabel("最长监听时长(秒):"), 0, 0)
        grid.addWidget(self.max_seconds_spin_box, 0, 1)
        grid.addWidget(QLabel("播放音量(倍):"), 0, 2)
        grid.addWidget(self.play_volume_spin_box, 0, 3)
        grid.addWidget(QLabel("置顶快捷键:"), 1, 0)
        grid.addWidget(self.visibility_hotkey_selector, 1, 1)
        grid.addWidget(QLabel("监听快捷键:"), 1, 2)
        grid.addWidget(self.hotkey_selector, 1, 3)
        grid.addWidget(QLabel("学习数据权重(0-1):"), 2, 0)
        grid.addWidget(self.save_weight_spin_box, 2, 1)
        grid.addWidget(QLabel("学习音频上限:"), 2, 2)
        grid.addLayout(caps_row, 2, 3)

        action_layout = QHBoxLayout()
        action_layout.addWidget(self.rebuild_button)
        action_layout.addWidget(self.view_save_button)
        action_layout.addWidget(self.help_button)
        action_layout.addWidget(self.rebuild_status_label, 1)
        action_layout.addWidget(buttons)
        grid.addLayout(action_layout, 3, 0, 1, 4)

    def accept(self):
        """确认前结束未完成的录制，并校验两个热键不重复"""
        for selector in (self.hotkey_selector, self.visibility_hotkey_selector):
            selector.cancel()
        if self.hotkey_selector.hotkey == self.visibility_hotkey_selector.hotkey:
            QMessageBox.warning(self, "设置", "监听快捷键与置顶快捷键不能相同。")
            return
        super().accept()

    def done(self, result):
        """任何关闭路径都结束未完成的录制，避免热键停留在挂起态"""
        for selector in (self.hotkey_selector, self.visibility_hotkey_selector):
            selector.cancel()
        super().done(result)

    def _on_category_selected(self, index: int):
        """下拉切换类别：输入框显示该类当前上限"""
        category = self.category_combo_box.itemData(index)
        if category is not None:
            self.cap_spin_box.setValue(self._caps[category])

    def _on_cap_changed(self, value: int):
        """输入框修改：更新该类上限并刷新菜单项显示"""
        index = self.category_combo_box.currentIndex()
        category = self.category_combo_box.itemData(index)
        if category is None:
            return
        self._caps[category] = value
        self.category_combo_box.setItemText(index, "%s（%d）" % (category, value))

    def set_building(self, busy: bool):
        """构建输出模板按钮的构建态/常态切换（绿->红构建中->绿重构）"""
        self.rebuild_button.setEnabled(not busy)
        self.rebuild_button.setText("构建中" if busy else "重构输出模板")
        self.rebuild_button.setStyleSheet("color: %s;" % (ACTIVE_COLOR if busy else NORMAL_COLOR))

    def _show_help(self):
        """打开参数说明"""
        HelpDialog(self).exec()

    def _show_save_viewer(self):
        """打开学习音频查看界面"""
        SaveViewerDialog(self, on_files_changed=self._on_save_files_changed).exec()

    def on_rebuild_progress(self, done: int, total: int, category: str):
        """保底模板采集进度更新"""
        self.rebuild_status_label.setText("采集 %s (%d/%d)..." % (category, done, total))

    def on_rebuild_finished(self, ok: bool):
        """输出模板构建结束：恢复按钮绿色与可用状态，此后为重构态"""
        self.set_building(False)
        self.rebuild_status_label.setText("已完成" if ok else "失败，详见控制台输出")

    @property
    def hotkey(self) -> str:
        return self.hotkey_selector.hotkey

    @property
    def visibility_hotkey(self) -> str:
        return self.visibility_hotkey_selector.hotkey

    @property
    def max_seconds(self) -> int:
        return self.max_seconds_spin_box.value()

    @property
    def play_volume(self) -> float:
        return self.play_volume_spin_box.value()

    @property
    def save_weight(self) -> float:
        return self.save_weight_spin_box.value()

    @property
    def save_caps(self) -> dict[str, int]:
        return dict(self._caps)
