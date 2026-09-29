import json
import threading
import time
import wave
import zipfile
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
BAND = (70, 8000)
SCORE_TEMPERATURE = 0.3
# 三层模板权重：保底模板惩罚0（主导），原始基准固定次要惩罚，学习数据权重可调
ORIGINAL_PENALTY = 0.2
SAVE_PENALTY_MAX = 1.0     # 学习权重为0时的距离惩罚上限
DEFAULT_SAVE_CAP = 5       # 每类学习音频的默认上限
CROP_PAD_SECONDS = 0.05
EVENT_GAP_SECONDS = 0.15   # 事件间的最小静音间隔，小于它视为同一事件
EVENT_NOISE_RATIO = 0.25   # 事件峰值低于最响事件的该比例视为噪声瞬态（实测杂音≤6%，真实≥59%）
SILENCE_RMS = 1e-4         # 整段能量低于此值视为真正的静音（1 LSB≈3e-5，轻录音≥1e-3）

# 基准文件名与 audio_map.json 类别键不一致时的映射
FILE_ALIASES = {"木制品沉默声": "木质品沉闷声"}

_PARAMS = {"sr": SAMPLE_RATE, "n_mfcc": N_MFCC, "band": list(BAND), "pipeline": 9}
_SOS = butter(4, BAND, btype="band", fs=SAMPLE_RATE, output="sos")


class AudioMatcher:
    """采集音频与基准音效的相似度比对：带通滤波→事件截取→MFCC→CMVN→DTW。
    基准特征按（文件名+修改时间+参数）缓存到磁盘，避免重复计算。"""

    def __init__(self, reference_dir: Path = REFERENCE_DIR, cache_dir: Path = CACHE_DIR,
                 save_caps: dict[str, int] | None = None,
                 save_weight: float = 0.5):
        self._reference_dir = Path(reference_dir)
        self._cache_dir = Path(cache_dir)
        self.save_caps: dict[str, int] = dict(save_caps or {})
        self.save_weight = min(1.0, max(0.0, float(save_weight)))
        self._reload_lock = threading.Lock()
        self._features = self._load_features()

    @property
    def categories(self) -> list[str]:
        return list(self._features)

    def reload(self):
        """重新扫描全部模板源并加载。加锁串行化：保存/设置/删除/重建等多处
        会并发触发重载，无锁时同时写缓存会产生写竞争甚至留下损坏文件。"""
        with self._reload_lock:
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
        for category, tiers in self._features.items():
            inf = float("inf")
            # 三层加权：保底模板(0) < 原始基准(+次要惩罚) < 学习数据(+可调惩罚)
            candidates = [
                min((self._distance(query, t) for t in tiers["templates"]), default=inf),
                min((self._distance(query, t) for t in tiers["originals"]),
                    default=inf) + ORIGINAL_PENALTY,
            ]
            if self.save_weight > 0 and tiers["save"]:
                penalty = SAVE_PENALTY_MAX * (1.0 - self.save_weight)
                candidates.append(
                    min((self._distance(query, t) for t in tiers["save"]), default=inf) + penalty
                )
            dists[category] = min(candidates)
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
        # 三层模板：保底模板主导，原始基准次要，学习数据（每类取最新N条）权重可调
        original_files: list[Path] = sorted(REFERENCE_DIR.glob("*.wav"))
        entries = [(path, self._category_of(path), "originals") for path in original_files]
        template_files: list[Path] = sorted(TEMPLATES_DIR.glob("*.wav"))
        entries += [(path, path.stem, "templates") for path in template_files]
        # 学习数据：用户保存在 data/save/类别/ 下的采集（每类取最新N条），仅微调
        save_files: list[Path] = sorted(USER_SAVE_DIR.glob("*/*.wav"))
        save_entries = [(path, path.parent.name, "save") for path in save_files]
        entries += self._cap_save_entries(save_entries)
        if not entries:
            raise FileNotFoundError(f"基准音频目录为空: {REFERENCE_DIR}")
        stamps = {str(path): path.stat().st_mtime for path, _, _ in entries}
        cached = self._read_cache(stamps)
        if cached is not None:
            return cached
        features: dict[str, dict[str, list[np.ndarray]]] = {}
        for path, category, kind in entries:
            try:
                tiers = features.setdefault(category, {"originals": [], "templates": [], "save": []})
                tiers[kind].extend(self._reference_feature(path))
            except (ValueError, RuntimeError, OSError) as exc:
                # 无有效声音、解码失败、不可读等坏文件只跳过，不能让匹配器启动崩溃
                print(f"[基准] 跳过无效音频 {path.name}: {exc}")
        self._write_cache(features, stamps)
        return features

    def _cap_save_entries(self, entries: list[tuple]) -> list[tuple]:
        """按各类别自己的上限只保留最新的学习音频（每条音频会产生
        首事件+全跨度两个模板），避免某类攒太多后凭数量优势压过其他类别"""
        grouped: dict[str, list[tuple]] = {}
        for entry in sorted(entries, key=lambda e: e[0].stat().st_mtime):
            grouped.setdefault(entry[1], []).append(entry)
        capped = []
        for category, items in grouped.items():
            cap = self.save_caps.get(category, DEFAULT_SAVE_CAP)
            if cap > 0:
                capped.extend(items[-cap:])
        return sorted(capped)

    def _reference_feature(self, path: Path) -> list[np.ndarray]:
        """基准模板：首个事件（与查询路径对称，保证自匹配距离为 0）
        加全活跃跨度（信息更全的备选模板）"""
        y = self._load(path)
        events = self._split_events(y)
        if not events:
            raise ValueError(f"基准音频无有效声音: {path}")
        selected = self._select_event(events)
        templates = [self._mfcc(selected)]
        span = self._full_span(y)
        if span is not None and len(span) != len(selected):
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

    def _current_params(self) -> dict:
        return {**_PARAMS, "save_caps": self.save_caps}

    def _read_cache(self, stamps: dict[str, float]) -> dict[str, dict[str, list[np.ndarray]]] | None:
        npz_path = self._cache_dir / "reference_features.npz"
        meta_path = self._cache_dir / "reference_features.json"
        if not (npz_path.exists() and meta_path.exists()):
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if meta.get("params") != self._current_params() or meta.get("files") != stamps:
            return None
        grouped: dict[str, dict[str, list[np.ndarray]]] = {}
        try:
            with np.load(npz_path) as data:
                for name in data.files:
                    category, kind, index = name.rsplit("|", 2)
                    tiers = grouped.setdefault(
                        category, {"originals": [], "templates": [], "save": []})
                    tiers[kind].insert(int(index), data[name])
        except (OSError, ValueError, EOFError, zipfile.BadZipFile):
            # 损坏的缓存视为未命中，走重建而不是让启动崩溃
            return None
        return grouped

    def _write_cache(self, features: dict[str, dict[str, list[np.ndarray]]], stamps: dict[str, float]):
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        flat = {f"{category}|{kind}|{i}": template
                for category, tiers in features.items()
                for kind, templates in tiers.items()
                for i, template in enumerate(templates)}
        np.savez(self._cache_dir / "reference_features.npz", **flat)
        meta = {"params": self._current_params(), "files": stamps}
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


def prune_save_dir(caps: dict[str, int]) -> list[str]:
    """按各类别上限清理 data/save（按类别子目录存储），
    超出上限时删除最旧的音频，返回被删文件名"""
    files: list[Path] = sorted(USER_SAVE_DIR.glob("*/*.wav"))
    grouped: dict[str, list[Path]] = {}
    for path in files:
        grouped.setdefault(path.parent.name, []).append(path)
    removed = []
    for category, paths in grouped.items():
        cap = max(0, int(caps.get(category, DEFAULT_SAVE_CAP)))
        excess = len(paths) - cap
        if excess > 0:
            for path in sorted(paths, key=lambda p: p.stat().st_mtime)[:excess]:
                path.unlink()
                removed.append(path.name)
    return removed


def rebuild_templates(progress=None) -> list[str]:
    """逐类播放基准并环回采集，重建保底模板（data/audio_cache/templates/类别.wav）。
    采集期间请保持安静，避免其他程序播放声音。progress(序号, 总数, 类别名) 上报进度。"""
    wavs: list[Path] = sorted(REFERENCE_DIR.glob("*.wav"))
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

            def delayed_play():
                time.sleep(0.3)
                sc.default_speaker().play(data, samplerate=rate)

            threading.Thread(target=delayed_play, daemon=True).start()
            captured: np.ndarray = recorder.record(numframes=int(48000 * 1.2))
        with wave.open(str(TEMPLATES_DIR / f"{category}.wav"), "wb") as f:
            f.setnchannels(2)
            f.setsampwidth(2)
            f.setframerate(48000)
            samples: np.ndarray = np.clip(captured, -1.0, 1.0)
            f.writeframes((samples * 32767).astype(np.int16).tobytes())
        built.append(category)
        time.sleep(0.4)
    return built
