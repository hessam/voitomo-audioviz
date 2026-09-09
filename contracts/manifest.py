"""
Audioviz Manifest Schema (Python contract)
Matches renderer/src/types/manifest.ts 1:1
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Literal

VisualizerPresetId = Literal["sphere", "iris", "neural", "monolith"]


@dataclass
class AudioMultibandFeatures:
    bass: List[float]  # 30 FPS normalized [0.0, 1.0]
    mids: List[float]  # 30 FPS normalized [0.0, 1.0]
    treble: List[float]  # 30 FPS normalized [0.0, 1.0]
    transients: List[int]  # Frame indices where transient drum kicks or drops occur
    bpm: float = 120.0  # Detected musical tempo
    beatFrames: List[int] = field(default_factory=list)  # Exact frame indices of quarter-note beats
    downbeatFrames: List[int] = field(default_factory=list)  # 1st-beat-of-bar downbeats
    vocalEnergy: List[float] = field(default_factory=list)  # 30 FPS isolated vocal envelope
    macroEnergy: List[float] = field(default_factory=list)  # 30 FPS structural build-up/drop curve
    musicalKey: str = ""  # Harmonic key tonality (e.g. "D Minor")


@dataclass
class LyricLine:
    text: str = ""
    startFrame: int = 0
    endFrame: int = 0
    isHero: bool = False


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
