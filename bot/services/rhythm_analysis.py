"""Hit, meter and riff-cycle analysis. numpy + ffmpeg only, no model downloads.

These are measured estimates with explicit confidence. Every function returns None / an
empty list when the evidence is weak, so a style hides the layer instead of faking it.
"""
import math
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

from contracts.manifest import OnsetEvent, RiffCycle

ANALYSIS_SR = 32000
N_FFT = 1024
HOP = 160  # 5 ms between spectra
# A hit is labelled by where the new energy sits on a log-frequency axis (candidate rule,
# to be confirmed on real fixtures): below KICK_MAX_HZ kick, below SNARE_MAX_HZ snare, else cymbal.
KICK_MAX_HZ = 180.0
SNARE_MAX_HZ = 3500.0
MIN_ONSET_GAP_S = 0.04
# The spectral-flux peak lands 7-14 ms BEFORE a synthetic hit (the window sees it early), so the
# stamp is moved later by this much to guarantee a response never shows before the sound.
# Calibrated on synthetic kicks, snares and cymbals (tests/test_rhythm_analysis.py); slower
# real attacks need re-checking on fixtures.
ONSET_OFFSET_S = 0.014


def decode_mono(path: str, sr: int = ANALYSIS_SR) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


@dataclass
class OnsetAnalysis:
    times: List[float]  # seconds
    strengths: List[float]  # 0..1
    kinds: List[str]

    def events(self, fps: int, total_frames: int) -> List[OnsetEvent]:
        out: List[OnsetEvent] = []
        last = -1
        for t, s, k in zip(self.times, self.strengths, self.kinds):
            frame = max(0, math.ceil(t * fps))
            if frame >= total_frames:
                continue
            if frame == last:  # one event per frame; the stronger one wins
                if s > out[-1].strength:
                    out[-1] = OnsetEvent(frame=frame, strength=round(s, 3), kind=k)
                continue
            out.append(OnsetEvent(frame=frame, strength=round(s, 3), kind=k))
            last = frame
        return out


def _flux(x: np.ndarray, sr: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Spectral flux per spectrum, the power spectra, and the frequency of each bin."""
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / sr)
    if len(x) < N_FFT + HOP:
        return np.zeros(0), np.zeros((0, len(freqs))), freqs
    windows = np.lib.stride_tricks.sliding_window_view(x, N_FFT)[::HOP]
    mag = np.abs(np.fft.rfft(windows * np.hanning(N_FFT), axis=1))
    logm = np.log1p(100.0 * mag)
    rise = np.maximum(0.0, np.diff(logm, axis=0, prepend=logm[:1]))
    rise[:, freqs < 30.0] = 0.0
    return rise.sum(axis=1), mag ** 2, freqs


def _kind(power: np.ndarray, peak: int, freqs: np.ndarray) -> str:
    """Label a hit by where its NEW power sits: after the hit minus just before it."""
    after = power[peak: peak + 5].mean(axis=0)
    before = power[max(0, peak - 5): max(1, peak - 1)].mean(axis=0)
    added = np.maximum(0.0, after - before)
    usable = freqs >= 30.0
    if added[usable].sum() <= 0:
        return "other"
    centroid = float(np.exp((added[usable] * np.log(freqs[usable])).sum() / added[usable].sum()))
    return "kick" if centroid < KICK_MAX_HZ else "snare" if centroid < SNARE_MAX_HZ else "cymbal"


def detect_onsets(x: np.ndarray, sr: int = ANALYSIS_SR, sensitivity: float = 1.0) -> OnsetAnalysis:
    """Find hit times with spectral flux and label each by the band that rose most."""
    total, power, freqs = _flux(x, sr)
    if len(total) == 0 or total.max() <= 0:
        return OnsetAnalysis([], [], [])
    rate = sr / HOP
    local = np.convolve(total, np.ones(int(rate * 0.5)) / int(rate * 0.5), mode="same")
    threshold = local + (0.6 / sensitivity) * total.std()
    radius = max(1, int(rate * 0.03))
    peaks: List[int] = []
    for i in range(radius, len(total) - radius):
        w = total[i - radius: i + radius + 1]
        if total[i] > threshold[i] and total[i] == w.max() and total[i] > 0:
            if peaks and (i - peaks[-1]) / rate < MIN_ONSET_GAP_S:
                if total[i] > total[peaks[-1]]:
                    peaks[-1] = i
                continue
            peaks.append(i)
    if not peaks:
        return OnsetAnalysis([], [], [])
    peak_max = max(total[p] for p in peaks)
    times, strengths, kinds = [], [], []
    for p in peaks:
        # Hit stamp: centre of the analysis window plus the calibrated offset.
        times.append(max(0.0, (p * HOP + N_FFT / 2) / sr + ONSET_OFFSET_S))
        strengths.append(float(total[p] / peak_max))
        kinds.append(_kind(power, p, freqs))
    return OnsetAnalysis(times, strengths, kinds)


def _beat_positions(times: Sequence[float], beat_times: Sequence[float]) -> np.ndarray:
    """Beat-relative position (beat index + fraction) of each time; NaN outside the grid."""
    b = np.asarray(beat_times, dtype=float)
    t = np.asarray(times, dtype=float)
    idx = np.searchsorted(b, t, side="right") - 1
    pos = np.full(len(t), np.nan)
    ok = (idx >= 0) & (idx < len(b) - 1)
    span = b[idx[ok] + 1] - b[idx[ok]]
    pos[ok] = idx[ok] + (t[ok] - b[idx[ok]]) / np.where(span > 0, span, 1.0)
    return pos


@dataclass
class MeterEstimate:
    beats_per_bar: int
    downbeat_phase: int  # beat index modulo beats_per_bar where the bar starts
    confidence: float


def estimate_meter(beat_times: Sequence[float], onset_times: Sequence[float],
                   onset_strengths: Sequence[float], candidates: Sequence[int] = range(2, 13),
                   min_confidence: float = 0.15) -> Optional[MeterEstimate]:
    """Estimate beats per bar from the repeating accent pattern, or None if unclear."""
    if len(beat_times) < 16 or len(onset_times) < 8:
        return None
    pos = _beat_positions(onset_times, beat_times)
    strengths = np.asarray(onset_strengths, dtype=float)
    accent = np.zeros(len(beat_times))
    for p, s in zip(pos, strengths):
        if np.isnan(p):
            continue
        nearest = int(round(p))
        if abs(p - nearest) <= 0.25 and 0 <= nearest < len(accent):
            accent[nearest] += s
    accent = accent - accent.mean()
    denom = float(np.dot(accent, accent))
    if denom <= 0:
        return None
    scores = {}
    for lag in candidates:
        if len(accent) < 4 * lag:
            continue
        scores[lag] = float(np.dot(accent[:-lag], accent[lag:]) / denom)
    if not scores:
        return None
    best = max(scores.values())
    if best <= 0:
        return None
    # Prefer the smallest period whose score is close to the best (4 over 8, 7 over 14).
    lag = min(k for k, v in scores.items() if v >= 0.9 * best)
    others = [v for k, v in scores.items() if k % lag != 0 and lag % k != 0]
    runner_up = max(others) if others else 0.0
    confidence = max(0.0, min(1.0, (scores[lag] - max(runner_up, 0.0)) / max(scores[lag], 1e-9)))
    if confidence < min_confidence or scores[lag] < 0.1:
        return None
    folded = np.array([accent[i::lag].mean() for i in range(lag)])
    return MeterEstimate(beats_per_bar=lag, downbeat_phase=int(np.argmax(folded)), confidence=round(confidence, 3))


def estimate_riff_cycle(beat_times: Sequence[float], onset_times: Sequence[float],
                        onset_strengths: Sequence[float], fps: int, steps_per_beat: int = 4,
                        min_length: int = 5, max_length: int = 64, min_repeats: int = 3,
                        min_confidence: float = 0.3) -> Optional[RiffCycle]:
    """Find the shortest step pattern that repeats (for example 23 sixteenth notes).

    Cycles of one beat or less are ignored: they only repeat the beat ring.
    """
    if len(beat_times) < 8 or len(onset_times) < 8:
        return None
    pos = _beat_positions(onset_times, beat_times)
    ok = ~np.isnan(pos)
    steps = np.round(pos[ok] * steps_per_beat).astype(int)
    if len(steps) == 0:
        return None
    grid = np.zeros(steps.max() + 1)
    for s, w in zip(steps, np.asarray(onset_strengths)[ok]):
        grid[s] = max(grid[s], w)
    grid = grid - grid.mean()
    denom = float(np.dot(grid, grid))
    if denom <= 0:
        return None
    scores = {}
    for lag in range(min_length, max_length + 1):
        if len(grid) < min_repeats * lag:
            break
        scores[lag] = float(np.dot(grid[:-lag], grid[lag:]) / denom)
    if not scores:
        return None
    best = max(scores.values())
    if best <= 0:
        return None
    lag = min(k for k, v in scores.items() if v >= 0.9 * best)
    typical = float(np.median(list(scores.values())))
    confidence = max(0.0, min(1.0, (scores[lag] - typical) / max(1e-9, 1.0 - typical)))
    if confidence < min_confidence:
        return None
    seconds_per_beat = float(np.median(np.diff(beat_times)))
    return RiffCycle(lengthSteps=lag, stepFrames=round(seconds_per_beat * fps / steps_per_beat, 4),
                     confidence=round(confidence, 3))
