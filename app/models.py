"""数据模型:以 pydantic 校验 json_map 四张表的结构与一致性。"""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemInfo(BaseModel):
    """collection_map 中单个物品的属性。

    Attributes:
        format_: 占位格式,如 "4格"。
        category: 类别名,如 "工具"。
        quality: 品质,如 "红"。
        sound: 声音名,如 "脑电装置声"。
    """

    model_config = ConfigDict(frozen=True)

    format_: str = Field(alias="格式")
    category: str = Field(alias="类别")
    quality: str = Field(alias="品质")
    sound: str = Field(alias="声音")


class MapData(BaseModel):
    """json_map 目录四张表的整体数据。

    Attributes:
        category_map: 类别 -> 物品名列表。
        footprint_map: 格式 -> 物品名列表。
        audio_map: 声音 -> 物品名列表(拿放音效的声音名含"拿放"字样)。
        collection_map: 物品名 -> 物品属性。
    """

    category_map: dict[str, tuple[str, ...]]
    footprint_map: dict[str, tuple[str, ...]]
    audio_map: dict[str, tuple[str, ...]]
    collection_map: dict[str, ItemInfo]

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        """校验三张索引表与主表双向一致。

        Returns:
            校验通过后的自身。

        Raises:
            ValueError: 索引表引用了不存在的物品、成员属性与桶键冲突,
                或物品未列入自身属性对应的桶。
        """
        self._check_buckets("category_map", "category", "类别")
        self._check_buckets("footprint_map", "format_", "格式")
        self._check_buckets("audio_map", "sound", "声音")
        return self

    def _check_buckets(self, map_name: str, field: str, label: str) -> None:
        """校验一张索引表与主表的双向一致性。

        Args:
            map_name: 本对象的索引表属性名。
            field: ItemInfo 上对应的属性名。
            label: 出错信息中的中文属性名。
        """
        index = getattr(self, map_name)
        for key, members in index.items():
            if len(members) != len(set(members)):
                raise ValueError(f"{map_name}[{key}] 存在重复物品")
            for name in members:
                info = self.collection_map.get(name)
                if info is None:
                    raise ValueError(
                        f"{map_name}[{key}] 引用了 collection_map 中不存在的物品: {name}"
                    )
                value = getattr(info, field)
                if value != key:
                    raise ValueError(f"{map_name}[{key}] 的物品 {name} 的{label}应为 {value}")
        for name, info in self.collection_map.items():
            value = getattr(info, field)
            if value not in index:
                raise ValueError(f"物品 {name} 的{label} {value} 不在 {map_name} 中")
            if name not in index[value]:
                raise ValueError(f"物品 {name} 未列入 {map_name}[{value}]")
