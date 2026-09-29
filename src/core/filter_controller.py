import json

from PySide6.QtCore import QObject
from PySide6.QtGui import QColor

from src.utils.app_paths import DATA_DIR
from src.widgets.sound_indicator import ANY_SOUND

JSON_DIR = DATA_DIR / "json_map"

QUALITY_COLORS = {
    "紫": QColor("#9400D3"),
    "金": QColor("#DAA520"),
    "红": QColor("#DC143C"),
}

QUALITY_ORDER = {"红": 0, "金": 1, "紫": 2}
UNKNOWN_QUALITY_COLOR = QColor("#888888")
UNKNOWN_QUALITY_ORDER = 9  # 未知品质排最后


class FilterController(QObject):
    """把顶栏筛选控件与内容区展示绑定起来"""

    def __init__(self, top_bar, content_area, parent=None):
        super().__init__(parent)
        self.top_bar = top_bar
        self.content_area = content_area
        self._collection_map: dict[str, dict[str, str]] = self._load_json("collection_map")
        self._category_map: dict[str, list[str]] = self._load_json("category_map")
        self._footprint_map: dict[str, list[str]] = self._load_json("footprint_map")
        self._audio_map: dict[str, list[str]] = self._load_json("audio_map")
        self._sound_category: str | None = None
        self._connect_signals()
        self.refresh()

    def set_sound(self, category: str | None):
        """按比对出的声音类别筛选物品（None 表示不按声音筛选）"""
        self._sound_category = category
        self.refresh()

    @staticmethod
    def _load_json(name: str) -> dict:
        with open(JSON_DIR / f"{name}.json", encoding="utf-8") as f:
            return json.load(f)

    def _connect_signals(self):
        """连接顶栏筛选控件的信号"""
        self.top_bar.type_selector.combo_box.currentTextChanged.connect(self.refresh)
        self.top_bar.format_selector.combo_box.currentTextChanged.connect(self.refresh)
        self.top_bar.sound_indicator.category_combo_box.currentTextChanged.connect(
            self._on_sound_changed)

    def _on_sound_changed(self, category: str):
        """信号触发：声音类别变化驱动筛选（任意音频视为不筛）"""
        self.set_sound(None if category == ANY_SOUND else category)

    def refresh(self, *_):
        """信号触发：按当前类别与格式筛选物品并刷新内容区，红品质在前、金其次、紫最后"""
        names = sorted(
            self._filtered_names(),
            key=lambda name: QUALITY_ORDER.get(
                self._quality_of(name), UNKNOWN_QUALITY_ORDER),
        )
        items = [
            (name, QUALITY_COLORS.get(self._quality_of(name), UNKNOWN_QUALITY_COLOR))
            for name in names
        ]
        self.content_area.show_items(items)

    def _quality_of(self, name: str) -> str | None:
        """物品品质；映射数据缺项时返回 None，排序与着色按未知品质处理"""
        return self._collection_map.get(name, {}).get("品质")

    def _filtered_names(self):
        """类别、格式与声音三重筛选取交集；均未选择时返回全部物品"""
        names: list[str] | None = None

        def intersect(other: list[str]):
            nonlocal names
            if names is None:
                names = list(other)
            else:
                allowed = set(other)
                names = [name for name in names if name in allowed]

        category = self.top_bar.type_selector.combo_box.currentText()
        if category != "神秘货物":
            intersect(self._category_map.get(category, []))
        format_name = self.top_bar.format_selector.combo_box.currentText()
        if format_name != "任意格式":
            intersect(self._footprint_map.get(format_name, []))
        if self._sound_category is not None:
            intersect(self._audio_map.get(self._sound_category, []))
        return names if names is not None else list(self._collection_map)
