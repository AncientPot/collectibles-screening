"""数据层:加载 data 目录并对外提供筛选与声音文件查询。"""

import json
from pathlib import Path
from typing import Any

from app.models import ItemInfo, MapData
from app.paths import base_dir

AUDIO_DIR_NAME = "original_ audio"


class DataStore:
    """加载 data 目录下的 json 数据,提供筛选与声音文件查找。"""

    def __init__(self, data_dir: str | Path | None = None) -> None:
        """初始化并加载 json_map 四张表。

        Args:
            data_dir: 数据根目录,默认为基准目录(源码运行为项目根,
                打包后为 exe 所在目录)下的 data 目录。

        Raises:
            OSError: 数据文件读取失败。
            ValueError: 数据校验失败(pydantic ValidationError 是其子类)。
        """
        self.data_dir = Path(data_dir) if data_dir else base_dir() / "data"
        self.audio_dir = self.data_dir / AUDIO_DIR_NAME
        self._data = self._load_data()

    def _load_data(self) -> MapData:
        """读取并校验 json_map 四张表。

        Returns:
            校验通过的整体数据。
        """
        json_map = self.data_dir / "json_map"
        return MapData.model_validate(
            {
                "category_map": self._read_json(json_map / "category_map.json"),
                "footprint_map": self._read_json(json_map / "footprint_map.json"),
                "audio_map": self._read_json(json_map / "audio_map.json"),
                "collection_map": self._read_json(json_map / "collection_map.json"),
            }
        )

    def reload(self) -> bool:
        """重新读取 json_map 四张表,支持运行中热更新。

        数据暂不合法(如编辑到一半)时保留旧数据,待下次文件变动重试。

        Returns:
            是否成功加载了新数据。
        """
        try:
            self._data = self._load_data()
        except OSError, ValueError:
            return False
        return True

    @staticmethod
    def _read_json(path: Path) -> Any:
        """读取一个 json 文件。

        Args:
            path: json 文件路径。

        Returns:
            解析后的 json 内容。

        Raises:
            FileNotFoundError: 文件不存在。
            json.JSONDecodeError: 内容不是合法 json。
        """
        with open(path, encoding="utf-8") as file:
            return json.load(file)

    def categories(self) -> list[str]:
        """类别选项,物品多的在前。

        Returns:
            类别名列表,同数量时保持表内顺序。
        """
        return sorted(
            self._data.category_map,
            key=lambda name: len(self._data.category_map[name]),
            reverse=True,
        )

    def formats(self) -> list[str]:
        """格式选项,按 footprint_map 键序。

        Returns:
            格式名列表。
        """
        return list(self._data.footprint_map)

    def sounds(self) -> list[tuple[str, str, str]]:
        """声音选项;有红在前、无红次之、无素材的最后;组内按物品数量降序。

        Returns:
            [(名称, 显示文本, 分组), ...] 列表;分组为空串表示有红组(不显示标题),
            "无红"、"暂无声音"等为分组标题,由调用方插入分组行;
            同数量时拿放声音靠后。
        """
        tiers = {"": 0, "无红": 1, "暂无声音": 2}
        options: list[tuple[tuple[int, int, int], str, str, str]] = []
        for name, members in self._data.audio_map.items():
            infos = (self._data.collection_map[item] for item in members)
            has_red = any(info.quality == "红" for info in infos)
            has_take = "拿放" in name
            if self.sound_file(name) is None:
                group = "暂无声音"
            elif has_red:
                group = ""
            else:
                group = "无红"
            order = (tiers[group], -len(members), 1 if has_take else 0)
            options.append((order, name, name, group))
        options.sort(key=lambda option: option[0])
        return [(name, name, group) for _, name, _, group in options]

    def filter_items(
        self, category: str = "", format_: str = "", sound: str = ""
    ) -> list[tuple[str, ItemInfo]]:
        """按类别、格式、声音取交集筛选;空条件表示不过滤。

        Args:
            category: 类别名,空字符串表示不过滤。
            format_: 格式名,空字符串表示不过滤。
            sound: 声音名,空字符串表示不过滤。

        Returns:
            [(物品名, 物品属性), ...],按主表顺序。
        """
        name_sets: list[set[str]] = []
        if category:
            name_sets.append(set(self._data.category_map.get(category, ())))
        if format_:
            name_sets.append(set(self._data.footprint_map.get(format_, ())))
        if sound:
            name_sets.append(set(self._data.audio_map.get(sound, ())))
        names = set.intersection(*name_sets) if name_sets else set(self._data.collection_map)
        return [(name, info) for name, info in self._data.collection_map.items() if name in names]

    def sound_file(self, sound_name: str) -> Path | None:
        """查找声音名对应的 wav 文件。

        文件位于同名子目录内,文件名以声音名开头并带序号后缀
        (如 显卡声/显卡声_0.wav);多个变体时取序号最小者。

        Args:
            sound_name: 声音名,空字符串直接返回 None。

        Returns:
            按文件名排序的第一个匹配 wav 路径;找不到时返回 None。
        """
        if not sound_name:
            return None
        directory = self.audio_dir / sound_name
        for path in sorted(directory.glob(f"{sound_name}*.wav")):
            return path
        return None

    def items_newest_first(self) -> list[str]:
        """物品名列表,最新添加的在前(json 中越靠下越新)。

        Returns:
            按主表逆序的物品名列表。
        """
        return list(reversed(self._data.collection_map))

    def qualities(self) -> list[str]:
        """物品品质选项,出现次数多的在前。

        Returns:
            品质名列表。
        """
        counts: dict[str, int] = {}
        for info in self._data.collection_map.values():
            counts[info.quality] = counts.get(info.quality, 0) + 1
        return sorted(counts, key=lambda quality: counts[quality], reverse=True)

    def add_item(self, name: str, format_: str, category: str, quality: str, sound: str) -> None:
        """新增物品并写回 json 文件,随后热加载生效。

        新物品追加到各表末尾(即最新);声音名允许是尚不存在的新名称。

        Args:
            name: 物品名。
            format_: 已有格式名。
            category: 已有类别名。
            quality: 品质名。
            sound: 声音名(已有或全新)。

        Raises:
            ValueError: 物品名已存在,或格式/类别不在已有选项中。
        """
        if name in self._data.collection_map:
            raise ValueError(f"物品「{name}」已存在")
        if format_ not in self._data.footprint_map:
            raise ValueError(f"格式「{format_}」不存在")
        if category not in self._data.category_map:
            raise ValueError(f"类别「{category}」不存在")
        self._data.collection_map[name] = ItemInfo.model_validate(
            {"格式": format_, "类别": category, "品质": quality, "声音": sound}
        )
        self._data.footprint_map[format_] = (*self._data.footprint_map[format_], name)
        self._data.category_map[category] = (*self._data.category_map[category], name)
        self._data.audio_map[sound] = (*self._data.audio_map.get(sound, ()), name)
        self._save()

    def remove_item(self, name: str) -> None:
        """删除物品并写回 json 文件,随后热加载生效。

        清空后的格式/类别键一并移除,避免下拉出现永远为空的选项;
        声音组允许清空保留(与"香水声"等占位一致)。

        Args:
            name: 物品名。

        Raises:
            ValueError: 物品不存在。
        """
        info = self._data.collection_map.get(name)
        if info is None:
            raise ValueError(f"物品「{name}」不存在")
        del self._data.collection_map[name]
        for field, bucket_key in (
            ("footprint_map", info.format_),
            ("category_map", info.category),
            ("audio_map", info.sound),
        ):
            bucket: dict[str, tuple[str, ...]] = getattr(self._data, field)
            members = tuple(member for member in bucket[bucket_key] if member != name)
            if members or field == "audio_map":
                bucket[bucket_key] = members
            else:
                del bucket[bucket_key]
        self._save()

    def _save(self) -> None:
        """把当前数据写回 json_map 四张表,保留键序与制表符缩进。"""
        payload = {
            "category_map": {
                key: list(members) for key, members in self._data.category_map.items()
            },
            "footprint_map": {
                key: list(members) for key, members in self._data.footprint_map.items()
            },
            "audio_map": {key: list(members) for key, members in self._data.audio_map.items()},
            "collection_map": {
                name: info.model_dump(by_alias=True)
                for name, info in self._data.collection_map.items()
            },
        }
        json_map = self.data_dir / "json_map"
        for filename, data in payload.items():
            (json_map / f"{filename}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8"
            )
        self.reload()
