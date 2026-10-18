"""全局热键管理:封装 keyboard 库,支持多个动作,回调经 Qt 信号转回主线程。"""

from typing import Any

import keyboard
from PySide6.QtCore import QObject, Signal


class HotkeyManager(QObject):
    """管理多个动作的全局热键,并支持按键捕获。

    keyboard 库的回调运行在独立线程,按键事件通过信号发出,
    由 Qt 以队列连接方式自动转回主线程。
    """

    # 热键触发,参数为动作标识
    hotkey_pressed = Signal(str)
    # 捕获到新按键,参数为(动作标识, 按键名);按键名为空串表示按了 Esc 取消
    key_captured = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        """初始化,不注册任何热键。

        Args:
            parent: 父 QObject。
        """
        super().__init__(parent)
        self._names: dict[str, str] = {}
        self._handlers: dict[str, Any] = {}
        self._capture_action: str | None = None
        self._hook: Any = None

    def name(self, action: str) -> str:
        """读取动作当前的热键名。

        Args:
            action: 动作标识。

        Returns:
            热键名;未设置或注册失败时返回空字符串。
        """
        return self._names.get(action, "")

    @property
    def is_capturing(self) -> bool:
        """是否正在进行按键捕获。"""
        return self._capture_action is not None or self._hook is not None

    def register(self, action: str, name: str) -> None:
        """为动作注册全局热键;空名称表示仅注销;名称被其他动作占用时拒绝;
        注册失败回退为未注册并记录警告。

        Args:
            action: 动作标识。
            name: 新热键名称。
        """
        owner = next(
            (
                other
                for other, used in self._names.items()
                if name and used == name and other != action
            ),
            None,
        )
        if owner is not None:
            # 同名热键会让 keyboard 库内部互相覆盖并在注销时抛 KeyError,直接拒绝
            return
        self.release(action)
        self._names[action] = name
        if not name:
            return

        def emit(bound: str = action) -> None:
            self.hotkey_pressed.emit(bound)

        try:
            self._handlers[action] = keyboard.add_hotkey(name, emit)
        except ValueError:
            # 热键串解析失败(如 "num +" 的 + 被当作组合分隔符),改用扫描码注册;
            # 键名仍无法映射则回退为未注册,不中断应用
            try:
                codes = keyboard.key_to_scan_codes(name, error_if_missing=True)
            except ValueError:
                self._names.pop(action, None)
            else:
                self._handlers[action] = keyboard.add_hotkey(codes, emit)

    def release(self, action: str) -> None:
        """注销动作的热键,保留其名称以便重新注册。

        Args:
            action: 动作标识。
        """
        handler = self._handlers.pop(action, None)
        if handler is not None:
            try:
                keyboard.remove_hotkey(handler)
            except KeyError, ValueError:
                # keyboard 以热键名等作内部索引,冲突场景下记录可能已被清理,忽略
                pass

    def start_capture(self, action: str) -> None:
        """进入按键捕获:暂停全部热键,捕获第一个按键后发出 key_captured。

        Args:
            action: 捕获结果归属的动作标识。
        """
        self._cancel_capture()
        self._capture_action = action
        for registered in list(self._handlers):
            self.release(registered)
        self._hook = keyboard.hook(self._on_key)

    def _cancel_capture(self) -> None:
        """取消进行中的捕获并恢复全部热键。"""
        if self._hook is not None:
            keyboard.unhook(self._hook)
            self._hook = None
        if self._capture_action is not None:
            self._capture_action = None
            self._restore()

    def _restore(self) -> None:
        """按已记录的名称重新注册尚未注册的热键。"""
        for action, name in list(self._names.items()):
            if name and action not in self._handlers:
                self.register(action, name)

    def _on_key(self, event: Any) -> None:
        """keyboard 回调线程:捕获第一个按下的键,Esc 视为取消。

        小键盘按键的规范名不带 "num " 前缀(如小键盘加号为 "+"),
        补上前缀以保持与 "num +" 这类名称的注册与显示一致。

        Args:
            event: keyboard 库的按键事件。
        """
        if event.event_type != "down" or self._capture_action is None:
            return
        key = event.name or ""
        if getattr(event, "is_keypad", False) and not key.startswith("num "):
            key = f"num {key}"
        key = "" if key == "esc" else key
        action = self._capture_action
        self._capture_action = None
        keyboard.unhook(self._hook)
        self._hook = None
        self._restore()
        self.key_captured.emit(action, key)
