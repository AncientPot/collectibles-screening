import json
import threading
import traceback
import wave

import keyboard
import numpy as np
import soundcard as sc
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog

from src.core.audio_matcher import (
    FILE_ALIASES,
    RECORDED_WAV,
    REFERENCE_DIR,
    USER_SAVE_DIR,
    AudioMatcher,
    prune_save_dir,
    rebuild_templates,
    templates_exist,
)
from src.core.audio_recorder import LoopbackRecorder
from src.utils.app_paths import DATA_DIR
from src.widgets.settings.settings_dialog import SettingsDialog
from src.widgets.sound_indicator import ANY_SOUND

CONFIG_PATH = DATA_DIR / "config.json"
_CONFIG_DEFAULTS = {
    "max_seconds": 5, "hotkey": "num +", "visibility_hotkey": "-", "play_volume": 5.0,
    "save_caps": {}, "save_weight": 0.5,
}
# 保底模板未构建时的门禁提示（多处引用，改动须同步）
GATE_MESSAGE = "请进入设置界面构建输出模板"

# 类别名 -> 基准文件名（大多数同名，个别有别名）
_FILE_OF_CATEGORY = {category: stem for stem, category in FILE_ALIASES.items()}


class ListenController(QObject):
    """监听按钮的状态切换、环回录音控制、声音比对与设置"""

    _toggle_requested = Signal()
    _record_finished = Signal(bool)
    _match_busy = Signal(bool)
    _visibility_requested = Signal()
    _rebuild_progress = Signal(int, int, str)
    _rebuild_finished = Signal(bool)
    match_completed = Signal(str, float)

    def __init__(self, top_bar, parent=None):
        super().__init__(parent)
        self.top_bar = top_bar
        config = self._load_config()
        self.recorder = LoopbackRecorder(
            max_seconds=int(config["max_seconds"]), on_finished=self._record_finished.emit
        )
        self.matcher = AudioMatcher(
            save_caps={str(k): int(v) for k, v in config["save_caps"].items()},
            save_weight=float(config["save_weight"]),
        )
        # 预建全部类别的学习目录，保证 save 目录结构完整可预期
        for category in self.matcher.categories:
            (USER_SAVE_DIR / category).mkdir(parents=True, exist_ok=True)
        self.top_bar.listen_button.button.toggled.connect(self._on_toggled)
        self.top_bar.settings_button.button.clicked.connect(self._on_settings_clicked)
        self.top_bar.play_button.button.clicked.connect(self._on_play_clicked)
        self._toggle_requested.connect(self._toggle_recording)
        self._record_finished.connect(self._on_record_finished)
        self._match_busy.connect(self._on_match_busy)
        self._visibility_requested.connect(self._toggle_visibility)
        self._rebuild_finished.connect(self._on_rebuild_done)
        # 启动时窗口位于前台，首次按置顶键先沉到后台
        self._front = True
        self._rebuilding = False
        # 播放音量倍率：1.0 为不做处理播放原始音频
        self.play_volume = float(config["play_volume"])
        # 'num +' 仅映射小键盘加号；keyboard 的回调在其钩子线程，经信号转回主线程
        self._hotkey = str(config["hotkey"])
        self._visibility_hotkey = str(config["visibility_hotkey"])
        self._hotkey_remover = lambda: None
        self._visibility_remover = lambda: None
        self._hotkeys_active = False
        self._resume_hotkeys()
        # 保底模板未构建时禁用监听并提示，构建完成后自动放开
        self._templates_gate = not templates_exist()
        if self._templates_gate:
            self.top_bar.listen_button.button.setEnabled(False)
            self.top_bar.probability_label.setText(GATE_MESSAGE)

    @property
    def hotkey(self) -> str:
        return self._hotkey

    @property
    def visibility_hotkey(self) -> str:
        return self._visibility_hotkey

    def set_hotkey(self, key: str):
        """更换监听热键；先注册成功再切换，无法解析的键名保持原热键"""
        try:
            remover = self._register_hotkey(key, self._toggle_requested)
        except (ValueError, TypeError) as exc:
            print("[热键] 无法注册 %r: %s" % (key, exc))
            return
        self._hotkey_remover()
        self._hotkey = key
        self._hotkey_remover = remover

    def set_visibility_hotkey(self, key: str):
        """更换置顶切换热键；先注册成功再切换，无法解析的键名保持原热键"""
        try:
            remover = self._register_hotkey(key, self._visibility_requested)
        except (ValueError, TypeError) as exc:
            print("[热键] 无法注册 %r: %s" % (key, exc))
            return
        self._visibility_remover()
        self._visibility_hotkey = key
        self._visibility_remover = remover

    @staticmethod
    def _register_hotkey(key: str, signal):
        """注册全局热键：按下触发一次，全部按键抬起后重置（长按不连发）。
        keyboard 的回调在其钩子线程，经信号转回主线程。"""
        return keyboard.hook(ListenController._edge_trigger(
            ListenController._scan_code_groups(key), signal))

    @staticmethod
    def _scan_code_groups(key: str) -> list[frozenset[int]]:
        """把键名解析为每组按键的扫描码集合（组合键每组一个）"""
        try:
            steps = keyboard.parse_hotkey(key)
        except ValueError:
            steps = ((keyboard.key_to_scan_codes(key),),)
        if len(steps) != 1:
            raise ValueError(f"序列热键不支持: {key!r}")
        return [frozenset(k) for k in steps[0]]

    @staticmethod
    def _edge_trigger(keys, signal):
        """生成边沿触发的事件处理器：全部按键按下时触发一次，
        按住期间的自动重复按下不触发，全部抬起后才会重新武装"""
        down_keys = set()

        def on_event(event):
            for i, codes in enumerate(keys):
                if event.scan_code in codes:
                    if event.event_type == "down":
                        if i not in down_keys:
                            down_keys.add(i)
                            if len(down_keys) == len(keys):
                                signal.emit()
                    else:
                        down_keys.discard(i)
                    break

        return on_event

    def _suspend_hotkeys(self):
        """录制新快捷键期间挂起全局热键，避免按下的键触发当前热键动作；幂等"""
        if not self._hotkeys_active:
            return
        self._hotkeys_active = False
        self._hotkey_remover()
        self._visibility_remover()
        self._hotkey_remover = lambda: None
        self._visibility_remover = lambda: None

    def _resume_hotkeys(self):
        """录制结束后恢复全局热键；幂等（防止两个录制框交叉时重复注册）。
        先注销现存钩子再注册，避免挂起期间被覆盖的钩子泄漏成双。"""
        if self._hotkeys_active:
            return
        self._hotkeys_active = True
        self._hotkey_remover()
        self._visibility_remover()
        try:
            self._hotkey_remover = self._register_hotkey(self._hotkey, self._toggle_requested)
        except (ValueError, TypeError) as exc:
            print("[热键] 无法注册 %r: %s" % (self._hotkey, exc))
        try:
            self._visibility_remover = self._register_hotkey(
                self._visibility_hotkey, self._visibility_requested)
        except (ValueError, TypeError) as exc:
            print("[热键] 无法注册 %r: %s" % (self._visibility_hotkey, exc))

    def _toggle_recording(self):
        """主线程中切换监听按钮，走完整的启停流程；比对期间忽略热键"""
        button = self.top_bar.listen_button.button
        if button.isEnabled():
            button.click()

    def _toggle_visibility(self):
        """信号触发：主界面前台/后台交替切换"""
        self._front = not self._front
        self.top_bar.window().set_topmost(self._front)

    def _on_record_finished(self, saved: bool):
        """一段录音结束后同步按钮状态；已落盘则立即触发比对"""
        if self.top_bar.listen_button.button.isChecked():
            self.top_bar.listen_button.button.click()
        if saved:
            self.top_bar.listen_button.button.setEnabled(False)
            threading.Thread(target=self._run_match, daemon=True).start()

    def _run_match(self):
        """后台比对采集音频；结果经信号回主线程"""
        try:
            result = self.matcher.match(RECORDED_WAV)
            category, probability = result if result is not None else (None, 0.0)
        except Exception:
            traceback.print_exc()
            category, probability = "", -1.0
        self.match_completed.emit(category, probability)
        self._match_busy.emit(False)

    def _on_match_busy(self, busy: bool):
        """比对期间禁止监听（模板门禁未解除时保持禁用）"""
        self.top_bar.listen_button.button.setEnabled(not busy and not self._templates_gate)

    def _on_toggled(self, checked: bool):
        """信号触发：切换按钮显示并开始/停止录音"""
        self.top_bar.listen_button.set_listening(checked)
        if checked:
            self.recorder.start()
        else:
            self.recorder.stop()

    def _on_play_clicked(self, *_):
        """信号触发：后台播放当前选中类别的基准音频"""
        category = self.top_bar.sound_indicator.current_category
        if not category or category == ANY_SOUND:
            return
        threading.Thread(target=self._play_reference, args=(category,), daemon=True).start()

    def _play_reference(self, category: str):
        """播放基准音频（阻塞至播放结束，须在后台线程调用）。
        play_volume 为音量倍率，1.0 即不做处理播放原始音频。"""
        path = REFERENCE_DIR / (_FILE_OF_CATEGORY.get(category, category) + ".wav")
        try:
            with wave.open(str(path), "rb") as f:
                frames = f.readframes(f.getnframes())
                rate, channels = f.getframerate(), f.getnchannels()
            data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            if self.play_volume != 1.0:
                data = np.clip(data * self.play_volume, -1.0, 1.0)
            if channels > 1:
                data = data.reshape(-1, channels)
            sc.default_speaker().play(data, samplerate=rate)
        except Exception:
            traceback.print_exc()

    def _on_settings_clicked(self, *_):
        """信号触发：打开设置对话框，确认后应用设置"""
        dialog = SettingsDialog(
            self.top_bar,
            max_seconds=self.recorder.max_seconds,
            hotkey=self.hotkey,
            visibility_hotkey=self.visibility_hotkey,
            play_volume=self.play_volume,
            save_weight=self.matcher.save_weight,
            categories=self.matcher.categories,
            save_caps=self.matcher.save_caps,
            on_save_files_changed=self._reload_matcher_async,
            suspend_hotkeys=self._suspend_hotkeys,
            resume_hotkeys=self._resume_hotkeys,
            templates_ready=not self._templates_gate,
        )
        dialog.rebuild_button.clicked.connect(lambda _, d=dialog: self._start_rebuild(d))
        self._rebuild_progress.connect(dialog.on_rebuild_progress)
        self._rebuild_finished.connect(dialog.on_rebuild_finished)

        def discard_dialog():
            # 对话框关闭即断开信号并销毁，避免隐藏实例与连接随打开次数累积
            self._rebuild_progress.disconnect(dialog.on_rebuild_progress)
            self._rebuild_finished.disconnect(dialog.on_rebuild_finished)
            dialog.deleteLater()

        dialog.finished.connect(discard_dialog)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.recorder.max_seconds = dialog.max_seconds
            self.play_volume = dialog.play_volume
            self.set_hotkey(dialog.hotkey)
            self.set_visibility_hotkey(dialog.visibility_hotkey)
            self.matcher.save_weight = dialog.save_weight
            self.matcher.save_caps = dialog.save_caps
            # 上限调整后清理超出上限的最旧学习音频，并后台重建特征
            removed = prune_save_dir(dialog.save_caps)
            if removed:
                print("[学习] 已删除超限最旧音频: %s" % ", ".join(removed))
            self._reload_matcher_async()
            self._save_config()

    def _reload_matcher_async(self):
        """后台重建匹配器特征（学习音频增删/设置变更后调用）"""

        def run():
            try:
                self.matcher.reload()
            except Exception:
                traceback.print_exc()

        threading.Thread(target=run, daemon=True).start()

    def _start_rebuild(self, dialog):
        """开始构建输出模板：重入直接忽略；构建期间禁用监听防止录入播放声"""
        if self._rebuilding:
            return
        self._rebuilding = True
        self.top_bar.listen_button.button.setEnabled(False)
        dialog.set_building(True)
        dialog.rebuild_status_label.setText("准备采集，请保持安静...")
        threading.Thread(target=self._run_rebuild, daemon=True).start()

    def _run_rebuild(self):
        """后台构建输出模板；无论成败都重载已写出的模板，结果经信号回主线程"""
        try:
            rebuild_templates(
                progress=lambda done, total, category:
                    self._rebuild_progress.emit(done, total, category)
            )
            ok = True
        except Exception:
            traceback.print_exc()
            ok = False
        try:
            self.matcher.reload()
        except Exception:
            traceback.print_exc()
            ok = False
        self._rebuilding = False
        self._rebuild_finished.emit(ok)

    def _on_rebuild_done(self, ok: bool):
        """输出模板构建结束：模板已就位即解除监听门禁（半途失败也按现状判断）"""
        if self._templates_gate and templates_exist():
            self._templates_gate = False
            label = self.top_bar.probability_label
            if label.text() == GATE_MESSAGE:
                label.setText("")
        if not self._templates_gate:
            self.top_bar.listen_button.button.setEnabled(True)

    @staticmethod
    def _load_config() -> dict:
        """读取持久化设置；文件缺失或损坏时回退默认值（深拷贝，嵌套 dict 不共享）"""
        try:
            stored = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            stored = {}
        config = dict(_CONFIG_DEFAULTS)
        config["save_caps"] = dict(config["save_caps"])
        for key, default in _CONFIG_DEFAULTS.items():
            if key in stored:
                config[key] = stored[key]
        return config

    def _save_config(self):
        config = {
            "max_seconds": self.recorder.max_seconds,
            "hotkey": self.hotkey,
            "visibility_hotkey": self.visibility_hotkey,
            "play_volume": self.play_volume,
            "save_caps": self.matcher.save_caps,
            "save_weight": self.matcher.save_weight,
        }
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
