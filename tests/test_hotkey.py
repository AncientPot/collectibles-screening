"""HotkeyManager 测试:以替身 keyboard 库模拟注册与按键捕获。"""

from typing import Any

import keyboard
import pytest
from PySide6.QtWidgets import QApplication

from app.utils.hotkey import HotkeyManager


class FakeEvent:
    """keyboard 按键事件的替身。"""

    def __init__(self, name: str, event_type: str = "down", is_keypad: bool = False) -> None:
        self.name = name
        self.event_type = event_type
        self.is_keypad = is_keypad


def press(state: dict[str, Any], name: str) -> None:
    """向当前钩子模拟一次按键按下。"""
    for _, callback in state["hooks"]:
        callback(FakeEvent(name))


class TestRegister:
    def test_register_records_name(self, qapp: QApplication, fake_keyboard: dict[str, Any]) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "-")
        assert manager.name("topmost") == "-"
        assert "-" in fake_keyboard["hotkeys"]

    def test_empty_name_registers_nothing(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "")
        assert manager.name("topmost") == ""
        assert fake_keyboard["hotkeys"] == {}

    def test_reregister_replaces_old(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "-")
        manager.register("topmost", "f5")
        assert list(fake_keyboard["hotkeys"]) == ["f5"]
        assert manager.name("topmost") == "f5"
        assert ("hotkey", "-") in fake_keyboard["removed"]

    def test_unknown_action_name_is_empty(self, qapp: QApplication) -> None:
        manager = HotkeyManager()
        assert manager.name("topmost") == ""

    def test_actions_are_independent(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "-")
        manager.register("play", "num +")
        assert set(fake_keyboard["hotkeys"]) == {"-", "codes:78"}
        manager.release("topmost")
        assert set(fake_keyboard["hotkeys"]) == {"codes:78"}

    def test_scan_code_fallback_for_numpad_keys(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        """含 + 的键名解析失败时按扫描码注册,名称保留,热键可触发。"""
        manager = HotkeyManager()
        manager.register("play", "num +")
        assert manager.name("play") == "num +"
        assert "codes:78" in fake_keyboard["hotkeys"]
        received: list[str] = []
        manager.hotkey_pressed.connect(received.append)
        fake_keyboard["hotkeys"]["codes:78"]()
        assert received == ["play"]

    def test_duplicate_name_rejected(
        self,
        qapp: QApplication,
        fake_keyboard: dict[str, Any],
    ) -> None:
        """同一热键名不能注册给两个动作,后注册的被拒绝并保持原热键。"""
        manager = HotkeyManager()
        manager.register("topmost", "-")
        manager.register("play", "f5")
        manager.register("play", "-")
        assert manager.name("play") == "f5"
        assert set(fake_keyboard["hotkeys"]) == {"-", "f5"}

    def test_release_tolerates_missing_entry(
        self,
        qapp: QApplication,
        fake_keyboard: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """注销时 keyboard 抛 KeyError 不向外传播,不中断捕获流程。"""

        def broken_remove(handler: Any) -> None:
            raise KeyError(handler)

        monkeypatch.setattr(keyboard, "remove_hotkey", broken_remove)
        manager = HotkeyManager()
        manager.register("topmost", "-")
        manager.release("topmost")
        assert manager.name("topmost") == "-"

    def test_register_failure_reverts_and_warns(
        self,
        qapp: QApplication,
        fake_keyboard: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """注册抛异常时回退为未注册并记录警告。"""

        def failing_add(_name: str, _callback: Any) -> None:
            raise ValueError("invalid hotkey")

        monkeypatch.setattr(keyboard, "add_hotkey", failing_add)
        manager = HotkeyManager()
        manager.register("topmost", "-")
        assert manager.name("topmost") == ""


class TestHotkeyPressed:
    def test_callback_carries_action(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "-")
        manager.register("play", "num +")
        received: list[str] = []
        manager.hotkey_pressed.connect(received.append)
        fake_keyboard["hotkeys"]["codes:78"]()
        assert received == ["play"]


class TestCapture:
    def test_capture_suspends_and_restores_all(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "-")
        manager.register("play", "num +")
        manager.start_capture("play")
        # 捕获期间全部热键暂停,钩子就位
        assert fake_keyboard["hotkeys"] == {}
        assert len(fake_keyboard["hooks"]) == 1
        press(fake_keyboard, "f5")
        # 捕获结束后自动恢复全部热键
        assert set(fake_keyboard["hotkeys"]) == {"-", "codes:78"}
        assert fake_keyboard["hooks"] == []

    def test_capture_emits_action_and_key(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "-")
        captured: list[tuple[str, str]] = []
        manager.key_captured.connect(lambda *args: captured.append(args))
        manager.start_capture("topmost")
        press(fake_keyboard, "f5")
        assert captured == [("topmost", "f5")]

    def test_esc_captures_empty_key(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "-")
        captured: list[tuple[str, str]] = []
        manager.key_captured.connect(lambda *args: captured.append(args))
        manager.start_capture("topmost")
        press(fake_keyboard, "esc")
        assert captured == [("topmost", "")]

    def test_second_capture_cancels_first(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "-")
        manager.register("play", "num +")
        captured: list[tuple[str, str]] = []
        manager.key_captured.connect(lambda *args: captured.append(args))
        manager.start_capture("topmost")
        manager.start_capture("play")
        # 第一次捕获被取消,只剩一个钩子;第二次捕获期间热键仍全部暂停
        assert len(fake_keyboard["hooks"]) == 1
        assert fake_keyboard["hotkeys"] == {}
        press(fake_keyboard, "f5")
        assert captured == [("play", "f5")]
        assert set(fake_keyboard["hotkeys"]) == {"-", "codes:78"}

    def test_key_up_ignored(self, qapp: QApplication, fake_keyboard: dict[str, Any]) -> None:
        manager = HotkeyManager()
        manager.register("topmost", "-")
        captured: list[tuple[str, str]] = []
        manager.key_captured.connect(lambda *args: captured.append(args))
        manager.start_capture("topmost")
        for _, callback in fake_keyboard["hooks"]:
            callback(FakeEvent("f5", event_type="up"))
        assert captured == []
        assert len(fake_keyboard["hooks"]) == 1

    def test_numpad_key_capture_normalizes_name(
        self, qapp: QApplication, fake_keyboard: dict[str, Any]
    ) -> None:
        """捕获小键盘按键时归一化为 num 前缀名称,可经扫描码回环注册。"""
        manager = HotkeyManager()
        manager.register("topmost", "-")
        captured: list[tuple[str, str]] = []
        manager.key_captured.connect(lambda *args: captured.append(args))
        manager.start_capture("play")
        for _, callback in fake_keyboard["hooks"]:
            callback(FakeEvent("+", is_keypad=True))
        assert captured == [("play", "num +")]
        manager.register("play", captured[0][1])
        assert manager.name("play") == "num +"
        assert "codes:78" in fake_keyboard["hotkeys"]
