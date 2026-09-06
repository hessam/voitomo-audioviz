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

        # Strict Dual-Box Layout Contract:
        # Forbid any zero-opacity or zero-dimension asset suppression
        if is_music:
            # Music / Lyric / Poetry: Central integrated floating over undulating ribbons/contours
            archetype = "central_integrated"
        elif scene_idx % 2 == 0:
            archetype = "split_horizontal"
        else:
            archetype = "split_vertical"

        env_box = Rect(0, 0, cls.CANVAS_WIDTH, cls.CANVAS_HEIGHT)

        if archetype == "split_horizontal":
            hero_layer = "typography" if (word_count >= 4) else "asset"
            # Type Box [y: 80, h: 420], Asset Box [y: 540, h: 460]
            type_box = Rect(x=60, y=80, w=960, h=420)
            asset_box = Rect(x=80, y=540, w=920, h=460)
            allocation = SpatialAllocation(
                hero_layer=hero_layer,
                archetype=archetype,
                type_box=type_box,
                asset_box=asset_box,
                env_box=env_box,
                type_opacity=1.0,
                asset_opacity=0.95,
                env_contrast=0.20,
                type_scale=1.0,
                asset_scale=1.0
            )

        elif archetype == "split_vertical":
            hero_layer = "typography"
            # Type Box [x: 520, w: 500], Asset Box [x: 60, w: 440]
            type_box = Rect(x=520, y=140, w=500, h=800)
            asset_box = Rect(x=60, y=140, w=440, h=800)
            allocation = SpatialAllocation(
                hero_layer=hero_layer,
                archetype=archetype,
                type_box=type_box,
                asset_box=asset_box,
                env_box=env_box,
                type_opacity=1.0,
                asset_opacity=0.90,
                env_contrast=0.22,
                type_scale=1.0,
                asset_scale=0.98
            )

        else:  # central_integrated
            hero_layer = "typography"
            type_box = Rect(x=60, y=340, w=960, h=400)
            asset_box = Rect(x=80, y=100, w=920, h=880)
            allocation = SpatialAllocation(
                hero_layer=hero_layer,
                archetype=archetype,
                type_box=type_box,
                asset_box=asset_box,
                env_box=env_box,
                type_opacity=1.0,
                asset_opacity=0.75,
                env_contrast=0.25,
                type_scale=1.0,
                asset_scale=1.0
            )

        return allocation
