"""听声鉴宝应用入口。

未运行在项目虚拟环境时,自动转入 .venv 的解释器重新启动本脚本;
子进程继承当前控制台与标准流,命令行输出保持可见。
"""

import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
_VENV_PYTHON = (
    _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if sys.platform == "win32"
    else _PROJECT_ROOT / ".venv" / "bin" / "python"
)


def _in_venv() -> bool:
    """当前解释器是否已是项目虚拟环境的 Python。"""
    try:
        return Path(sys.executable).samefile(_VENV_PYTHON)
    except OSError:
        return False


def _reexec_in_venv() -> int:
    """在虚拟环境解释器中重新启动本脚本并等待其退出。

    子进程继承当前控制台与标准流,命令行显示保持不变。

    Returns:
        子进程退出码;虚拟环境缺失时返回 1。
    """
    if not _VENV_PYTHON.is_file():
        print(f"未找到虚拟环境 {_VENV_PYTHON},请先执行 uv sync 创建", file=sys.stderr)
        return 1
    print(f"转入虚拟环境启动:{_VENV_PYTHON}")
    completed = subprocess.run([str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])
    return completed.returncode


def main() -> int:
    """创建应用与主窗口并进入事件循环;不在虚拟环境时先转入虚拟环境重启。

    Returns:
        应用退出码。
    """
    if not getattr(sys, "frozen", False) and not _in_venv():
        return _reexec_in_venv()
    # 虚拟环境就绪后才导入 Qt,避免系统解释器缺少 PySide6 时导入失败
    from PySide6.QtWidgets import QApplication

    from app.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
