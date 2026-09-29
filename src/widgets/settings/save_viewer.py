from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.core.audio_matcher import USER_SAVE_DIR
from src.utils.set_layout import set_layout


class SaveViewerDialog(QDialog):
    """学习音频查看界面：各类别数量、刚录制标记与逐条删除"""

    def __init__(self, parent=None, on_files_changed=None):
        super().__init__(parent)
        self.setWindowTitle("学习音频")
        self._on_files_changed = on_files_changed
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        """组装ui"""
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.accept)
        layout = set_layout(QVBoxLayout(self), 12, 12, 12, 12, 8)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(close_button)
        self.resize(520, 420)

    def _refresh(self):
        """按类别目录重建音频清单（空类别也显示，数量为0）"""
        container = QWidget()
        layout = set_layout(QVBoxLayout(container), 4, 4, 4, 4, 2)
        files: list[Path] = sorted(USER_SAVE_DIR.glob("*/*.wav"))
        newest = max(files, key=lambda p: p.stat().st_mtime) if files else None
        # 目录被外部删除时按空处理（glob 对缺失目录返回空，iterdir 会抛错）
        category_dirs = (sorted(p for p in USER_SAVE_DIR.iterdir() if p.is_dir())
                         if USER_SAVE_DIR.is_dir() else [])
        if not category_dirs:
            layout.addWidget(QLabel("暂无学习音频，保存后在此查看。"))
        for category_dir in category_dirs:
            paths = sorted(category_dir.glob("*.wav"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            layout.addWidget(QLabel("%s（%d 个）" % (category_dir.name, len(paths))))
            for path in paths:
                row = QHBoxLayout()
                mark = "　[刚录制]" if path == newest else ""
                row.addWidget(QLabel(path.name + mark), 1)
                delete_button = QPushButton("删除")
                delete_button.clicked.connect(lambda _, p=path: self._delete(p))
                row.addWidget(delete_button)
                layout.addLayout(row)
        layout.addStretch(1)
        self.scroll_area.setWidget(container)

    def _delete(self, path: Path):
        """删除指定学习音频并通知刷新；文件被占用时提示失败"""
        try:
            path.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "删除", "删除失败（文件可能被占用）：%s" % exc)
            return
        if self._on_files_changed is not None:
            self._on_files_changed()
        self._refresh()
