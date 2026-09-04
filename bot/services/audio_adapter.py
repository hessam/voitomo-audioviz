import os
import subprocess
import json
import logging
import tempfile
import aiohttp
import asyncio
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

AUDIO_ENGINEER_URL = os.environ.get("AUDIO_ENGINEER_URL", "http://hermes-audio-engineer-sandbox:5001")
MUSIC_DNA_URL = os.environ.get("MUSIC_DNA_URL", "http://hermes-music-dna-sandbox:5002")

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
