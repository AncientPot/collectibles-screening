"""运行配置:音量与可设置快捷键的持久化,存于 data/config.json。"""

import json
from pathlib import Path
from typing import Any

from app.paths import base_dir

# 各配置项默认值;play/topmost 与设置界面的两个可设置快捷键对应
DEFAULT_VOLUME = 0.25
DEFAULT_HOTKEYS = {"play": "right", "topmost": "left"}
# json 中的中文键名
_KEY_VOLUME = "音量"
_KEY_HOTKEYS = "快捷键"


class AppConfig:
    """读写 data/config.json;文件缺失或内容非法时回退默认值。"""

    def __init__(self, path: str | Path | None = None) -> None:
        """加载配置文件。

        Args:
            path: 配置文件路径,默认为基准目录 data 下的 config.json。
        """
        self.path = Path(path) if path else base_dir() / "data" / "config.json"
        data = self._read()
        volume = data.get(_KEY_VOLUME, DEFAULT_VOLUME)
        self.volume = (
            float(volume)
            if isinstance(volume, int | float) and not isinstance(volume, bool) and 0 <= volume <= 1
            else DEFAULT_VOLUME
        )
        stored = data.get(_KEY_HOTKEYS)
        stored_map = stored if isinstance(stored, dict) else {}
        self._hotkeys = {}
        for action, default in DEFAULT_HOTKEYS.items():
            stored_key = stored_map.get(action)
            self._hotkeys[action] = (
                stored_key if isinstance(stored_key, str) and stored_key else default
            )

    def hotkey(self, action: str) -> str:
        """读取动作的持久化热键。

        Args:
            action: 动作标识,如 "play"、"topmost"。

        Returns:
            热键名;未知动作返回空字符串。
        """
        return self._hotkeys.get(action, "")

    def set_hotkey(self, action: str, key: str) -> None:
        """更新动作热键并立即写盘。

        Args:
            action: 动作标识。
            key: 新热键名;为空(注册失败回退)时不写入。
        """
        if not key or action not in DEFAULT_HOTKEYS:
            return
        self._hotkeys[action] = key
        self._save()

    def set_volume(self, value: float) -> None:
        """更新音量并立即写盘。

        Args:
            value: 音量,0~1。
        """
        self.volume = value
        self._save()

    def _read(self) -> dict[str, Any]:
        """读取配置文件,缺失或非法时返回空字典。"""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self) -> None:
        """把当前配置写回文件。"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {_KEY_VOLUME: self.volume, _KEY_HOTKEYS: self._hotkeys}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8"
        )
