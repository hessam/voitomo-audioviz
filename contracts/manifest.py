"""
Audioviz Manifest Schema (Python contract)
Matches renderer/src/types/manifest.ts 1:1
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Literal

VisualizerPresetId = Literal["sphere", "orrery", "cymatic", "bodies"]
RhythmSource = Literal["unknown", "broker", "estimated"]
OnsetKind = Literal["kick", "snare", "cymbal", "other"]


@dataclass
class OnsetEvent:
    frame: int  # First video frame that may show this hit (never earlier than the hit)
    strength: float  # 0..1, relative to the strongest onset in the clip
    kind: OnsetKind = "other"


@dataclass
class NoteEvent:
    startFrame: int
    endFrame: int
    pitchHz: float
    stem: str = "other"
    confidence: float = 0.0


@dataclass
class RiffCycle:
    lengthSteps: int  # Repeat length in subdivision steps (for example 23 sixteenth notes)
    stepFrames: float  # Video frames per step
    confidence: float


@dataclass
class AudioMultibandFeatures:
    bass: List[float]  # 30 FPS normalized [0.0, 1.0]
    mids: List[float]  # 30 FPS normalized [0.0, 1.0]
    treble: List[float]  # 30 FPS normalized [0.0, 1.0]
    transients: List[int]  # Frame indices where transient drum kicks or drops occur
    bpm: Optional[float] = None  # Detected musical tempo; None when unknown
    beatFrames: List[int] = field(default_factory=list)  # Exact frame indices of quarter-note beats
    downbeatFrames: List[int] = field(default_factory=list)  # 1st-beat-of-bar downbeats
    vocalEnergy: List[float] = field(default_factory=list)  # 30 FPS isolated vocal envelope
    drumsEnergy: List[float] = field(default_factory=list)  # 30 FPS isolated drums envelope
    macroEnergy: List[float] = field(default_factory=list)  # 30 FPS structural build-up/drop curve
    musicalKey: str = ""  # Harmonic key tonality (e.g. "D Minor"); empty when unknown
    rhythmSource: RhythmSource = "unknown"  # Where beatFrames came from
    downbeatsAssumed: bool = False  # True when downbeats are only "every Nth beat", not measured
    meterBeats: Optional[int] = None  # Beats per bar when measured or estimated
    onsets: List[OnsetEvent] = field(default_factory=list)  # Classified hit events
    notes: List[NoteEvent] = field(default_factory=list)  # Pitched note events (optional)
    riffCycle: Optional[RiffCycle] = None  # Repeating pattern length, when one was found
    # Per-stem spectral bands for Resonant Bodies: stem name -> frames x 12 values in 0..1.
    # Only stems that exist are present; "mix" appears only when there are no stems at all.
    bodyBands: Dict[str, List[List[float]]] = field(default_factory=dict)


@dataclass
class LyricWord:
    word: str = ""
    startFrame: int = 0
    endFrame: int = 0
    score: float = 1.0
    isInterpolated: bool = False
    alignmentSource: str = "acoustic"


@dataclass
class LyricLine:
    text: str = ""
    startFrame: int = 0
    endFrame: int = 0
    isHero: bool = False
    confidence: float = 1.0
    words: List[LyricWord] = field(default_factory=list)


@dataclass
class PresetConfig:
    id: VisualizerPresetId
    version: str = "1.0.0"
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoConfig:
    width: int = 1920
    height: int = 1080
    fpsNumerator: int = 30
    fpsDenominator: int = 1
    frameCount: int = 300


@dataclass
class AudioConfig:
    masterUri: str
    sha256: str
    sampleRate: int = 44100
    vocalStemUri: Optional[str] = None
    bassStemUri: Optional[str] = None
    features: Optional[AudioMultibandFeatures] = None


@dataclass
class LyricsConfig:
    lines: List[LyricLine] = field(default_factory=list)
    mode: Literal["off", "subtitles", "video"] = "subtitles"  # how the renderer shows the lines


@dataclass
class RenderManifest:
    schemaVersion: int
    jobId: str
    seed: int
    preset: PresetConfig
    video: VideoConfig
    audio: AudioConfig
    lyrics: LyricsConfig
    environment: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
