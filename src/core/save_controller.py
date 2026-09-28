import hashlib
import json
import threading
import traceback

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QDialog, QMessageBox

from src.core.audio_matcher import RECORDED_WAV
from src.widgets.save_dialog import SaveDialog
from src.widgets.sound_indicator import ANY_SOUND

from src.utils.app_paths import DATA_DIR

SAVE_DIR = DATA_DIR / "save"
JSON_DIR = DATA_DIR / "json_map"


class SaveController(QObject):
    """保存按钮：把当前采集音频以「音频名称_内容哈希」命名存档，
    并在后台热重载匹配器使新学习模板立即生效"""

    _reload_done = Signal(bool)

    def __init__(self, top_bar, matcher, parent=None):
        super().__init__(parent)
        self.top_bar = top_bar
        self._matcher = matcher
        self.top_bar.save_button.button.clicked.connect(self._on_save_clicked)
        self._reload_done.connect(self._on_reload_done)

    def _on_save_clicked(self, *_):
        """信号触发：选择音频名称并保存当前采集音频"""
        if not RECORDED_WAV.exists():
            QMessageBox.warning(self.top_bar, "保存", "没有可保存的采集音频，请先录制。")
            return
        dialog = SaveDialog(self.top_bar, self._load_categories(),
                            default=self._current_category())
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._save(dialog.category_name)

    def _save(self, category_name: str):
        data = RECORDED_WAV.read_bytes()
        # 内容哈希做后缀：同一段音频重名不会产生重复文件
        digest = hashlib.sha256(data).hexdigest()[:8]
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        target = SAVE_DIR / f"{category_name}_{digest}.wav"
        if target.exists():
            QMessageBox.information(self.top_bar, "保存", "该音频已保存过：%s" % target.name)
            return
        target.write_bytes(data)
        QMessageBox.information(self.top_bar, "保存", "已保存：%s" % target.name)
        # 后台热重载，新学习模板约两秒内生效，无需重启应用
        threading.Thread(target=self._reload_and_notify, daemon=True).start()

    def _reload_and_notify(self):
        try:
            self._matcher.reload()
            ok = True
        except Exception:
            traceback.print_exc()
            ok = False
        self._reload_done.emit(ok)

    def _on_reload_done(self, ok: bool):
        """重载结果经信号回主线程，在相似度标签处短暂提示"""
        label = self.top_bar.probability_label
        message = "学习模板已更新" if ok else "模板重载失败"
        label.setText(message)

        def clear():
            # 期间被比对结果覆盖则不清除
            if label.text() == message:
                label.setText("")

        QTimer.singleShot(3000, clear)

    def _current_category(self) -> str | None:
        """当前指示区选中的声音类别（任意声音视为未选择）"""
        category = self.top_bar.sound_indicator.current_category
        return category if category != ANY_SOUND else None

    @staticmethod
    def _load_categories() -> list[str]:
        with open(JSON_DIR / "audio_map.json", encoding="utf-8") as f:
            return sorted(json.load(f))
