from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

@dataclass
class Palette:
    bg: str
    fg: str
    accent: str
    muted: str

@dataclass
class TypeScale:
    family: str
    weights: List[str]
    ratio: float = 1.333

@dataclass
class Grid:
    alignment: str = "left"  # "left" | "center" | "right"
    margin: int = 80
    columns: int = 12

@dataclass
class MotionSignature:
    chunking: str = "phrase"  # "phrase" | "word" | "glyph"
    stagger_frames: int = 6
    reveal_direction: str = "in_place"  # "in_place" | "left_to_right" | "top_to_bottom"
    corruption_density: float = 0.35

@dataclass
class CreativeDNA:
    thesis: str
    emotional_contradiction: str
    metaphor_system: str  # Relational transfer metaphor (e.g. "Centrifugal compression of market forces")
    transformation_verbs: List[str]  # e.g. ["compress", "invert", "accrete", "reconcile"]
    palette: Palette
    font_family: str = "Dana"  # "Dana" | "Vazirmatn"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thesis": self.thesis,
            "emotional_contradiction": self.emotional_contradiction,
            "metaphor_system": self.metaphor_system,
            "transformation_verbs": self.transformation_verbs,
            "palette": asdict(self.palette),
            "font_family": self.font_family
        }

HARMONIC_PALETTES = [
    # 0. Warm Terracotta / Rust Copper
    Palette(bg="#2A140E", fg="#F8F3F0", accent="#FF5722", muted="#9C8279"),
    # 1. Architectural Monochrome / Ink on Cream (High-Key Light Mode)
    Palette(bg="#F5F0E6", fg="#18181B", accent="#E11D48", muted="#71717A"),
    # 2. Deep Emerald Forest / Mint
    Palette(bg="#062C22", fg="#F0FDF4", accent="#10B981", muted="#6EE7B7"),
    # 3. Swiss Minimalist Concrete / Cobalt (Light Mode)
    Palette(bg="#E5E7EB", fg="#111827", accent="#2563EB", muted="#4B5563"),
    # 4. Neo-Cobalt Midnight / Solar Gold
    Palette(bg="#0A192F", fg="#F8FAFC", accent="#F59E0B", muted="#60A5FA"),
    # 5. Solar Sand / Warm Ochre (Light Mode)
    Palette(bg="#FEF3C7", fg="#451A03", accent="#D97706", muted="#92400E"),
    # 6. Deep Velvet Plum / Neon Orchid
    Palette(bg="#2E1035", fg="#FAF5FF", accent="#EC4899", muted="#C084FC"),
    # 7. Editorial Charcoal / Electric Violet
    Palette(bg="#18181B", fg="#FAFAFA", accent="#A855F7", muted="#A1A1AA"),
]

def generate_harmonic_palette(seed_text: str, mood_verb: str = "") -> Palette:
    """
    Procedurally generates an expressive, harmonic palette from text semantics and mood verb.
    Categorizes emotional/domain mood to prevent palette collision across genres:
    - Literary / Nocturne / Melodic -> Deep Emerald (#062C22) or Velvet Plum (#2E1035)
    - Systems / Science / Architecture -> Architectural Cream (#F5F0E6) or Concrete (#E5E7EB)
    - Velocity / Commercial / Action -> Warm Terracotta (#2A140E) or Solar Gold (#FEF3C7)
    - Cyber / Modern Tech -> Neo-Cobalt (#0A192F) or Charcoal (#18181B)
    STRICT BAN on hardcoded '#090A0F' navy fallback.
    """
    import hashlib
    combined = f"{seed_text}_{mood_verb}".lower()

    # 1. Nocturne / Lyric / Poetry / Organic
    lyric_keywords = ["شب", "سکوت", "کویر", "ماه", "رقص", "ستاره", "عشق", "شعر", "دل", "ترانه", "موزیک", "آواز", "باران"]
    if any(k in combined for k in lyric_keywords):
        return HARMONIC_PALETTES[2]  # Deep Emerald (#062C22)

    # 2. Systems / Governance / Academic / Structure
    systems_keywords = ["سیستم", "غیرمتمرکز", "ساختار", "داده", "الگوریتم", "معماری", "توسعه", "علم", "تحلیل", "کنترل", "تصمیم"]
    if any(k in combined for k in systems_keywords):
        return HARMONIC_PALETTES[1]  # Architectural Cream Light (#F5F0E6)

    # 3. Commercial / Speed / High-Tempo / Marketing
    commercial_keywords = ["ثانیه", "فقط", "برند", "فروش", "سریع", "پول", "کسب", "جهانی", "میلیون", "تخفیف", "تبلیغ", "بازار"]
    if any(k in combined for k in commercial_keywords):
        return HARMONIC_PALETTES[0]  # Warm Terracotta (#2A140E)

    # Fallback to high-dispersion SHA-256 hash
    hash_int = int(hashlib.sha256(combined.encode("utf-8")).hexdigest(), 16)
    idx = hash_int % len(HARMONIC_PALETTES)
    base = HARMONIC_PALETTES[idx]
    return Palette(bg=base.bg, fg=base.fg, accent=base.accent, muted=base.muted)

def clamp_badge(text: Optional[str], default_tag: str = "نکته کلیدی") -> str:
    """
    Clamp badge to <= 3 words and <= 20 characters.
    Strictly prevents essay-length sentences or CreativeDNA.thesis from leaking into badges.
    """
    if not text or not isinstance(text, str):
        return default_tag
    cleaned = text.strip().replace("\n", " ")
    words = cleaned.split()
    if not words:
        return default_tag
    clamped = " ".join(words[:3])
    if len(clamped) > 20:
        clamped = clamped[:20].rstrip()
    return clamped or default_tag

@dataclass
class LayerNode:
    id: str
    type: str  # "typography" | "vector_shape" | "clip_mask" | "kinetic_badge"
    text: Optional[str] = None
    weight: Optional[str] = "700"  # "300" | "500" | "700" | "900"
    is_hero: bool = False
    spatial_anchor: str = "center"  # "top_left" | "top_center" | "center" | "bottom_right"
    action_verb: str = "reveal"  # "compress" | "invert" | "accrete" | "shatter" | "reconcile" | "reveal"
    style: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        clean_text = self.text
        if self.type == "kinetic_badge" and clean_text:
            clean_text = clamp_badge(clean_text)
        return {
            "id": self.id,
            "type": self.type,
            "text": clean_text,
            "weight": self.weight,
            "is_hero": self.is_hero,
            "spatial_anchor": self.spatial_anchor,
            "action_verb": self.action_verb,
            "style": self.style
        }

@dataclass
class SceneNode:
    id: str
    frame_range: List[int]  # [start_frame, end_frame]
    layout: str = "hero_focus"  # "split_viewport" | "bento_grid" | "specimen_ladder" | "metric_punch" | "hero_focus"
    camera_dynamic: str = "push"  # "push" | "pan_left" | "pan_right" | "drift" | "static"
    entry_transition: str = "wipe"  # "wipe" | "cut" | "glitch" | "dissolve"
    exit_transition: str = "cut"
    badge: Optional[str] = None  # Clamped <= 3 words, max 20 chars
    layers: List[LayerNode] = field(default_factory=list)
    narrative_beat: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "frame_range": self.frame_range,
            "layout": self.layout,
            "camera_dynamic": self.camera_dynamic,
            "entry_transition": self.entry_transition,
            "exit_transition": self.exit_transition,
            "badge": clamp_badge(self.badge) if self.badge else None,
            "layers": [l.to_dict() for l in self.layers],
            "narrative_beat": self.narrative_beat
        }

@dataclass
class CompositionGraph:
    meta: Dict[str, Any]
    creative_dna: CreativeDNA
    scenes: List[SceneNode]
    audio_anchors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": self.meta,
            "creative_dna": self.creative_dna.to_dict(),
            "scenes": [s.to_dict() for s in self.scenes],
            "audio_anchors": self.audio_anchors
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

@dataclass
class DesignSystem:
    concept: str
    palette: Palette
    type_scale: TypeScale
    grid: Grid
    motion_signature: MotionSignature

@dataclass
class RevealConfig:
    primitive: str = "glitch_decode"  # "glitch_decode" | "block_wipe"
    target: str = "phrase"  # "phrase" | "word" | "glyph"
    channel_offset_px: int = 5
    stagger_frames: int = 4
    direction: str = "forward"  # "forward" | "reverse"

@dataclass
class SceneContent:
    text: str
    weight: Optional[str] = None
    is_hero: bool = False

@dataclass
class Scene:
    id: str
    layout: str  # "hero_focus" | "split_viewport" | "bento_grid" | "specimen_ladder" | "metric_punch" | "paragraph_stack" | "caption_panel"
    frame_range: List[int]  # [start_frame, end_frame]
    reveal: RevealConfig
    content: List[SceneContent]
    badge: Optional[str] = None  # Clamped <= 3 words, max 20 chars
    motion: Dict[str, Any] = field(default_factory=dict)
    layers: Optional[List[LayerNode]] = None
    camera_dynamic: str = "push"

@dataclass
class CreativeSpec:
    meta: Dict[str, Any]
    design_system: DesignSystem
    scenes: List[Scene]
    creative_dna: Optional[CreativeDNA] = None
    composition_graph: Optional[CompositionGraph] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "meta": self.meta,
            "design_system": asdict(self.design_system),
            "timeline": {
                "scenes": [
                    {
                        "id": s.id,
                        "layout": s.layout,
                        "frame_range": s.frame_range,
                        "reveal": asdict(s.reveal),
                        "content": [asdict(c) for c in s.content],
                        "badge": clamp_badge(s.badge) if s.badge else None,
                        "motion": s.motion,
                        "layers": [l.to_dict() for l in s.layers] if s.layers else None,
                        "camera_dynamic": s.camera_dynamic
                    }
                    for s in self.scenes
                ]
            }
        }
        if self.creative_dna:
            d["creative_dna"] = self.creative_dna.to_dict()
        if self.composition_graph:
            d["composition_graph"] = self.composition_graph.to_dict()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CreativeSpec":
        ds_data = data["design_system"]
        design_system = DesignSystem(
            concept=ds_data.get("concept", "Bespoke Typographic Narrative"),
            palette=Palette(**ds_data["palette"]),
            type_scale=TypeScale(**ds_data["type_scale"]),
            grid=Grid(**ds_data.get("grid", {})),
            motion_signature=MotionSignature(**ds_data.get("motion_signature", {}))
        )

        timeline_data = data.get("timeline", {})
        scenes_raw = timeline_data.get("scenes", data.get("scenes", []))
        scenes = []
        for s in scenes_raw:
            reveal_data = s.get("reveal", {})
            reveal = RevealConfig(
                primitive=reveal_data.get("primitive", "glitch_decode"),
                target=reveal_data.get("target", "phrase"),
                channel_offset_px=reveal_data.get("channel_offset_px", 5),
                stagger_frames=reveal_data.get("stagger_frames", 4),
                direction=reveal_data.get("direction", "forward")
            )
            content_items = [
                SceneContent(
                    text=c["text"] if isinstance(c, dict) else str(c),
                    weight=c.get("weight") if isinstance(c, dict) else None,
                    is_hero=c.get("is_hero", False) if isinstance(c, dict) else False
                )
                for c in s.get("content", [])
            ]
            scenes.append(Scene(
                id=s["id"],
                layout=s["layout"],
                frame_range=s["frame_range"],
                reveal=reveal,
                content=content_items,
                motion=s.get("motion", {})
            ))

        return cls(
            meta=data.get("meta", {}),
            design_system=design_system,
            scenes=scenes
        )

    @classmethod
    def from_json(cls, json_str: str) -> "CreativeSpec":
        return cls.from_dict(json.loads(json_str))
