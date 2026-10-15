"""Monophonic pitch and note events with the YIN method. numpy + ffmpeg only.

Honest limits: one pitch at a time (the strongest periodicity), so chords give one note or none;
heavy distortion and drums bleeding into a master mix lower the confidence or drop frames.
Frames and notes with weak periodicity are dropped, never guessed.
"""
import math
import subprocess
from typing import List, Optional

import numpy as np

from contracts.manifest import NoteEvent

PITCH_SR = 16000
WINDOW = 1024  # 64 ms; the longest period it can see is WINDOW/2 samples (31 Hz)
HOP = 160  # 10 ms
HALF = WINDOW // 2
YIN_THRESHOLD = 0.15
MIN_VOICED_CONFIDENCE = 0.7
MIN_NOTE_SECONDS = 0.06
NOTE_SPLIT_SEMITONES = 0.6
SILENCE_FRACTION = 0.05  # frames quieter than this fraction of the loud frames are skipped


def decode_band(path: str, low_hz: float, high_hz: float, sr: int = PITCH_SR) -> np.ndarray:
    filt = f"highpass=f={low_hz},lowpass=f={high_hz}"
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-af", filt, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def track_pitch(x: np.ndarray, sr: int = PITCH_SR, min_hz: float = 32.0, max_hz: float = 800.0):
    """Per 10 ms frame: (pitch Hz or 0 when unvoiced, confidence 0..1, rms)."""
    if len(x) < WINDOW + HOP:
        return np.zeros(0), np.zeros(0), np.zeros(0)
    frames = np.lib.stride_tricks.sliding_window_view(x, WINDOW)[::HOP]
    count = len(frames)
    tau_min = max(2, int(sr / max_hz))
    tau_max = min(HALF - 1, int(sr / min_hz))
    pitch = np.zeros(count)
    confidence = np.zeros(count)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    chunk = 400
    for start in range(0, count, chunk):
        block = frames[start: start + chunk]
        head = block[:, :HALF]
        a = np.fft.rfft(head, n=2 * WINDOW, axis=1)
        b = np.fft.rfft(block, n=2 * WINDOW, axis=1)
        corr = np.fft.irfft(np.conj(a) * b, axis=1)[:, :HALF]
        energy = np.cumsum(block ** 2, axis=1)
        e0 = energy[:, HALF - 1]
        # Sum of squares over [tau, tau + HALF)
        e_tau = np.stack([energy[:, min(WINDOW - 1, t + HALF - 1)] - (energy[:, t - 1] if t > 0 else 0) for t in range(HALF)], axis=1)
        diff = e0[:, None] + e_tau - 2 * corr
        diff[:, 0] = 0
        running = np.cumsum(diff, axis=1)
        cmnd = np.ones_like(diff)
        taus = np.arange(1, HALF)
        cmnd[:, 1:] = diff[:, 1:] * taus / np.maximum(running[:, 1:], 1e-12)
        for i in range(len(block)):
            c = cmnd[i]
            window = c[tau_min:tau_max + 1]
            below = np.where(window < YIN_THRESHOLD)[0]
            if len(below):
                k = below[0]
                while k + 1 < len(window) and window[k + 1] < window[k]:
                    k += 1
            else:
                k = int(np.argmin(window))
            tau = tau_min + k
            value = float(c[tau])
            if 1 <= tau < HALF - 1:  # parabolic refinement
                y0, y1, y2 = c[tau - 1], c[tau], c[tau + 1]
                denom = y0 - 2 * y1 + y2
                shift = 0.5 * (y0 - y2) / denom if abs(denom) > 1e-12 else 0.0
                tau_f = tau + max(-1.0, min(1.0, shift))
            else:
                tau_f = float(tau)
            conf = max(0.0, 1.0 - value)
            confidence[start + i] = conf
            pitch[start + i] = sr / tau_f if conf >= MIN_VOICED_CONFIDENCE else 0.0
    return pitch, confidence, rms


def detect_notes(x: np.ndarray, fps: int, total_frames: int, stem: str = "bass", sr: int = PITCH_SR,
                 min_hz: float = 32.0, max_hz: float = 800.0) -> List[NoteEvent]:
    """Group voiced frames with a steady pitch into notes (frame times are video frames, never early)."""
    pitch, confidence, rms = track_pitch(x, sr, min_hz, max_hz)
    if len(pitch) == 0:
        return []
    loud = np.percentile(rms, 95)
    voiced = (pitch > 0) & (rms > SILENCE_FRACTION * loud)
    hop_s = HOP / sr
    notes: List[NoteEvent] = []
    i = 0
    while i < len(pitch):
        if not voiced[i]:
            i += 1
            continue
        j = i
        reference = pitch[i]
        while (j + 1 < len(pitch) and voiced[j + 1] and
               abs(12 * math.log2(pitch[j + 1] / reference)) < NOTE_SPLIT_SEMITONES):
            j += 1
        if (j - i + 1) * hop_s >= MIN_NOTE_SECONDS:
            seg = slice(i, j + 1)
            start_s = i * hop_s + WINDOW / sr  # the window must be full before its pitch is real
            end_s = (j + 1) * hop_s + WINDOW / sr
            start = max(0, math.ceil(start_s * fps))
            end = min(total_frames, max(start + 1, math.ceil(end_s * fps)))
            if start < total_frames:
                notes.append(NoteEvent(startFrame=start, endFrame=end, pitchHz=round(float(np.median(pitch[seg])), 2),
                                       stem=stem, confidence=round(float(confidence[seg].mean()), 3)))
        i = j + 1
    return notes


def note_name(pitch_hz: float) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    midi = int(round(69 + 12 * math.log2(pitch_hz / 440.0)))
    return f"{names[midi % 12]}{midi // 12 - 1}"
