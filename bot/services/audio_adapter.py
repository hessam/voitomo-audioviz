import os
import subprocess
import json
import logging
import tempfile
import asyncio
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
import math
import struct

import shutil
import uuid

logger = logging.getLogger(__name__)

AUDIOVIZ_BROKER_DIR = os.environ.get("AUDIOVIZ_BROKER_DIR", "/workspace/audioviz-broker")
# Filename written inside job_dir before polling starts.
# Contains caller context so restarts can re-deliver completed jobs.
_CLAIM_FILE = "claim.json"

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
    2. hermes-music-dna: Rhythm grid, BPM, downbeats, and musical key
    Includes robust local DSP fallbacks to ensure 100% service uptime.
    """

    @staticmethod
    async def separate_stems_broker(
        audio_path: str,
        timeout_seconds: int = 1800,
        chat_id: int = 0,
        message_id: int = 0,
    ) -> Dict[str, str]:
        """
        Delegates stem separation to hermes-audio-engineer-sandbox via host broker.
        Allows full high-fidelity neural processing without artificial short timeouts.
        Returns dict with paths to 'vocals', 'instrumental' (or 'bass'/'drums' if present).
        Falls back gracefully if broker is offline or timed out.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Input audio file not found: {audio_path}")

        job_id = f"stems_{uuid.uuid4().hex[:10]}"
        job_dir = os.path.join(AUDIOVIZ_BROKER_DIR, "jobs", job_id)
        
        # Check if broker directory exists
        if not os.path.exists(AUDIOVIZ_BROKER_DIR):
            logger.info(f"Broker dir {AUDIOVIZ_BROKER_DIR} not mounted, using local fallback.")
            return {}

        try:
            os.makedirs(job_dir, exist_ok=True)
            input_dest = os.path.join(job_dir, "input.wav")
            shutil.copy2(audio_path, input_dest)

            trigger_payload = {
                "job_id": job_id,
                "action": "separate_stems",
                "audio_filename": "input.wav"
            }
            with open(os.path.join(job_dir, "trigger.json"), "w") as f:
                json.dump(trigger_payload, f)

            # --- RESURRECTION ANCHOR ---
            # Write caller identity BEFORE we start polling.
            # If this process is killed mid-wait, the restart scan finds this
            # file, sees result.json exists, and re-delivers the result.
            claim_path = os.path.join(job_dir, _CLAIM_FILE)
            claim = {
                "job_id": job_id,
                "submitted_at": time.time(),
                "chat_id": chat_id,
                "message_id": message_id,
            }
            with open(claim_path, "w") as f:
                json.dump(claim, f)

            logger.info(f"🚀 Sent stem separation job {job_id} to host broker...")
            result_file = os.path.join(job_dir, "result.json")
            output_dir = os.path.join(job_dir, "output")

            start_time = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                if os.path.exists(result_file):
                    break
                await asyncio.sleep(0.5)

            if not os.path.exists(result_file):
                logger.warning(f"Stem separation job {job_id} timed out after {timeout_seconds}s.")
                return {}

            with open(result_file, "r") as f:
                res_data = json.load(f)

            if res_data.get("status") != "success":
                logger.warning(f"Stem separation job {job_id} failed: {res_data.get('error')}")
                return {}

            stems: Dict[str, str] = {}
            if os.path.exists(output_dir):
                # Copy isolated stems to persistent safe cache dir
                cache_dir = tempfile.mkdtemp(prefix=f"audioviz_stems_{job_id}_")
                for fname in os.listdir(output_dir):
                    fpath = os.path.join(output_dir, fname)
                    dest_path = os.path.join(cache_dir, fname)
                    shutil.copy2(fpath, dest_path)
                    lower_name = fname.lower()
                    if "vocal" in lower_name:
                        stems["vocals"] = dest_path
                    elif "instrumental" in lower_name or "no_vocals" in lower_name:
                        stems["instrumental"] = dest_path
                    elif "bass" in lower_name:
                        stems["bass"] = dest_path
                    elif "drum" in lower_name:
                        stems["drums"] = dest_path
                    elif "other" in lower_name:
                        stems["other"] = dest_path

            logger.info(f"✨ Stem separation completed successfully: {list(stems.keys())}")
            return stems

        except Exception as e:
            logger.warning(f"Broker stem separation error: {e}")
            return {}
        finally:
            # Remove claim file so resurrection scan ignores completed jobs
            try:
                claim_path = os.path.join(job_dir, _CLAIM_FILE)
                if os.path.exists(claim_path):
                    os.remove(claim_path)
            except Exception:
                pass
            try:
                if os.path.exists(job_dir):
                    shutil.rmtree(job_dir, ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def collect_orphaned_stem_jobs() -> List[Tuple[str, int, int, Dict[str, str]]]:
        """
        Startup resurrection scan.

        Finds jobs that:
        - Were submitted (claim.json exists with chat_id/message_id)
        - Completed while this process was dead (result.json status=success)
        - Output stems are still on disk

        Returns list of (job_id, chat_id, message_id, stems_dict) tuples.
        Call once at bot startup; re-deliver each to the original user.
        """
        results = []
        jobs_root = os.path.join(AUDIOVIZ_BROKER_DIR, "jobs")
        if not os.path.isdir(jobs_root):
            return results

        for job_id in os.listdir(jobs_root):
            job_dir = os.path.join(jobs_root, job_id)
            if not os.path.isdir(job_dir):
                continue
            claim_path = os.path.join(job_dir, _CLAIM_FILE)
            result_path = os.path.join(job_dir, "result.json")
            output_dir = os.path.join(job_dir, "output")

            if not os.path.exists(claim_path) or not os.path.exists(result_path):
                continue

            try:
                with open(claim_path) as f:
                    claim = json.load(f)
                with open(result_path) as f:
                    res = json.load(f)
            except Exception:
                continue

            if res.get("status") != "success":
                continue

            chat_id = claim.get("chat_id", 0)
            message_id = claim.get("message_id", 0)
            if not chat_id:
                continue

            # Collect stem file paths
            stems: Dict[str, str] = {}
            if os.path.isdir(output_dir):
                try:
                    cache_dir = tempfile.mkdtemp(prefix=f"audioviz_stems_{job_id}_")
                    for fname in os.listdir(output_dir):
                        fpath = os.path.join(output_dir, fname)
                        dest = os.path.join(cache_dir, fname)
                        shutil.copy2(fpath, dest)
                        lname = fname.lower()
                        if "vocal" in lname:
                            stems["vocals"] = dest
                        elif "instrumental" in lname or "no_vocals" in lname:
                            stems["instrumental"] = dest
                        elif "bass" in lname:
                            stems["bass"] = dest
                        elif "drum" in lname:
                            stems["drums"] = dest
                        elif "other" in lname:
                            stems["other"] = dest
                except Exception as e:
                    logger.warning(f"Resurrection copy failed for {job_id}: {e}")
                    continue

            if not stems:
                continue

            logger.info(f"🔁 Resurrecting orphaned job {job_id} → chat_id={chat_id}")
            # Remove claim so this job isn't re-delivered twice
            try:
                os.remove(claim_path)
            except Exception:
                pass

            results.append((job_id, chat_id, message_id, stems))

        return results

    @staticmethod
    async def extract_music_dna_broker(audio_path: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        """
        Delegates groove, BPM, beat grid, and musical key extraction to hermes-music-dna via Broker.
        Falls back gracefully to local librosa extraction.
        """
        if not os.path.exists(audio_path):
            return {}

        job_id = f"dna_{uuid.uuid4().hex[:10]}"
        job_dir = os.path.join(AUDIOVIZ_BROKER_DIR, "jobs", job_id)

        if not os.path.exists(AUDIOVIZ_BROKER_DIR):
            return {}

        try:
            os.makedirs(job_dir, exist_ok=True)
            input_dest = os.path.join(job_dir, "input.wav")
            shutil.copy2(audio_path, input_dest)

            trigger_payload = {
                "job_id": job_id,
                "action": "music_dna",
                "audio_filename": "input.wav"
            }
            with open(os.path.join(job_dir, "trigger.json"), "w") as f:
                json.dump(trigger_payload, f)

            logger.info(f"🎵 Sent music DNA job {job_id} to host broker...")
            result_file = os.path.join(job_dir, "result.json")
            output_dna = os.path.join(job_dir, "output", "dna.json")

            start_time = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                if os.path.exists(result_file):
                    break
                await asyncio.sleep(0.5)

            if not os.path.exists(result_file):
                logger.warning(f"Music DNA job {job_id} timed out after {timeout_seconds}s.")
                return {}

            if os.path.exists(output_dna):
                with open(output_dna, "r") as f:
                    dna_json = json.load(f)
                logger.info(f"🎶 Music DNA extracted: BPM={dna_json.get('bpm')}, Key={dna_json.get('musical_key')}")
                return dna_json

            return {}
        except Exception as e:
            logger.warning(f"Broker music DNA error: {e}")
            return {}
        finally:
            try:
                if os.path.exists(job_dir):
                    shutil.rmtree(job_dir, ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    async def separate_vocals(audio_path: str, timeout_seconds: int = 1800) -> str:
        """
        Extracts dry vocal stem from a song.
        Uses Mel-Band RoFormer via Broker; falls back to spectral center-channel isolation.
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Input audio file not found: {audio_path}")

        # 1. Attempt broker stem separation
        try:
            stems = await AudioIntelligenceAdapter.separate_stems_broker(audio_path, timeout_seconds=timeout_seconds)
            if stems.get("vocals") and os.path.exists(stems["vocals"]):
                logger.info(f"🎙 Isolated dry vocals via Mel-Band RoFormer: {stems['vocals']}")
                return stems["vocals"]
        except Exception as e:
            logger.info(f"Broker stem separation bypassed ({e}), using local acoustic vocal extraction.")

        # 2. Resilient local fallback: Bandpass vocal formant extraction via FFmpeg
        out_vocal = tempfile.NamedTemporaryFile(suffix="_vocals.wav", delete=False).name
        try:
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
