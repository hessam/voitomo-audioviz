"""Per-stem spectral bands for the Resonant Bodies style. numpy + ffmpeg only.

Each video frame reads only the audio BEFORE its own time (a trailing window), so a body can never
move before its sound. Values are dB relative to the stem's own loud level, mapped to 0..1.
"""
import subprocess
from typing import Dict, List, Optional

import numpy as np

BAND_COUNT = 12
LOW_HZ = 30.0
HIGH_HZ = 12000.0
ANALYSIS_SR = 32000
WINDOW = 2048  # 64 ms trailing window
DYNAMIC_RANGE_DB = 54.0


def band_edges_hz() -> np.ndarray:
    return np.geomspace(LOW_HZ, HIGH_HZ, BAND_COUNT + 1)


def decode(path: str, sr: int = ANALYSIS_SR) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype="<f4").astype(np.float64)


def stem_bands(x: np.ndarray, fps: int, total_frames: int, sr: int = ANALYSIS_SR) -> List[List[float]]:
    """BAND_COUNT values in 0..1 per video frame, from the window that ENDS at the frame's time."""
    padded = np.concatenate([np.zeros(WINDOW), x])
    ends = (np.arange(total_frames) * sr / fps).astype(int) + WINDOW  # exclusive end in padded coordinates
    ends = np.minimum(ends, len(padded))
    freqs = np.fft.rfftfreq(WINDOW, 1.0 / sr)
    edges = band_edges_hz()
    weights = np.hanning(WINDOW)
    mags = np.zeros((total_frames, BAND_COUNT))
    selection = [(freqs >= edges[b]) & (freqs < edges[b + 1]) for b in range(BAND_COUNT)]
    chunk = 512
    for start in range(0, total_frames, chunk):
        idx = ends[start: start + chunk]
        windows = np.stack([padded[e - WINDOW: e] for e in idx]) * weights
        power = np.abs(np.fft.rfft(windows, axis=1)) ** 2
        for b, sel in enumerate(selection):
            if sel.any():
                mags[start: start + chunk, b] = np.sqrt(power[:, sel].mean(axis=1))
    reference = float(np.percentile(mags, 99))
    if reference <= 1e-9:
        return [[0.0] * BAND_COUNT for _ in range(total_frames)]
    db = 20 * np.log10(mags / reference + 1e-9)
    return np.round(np.clip((db + DYNAMIC_RANGE_DB) / DYNAMIC_RANGE_DB, 0.0, 1.0), 3).tolist()


def body_bands(stems: Dict[str, Optional[str]], master_path: str, fps: int, total_frames: int) -> Dict[str, List[List[float]]]:
    """Bands for every stem that exists. With no stems at all, the full mix under the name "mix"."""
    out: Dict[str, List[List[float]]] = {}
    for name, path in stems.items():
        if path:
            try:
                out[name] = stem_bands(decode(path), fps, total_frames)
            except Exception:
                continue
    if not out:
        out["mix"] = stem_bands(decode(master_path), fps, total_frames)
    return out
