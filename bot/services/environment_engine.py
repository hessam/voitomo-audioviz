"""
Environment Engine (The Atmosphere)
Part of Astra's 4-Engine Negotiated Compiler.

Owns 100% of canvas depth and spatial texture.
Rules: Never renders a flat solid hex.
Generative Vocabulary:
- Dynamic isometric blueprint grids with coordinate ticks.
- Organic gradient meshes with safe harmonic color stops.
- Halftone noise / dot matrices.
- Celestial floating particle dust.
- Studio minimal backdrops with radial key lighting.
Contract: Receives saliency_budget and dims contrast when text/asset is dense.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
import hashlib


@dataclass
class EnvironmentSpec:
    style: str  # "isometric_grid" | "gradient_mesh" | "halftone_dots" | "celestial_dust" | "studio_minimal"
    bg_color: str
    accent_color: str
    fg_color: str
    contrast: float = 0.25  # Contrast ratio (0.10 to 0.45) dictated by Saliency Budget
    grid_size: int = 54
    grain_intensity: float = 0.12
    lighting_angle: int = 135
    gradient_stops: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EnvironmentEngine:
    """
    Synthesizes procedural environment shaders and spatial atmospheres.
    """

    STYLES = [
        "isometric_grid",
        "gradient_mesh",
        "halftone_dots",
        "celestial_dust",
        "studio_minimal"
    ]

    @classmethod
    def propose(
        cls,
        seed_text: str,
        palette: Any,
        saliency_contrast: float = 0.25,
        scene_idx: int = 0,
        world: str = "editorial"
    ) -> EnvironmentSpec:
        """
        Generate procedural atmosphere according to world archetype and saliency budget.
        """
        bg = getattr(palette, "bg", "#5537ED")
        fg = getattr(palette, "fg", "#FFFFFF")
        accent = getattr(palette, "accent", "#FF5500")

        # Cycle environment style harmonically per scene
        if world == "kinetic-poster":
            # Music / poetry: celestial dust or smooth gradient mesh
            style = "celestial_dust" if scene_idx % 2 == 0 else "gradient_mesh"
        elif world == "pop-bento":
            # Commercial: halftone dots or isometric grid
            style = "halftone_dots" if scene_idx % 2 == 0 else "isometric_grid"
        else:
            # Editorial: isometric grid, studio minimal, or gradient mesh
            styles = ["isometric_grid", "studio_minimal", "gradient_mesh", "halftone_dots"]
            style = styles[scene_idx % len(styles)]

        # Clamped contrast based on saliency budget
        contrast = max(0.08, min(0.35, saliency_contrast))

        # Dynamic gradient stops derived from bg and accent
        gradient_stops = [
            bg,
            f"{bg}DD",
            f"{accent}33",
            bg
        ]

        return EnvironmentSpec(
            style=style,
            bg_color=bg,
            accent_color=accent,
            fg_color=fg,
            contrast=contrast,
            grid_size=48 if style == "isometric_grid" else 64,
            grain_intensity=0.10 if style == "studio_minimal" else 0.16,
            lighting_angle=135 + (scene_idx * 25) % 90,
            gradient_stops=gradient_stops
        )
