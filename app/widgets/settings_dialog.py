"""设置界面:音量、全局快捷键与物品的增删管理。"""

from PySide6.QtCore import QEvent, QObject, Slot
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.data_store import DataStore
from app.utils.hotkey import HotkeyManager


class AddItemDialog(QDialog):
    """新增物品弹窗:填写名称并从已有选项中选择格式、类别、品质与声音。

    声音名允许自行输入新名称(可无音频文件,自动归入"暂无声音"分组)。
    """

    def __init__(self, store: DataStore, parent: QWidget | None = None) -> None:
        """初始化弹窗控件。

        Args:
            store: 数据层,提供格式/类别/品质/声音选项。
            parent: 父控件。
        """
        super().__init__(parent)
        self.setWindowTitle("添加物品")
        self._store = store
        self.name_edit = QLineEdit()
        self.format_combo = QComboBox()
        self.format_combo.addItems(store.formats())
        self.category_combo = QComboBox()
        self.category_combo.addItems(store.categories())
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(store.qualities())
        self.sound_combo = QComboBox()
        self.sound_combo.setEditable(True)
        self.sound_combo.addItems([name for name, _label, _group in store.sounds()])
        self._setup_layout()

    def _setup_layout(self) -> None:
        """表单布局:名称与四项属性,底部确定/取消。"""
        form = QFormLayout()
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(8)
        form.addRow(QLabel("名称"), self.name_edit)
        form.addRow(QLabel("格式"), self.format_combo)
        form.addRow(QLabel("类别"), self.category_combo)
        form.addRow(QLabel("品质"), self.quality_combo)
        form.addRow(QLabel("声音"), self.sound_combo)
        buttons = QDialogButtonBox()
        buttons.addButton("确定", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton("取消", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def item_values(self) -> tuple[str, str, str, str, str]:
        """读取表单填写值。

        Returns:
            (名称, 格式, 类别, 品质, 声音),首尾空白已去除。
        """
        return (
            self.name_edit.text().strip(),
            self.format_combo.currentText().strip(),
            self.category_combo.currentText().strip(),
            self.quality_combo.currentText().strip(),
            self.sound_combo.currentText().strip(),
        )

    def accept(self) -> None:
        """校验名称与声音非空且名称不重复后接受,否则提示并留在弹窗。"""
        name, _fmt, _cat, _qly, sound = self.item_values()
        if not name:
            QMessageBox.warning(self, "添加物品", "物品名称不能为空")
            return
        if name in self._store.items_newest_first():
            QMessageBox.warning(self, "添加物品", f"物品「{name}」已存在")
            return
        if not sound:
            QMessageBox.warning(self, "添加物品", "声音名称不能为空")
            return
        super().accept()


class SettingsDialog(QDialog):
    """设置界面:音量输入框、全局快捷键设置按钮与物品增删行。"""

    def __init__(
        self,
        manager: HotkeyManager,
        store: DataStore,
        config: AppConfig,
        hotkey_labels: dict[str, str],
        parent: QWidget | None = None,
    ) -> None:
        """初始化设置界面。

        Args:
            manager: 全局热键管理器,读取当前热键名并接收捕获结果。
            store: 数据层,提供物品增删与选项。
            config: 运行配置,音量与热键改动即时持久化。
            hotkey_labels: 动作标识 -> 界面描述文字,按传入顺序排列。
            parent: 父控件。
        """
        super().__init__(parent)
        self.setWindowTitle("设置")
        self._manager = manager
        self._store = store
        self._config = config
        self._labels = list(hotkey_labels.items())
        self.volume_spin = QDoubleSpinBox()
        self.hotkey_buttons: dict[str, QPushButton] = {}
        for action, _text in self._labels:
            button = QPushButton(manager.name(action))
            # 对话框会把首个按钮自动当作默认按钮而常亮边框,关闭该行为
            button.setAutoDefault(False)
            button.setMinimumWidth(40)
            button.setToolTip("点击后按下新按键,用于设置该快捷键;按 Esc 取消")
            button.clicked.connect(lambda _checked=False, bound=action: self.start_capture(bound))
            self.hotkey_buttons[action] = button
        self.add_button = QPushButton("添加")
        self.add_button.setAutoDefault(False)
        self.item_combo = QComboBox()
        self.remove_button = QPushButton("删除")
        self.remove_button.setAutoDefault(False)
        self._manager.key_captured.connect(self.apply_hotkey)
        # 捕获期间吞掉本对话框的按键事件,避免物理按键落入音量框等输入控件
        for widget in (self, self.volume_spin, *self.hotkey_buttons.values()):
            widget.installEventFilter(self)
        # 设置控件
        self._setup_widgets()
        # 设置布局
        self._setup_layout()

    def _setup_widgets(self) -> None:
        """设置音量输入框与物品增删控件初始状态,音量取持久化配置。"""
        self.volume_spin.setStyle(QStyleFactory.create("Fusion"))
        self.volume_spin.setRange(0, 1)
        self.volume_spin.setDecimals(2)
        self.volume_spin.setSingleStep(0.1)
        self.volume_spin.setValue(self._config.volume)
        self.add_button.setToolTip("打开新增物品弹窗,保存后自动写入 data 的 json")
        self.remove_button.setToolTip("删除列表中选中的物品,删除前需确认")
        self.reload_items()

    def _setup_layout(self) -> None:
        """三行布局:音量与添加按钮;物品列表与删除按钮;快捷键。"""
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        volume_row = QHBoxLayout()
        volume_row.setSpacing(8)
        volume_row.addWidget(QLabel("音量"))
        volume_row.addWidget(self.volume_spin)
        volume_row.addStretch()
        volume_row.addWidget(self.add_button)  # 与下行的删除按钮右对齐

        items_row = QHBoxLayout()
        items_row.setSpacing(8)
        items_row.addWidget(self.item_combo, 1)
        items_row.addWidget(self.remove_button)

        hotkeys_row = QHBoxLayout()
        hotkeys_row.setSpacing(8)
        for action, text in self._labels:
            hotkeys_row.addWidget(QLabel(text))
            hotkeys_row.addWidget(self.hotkey_buttons[action])
        hotkeys_row.addStretch()

        layout.addLayout(volume_row)
        layout.addLayout(items_row)
        layout.addLayout(hotkeys_row)

        self.add_button.clicked.connect(self.open_add_item)
        self.remove_button.clicked.connect(self.remove_selected_item)

    def reload_items(self) -> None:
        """数据变化后重建物品列表,最新添加的在最前,保留仍然存在的选择。"""
        current = self.item_combo.currentText()
        self.item_combo.blockSignals(True)
        self.item_combo.clear()
        self.item_combo.addItems(self._store.items_newest_first())
        index = self.item_combo.findText(current) if current else -1
        self.item_combo.setCurrentIndex(max(index, 0))
        self.item_combo.blockSignals(False)

    def showEvent(self, event: QShowEvent) -> None:
        """打开时把焦点留在对话框自身,不落到音量输入框或按钮。

        先清除子控件残留焦点,再由对话框认领焦点,
        阻止窗口激活时 Qt 把焦点派给第一个可聚焦子控件(音量输入框)。

        Args:
            event: 显示事件。
        """
        super().showEvent(event)
        self._clear_child_focus()
        self.setFocus()

    def _clear_child_focus(self) -> None:
        """把子控件的焦点移回对话框,避免按钮保持焦点高亮边框。"""
        widget = self.focusWidget()
        if widget is not None and widget is not self:
            widget.clearFocus()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """捕获按键期间吞掉对话框内所有按键事件。

        用于设置快捷键的物理按键在系统层同时会送达本对话框,若不拦截,
        方向键、数字、Tab 等会落入音量输入框(出现光标、改动数值)或移动焦点。

        Args:
            obj: 安装了本过滤器的控件。
            event: 控件收到的事件。

        Returns:
            True 表示拦截该事件,False 交还默认处理。
        """
        if self._manager.is_capturing and event.type() in (
            QEvent.Type.KeyPress,
            QEvent.Type.KeyRelease,
        ):
            return True
        return super().eventFilter(obj, event)

    @Slot(str)
    def start_capture(self, action: str) -> None:
        """点击按钮后进入按键捕获,期间暂停全部热键。

        Args:
            action: 动作标识。
        """
        self.hotkey_buttons[action].setText("请按键...")
        self._manager.start_capture(action)

    @Slot(str, str)
    def apply_hotkey(self, action: str, key: str) -> None:
        """应用新热键并持久化;空名称表示取消设置,恢复原热键。

        Args:
            action: 动作标识。
            key: 新热键名称;空字符串表示取消。
        """
        self._manager.register(action, key or self._manager.name(action))
        text = self._manager.name(action)
        self.hotkey_buttons[action].setText(text)
        self._config.set_hotkey(action, text)
        # 焦点移回对话框,避免设置按钮保持高亮
        self._clear_child_focus()

    @Slot()
    def open_add_item(self) -> None:
        """打开新增物品弹窗,确认后写入数据文件。"""
        dialog = AddItemDialog(self._store, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, format_, category, quality, sound = dialog.item_values()
        try:
            self._store.add_item(name, format_, category, quality, sound)
        except ValueError as error:
            QMessageBox.warning(self, "添加物品", str(error))
        self.reload_items()

    @Slot()
    def remove_selected_item(self) -> None:
        """删除列表中选中的物品,删除前弹窗确认。"""
        name = self.item_combo.currentText()
        if not name:
            QMessageBox.information(self, "删除物品", "没有可删除的物品")
            return
        answer = QMessageBox.question(
            self,
            "删除物品",
            f"确定删除「{name}」?将同时从 data 的 json 中移除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._store.remove_item(name)
        except ValueError as error:
            QMessageBox.warning(self, "删除物品", str(error))
        self.reload_items()
