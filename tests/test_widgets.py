"""控件测试:ButtonBar、ContentArea、FlowLayout。"""

from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox, QWidget

from app.config import AppConfig
from app.data_store import DataStore
from app.widgets.button_bar import ACTION_PLAY, ACTION_TOPMOST, ButtonBar
from app.widgets.content_area import ContentArea
from app.widgets.flow_layout import FlowLayout
from app.widgets.settings_dialog import AddItemDialog


def label_at(layout: FlowLayout, index: int) -> QLabel:
    """取布局中第 index 个子项的标签,断言存在且为 QLabel。"""
    item = layout.itemAt(index)
    assert item is not None
    widget = item.widget()
    assert isinstance(widget, QLabel)
    return widget


def press_key(state: dict[str, Any], name: str) -> None:
    """向替身 keyboard 的当前钩子模拟一次按键按下。"""
    for _, callback in state["hooks"]:
        callback(type("E", (), {"event_type": "down", "name": name})())


class TestButtonBar:
    def test_combo_contents(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        bar = ButtonBar(store)
        # 各下拉 = "全部"首项 + 数据选项
        assert bar.category_combo.count() == 4
        assert bar.category_combo.itemText(0) == "神秘货物"
        assert bar.format_combo.count() == 4
        # 声音下拉 = 全部 + 甲声 + 无红标题 + 乙拿放声 + 暂无声音标题 + 丙声
        assert bar.sound_combo.count() == 6
        assert bar.sound_combo.itemText(1) == "甲声"
        assert bar.sound_combo.itemText(2) == "── 无红 ──"
        assert bar.sound_combo.itemText(3) == "乙拿放声"
        assert bar.sound_combo.itemText(4) == "── 暂无声音 ──"
        assert bar.sound_combo.itemText(5) == "丙声"
        model = bar.sound_combo.model()
        assert isinstance(model, QStandardItemModel)
        for header_index in (2, 4):
            header = model.item(header_index)
            assert header is not None and not header.isEnabled()

    def test_initial_filter_is_all(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        bar = ButtonBar(store)
        assert bar.current_filter() == ("", "", "")

    def test_filter_changed_signal_carries_conditions(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        bar = ButtonBar(store)
        received: list[tuple[str, str, str]] = []
        bar.filter_changed.connect(lambda *args: received.append(args))
        bar.category_combo.setCurrentText("工具")
        assert received[-1] == ("工具", "", "")
        bar.sound_combo.setCurrentIndex(1)
        # 条件是累积的:类别仍为 "工具"
        assert received[-1] == ("工具", "", "甲声")

    def test_volume_spin_updates_effect(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """设置界面音量输入框实时调整播放音量并持久化。"""
        bar = ButtonBar(store)
        bar.settings_dialog.volume_spin.setValue(0.5)
        assert bar.sound_effect.volume() == 0.5
        assert AppConfig().volume == 0.5

    def test_play_without_sound_is_noop(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        bar = ButtonBar(store)
        bar.play_sound()  # 未选声音,不应抛异常
        assert bar.sound_effect.source().isEmpty()

    def test_reload_options_after_data_change(
        self,
        qapp: QApplication,
        store: DataStore,
        data_dir: Any,
        fake_keyboard: dict[str, Any],
    ) -> None:
        """热更新后重建下拉:新增音频文件使丙声离开暂无声音分组,且保留当前选择。"""
        from pathlib import Path

        audio_dir = Path(data_dir) / "original_ audio"
        bar = ButtonBar(store)
        bar.category_combo.setCurrentText("工具")
        # 为丙声补上音频文件(同名子目录 + _0 后缀)并热更新
        sound_dir = audio_dir / "丙声"
        sound_dir.mkdir()
        (sound_dir / "丙声_0.wav").write_bytes(b"RIFF")
        assert store.reload() is True
        bar.reload_options()
        texts = [bar.sound_combo.itemText(i) for i in range(bar.sound_combo.count())]
        assert "丙声" in texts
        assert "── 暂无声音 ──" not in texts  # 无素材声音已不存在,分组标题消失
        assert bar.category_combo.currentText() == "工具"  # 有效选择保留

    def test_sound_switch_wraps(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """切换方法循环滚动声音选项,跳过分组标题,并联动筛选条件。"""
        bar = ButtonBar(store)
        total = bar.sound_combo.count()
        assert total == 6  # 全部 + 甲声 + 无红标题 + 乙拿放声 + 暂无声音标题 + 丙声
        received: list[tuple[str, str, str]] = []
        bar.filter_changed.connect(lambda *args: received.append(args))
        bar.switch_sound_down()
        assert bar.sound_combo.currentIndex() == 1
        # 切换会带动筛选条件变化
        assert received[-1] == ("", "", "甲声")
        bar.switch_sound_up()
        assert bar.sound_combo.currentIndex() == 0
        assert received[-1] == ("", "", "")
        # 循环滚动:从第一项向上到最后一项(跳过分组标题)
        bar.switch_sound_up()
        assert bar.sound_combo.currentIndex() == total - 1
        assert received[-1] == ("", "", "丙声")
        # 再向下循环回"全部"
        bar.switch_sound_down()
        assert bar.sound_combo.currentIndex() == 0

    def test_sound_switch_hotkeys(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """固定方向键热键已注册并可切换声音。"""
        bar = ButtonBar(store)
        assert {"up", "down"} <= set(fake_keyboard["hotkeys"])
        fake_keyboard["hotkeys"]["down"]()
        assert bar.sound_combo.currentIndex() == 1
        fake_keyboard["hotkeys"]["up"]()
        assert bar.sound_combo.currentIndex() == 0

    def test_arrow_keys_blocked_on_input_widgets(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """焦点在输入控件上时,上下方向键不改变其取值,仅全局热键切换声音。"""
        bar = ButtonBar(store)
        QTest.keyClick(bar.category_combo, Qt.Key.Key_Down)
        assert bar.category_combo.currentIndex() == 0
        QTest.keyClick(bar.format_combo, Qt.Key.Key_Up)
        assert bar.format_combo.currentIndex() == 0
        QTest.keyClick(bar.sound_combo, Qt.Key.Key_Down)
        assert bar.sound_combo.currentIndex() == 0
        QTest.keyClick(bar.settings_dialog.volume_spin, Qt.Key.Key_Up)
        assert bar.settings_dialog.volume_spin.value() == 0.25
        # 全局热键路径仍切换声音
        fake_keyboard["hotkeys"]["down"]()
        assert bar.sound_combo.currentIndex() == 1

    def test_hotkey_flow(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """设置界面快捷键按钮的初始文本与捕获流程。"""
        bar = ButtonBar(store)
        dialog = bar.settings_dialog
        topmost_button = dialog.hotkey_buttons[ACTION_TOPMOST]
        assert topmost_button.text() == "left"
        assert dialog.hotkey_buttons[ACTION_PLAY].text() == "right"
        # 默认热键 "-" 触发置顶切换
        toggled: list[bool] = []
        bar.toggle_topmost.connect(lambda: toggled.append(True))
        fake_keyboard["hotkeys"]["left"]()
        assert toggled == [True]
        # 捕获 f5 后按钮文本更新,两个热键均恢复注册,并持久化到配置
        topmost_button.click()
        assert topmost_button.text() == "请按键..."
        press_key(fake_keyboard, "f5")
        assert topmost_button.text() == "f5"
        assert AppConfig().hotkey("topmost") == "f5"
        assert set(fake_keyboard["hotkeys"]) == {"f5", "right", "up", "down"}
        # 再次捕获时按 Esc 取消,保持原热键
        topmost_button.click()
        press_key(fake_keyboard, "esc")
        assert topmost_button.text() == "f5"
        assert set(fake_keyboard["hotkeys"]) == {"f5", "right", "up", "down"}

    def test_play_hotkey_triggers_play(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        bar = ButtonBar(store)
        bar.sound_combo.setCurrentIndex(1)  # 甲声
        assert bar.sound_effect.source().isEmpty()
        fake_keyboard["hotkeys"]["right"]()
        assert not bar.sound_effect.source().isEmpty()

    def test_play_hotkey_skips_when_sound_is_all(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """声音下拉为"全部"时按播放热键不播放。"""
        bar = ButtonBar(store)
        fake_keyboard["hotkeys"]["right"]()
        assert bar.sound_effect.source().isEmpty()

    def test_play_hotkey_recording(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        bar = ButtonBar(store)
        play_button = bar.settings_dialog.hotkey_buttons[ACTION_PLAY]
        play_button.click()
        assert play_button.text() == "请按键..."
        press_key(fake_keyboard, "f6")
        assert play_button.text() == "f6"
        assert set(fake_keyboard["hotkeys"]) == {"left", "f6", "up", "down"}


class TestSettingsDialog:
    def test_dialog_fixed_to_minimal_size(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """设置界面尺寸固定为内容所需的最小值,不可拉伸。"""
        dialog = ButtonBar(store).settings_dialog
        layout = dialog.layout()
        assert layout is not None
        layout.activate()
        assert dialog.minimumSize() == dialog.maximumSize()

    def test_volume_spin_uses_fusion_style(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """音量输入框使用 Fusion 样式,增减按钮上下堆叠。"""
        dialog = ButtonBar(store).settings_dialog
        assert dialog.volume_spin.style().objectName() == "fusion"

    def test_keys_blocked_during_capture(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """捕获期间物理按键不会落入音量输入框;完成后焦点离开音量框。"""
        bar = ButtonBar(store)
        dialog = bar.settings_dialog
        dialog.show()
        qapp.processEvents()
        dialog.volume_spin.setFocus()
        assert dialog.volume_spin.hasFocus()
        dialog.hotkey_buttons[ACTION_PLAY].click()
        QTest.keyClicks(dialog.volume_spin, "9")
        assert dialog.volume_spin.value() == 0.25
        QTest.keyClick(dialog.volume_spin, Qt.Key.Key_Right)
        assert dialog.volume_spin.value() == 0.25
        press_key(fake_keyboard, "f7")
        assert dialog.hotkey_buttons[ACTION_PLAY].text() == "f7"
        assert not dialog.volume_spin.hasFocus()
        assert not dialog.hotkey_buttons[ACTION_PLAY].hasFocus()
        dialog.close()

    def test_hotkey_buttons_not_default(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """快捷键按钮不是对话框默认按钮,无常亮边框。"""
        dialog = ButtonBar(store).settings_dialog
        assert all(not button.autoDefault() for button in dialog.hotkey_buttons.values())

    def test_item_list_newest_first(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """物品列表最新添加的在最前(json 越靠下越新)。"""
        dialog = ButtonBar(store).settings_dialog
        texts = [dialog.item_combo.itemText(i) for i in range(dialog.item_combo.count())]
        assert texts == ["绿物", "蓝物", "金物", "紫物", "红金物品"]

    def test_add_item_dialog_validation(
        self,
        qapp: QApplication,
        store: DataStore,
        fake_keyboard: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """新增弹窗:空名/重名/空声音被拦下,合法填写才接受。"""
        warned: list[str] = []
        monkeypatch.setattr(
            QMessageBox, "warning", staticmethod(lambda *_args, **_kwargs: warned.append("warn"))
        )
        dialog = AddItemDialog(store)
        dialog.name_edit.setText("")
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted

        dialog.name_edit.setText("红金物品")  # 重名
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert warned  # 弹过提示

        dialog.name_edit.setText("崭新物品")
        dialog.sound_combo.setCurrentText("全新声")
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert dialog.item_values() == ("崭新物品", "竖2格", "工具", "红", "全新声")

    def test_delete_item_flow(
        self,
        qapp: QApplication,
        store: DataStore,
        data_dir: Any,
        fake_keyboard: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """确认删除后物品从内存与 json 中移除,列表同步刷新。"""
        monkeypatch.setattr(
            QMessageBox,
            "question",
            staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
        )
        dialog = ButtonBar(store).settings_dialog
        dialog.item_combo.setCurrentText("蓝物")
        dialog.remove_selected_item()
        assert {n for n, _ in store.filter_items()} == {"红金物品", "紫物", "金物", "绿物"}
        fresh = DataStore(data_dir)
        assert {n for n, _ in fresh.filter_items()} == {"红金物品", "紫物", "金物", "绿物"}
        assert dialog.item_combo.count() == 4

    def test_volume_not_focused_on_open(
        self, qapp: QApplication, store: DataStore, fake_keyboard: dict[str, Any]
    ) -> None:
        """打开设置界面时焦点不默认落在音量输入框。"""
        dialog = ButtonBar(store).settings_dialog
        dialog.show()
        qapp.processEvents()
        assert not dialog.volume_spin.hasFocus()
        dialog.close()


class TestContentArea:
    @staticmethod
    def labels(area: ContentArea) -> list[str]:
        return [label_at(area.flow_layout, i).text() for i in range(area.flow_layout.count())]

    def test_initial_shows_all_sorted_by_quality(
        self, qapp: QApplication, store: DataStore
    ) -> None:
        area = ContentArea(store)
        assert area.count_label.text() == "共 5 件"
        # 红 -> 金 -> 紫 -> 未知品质按主表顺序
        assert self.labels(area) == ["红金物品", "金物", "紫物", "蓝物", "绿物"]

    def test_refresh_with_filter(self, qapp: QApplication, store: DataStore) -> None:
        area = ContentArea(store)
        area.refresh(category="工具")
        assert area.count_label.text() == "共 2 件"
        assert self.labels(area) == ["红金物品", "紫物"]

    def test_topmost_status_display(self, qapp: QApplication, store: DataStore) -> None:
        """置顶状态默认为否,随主窗口切换更新。"""
        area = ContentArea(store)
        assert area.topmost_label.text() == "置顶:否"
        area.set_topmost(True)
        assert area.topmost_label.text() == "置顶:是"
        area.set_topmost(False)
        assert area.topmost_label.text() == "置顶:否"

    def test_quality_color_applied(self, qapp: QApplication, store: DataStore) -> None:
        area = ContentArea(store)
        assert "color" in label_at(area.flow_layout, 0).styleSheet()

    def test_no_match_clears_grid(self, qapp: QApplication, store: DataStore) -> None:
        area = ContentArea(store)
        area.refresh(category="工具", sound="乙拿放声")
        assert area.count_label.text() == "共 0 件"
        assert self.labels(area) == []


class TestFlowLayout:
    def test_add_take_count(self, qapp: QApplication) -> None:
        container = QWidget()
        layout = FlowLayout(container, spacing=8)
        for text in ("甲", "乙", "丙"):
            layout.addWidget(QLabel(text))
        assert layout.count() == 3
        removed = layout.takeAt(1)
        assert removed is not None
        widget = removed.widget()
        assert isinstance(widget, QLabel)
        assert widget.text() == "乙"
        assert layout.count() == 2
        assert layout.takeAt(9) is None

    def test_height_depends_on_width(self, qapp: QApplication) -> None:
        container = QWidget()
        layout = FlowLayout(container, spacing=8)
        for text in ("甲", "乙", "丙"):
            layout.addWidget(QLabel(text))
        assert layout.hasHeightForWidth()
        narrow = layout.heightForWidth(30)
        wide = layout.heightForWidth(3000)
        assert narrow > wide > 0
