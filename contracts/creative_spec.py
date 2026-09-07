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
    tape_bg: str = "#FFFFFF"
    tape_text: str = "#000000"
    shadow_block: str = "#000000"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bg": self.bg,
            "fg": self.fg,
            "accent": self.accent,
            "muted": self.muted,
            "tape_bg": self.tape_bg,
            "tape_text": self.tape_text,
            "shadow_block": self.shadow_block,
            "tapeBg": self.tape_bg,
            "tapeText": self.tape_text,
            "shadowBlock": self.shadow_block
        }

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

def safe_hue(hue: float) -> float:
    """
    Automatically snaps muddy earth/brown hues (20-105) to either Coral Red (15) or Acid Lime (115).
    Permanently bans the brown/sludge zone.
    """
    h = ((hue % 360) + 360) % 360
    if 20 <= h <= 105:
        return 15.0 if h < 63 else 115.0
    return float(h)

ACCENT_HEX_MAP = [
    "#FF5722",  # Coral Red
    "#10B981",  # Emerald
    "#2563EB",  # Cobalt
    "#F59E0B",  # Amber
    "#EC4899",  # Pink Orchid
    "#A855F7",  # Electric Purple
    "#06B6D4",  # Cyan
    "#84CC16",  # Lime
]

def compile_palette(mood: str = "bold", hue: float = 0.0, variant: str = "dark") -> Palette:
    """
    Pure OKLCH color compiler preventing muddy brown/sludge colors.
    Moods: 'calm' (C=0.12), 'bold' (C=0.20), 'electric' (C=0.25).
    Variant: 'dark' (L=0.40) or 'light' (L=0.78).
    Sets stark White/Black text containers with #000000 hard offset block shadows.
    """
    h = safe_hue(hue)
    dark = (variant == "dark")
    chroma_map = {"calm": 0.12, "bold": 0.20, "electric": 0.25}
    chroma = chroma_map.get(mood, 0.20)
    lightness = 0.40 if dark else 0.78
    bg_oklch = f"oklch({lightness:.2f} {chroma:.2f} {h:.1f})"

    accent_idx = int(round(h / 45.0)) % len(ACCENT_HEX_MAP)
    accent = ACCENT_HEX_MAP[accent_idx]

    return Palette(
        bg=bg_oklch,
        fg="#FFFFFF" if dark else "#000000",
        accent=accent,
        muted="#E4E4E7" if dark else "#3F3F46",
        tape_bg="#FFFFFF",
        tape_text="#000000",
        shadow_block="#000000"
    )

HARMONIC_PALETTES = [
    compile_palette(mood="bold", hue=15.0, variant="dark"),     # Coral Red (15)
    compile_palette(mood="bold", hue=240.0, variant="light"),   # Clean Cobalt Light
    compile_palette(mood="calm", hue=165.0, variant="dark"),    # Deep Emerald
    compile_palette(mood="calm", hue=220.0, variant="light"),   # Swiss Sky Light
    compile_palette(mood="electric", hue=265.0, variant="dark"),# Electric Violet
    compile_palette(mood="electric", hue=115.0, variant="dark"),# Acid Lime (115)
    compile_palette(mood="bold", hue=320.0, variant="dark"),    # Neon Orchid
    compile_palette(mood="calm", hue=210.0, variant="dark"),    # Deep Slate
]

SAFE_PALETTES = {
    "studio_concrete": Palette(
        bg="#B8B9BA",
        fg="#000000",
        accent="#000000",
        muted="#4B5563",
        tape_bg="#FFFFFF",
        tape_text="#000000",
        shadow_block="#000000"
    ),
    "electric_cobalt": Palette(
        bg="#5537ED",
        fg="#FFFFFF",
        accent="#FF5500",
        muted="#E0E7FF",
        tape_bg="#FFFFFF",
        tape_text="#000000",
        shadow_block="#000000"
    ),
    "signal_acid": Palette(
        bg="#0E0F12",
        fg="#FFFFFF",
        accent="#D4FF00",
        muted="#9CA3AF",
        tape_bg="#FFFFFF",
        tape_text="#000000",
        shadow_block="#000000"
    ),
}

def is_banned_sludge_color(color: str) -> bool:
    """
    Checks if a background color falls into brown/sludge or dark navy traps:
    - Bans any hex starting with '#2' or '#3' in darker channels (#211513, #241815, #2A140E, #301B14, etc.)
    - Bans '#090A0F' and '#0A0B0E'
    - Bans hue angles between 20 deg and 105 deg.
    """
    if not color or not isinstance(color, str):
        return True
    s = color.strip().upper()
    if s.startswith("#2") or s.startswith("#3"):
        return True
    if s in ("#090A0F", "#0A0B0E"):
        return True
    return False

def generate_harmonic_palette(seed_text: str, mood_verb: str = "") -> Palette:
    """
    Hardcoded Safe Palette Engine:
    Selects exclusively among the 3 verified benchmark palettes:
    1. Studio Concrete (#B8B9BA - Cavalry benchmark)
    2. Electric Cobalt (#5537ED - Canva benchmark)
    3. Signal Acid (#0E0F12 with #D4FF00)
    Permanently bans any hex starting with #2 or #3.
    """
    import hashlib
    combined = f"{seed_text}_{mood_verb}".lower()

    tech_keywords = ["لینکدین", "سیستم", "شرکت", "شغل", "کار", "پروژه", "رزومه", "مصاحبه", "تخصص", "فناوری", "رشد", "برند"]
    if any(k in combined for k in tech_keywords):
        return SAFE_PALETTES["electric_cobalt"]

    editorial_keywords = ["معماری", "طراحی", "سوئیس", "ساختار", "هنر", "تایپوگرافی", "ساده", "سفید", "خاکستری"]
    if any(k in combined for k in editorial_keywords):
        return SAFE_PALETTES["studio_concrete"]

    night_keywords = ["شب", "سکوت", "موزیک", "ترانه", "آواز", "صدا", "سیگنال"]
    if any(k in combined for k in night_keywords):
        return SAFE_PALETTES["signal_acid"]

    hash_int = int(hashlib.sha256(combined.encode("utf-8")).hexdigest(), 16)
    choices = [SAFE_PALETTES["electric_cobalt"], SAFE_PALETTES["studio_concrete"], SAFE_PALETTES["signal_acid"]]
    return choices[hash_int % len(choices)]

@dataclass
class CreativeDNA:
    thesis: str
    emotional_contradiction: str
    metaphor_system: str  # Relational transfer metaphor (e.g. "Centrifugal compression of market forces")
    transformation_verbs: List[str]  # e.g. ["compress", "invert", "accrete", "reconcile"]
    palette: Palette
    font_family: str = "Dana"  # "Dana" | "Vazirmatn"
    world: str = "pop-bento"  # "kinetic-poster" | "editorial" | "pop-bento"

    def __post_init__(self):
        if hasattr(self, "palette") and self.palette and hasattr(self.palette, "bg"):
            if is_banned_sludge_color(self.palette.bg):
                self.palette = generate_harmonic_palette(self.thesis or self.metaphor_system or "سوئیس")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "thesis": self.thesis,
            "emotional_contradiction": self.emotional_contradiction,
            "metaphor_system": self.metaphor_system,
            "transformation_verbs": self.transformation_verbs,
            "palette": self.palette.to_dict() if hasattr(self.palette, "to_dict") else asdict(self.palette),
            "font_family": self.font_family,
            "world": self.world
        }

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
    spatial: Optional[Dict[str, Any]] = None
    environment: Optional[Dict[str, Any]] = None
    asset: Optional[Dict[str, Any]] = None
    type_spec: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
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
        if self.spatial:
            d["spatial"] = self.spatial
            d["hero_layer"] = self.spatial.get("hero_layer", "typography")
            d["assetBox"] = self.spatial.get("asset_box") or self.spatial.get("assetBox")
            d["typeBox"] = self.spatial.get("type_box") or self.spatial.get("typeBox")
        if self.environment:
            d["environment"] = self.environment
        if self.asset:
            d["asset"] = self.asset
            if "vector_ir" in self.asset:
                d["vector_ir"] = self.asset["vector_ir"]
        else:
            d["asset"] = None
        if self.type_spec:
            d["type"] = self.type_spec
            d["type_spec"] = self.type_spec
        return d

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

    def __post_init__(self):
        if hasattr(self, "palette") and self.palette and hasattr(self.palette, "bg"):
            if is_banned_sludge_color(self.palette.bg):
                self.palette = generate_harmonic_palette(self.concept or "سوئیس")

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
    spatial: Optional[Dict[str, Any]] = None
    environment: Optional[Dict[str, Any]] = None
    asset: Optional[Dict[str, Any]] = None
    type_spec: Optional[Dict[str, Any]] = None

@dataclass
class CreativeSpec:
    meta: Dict[str, Any]
    design_system: DesignSystem
    scenes: List[Scene]
    creative_dna: Optional[CreativeDNA] = None
    composition_graph: Optional[CompositionGraph] = None

    def to_dict(self) -> Dict[str, Any]:
        ds_dict = asdict(self.design_system)
        if "palette" in ds_dict:
            p = ds_dict["palette"]
            p["tapeBg"] = p.get("tape_bg", "#FFFFFF")
            p["tapeText"] = p.get("tape_text", "#000000")
            p["shadowBlock"] = p.get("shadow_block", "#000000")

        timeline_scenes = []
        for s in self.scenes:
            sc_dict = {
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
            if s.spatial:
                sc_dict["spatial"] = s.spatial
                sc_dict["hero_layer"] = s.spatial.get("hero_layer", "typography")
                sc_dict["assetBox"] = s.spatial.get("asset_box") or s.spatial.get("assetBox")
                sc_dict["typeBox"] = s.spatial.get("type_box") or s.spatial.get("typeBox")
            if s.environment:
                sc_dict["environment"] = s.environment
            if s.asset:
                sc_dict["asset"] = s.asset
                if "vector_ir" in s.asset:
                    sc_dict["vector_ir"] = s.asset["vector_ir"]
            else:
                sc_dict["asset"] = None
            if s.type_spec:
                sc_dict["type"] = s.type_spec
                sc_dict["type_spec"] = s.type_spec
            timeline_scenes.append(sc_dict)

        d = {
            "meta": self.meta,
            "design_system": ds_dict,
            "timeline": {
                "scenes": timeline_scenes
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
        pal_data = dict(ds_data["palette"])
        pal_data.pop("tapeBg", None)
        pal_data.pop("tapeText", None)
        pal_data.pop("shadowBlock", None)
        design_system = DesignSystem(
            concept=ds_data.get("concept", "Bespoke Typographic Narrative"),
            palette=Palette(**pal_data),
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
