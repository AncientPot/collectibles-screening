import json
import threading
import time
import wave
from pathlib import Path

import librosa
import librosa.feature
import numpy as np
import soundcard as sc
from fastdtw import fastdtw
from scipy.signal import butter, sosfiltfilt

from src.core.audio_recorder import AUDIO_NAME, SAVE_DIR

from src.utils.app_paths import DATA_DIR

REFERENCE_DIR = DATA_DIR / "original_ audio"
TEMPLATES_DIR = DATA_DIR / "audio_cache" / "templates"
USER_SAVE_DIR = DATA_DIR / "save"
CACHE_DIR = DATA_DIR / "audio_cache"
RECORDED_WAV = SAVE_DIR / AUDIO_NAME

SAMPLE_RATE = 22050
N_MFCC = 20
BAND = (150, 8000)
SCORE_TEMPERATURE = 0.3
SAVE_PENALTY = 0.5           # save 学习模板的距离惩罚：基准模板权重最大，save 仅微调
CROP_PAD_SECONDS = 0.05
EVENT_GAP_SECONDS = 0.15   # 事件间的最小静音间隔，小于它视为同一事件
EVENT_NOISE_RATIO = 0.25   # 事件峰值低于最响事件的该比例视为噪声瞬态（实测杂音≤6%，真实≥59%）
SILENCE_RMS = 1e-4         # 整段能量低于此值视为真正的静音（1 LSB≈3e-5，轻录音≥1e-3）

# 基准文件名与 audio_map.json 类别键不一致时的映射
FILE_ALIASES = {"木制品沉默声": "木质品沉闷声"}

_PARAMS = {"sr": SAMPLE_RATE, "n_mfcc": N_MFCC, "band": list(BAND), "pipeline": 8}
_SOS = butter(4, BAND, btype="band", fs=SAMPLE_RATE, output="sos")


class AudioMatcher:
    """采集音频与基准音效的相似度比对：带通滤波→事件截取→MFCC→CMVN→DTW。
    基准特征按（文件名+修改时间+参数）缓存到磁盘，避免重复计算。"""

    def __init__(self, reference_dir: Path = REFERENCE_DIR, cache_dir: Path = CACHE_DIR):
        self._reference_dir = Path(reference_dir)
        self._cache_dir = Path(cache_dir)
        self._features = self._load_features()

    @property
    def categories(self) -> list[str]:
        return list(self._features)

    def reload(self):
        """重新扫描全部模板源并加载（保底模板重建后调用）"""
        self._features = self._load_features()

    def match(self, wav_path: Path) -> tuple[str, float] | None:
        """返回（最相似的类别, 置信概率）；未检测到有效声音时返回 None。
        采集可能包含多个事件（拿起+放下），物品类别由拿起声（首个事件）
        决定，放下声是落地音效、不参与类别判定。每类基准有首事件与全跨度
        两个模板，取距离更近者。"""
        y = self._load(Path(wav_path))
        events = self._split_events(y)
        if not events:
            return None
        query = self._mfcc(self._select_event(events))
        dists = {}
        for category, templates in self._features.items():
            base = min((self._distance(query, t) for t in templates["base"]), default=float("inf"))
            save = min((self._distance(query, t) for t in templates["save"]), default=float("inf"))
            # 基准模板权重最大；save 仅微调（带距离惩罚，须显著更近才能影响结论）
            dists[category] = min(base, save + SAVE_PENALTY)
        best = min(dists, key=lambda c: dists[c])
        # 概率 = 各类别相对最优类别的距离差做 softmax，尺度无关的置信度
        best_distance = dists[best]
        weights = {c: np.exp(-(d - best_distance) / SCORE_TEMPERATURE) for c, d in dists.items()}
        total = sum(weights.values())
        return best, float(weights[best] / total)

    @staticmethod
    def _distance(query: np.ndarray, reference: np.ndarray) -> float:
        cost, _ = fastdtw(query, reference)
        return cost / (len(query) + len(reference))

    def _load_features(self) -> dict[str, dict[str, list[np.ndarray]]]:
        entries = [(path, self._category_of(path), "base")
                   for path in sorted(REFERENCE_DIR.glob("*.wav"))]
        # 保底模板：与基准同信道的追加样本（无哈希后缀，文件名即类别）
        entries += [(path, path.stem, "base") for path in sorted(TEMPLATES_DIR.glob("*.wav"))]
        # 学习数据：用户保存在 data/save 的采集（类别_哈希.wav），仅微调
        entries += [
            (path, path.stem.rsplit("_", 1)[0], "save")
            for path in sorted(USER_SAVE_DIR.glob("*.wav"))
            if "_" in path.stem
        ]
        if not entries:
            raise FileNotFoundError(f"基准音频目录为空: {REFERENCE_DIR}")
        stamps = {str(path): path.stat().st_mtime for path, _, _ in entries}
        cached = self._read_cache(stamps)
        if cached is not None:
            return cached
        features: dict[str, dict[str, list[np.ndarray]]] = {}
        for path, category, kind in entries:
            try:
                features.setdefault(category, {"base": [], "save": []})[kind].extend(
                    self._reference_feature(path)
                )
            except (ValueError, RuntimeError, OSError) as exc:
                # 无有效声音、解码失败、不可读等坏文件只跳过，不能让匹配器启动崩溃
                print(f"[基准] 跳过无效音频 {path.name}: {exc}")
        self._write_cache(features, stamps)
        return features

    def _reference_feature(self, path: Path) -> list[np.ndarray]:
        """基准模板：首个事件（与查询路径对称，保证自匹配距离为 0）
        加全活跃跨度（信息更全的备选模板）"""
        y = self._load(path)
        events = self._split_events(y)
        if not events:
            raise ValueError(f"基准音频无有效声音: {path}")
        templates = [self._mfcc(self._select_event(events))]
        span = self._full_span(y)
        if span is not None and len(span) != len(events[0]):
            templates.append(self._mfcc(span))
        return templates

    @staticmethod
    def _full_span(y: np.ndarray) -> np.ndarray | None:
        """从首个活跃帧到最后活跃帧的整体跨度"""
        rms = librosa.feature.rms(y=y, frame_length=512, hop_length=256)[0]
        median = np.median(rms)
        threshold = median + 2 * np.median(np.abs(rms - median))
        active = rms > threshold
        if not active.any():
            return None
        i0 = int(np.argmax(active))
        i1 = len(active) - int(np.argmax(active[::-1])) - 1
        pad = int(CROP_PAD_SECONDS * SAMPLE_RATE / 256)
        s0 = max(0, (i0 - pad) * 256)
        s1 = min(len(y), (i1 + 1 + pad) * 256)
        return y[s0:s1]

    @staticmethod
    def _category_of(path: Path) -> str:
        return FILE_ALIASES.get(path.stem, path.stem)

    def _read_cache(self, stamps: dict[str, float]) -> dict[str, dict[str, list[np.ndarray]]] | None:
        npz_path = self._cache_dir / "reference_features.npz"
        meta_path = self._cache_dir / "reference_features.json"
        if not (npz_path.exists() and meta_path.exists()):
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("params") != _PARAMS or meta.get("files") != stamps:
            return None
        grouped: dict[str, dict[str, list[np.ndarray]]] = {}
        with np.load(npz_path) as data:
            for name in data.files:
                category, kind, index = name.rsplit("|", 2)
                kinds = grouped.setdefault(category, {"base": [], "save": []})
                slots = kinds[kind]
                slots.insert(int(index), data[name])
        return grouped

    def _write_cache(self, features: dict[str, dict[str, list[np.ndarray]]], stamps: dict[str, float]):
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        flat = {f"{category}|{kind}|{i}": template
                for category, kinds in features.items()
                for kind, templates in kinds.items()
                for i, template in enumerate(templates)}
        np.savez(self._cache_dir / "reference_features.npz", **flat)
        meta = {"params": _PARAMS, "files": stamps}
        (self._cache_dir / "reference_features.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _load(path: Path) -> np.ndarray:
        y, _ = librosa.load(str(path), sr=SAMPLE_RATE, mono=True)
        return sosfiltfilt(_SOS, y)

    @staticmethod
    def _select_event(events: list[np.ndarray]) -> np.ndarray:
        """选取首个有效事件：跳过能量远低于最响事件的噪声瞬态
        （如录音触发时的干扰声），返回第一个达到阈值的真实事件"""
        peaks = [float(np.sqrt((event ** 2).mean())) for event in events]
        loudest = max(peaks)
        for event, peak in zip(events, peaks):
            if peak >= loudest * EVENT_NOISE_RATIO:
                return event
        return events[0]

    @staticmethod
    def _split_events(y: np.ndarray) -> list[np.ndarray]:
        """按静音间隔把采集切分为独立事件（如拿起与放下），过滤过短活跃区"""
        rms = librosa.feature.rms(y=y, frame_length=512, hop_length=256)[0]
        median = np.median(rms)
        threshold = median + 2 * np.median(np.abs(rms - median))
        active = rms > threshold
        gap_frames = int(EVENT_GAP_SECONDS * SAMPLE_RATE / 256)
        pad = int(CROP_PAD_SECONDS * SAMPLE_RATE / 256)
        regions: list[tuple[int, int]] = []
        start, gap = None, 0
        for i, is_active in enumerate(active):
            if is_active:
                if start is None:
                    start = i
                gap = 0
            elif start is not None:
                gap += 1
                if gap >= gap_frames:
                    regions.append((start, i - gap))
                    start, gap = None, 0
        if start is not None:
            regions.append((start, len(active) - 1))
        events = []
        for s, e in regions:
            # 以填充后的窗口长度为过滤条件，短促声（如饰品细碎声）也能形成紧致模板
            s0 = max(0, (s - pad) * 256)
            s1 = min(len(y), (e + 1 + pad) * 256)
            if s1 - s0 >= SAMPLE_RATE // 10:
                events.append(y[s0:s1])
        if not events and rms.max() > SILENCE_RMS:
            # 切不出可用事件但整段确有声响（连续型或极短促的声音）：整段作为一个事件
            return [y]
        return events

    @staticmethod
    def _mfcc(y: np.ndarray) -> np.ndarray:
        mf = librosa.feature.mfcc(y=y, sr=SAMPLE_RATE, n_mfcc=N_MFCC)
        # 倒谱均值归一化（CMVN），抹平电平与信道染色差异
        mf = (mf - mf.mean(axis=1, keepdims=True)) / (mf.std(axis=1, keepdims=True) + 1e-9)
        return mf.T


def rebuild_templates(progress=None) -> list[str]:
    """逐类播放基准并环回采集，重建保底模板（data/audio_cache/templates/类别.wav）。
    采集期间请保持安静，避免其他程序播放声音。progress(序号, 总数, 类别名) 上报进度。"""
    wavs = sorted(REFERENCE_DIR.glob("*.wav"))
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    built = []
    for index, wav in enumerate(wavs, 1):
        category = FILE_ALIASES.get(wav.stem, wav.stem)
        if progress is not None:
            progress(index, len(wavs), category)
        with wave.open(str(wav), "rb") as f:
            frames = f.readframes(f.getnframes())
            rate, channels = f.getframerate(), f.getnchannels()
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        peak = float(np.max(np.abs(data)))
        if peak > 0:
            data = data * (0.5 / peak)  # 固定归一化响度，与用户播放音量设置无关
        if channels > 1:
            data = data.reshape(-1, channels)
        microphone = sc.get_microphone(id=str(sc.default_speaker().name), include_loopback=True)
        with microphone.recorder(samplerate=48000, channels=2) as recorder:
            threading.Thread(
                target=lambda: (time.sleep(0.3), sc.default_speaker().play(data, samplerate=rate)),
                daemon=True,
            ).start()
            captured = recorder.record(numframes=int(48000 * 1.2))
        with wave.open(str(TEMPLATES_DIR / f"{category}.wav"), "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(48000)
            f.writeframes((np.clip(captured, -1, 1) * 32767).astype(np.int16).tobytes())
        built.append(category)
        time.sleep(0.4)
    return built
