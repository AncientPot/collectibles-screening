"""测试夹具:Qt 应用、受控样例数据与 keyboard 替身。"""

import json
import os
from pathlib import Path
from typing import Any

import keyboard
import pytest
from PySide6.QtWidgets import QApplication

import app.config
from app.data_store import DataStore


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """把运行配置指向临时目录,避免测试写穿真实 data/config.json。"""
    monkeypatch.setattr(app.config, "base_dir", lambda: tmp_path)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """提供整个测试会话共用的离屏 QApplication。"""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """构造受控的样例数据目录。

    覆盖类别排序、声音标注、筛选交集与 wav 后缀匹配等分支。

    Args:
        tmp_path: pytest 临时目录。

    Returns:
        数据根目录路径。
    """
    json_map = tmp_path / "json_map"
    json_map.mkdir()
    audio_dir = tmp_path / "original_ audio"
    audio_dir.mkdir()

    maps: dict[str, dict[str, Any]] = {
        "category_map": {"工具": ["红金物品", "紫物"], "杂物": ["金物", "蓝物"], "生活": ["绿物"]},
        "footprint_map": {
            "竖2格": ["红金物品"],
            "4格": ["紫物", "金物"],
            "6格横": ["蓝物", "绿物"],
        },
        "audio_map": {
            "甲声": ["红金物品", "紫物"],
            "乙拿放声": ["金物", "蓝物", "绿物"],
            "丙声": [],
        },
        "collection_map": {
            "红金物品": {"格式": "竖2格", "类别": "工具", "品质": "红", "声音": "甲声"},
            "紫物": {"格式": "4格", "类别": "工具", "品质": "紫", "声音": "甲声"},
            "金物": {"格式": "4格", "类别": "杂物", "品质": "金", "声音": "乙拿放声"},
            "蓝物": {"格式": "6格横", "类别": "杂物", "品质": "蓝", "声音": "乙拿放声"},
            "绿物": {"格式": "6格横", "类别": "生活", "品质": "绿", "声音": "乙拿放声"},
        },
    }
    for name, data in maps.items():
        (json_map / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    for sound in ("甲声", "乙拿放声"):
        sound_dir = audio_dir / sound
        sound_dir.mkdir()
        (sound_dir / f"{sound}_0.wav").write_bytes(b"RIFF")
    return tmp_path


@pytest.fixture
def store(data_dir: Path) -> DataStore:
    """基于样例数据目录的数据层。

    Args:
        data_dir: 样例数据根目录。

    Returns:
        DataStore 实例。
    """
    return DataStore(data_dir)


@pytest.fixture
def fake_keyboard(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """以替身替换 keyboard 库,记录调用并允许模拟按键。

    模拟真实库的解析语义:热键串按 + 分词,词不在已知键名表中抛 ValueError;
    此时可通过 key_to_scan_codes 查扫描码,以 tuple 形式注册。

    Args:
        monkeypatch: pytest 替身工具。

    Returns:
        状态字典:hotkeys 为目标键到回调的映射(扫描码目标形如 "codes:78"),
        hooks 为激活的按键钩子,removed 为已注销的句柄。
    """
    state: dict[str, Any] = {"hotkeys": {}, "hooks": [], "removed": []}
    known_keys = {"-", "f5", "f6", "f7", "up", "down", "left", "right", "ctrl", "shift", "a"}
    scan_codes = {"num +": (78,)}

    def hotkey_key(target: Any) -> str:
        """把热键目标归一化为状态字典的键。"""
        if isinstance(target, tuple):
            return "codes:" + ",".join(map(str, target))
        return str(target)

    def add_hotkey(target: Any, callback: Any) -> tuple[str, str]:
        if isinstance(target, str):
            tokens = [token.strip() for token in target.split("+") if token.strip()] or [target]
            if any(token not in known_keys for token in tokens):
                raise ValueError(f"Key {target!r} is not mapped to any known key.")
        key = hotkey_key(target)
        state["hotkeys"][key] = callback
        return "hotkey", key

    def remove_hotkey(handler: tuple[str, str]) -> None:
        state["removed"].append(handler)
        if handler[0] == "hotkey":
            state["hotkeys"].pop(handler[1], None)

    def key_to_scan_codes(name: str, error_if_missing: bool = True) -> tuple[int, ...]:
        if name not in scan_codes:
            if error_if_missing:
                raise ValueError(f"Key {name!r} is not mapped to any known key.")
            return ()
        return scan_codes[name]

    def hook(callback: Any) -> tuple[str, int]:
        handle = ("hook", len(state["hooks"]))
        state["hooks"].append((handle, callback))
        return handle

    def unhook(handle: tuple[str, int]) -> None:
        state["hooks"] = [pair for pair in state["hooks"] if pair[0] != handle]

    monkeypatch.setattr(keyboard, "add_hotkey", add_hotkey)
    monkeypatch.setattr(keyboard, "remove_hotkey", remove_hotkey)
    monkeypatch.setattr(keyboard, "key_to_scan_codes", key_to_scan_codes)
    monkeypatch.setattr(keyboard, "hook", hook)
    monkeypatch.setattr(keyboard, "unhook", unhook)
    return state
