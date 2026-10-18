"""DataStore 与数据模型的测试。"""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.data_store import DataStore
from app.models import ItemInfo, MapData


class TestItemInfo:
    def test_alias_from_chinese_keys(self) -> None:
        info = ItemInfo.model_validate(
            {"格式": "4格", "类别": "工具", "品质": "红", "声音": "甲声"}
        )
        assert (info.format_, info.category, info.quality, info.sound) == (
            "4格",
            "工具",
            "红",
            "甲声",
        )

    def test_frozen(self) -> None:
        info = ItemInfo.model_validate(
            {"格式": "4格", "类别": "工具", "品质": "红", "声音": "甲声"}
        )
        with pytest.raises(ValidationError):
            info.quality = "金"


class TestOptions:
    def test_categories_sorted_by_count(self, store: DataStore) -> None:
        # 工具、杂物各 2 件按表内顺序在前,生活 1 件在后
        assert store.categories() == ["工具", "杂物", "生活"]

    def test_formats_follow_map_order(self, store: DataStore) -> None:
        assert store.formats() == ["竖2格", "4格", "6格横"]

    def test_sounds_order_and_labels(self, store: DataStore) -> None:
        # 有红组在前;无红组次之(拿放嵌入名称);无素材的最后
        assert store.sounds() == [
            ("甲声", "甲声", ""),
            ("乙拿放声", "乙拿放声", "无红"),
            ("丙声", "丙声", "暂无声音"),
        ]


class TestFilterItems:
    def test_empty_conditions_return_all(self, store: DataStore) -> None:
        names = [name for name, _ in store.filter_items()]
        assert names == ["红金物品", "紫物", "金物", "蓝物", "绿物"]

    def test_single_conditions(self, store: DataStore) -> None:
        assert [n for n, _ in store.filter_items(category="工具")] == ["红金物品", "紫物"]
        assert [n for n, _ in store.filter_items(format_="4格")] == ["紫物", "金物"]
        assert [n for n, _ in store.filter_items(sound="乙拿放声")] == ["金物", "蓝物", "绿物"]

    def test_intersection(self, store: DataStore) -> None:
        assert [n for n, _ in store.filter_items(category="工具", format_="4格")] == ["紫物"]
        assert [
            n for n, _ in store.filter_items(category="工具", format_="4格", sound="乙拿放声")
        ] == []

    def test_unknown_condition_matches_nothing(self, store: DataStore) -> None:
        assert store.filter_items(format_="不存在") == []

    def test_returns_item_info(self, store: DataStore) -> None:
        _, info = store.filter_items(category="生活")[0]
        assert isinstance(info, ItemInfo)
        assert info.quality == "绿"


class TestReload:
    def test_reload_picks_up_changes(self, store: DataStore, data_dir: Path) -> None:
        """修改 json 后热加载生效。"""
        collection: dict[str, Any] = json.loads(
            (data_dir / "json_map" / "collection_map.json").read_text(encoding="utf-8")
        )
        collection["红金物品"]["品质"] = "紫"
        (data_dir / "json_map" / "collection_map.json").write_text(
            json.dumps(collection, ensure_ascii=False), encoding="utf-8"
        )
        assert store.reload() is True
        assert store.filter_items(category="工具")[0][1].quality == "紫"

    def test_reload_keeps_old_data_on_invalid_change(
        self, store: DataStore, data_dir: Path
    ) -> None:
        """数据非法(如编辑到一半)时保留旧数据。"""
        (data_dir / "json_map" / "category_map.json").write_text(
            json.dumps({"工具": ["幽灵物品"]}, ensure_ascii=False), encoding="utf-8"
        )
        assert store.reload() is False
        # 旧数据仍可用
        assert len(store.filter_items()) == 5


class TestAddRemoveItems:
    def test_add_item_appends_and_saves(self, store: DataStore, data_dir: Path) -> None:
        """新增物品写入内存与 json,最新添加的在列表最前。"""
        store.add_item("新物品", "4格", "工具", "紫", "乙拿放声")
        assert [n for n, _ in store.filter_items(category="工具")] == ["红金物品", "紫物", "新物品"]
        fresh = DataStore(data_dir)
        assert [n for n, _ in fresh.filter_items(format_="4格", category="工具")] == [
            "紫物",
            "新物品",
        ]
        assert fresh.items_newest_first()[0] == "新物品"

    def test_add_item_duplicate_rejected(self, store: DataStore) -> None:
        with pytest.raises(ValueError, match="已存在"):
            store.add_item("红金物品", "4格", "工具", "紫", "甲声")

    def test_add_item_new_sound_allowed(self, store: DataStore, data_dir: Path) -> None:
        """声音名允许是全新名称(无音频文件,自动归入暂无声音)。"""
        store.add_item("新声音物品", "4格", "工具", "紫", "全新声")
        fresh = DataStore(data_dir)
        assert [n for n, _ in fresh.filter_items(sound="全新声")] == ["新声音物品"]

    def test_add_item_unknown_format_rejected(self, store: DataStore) -> None:
        with pytest.raises(ValueError, match="格式"):
            store.add_item("物品", "9x9", "工具", "紫", "甲声")

    def test_remove_item_updates_all_maps(self, store: DataStore, data_dir: Path) -> None:
        """删除物品同步清理三张索引表;清空的格式键移除,声音组保留。"""
        store.remove_item("红金物品")  # 竖2格的唯一成员
        fresh = DataStore(data_dir)
        assert {n for n, _ in fresh.filter_items()} == {"紫物", "金物", "蓝物", "绿物"}
        assert "竖2格" not in fresh.formats()
        assert [n for n, _ in fresh.filter_items(sound="甲声")] == ["紫物"]

    def test_remove_missing_item_rejected(self, store: DataStore) -> None:
        with pytest.raises(ValueError, match="不存在"):
            store.remove_item("幽灵物品")

    def test_qualities_from_data(self, store: DataStore) -> None:
        assert set(store.qualities()) == {"红", "紫", "金", "蓝", "绿"}


class TestSoundFile:
    def test_matches_take_sound_file(self, store: DataStore) -> None:
        """拿放声音的音频位于同名子目录并带序号后缀。"""
        path = store.sound_file("乙拿放声")
        assert path is not None and path.name == "乙拿放声_0.wav"

    def test_matches_plain_file(self, store: DataStore) -> None:
        path = store.sound_file("甲声")
        assert path is not None and path.name == "甲声_0.wav"

    def test_empty_name_returns_none(self, store: DataStore) -> None:
        assert store.sound_file("") is None

    def test_missing_file_returns_none(self, store: DataStore) -> None:
        assert store.sound_file("丙声") is None


class TestMapDataValidation:
    """破坏一张表后整体校验必须失败。"""

    @staticmethod
    def _rewrite(data_dir: Path, name: str, data: dict[str, Any]) -> None:
        path = data_dir / "json_map" / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _load(data_dir: Path) -> MapData:
        return DataStore(data_dir)._data  # noqa: SLF001 测试需要触达私有数据

    def test_unknown_member_rejected(self, data_dir: Path) -> None:
        broken = {
            "工具": ["红金物品", "紫物", "幽灵物品"],
            "杂物": ["金物", "蓝物"],
            "生活": ["绿物"],
        }
        self._rewrite(data_dir, "category_map", broken)
        with pytest.raises(ValidationError, match="幽灵物品"):
            self._load(data_dir)

    def test_bucket_key_mismatch_rejected(self, data_dir: Path) -> None:
        collection: dict[str, Any] = json.loads(
            (data_dir / "json_map" / "collection_map.json").read_text(encoding="utf-8")
        )
        collection["紫物"]["类别"] = "杂物"
        self._rewrite(data_dir, "collection_map", collection)
        with pytest.raises(ValidationError, match="紫物"):
            self._load(data_dir)

    def test_item_missing_from_own_bucket_rejected(self, data_dir: Path) -> None:
        broken = {"甲声": ["红金物品"], "乙拿放声": ["金物", "蓝物", "绿物"]}
        self._rewrite(data_dir, "audio_map", broken)
        with pytest.raises(ValidationError, match="紫物"):
            self._load(data_dir)

    def test_duplicate_member_rejected(self, data_dir: Path) -> None:
        broken = {
            "竖2格": ["红金物品", "红金物品"],
            "4格": ["紫物", "金物"],
            "6格横": ["蓝物", "绿物"],
        }
        self._rewrite(data_dir, "footprint_map", broken)
        with pytest.raises(ValidationError, match="重复"):
            self._load(data_dir)

    def test_unknown_item_field_rejected(self, data_dir: Path) -> None:
        collection = json.loads(
            (data_dir / "json_map" / "collection_map.json").read_text(encoding="utf-8")
        )
        collection["红金物品"] = {"格式": "竖2格", "品质": "红", "声音": "甲声"}
        self._rewrite(data_dir, "collection_map", collection)
        with pytest.raises(ValidationError):
            self._load(data_dir)
