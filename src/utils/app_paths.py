"""程序数据目录定位：开发态基于项目根，打包后（PyInstaller）基于 exe 所在目录。"""
import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):  # PyInstaller 打包环境
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


DATA_DIR = app_root() / "data"
