"""真实数据完整性测试:项目自带 data 目录必须通过模型校验。"""

from pathlib import Path

from app.data_store import DataStore

PROJECT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXPECTED_ITEMS = 180


def test_real_data_passes_validation() -> None:
    """加载真实数据即完成交叉一致性校验,不抛异常。"""
    store = DataStore(PROJECT_DATA_DIR)
    assert len(store.filter_items()) == EXPECTED_ITEMS


def test_real_data_format_options() -> None:
    """格式选项应为改名后的六种。"""
    store = DataStore(PROJECT_DATA_DIR)
    assert store.formats() == [
        "1格",
        "竖2格",
        "横2格",
        "竖3格",
        "横3格",
        "4格",
        "竖6格",
        "横6格",
        "横8格",
        "9格",
    ]


def test_real_data_categories_non_empty_and_sorted() -> None:
    """类别按物品数降序,且不含空类别。"""
    store = DataStore(PROJECT_DATA_DIR)
    categories = store.categories()
    assert categories
    assert store.filter_items(category=categories[-1])


def test_real_data_groups_sounds_without_material() -> None:
    """无素材声音归入"暂无声音"分组,其余声音均有音频文件。"""
    store = DataStore(PROJECT_DATA_DIR)
    groups = {name: group for name, _label, group in store.sounds()}
    assert groups["香水声"] == "暂无声音"
    assert groups["火焰喷灯声"] == "暂无声音"
    with_material = {name: group for name, group in groups.items() if group != "暂无声音"}
    assert with_material
    assert all(store.sound_file(name) is not None for name in with_material)


def test_real_data_sound_counts_descend_within_group() -> None:
    """声音下拉每个分组内按物品数量降序排列。"""
    store = DataStore(PROJECT_DATA_DIR)
    counts: list[int] = []
    last_group: str | None = None
    for name, _label, group in store.sounds():
        if group != last_group:
            if counts:
                assert counts == sorted(counts, reverse=True)
            counts = []
            last_group = group
        counts.append(len(store.filter_items(sound=name)))
    assert counts == sorted(counts, reverse=True)
