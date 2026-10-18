"""应用路径:打包(exe)与源码运行时统一解析数据与日志目录。"""

import sys
from pathlib import Path


def base_dir() -> Path:
    """返回应用基准目录。

    Returns:
        打包为 exe 时为 exe 所在目录,数据与日志随 exe 分发、可直接修改;
        源码运行时为项目根目录。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
