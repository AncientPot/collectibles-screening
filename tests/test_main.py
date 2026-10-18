"""入口脚本虚拟环境检测与转入逻辑的测试。"""

import sys
from pathlib import Path

import pytest

import main


def test_in_venv_when_running_project_venv() -> None:
    """uv run 下当前解释器即项目虚拟环境。"""
    assert main._in_venv()


def test_not_in_venv_for_foreign_interpreter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """解释器指向其他路径时判定为不在虚拟环境。"""
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python.exe"))
    assert not main._in_venv()


def test_reexec_reports_missing_venv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """虚拟环境缺失时不重启,记录 error 日志并返回错误码。"""
    monkeypatch.setattr(main, "_VENV_PYTHON", tmp_path / "missing" / "python.exe")
    assert main._reexec_in_venv() == 1
    assert "uv sync" in capsys.readouterr().err
