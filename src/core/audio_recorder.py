import os
import threading
import time
import traceback
import warnings
import wave
from pathlib import Path

import numpy as np
import soundcard as sc

# 环回采集在无声段与恢复切换时会报"数据断流"，对应静音间隙而非数据损坏，屏蔽之
warnings.filterwarnings("ignore", message="data discontinuity in recording")

from src.utils.app_paths import DATA_DIR

SAVE_DIR = DATA_DIR / "collected_audio"
AUDIO_NAME = "collected_audio.wav"
SAMPLE_RATE = 48000
CHANNELS = 2
MAX_SECONDS = 5


class LoopbackRecorder:
    """环回采集扬声器输出，固定保存为一段 wav，新录音自动覆盖"""

    def __init__(self, save_dir: Path = SAVE_DIR, max_seconds: int = MAX_SECONDS,
                 on_finished=None):
        self._save_dir = Path(save_dir)
        self._audio_path = self._save_dir / AUDIO_NAME
        self._max_seconds = max_seconds
        self._on_finished = on_finished
        self._stop_event = threading.Event()
        self._session = 0
        self._thread: threading.Thread | None = None

    @property
    def recording(self) -> bool:
        # 已请求停止但尚未退出的残留线程不算在录，否则 start() 会被它挡住
        thread = self._thread
        return thread is not None and thread.is_alive() and not self._stop_event.is_set()

    @property
    def max_seconds(self) -> int:
        return self._max_seconds

    @max_seconds.setter
    def max_seconds(self, value: int):
        self._max_seconds = value

    def start(self):
        """开始一段录音"""
        if self.recording:
            return
        self._stop_event.clear()
        self._session += 1
        session = self._session
        thread = threading.Thread(target=self._record, args=(session,), daemon=True)
        self._thread = thread
        thread.start()

    def stop(self):
        """停止录音，等待本段落盘完成（最多1秒，防止无声阻塞卡住界面）"""
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        self._stop_event.set()
        thread.join(timeout=1.0)

    def _record(self, session: int):
        chunks = []
        try:
            deadline = time.monotonic() + self._max_seconds
            microphone = sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True)
            with microphone.recorder(samplerate=SAMPLE_RATE, channels=CHANNELS) as recorder:
                while not self._stop_event.is_set() and time.monotonic() < deadline:
                    chunks.append(recorder.record(numframes=2048))
        except Exception:
            # 设备异常时线程也不能无声死亡，否则收尾回调不会执行、按钮状态卡死
            traceback.print_exc()
        # 会话已过期（停止超时后又被重新开始）则丢弃，避免陈旧线程补写文件
        if self._session == session:
            saved = bool(chunks)
            if saved:
                self._save(np.concatenate(chunks))
            if self._on_finished is not None:
                self._on_finished(saved)

    def _save(self, data: np.ndarray):
        self._save_dir.mkdir(parents=True, exist_ok=True)
        pcm = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
        # 先写临时文件再原子替换，避免保存/比对读侧读到写了一半的音频
        temp_path = self._audio_path.with_suffix(".tmp")
        with wave.open(str(temp_path), "wb") as f:
            f.setnchannels(data.shape[1])
            f.setsampwidth(2)
            f.setframerate(SAMPLE_RATE)
            f.writeframes(pcm.tobytes())
        os.replace(temp_path, self._audio_path)
