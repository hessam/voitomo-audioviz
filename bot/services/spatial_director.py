"""
Spatial Director Engine (The Arbiter & Conductor)
Part of Astra's 4-Engine Negotiated Compiler.

Allocates canvas real estate (Rect(x, y, w, h)) and visual weight budgets.
Applies the Conflict Firewall and Saliency Budget:
- hero_layer: "typography" | "asset" | "environment"
- Non-hero layers automatically drop opacity and scale by ~50% to guarantee zero visual competition.
- Conflict Firewall prevents overlapping dense typography and primary visual metaphors.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional


@dataclass
class Rect:
    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> Dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass
class SpatialAllocation:
    hero_layer: str  # "typography" | "asset" | "environment"
    archetype: str   # "typography_dominant" | "asset_dominant" | "split_contrast"
    type_box: Rect
    asset_box: Rect
    env_box: Rect
    type_opacity: float = 1.0
    asset_opacity: float = 1.0
    env_contrast: float = 0.25
    type_scale: float = 1.0
    asset_scale: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hero_layer": self.hero_layer,
            "archetype": self.archetype,
            "type_box": self.type_box.to_dict(),
            "asset_box": self.asset_box.to_dict(),
            "env_box": self.env_box.to_dict(),
            "typeBox": self.type_box.to_dict(),
            "assetBox": self.asset_box.to_dict(),
            "envBox": self.env_box.to_dict(),
            "type_opacity": self.type_opacity,
            "asset_opacity": self.asset_opacity,
            "env_contrast": self.env_contrast,
            "type_scale": self.type_scale,
            "asset_scale": self.asset_scale,
        }


class SpatialDirectorEngine:
    """
    Arbiter of the 1080x1080 canvas.
    Negotiates spatial layouts and enforces the Saliency Budget.
    """

    CANVAS_WIDTH = 1080
    CANVAS_HEIGHT = 1080

    @classmethod
    def allocate(
        cls,
        type_proposal: Dict[str, Any],
        asset_proposal: Optional[Dict[str, Any]],
        scene_idx: int,
        total_scenes: int,
        is_music: bool = False
    ) -> SpatialAllocation:
        """
        Negotiate canvas real estate between Type and Asset engines.
        """
        has_asset = bool(asset_proposal and asset_proposal.get("asset_type"))
        is_hero_candidate = type_proposal.get("is_hero", False)
        word_count = len(type_proposal.get("text", "").split())

        # Scene Archetype Selection
        if is_music:
            # Music / Lyric / Poetry is strictly typography-first
            archetype = "typography_dominant"
        elif not has_asset:
            archetype = "typography_dominant"
        elif scene_idx == 0:
            # First scene: strong typographic hook
            archetype = "typography_dominant"
        elif scene_idx == total_scenes - 1:
            # Final resolution: Call to action or punchy conclusion
            archetype = "split_contrast"
        elif scene_idx % 3 == 1:
            # Cyclic rhythm: Scene A (Visual Metaphor Dominant)
            archetype = "asset_dominant"
        elif scene_idx % 3 == 2:
            # Scene C (Dual Contrast: 50/50 Split)
            archetype = "split_contrast"
        else:
            archetype = "typography_dominant"

        # Conflict Firewall:
        # If Type Engine proposes massive text (>6 words) AND archetype is asset_dominant,
        # prevent occlusion by falling back to split_contrast.
        if archetype == "asset_dominant" and word_count >= 6:
            archetype = "split_contrast"

        env_box = Rect(0, 0, cls.CANVAS_WIDTH, cls.CANVAS_HEIGHT)

        if archetype == "asset_dominant":
            hero_layer = "asset"
            # 70% Asset upper/central, 30% bottom subtitle tape
            asset_box = Rect(x=80, y=90, w=920, h=640)
            type_box = Rect(x=60, y=770, w=960, h=250)
            # Saliency Budget: Hero asset 100%, non-hero typography secondary
            allocation = SpatialAllocation(
                hero_layer=hero_layer,
                archetype=archetype,
                type_box=type_box,
                asset_box=asset_box,
                env_box=env_box,
                type_opacity=0.92,
                asset_opacity=1.0,
                env_contrast=0.18,  # Dim environment contrast to avoid visual clutter
                type_scale=0.95,
                asset_scale=1.0
            )

        elif archetype == "split_contrast":
            # 50/50 Split Viewport
            hero_layer = "typography"
            type_box = Rect(x=60, y=80, w=960, h=450)
            asset_box = Rect(x=80, y=550, w=920, h=470)
            allocation = SpatialAllocation(
                hero_layer=hero_layer,
                archetype=archetype,
                type_box=type_box,
                asset_box=asset_box,
                env_box=env_box,
                type_opacity=1.0,
                asset_opacity=0.88,
                env_contrast=0.22,
                type_scale=1.0,
                asset_scale=0.95
            )

        else:  # typography_dominant
            hero_layer = "typography"
            # 90% Fullscreen poster type, asset hidden or subtle watermark
            type_box = Rect(x=60, y=140, w=960, h=800)
            asset_box = Rect(x=0, y=0, w=0, h=0)
            allocation = SpatialAllocation(
                hero_layer=hero_layer,
                archetype=archetype,
                type_box=type_box,
                asset_box=asset_box,
                env_box=env_box,
                type_opacity=1.0,
                asset_opacity=0.0,
                env_contrast=0.28,
                type_scale=1.0,
                asset_scale=0.0
            )

        return allocation
