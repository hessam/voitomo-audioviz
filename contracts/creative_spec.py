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
    layout: str  # "hero_focus" | "specimen_ladder" | "paragraph_stack" | "caption_panel"
    frame_range: List[int]  # [start_frame, end_frame]
    reveal: RevealConfig
    content: List[SceneContent]
    motion: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CreativeSpec:
    meta: Dict[str, Any]
    design_system: DesignSystem
    scenes: List[Scene]

    def to_dict(self) -> Dict[str, Any]:
        return {
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
                        "motion": s.motion
                    }
                    for s in self.scenes
                ]
            }
        }

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
