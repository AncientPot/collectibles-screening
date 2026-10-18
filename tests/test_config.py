"""运行配置持久化测试。"""

from pathlib import Path

from app.config import AppConfig


class TestAppConfig:
    def test_defaults_when_missing(self, tmp_path: Path) -> None:
        """配置文件不存在时回退默认值。"""
        config = AppConfig(tmp_path / "config.json")
        assert config.volume == 0.25
        assert config.hotkey("play") == "right"
        assert config.hotkey("topmost") == "left"
        assert config.hotkey("unknown") == ""

    def test_load_and_save_roundtrip(self, tmp_path: Path) -> None:
        """音量与热键更新后落盘,重新加载可读回。"""
        path = tmp_path / "config.json"
        config = AppConfig(path)
        config.set_volume(0.6)
        config.set_hotkey("play", "f8")
        fresh = AppConfig(path)
        assert fresh.volume == 0.6
        assert fresh.hotkey("play") == "f8"
        assert fresh.hotkey("topmost") == "left"  # 未改动项保持默认

    def test_invalid_values_fall_back(self, tmp_path: Path) -> None:
        """音量越界、热键为空等非法值回退默认。"""
        path = tmp_path / "config.json"
        path.write_text('{"音量": 9.9, "快捷键": {"play": ""}}', encoding="utf-8")
        config = AppConfig(path)
        assert config.volume == 0.25
        assert config.hotkey("play") == "right"

    def test_corrupt_file_falls_back(self, tmp_path: Path) -> None:
        """配置文件损坏(非法 json)时回退默认。"""
        path = tmp_path / "config.json"
        path.write_text("{不是json", encoding="utf-8")
        config = AppConfig(path)
        assert config.volume == 0.25
        assert config.hotkey("topmost") == "left"

    def test_set_hotkey_ignores_empty(self, tmp_path: Path) -> None:
        """注册失败回退产生的空热键名不写入。"""
        path = tmp_path / "config.json"
        config = AppConfig(path)
        config.set_hotkey("play", "")
        assert AppConfig(path).hotkey("play") == "right"
