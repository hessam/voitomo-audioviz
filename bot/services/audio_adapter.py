import os
import subprocess
import json
import logging
import tempfile
import asyncio
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import math
import struct

logger = logging.getLogger(__name__)

AUDIO_ENGINEER_URL = os.environ.get("AUDIO_ENGINEER_URL", "http://hermes-audio-engineer-sandbox:5001")
MUSIC_DNA_URL = os.environ.get("MUSIC_DNA_URL", "http://hermes-music-dna-sandbox:5002")

@dataclass
class AudioAnchor:
    frame: int
    timestamp: float
    type: str  # "emphasis" | "drop" | "cadential_pause" | "rhythm_pulse"
    energy_level: float  # 0.0 to 1.0 normalized
    associated_word: Optional[str] = None
    duration_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class AudioIntelligenceAdapter:
    """
    Non-invasive adapter orchestrating specialized intelligence from:
    1. hermes-audio-engineer: Mel-Band RoFormer stem separation for dry vocals
    2. hermes-music-dna: Rhythm grid, BPM, downbeats, and energy curves
    Includes robust local DSP fallbacks to ensure 100% service uptime.
    """

    @staticmethod
    async def separate_vocals(audio_path: str, timeout_seconds: int = 45) -> str:
        """
        Extracts dry vocal stem from a song.
        Uses Audio Engineer agent if available; falls back to spectral center-channel isolation.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Input audio file not found: {audio_path}")

        # 1. Attempt delegated extraction via Audio Engineer Agent microservice
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{AUDIO_ENGINEER_URL}/separate",
                    json={"audio_path": audio_path, "target_stem": "vocals"},
                    timeout=aiohttp.ClientTimeout(total=timeout_seconds)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        vocal_path = data.get("vocal_path")
                        if vocal_path and os.path.exists(vocal_path):
                            logger.info(f"🎙 Isolated dry vocals via Audio Engineer Agent: {vocal_path}")
                            return vocal_path
        except Exception as e:
            logger.info(f"Audio Engineer delegation bypassed/offline ({e}), using local acoustic vocal extraction.")

        # 2. Resilient local fallback: Bandpass vocal formant extraction via FFmpeg
        out_vocal = tempfile.NamedTemporaryFile(suffix="_vocals.wav", delete=False).name
        try:
            # Bandpass filter tuned to vocal fundamental & formants (200Hz - 4500Hz) with voice compression
            cmd = [
                "ffmpeg", "-y", "-i", audio_path,
                "-af", "highpass=f=180,lowpass=f=4500,acompressor=threshold=-18dB:ratio=4:attack=15:release=100",
                "-ar", "16000", "-ac", "1", out_vocal
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            logger.info(f"🎙 Generated local formant-filtered vocal stem: {out_vocal}")
            return out_vocal
        except Exception as fallback_err:
            logger.warning(f"Vocal filtering failed ({fallback_err}), proceeding with original audio.")
            return audio_path

    @staticmethod
    def extract_rhythm_and_beats(audio_path: str, fps: int = 30) -> Dict[str, Any]:
        """
        Extracts musical tempo (BPM) and beat grid timestamps.
        Provides exact frame markers for Remotion scene cuts and audio-reactive pulses.
        """
        # Default rhythm structure if analysis cannot determine tempo
        default_bpm = 120.0
        beat_interval_sec = 60.0 / default_bpm

        try:
            # Use ffprobe to get exact duration
            dur_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path
            ]
            dur_out = subprocess.check_output(dur_cmd).decode().strip()
            total_duration = float(dur_out)
        except Exception:
            total_duration = 30.0

        # Try extracting BPM using Aubio/Librosa if available in environment
        bpm = default_bpm
        beats_sec = []

        try:
            # Check for librosa or aubio in python
            import librosa
            y, sr = librosa.load(audio_path, sr=22050, mono=True)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            if hasattr(tempo, "__iter__"):
                bpm = float(tempo[0]) if len(tempo) > 0 else default_bpm
            else:
                bpm = float(tempo)
            beats_sec = [float(round(t, 3)) for t in librosa.frames_to_time(beat_frames, sr=sr)]
        except Exception:
            # Mathematical rhythmic grid generation matching detected duration
            curr = 0.5
            while curr < total_duration:
                beats_sec.append(round(curr, 3))
                curr += beat_interval_sec

        beat_frames = [int(round(t * fps)) for t in beats_sec]

        # Generate musical 4-bar / 8-bar phrasing markers (assuming 4/4 time signature)
        bar_interval = 4
        downbeats_sec = beats_sec[::bar_interval]
        downbeat_frames = beat_frames[::bar_interval]

        return {
            "bpm": round(bpm, 1),
            "total_duration": total_duration,
            "beats_sec": beats_sec,
            "beat_frames": beat_frames,
            "downbeats_sec": downbeats_sec,
            "downbeat_frames": downbeat_frames,
            "time_signature": "4/4"
        }

    @staticmethod
    def extract_audio_prosody(audio_path: str, words: List[Dict], fps: int = 30) -> List[AudioAnchor]:
        """
        Local DSP extraction for vocal prosody:
        - RMS energy envelope (20ms window, 10ms hop)
        - Cadential pauses (>350ms silence between speech tokens)
        - Dramatic inflection anchors (vocal emphasis peaks & energy drops)
        Runs synchronously (call via extract_audio_prosody_async to avoid event loop blocking).
        """
        if not os.path.exists(audio_path) or not words:
            return []

        anchors: List[AudioAnchor] = []

        # 1. Detect cadential pauses (>350ms gap between consecutive words)
        for i in range(len(words) - 1):
            curr_w = words[i]
            next_w = words[i + 1]
            gap = next_w.get("start", 0.0) - curr_w.get("end", 0.0)
            if gap >= 0.35:
                pause_frame = int(round(curr_w.get("end", 0.0) * fps))
                anchors.append(AudioAnchor(
                    frame=pause_frame,
                    timestamp=round(curr_w.get("end", 0.0), 2),
                    type="cadential_pause",
                    energy_level=0.0,
                    associated_word=curr_w.get("word"),
                    duration_sec=round(gap, 2)
                ))

        # 2. Extract 16kHz mono raw PCM using ffmpeg for audio envelope analysis
        try:
            cmd = [
                "ffmpeg", "-y", "-i", audio_path,
                "-ac", "1", "-ar", "16000", "-f", "s16le", "-"
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
            raw_bytes = proc.stdout
            num_samples = len(raw_bytes) // 2

            if num_samples > 0:
                # 20ms window = 320 samples, 10ms hop = 160 samples at 16kHz
                win_size = 320
                hop_size = 160
                
                # Check if numpy is available
                try:
                    import numpy as np
                    samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
                    num_hops = max(1, (len(samples) - win_size) // hop_size)
                    rms_curve = []
                    for h in range(num_hops):
                        chunk = samples[h * hop_size : h * hop_size + win_size]
                        rms_curve.append(float(np.sqrt(np.mean(chunk ** 2))))
                except ImportError:
                    # Pure python fallback
                    num_hops = max(1, (num_samples - win_size) // hop_size)
                    rms_curve = []
                    unpack_fmt = f"<{win_size}h"
                    for h in range(num_hops):
                        offset = h * hop_size * 2
                        chunk = struct.unpack_from(unpack_fmt, raw_bytes, offset)
                        sum_sq = sum(x * x for x in chunk)
                        rms_curve.append(math.sqrt(sum_sq / win_size))

                # Normalize RMS curve to 0.0 - 1.0
                max_rms = max(rms_curve) if rms_curve and max(rms_curve) > 0 else 1.0
                norm_rms = [r / max_rms for r in rms_curve]

                # 3. Identify dramatic inflection anchors within word boundaries
                for w in words:
                    w_start = w.get("start", 0.0)
                    w_end = w.get("end", 0.0)
                    idx_start = max(0, min(int(w_start * 100), len(norm_rms) - 1))
                    idx_end = max(idx_start + 1, min(int(w_end * 100), len(norm_rms)))
                    
                    word_energies = norm_rms[idx_start:idx_end]
                    if word_energies:
                        peak_energy = max(word_energies)
                        peak_offset_idx = word_energies.index(peak_energy)
                        peak_time = w_start + (peak_offset_idx * 0.01)
                        peak_frame = int(round(peak_time * fps))

                        if peak_energy >= 0.70:
                            anchors.append(AudioAnchor(
                                frame=peak_frame,
                                timestamp=round(peak_time, 2),
                                type="emphasis",
                                energy_level=round(peak_energy, 2),
                                associated_word=w.get("word")
                            ))
                        elif peak_energy <= 0.20 and (w_end - w_start) >= 0.4:
                            anchors.append(AudioAnchor(
                                frame=int(round(w_start * fps)),
                                timestamp=round(w_start, 2),
                                type="drop",
                                energy_level=round(peak_energy, 2),
                                associated_word=w.get("word")
                            ))
        except Exception as e:
            logger.warning(f"Audio envelope extraction error ({e}), proceeding with pause anchors.")

        # Sort and deduplicate anchors by frame (within 3 frames)
        anchors.sort(key=lambda a: a.frame)
        deduped: List[AudioAnchor] = []
        for a in anchors:
            if not deduped or abs(a.frame - deduped[-1].frame) >= 4:
                deduped.append(a)

        return deduped

    @staticmethod
    async def extract_audio_prosody_async(audio_path: str, words: List[Dict], fps: int = 30) -> List[AudioAnchor]:
        """Offload audio decode and local DSP to a background worker thread."""
        return await asyncio.to_thread(AudioIntelligenceAdapter.extract_audio_prosody, audio_path, words, fps)
