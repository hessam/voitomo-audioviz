# AudioViz 3D Visualizer Target Visual Specifications

Reference targets for upgrading the 3 non-sphere visualizers to production Netflix/Cavalry grade.

---

## 1. Quantum Iris (`iris`)
- **Reference Image**: `iris_quantum_vortex.jpg`
- **Visual Concept**: Swirling Cosmic Energy Vortex / Multi-Strand Torus Knot.
- **Color Palette**: Electric Cyan (`#00F5D4`), Deep Violet/Magenta (`#7928CA`, `#9D4EDD`), Glowing White core.
- **Key Geometric Elements**:
  - Interwoven parametric ribbon curves (Torus Knot / Logarithmic spiral ribbons).
  - Emissive core flare pulsing to bass/mids.
  - Tangential particle spray & spark trails bursting along velocity vectors on beat transients.
- **Material & Shaders**:
  - Additive blending (`THREE.AdditiveBlending`).
  - Fresnel edge glow shader with depth falloff.
  - Dynamic hue shift based on audio frequency spectrum.

---

## 2. Monolith Field (`monolith`)
- **Reference Image**: `monolith_hex_field.jpg`
- **Visual Concept**: Brutalist Hexagonal Column Grid with Emissive Caps.
- **Color Palette**: Acid Lime / Toxic Neon Green (`#CCFF00`, `#A3E635`), Dark Slate / Basalt Gray bodies (`#121417`), Glossy reflective floor (`#08090A`).
- **Key Geometric Elements**:
  - Instanced 6-sided prism columns (`InstancedMesh` with hexagonal geometry) arranged in an axial/offset hex grid.
  - Emissive top cap surfaces that glow intensely with bass kicks.
  - Procedural height waves (Perlin noise + radial audio displacement ripples).
  - Dark reflective ground plane simulating wet asphalt / polished obsidian.
- **Material & Shaders**:
  - `MeshStandardMaterial` / custom shader with roughness and emissive multiplier.
  - Point lights floating across the grid to highlight specular column edges.

---

## 3. Neural Synapse (`neural`)
- **Reference Image**: `neural_synapse_web.jpg`
- **Visual Concept**: Constellation / Axon Ring Web with Electrical Discharges.
- **Color Palette**: Emerald / Mint Neon (`#10B981`, `#2DD4BF`), Brilliant White Nodes (`#FFFFFF`), Deep Space Void (`#030708`).
- **Key Geometric Elements**:
  - Circular / tunnel network architecture with nodes distributed around a hollow aperture.
  - Dynamic line segments (`LineSegments` or glowing tube meshes) connecting proximity nodes.
  - Synaptic firing pulses: traveling charge packets racing along filaments on transients.
  - Soft out-of-focus background bokeh particles.
- **Material & Shaders**:
  - Emissive point sprites for nodes.
  - Line material with distance attenuation and audio-reactive glow pulses.

---
