import React from "react";
import { Audio, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { HeroFocus } from "./primitives/layouts/HeroFocus";
import { SpecimenLadder } from "./primitives/layouts/SpecimenLadder";
import { ParagraphStack } from "./primitives/layouts/ParagraphStack";
import { CaptionPanel } from "./primitives/layouts/CaptionPanel";
import { PersianText } from "./primitives/PersianText";
import { TapeStrip } from "./primitives/TapeStrip";
import { BentoMatrix, GraphicTile } from "./primitives/BentoMatrix";

export interface LayerNodeInput {
  id: string;
  type: string; // "typography" | "vector_shape" | "kinetic_badge" | "clip_mask"
  text?: string;
  weight?: string;
  is_hero?: boolean;
  spatial_anchor?: string;
  action_verb?: string;
  style?: Record<string, any>;
}

export interface CreativeSpecInput {
  meta?: {
    duration?: number;
    fps?: number;
    width?: number;
    height?: number;
    total_frames?: number;
  };
  creative_dna?: {
    thesis?: string;
    emotional_contradiction?: string;
    metaphor_system?: string;
    transformation_verbs?: string[];
    palette?: { bg: string; fg: string; accent: string; muted: string };
    font_family?: string;
  };
  design_system: {
    concept?: string;
    palette: {
      bg: string;
      fg: string;
      accent: string;
      muted: string;
    };
    type_scale: {
      family: string;
      weights: string[];
      ratio: number;
    };
    grid: {
      alignment: string;
      margin: number;
      columns?: number;
    };
  };
  timeline: {
    scenes: Array<{
      id: string;
      layout: string;
      badge?: string;
      frame_range: [number, number];
      reveal: {
        primitive?: string;
        target?: string;
        channel_offset_px?: number;
        stagger_frames?: number;
        direction?: "forward" | "reverse";
      };
      content: Array<{
        text: string;
        weight?: string;
        is_hero?: boolean;
      }>;
      layers?: LayerNodeInput[];
      camera_dynamic?: string;
      motion?: Record<string, any>;
    }>;
  };
}

export interface SwissRuntimeProps {
  creativeSpec?: CreativeSpecInput;
  audioSrc?: string;
  words?: Array<{ word: string; start: number; end: number }>;
}

/**
 * Maps transformation verbs (compress, invert, accrete, shatter, reconcile)
 * directly to Remotion physical spring/interpolate styles.
 */
function getVerbMotionStyle(
  verb: string,
  progress: number,
  springVal: number,
  accentColor: string,
  fgColor: string
): React.CSSProperties {
  switch (verb) {
    case "compress": {
      // Elements converge under spatial pressure towards center with high spring tension
      const scaleX = interpolate(progress, [0, 0.7, 1], [1.3, 0.95, 1.0], { extrapolateRight: "clamp" });
      const scaleY = interpolate(progress, [0, 0.7, 1], [0.8, 1.05, 1.0], { extrapolateRight: "clamp" });
      const ls = interpolate(progress, [0, 1], [0.15, -0.015], { extrapolateRight: "clamp" });
      return {
        transform: `scale(${scaleX}, ${scaleY})`,
        letterSpacing: `${ls}em`,
      };
    }
    case "invert": {
      // Dynamic contrast flip or polar tilt
      const filter = progress < 0.45 ? "contrast(1.3)" : "none";
      const rot = interpolate(progress, [0, 1], [-4, 0], { extrapolateRight: "clamp" });
      return {
        filter,
        transform: `rotate(${rot}deg)`,
      };
    }
    case "accrete": {
      // Staggered geometric accumulation of mass and typography
      const translateY = interpolate(progress, [0, 1], [40, 0], { extrapolateRight: "clamp" });
      const opacity = interpolate(progress, [0, 0.3, 1], [0, 0.85, 1.0], { extrapolateRight: "clamp" });
      return {
        transform: `translateY(${translateY}px)`,
        opacity,
      };
    }
    case "shatter": {
      // Controlled outward dispersal snapping into structural tension
      const scale = interpolate(progress, [0, 0.35, 1], [0.88, 1.06, 1.0], { extrapolateRight: "clamp" });
      const blur = interpolate(progress, [0, 1], [6, 0], { extrapolateRight: "clamp" });
      return {
        transform: `scale(${scale})`,
        filter: blur > 0.2 ? `blur(${blur}px)` : "none",
      };
    }
    case "reconcile": {
      // Harmonious synthesis of previous opposing tensions into balanced stillness
      const scale = interpolate(progress, [0, 0.8, 1], [0.95, 1.02, 1.0], { extrapolateRight: "clamp" });
      const opacity = interpolate(progress, [0, 1], [0.2, 1.0], { extrapolateRight: "clamp" });
      return {
        transform: `scale(${scale})`,
        opacity,
      };
    }
    default:
      return {};
  }
}

/**
 * Calculates camera translation and scale from camera_dynamic.
 */
function getCameraTransform(camera: string, progress: number): string {
  switch (camera) {
    case "push": {
      const scale = interpolate(progress, [0, 1], [1.0, 1.07], { extrapolateRight: "clamp" });
      return `scale(${scale})`;
    }
    case "pan_left": {
      const x = interpolate(progress, [0, 1], [30, -30], { extrapolateRight: "clamp" });
      return `translateX(${x}px)`;
    }
    case "pan_right": {
      const x = interpolate(progress, [0, 1], [-30, 30], { extrapolateRight: "clamp" });
      return `translateX(${x}px)`;
    }
    case "drift": {
      const scale = interpolate(progress, [0, 1], [1.02, 1.06], { extrapolateRight: "clamp" });
      const y = interpolate(progress, [0, 1], [12, -12], { extrapolateRight: "clamp" });
      return `scale(${scale}) translateY(${y}px)`;
    }
    case "static":
    default:
      return "none";
  }
}

function clampBadge(text?: string, fallback: string = "نکته کلیدی"): string {
  if (!text || typeof text !== "string") return fallback;
  const words = text.trim().replace(/\n/g, " ").split(/\s+/);
  if (words.length === 0) return fallback;
  const clamped = words.slice(0, 3).join(" ");
  return clamped.length > 20 ? clamped.slice(0, 20).trim() : clamped;
}

export const SwissRuntime: React.FC<SwissRuntimeProps> = ({ creativeSpec, audioSrc, words = [] }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  // Design system with procedural harmonic palette
  const ds = creativeSpec?.design_system ?? {
    concept: creativeSpec?.creative_dna?.metaphor_system || "Architectural Kinetic Specimen",
    palette: creativeSpec?.creative_dna?.palette || { bg: "#1C1412", fg: "#F7F1ED", accent: "#E05638", muted: "#8C7D75" },
    type_scale: { family: creativeSpec?.creative_dna?.font_family || "Dana, Vazirmatn, sans-serif", weights: ["300", "500", "700", "900"], ratio: 1.333 },
    grid: { alignment: "center", margin: 80, columns: 12 },
  };

  const fontFamily = creativeSpec?.creative_dna?.font_family || ds.type_scale.family || "Dana, Vazirmatn, sans-serif";
  const scenes = creativeSpec?.timeline?.scenes ?? [];
  const totalFrames = creativeSpec?.meta?.total_frames || 300;
  const margin = ds.grid?.margin || 80;

  // Active scene selection
  let activeSceneIdx = scenes.findIndex((s) => frame >= s.frame_range[0] && frame < s.frame_range[1]);
  if (activeSceneIdx === -1 && scenes.length > 0) {
    activeSceneIdx = frame < scenes[0].frame_range[0] ? 0 : scenes.length - 1;
  }
  const activeScene = scenes[activeSceneIdx];

  const startFrame = activeScene?.frame_range[0] ?? 0;
  const endFrame = activeScene?.frame_range[1] ?? totalFrames;
  const sceneDuration = Math.max(1, endFrame - startFrame);
  const relFrame = Math.max(0, frame - startFrame);
  const sceneProgress = Math.min(1, relFrame / sceneDuration);

  // Remotion spring calculation for punchy physics
  const springVal = spring({
    frame: relFrame,
    fps,
    config: { damping: 14, mass: 0.8, stiffness: 120 },
  });

  const isExiting = activeScene ? (endFrame - frame) <= 12 : false;
  const currentTime = frame / fps;
  const cameraDynamic = activeScene?.camera_dynamic || "push";
  const cameraTransform = getCameraTransform(cameraDynamic, sceneProgress);

  // Accumulating Multi-Line Tape Strips
  // Stacks 1 to 3 phrases sequentially before clearing, matching Canva/Cavalry kinetic flow
  const cycleIdx = activeSceneIdx % 3; // 0, 1, 2
  const showBento = (cycleIdx === 2) || (activeSceneIdx === scenes.length - 1) || activeScene?.layout === "bento_grid";

  const stackedScenes: Array<{ scene: (typeof scenes)[0]; isCurrent: boolean }> = [];
  for (let offset = cycleIdx; offset >= 0; offset--) {
    const sIdx = activeSceneIdx - offset;
    if (sIdx >= 0 && scenes[sIdx]) {
      stackedScenes.push({ scene: scenes[sIdx], isCurrent: offset === 0 });
    }
  }

  const renderLayout = () => {
    if (!activeScene) return null;

    const currentBadge = clampBadge(activeScene.badge || activeScene.layers?.find(l => l.type === "kinetic_badge")?.text);

    return (
      <div
        style={{
          width: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "8px",
          direction: "rtl",
        }}
      >
        {/* Kinetic Badge */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "4px 16px",
            backgroundColor: "#000000",
            color: "#FFFFFF",
            boxShadow: "4px 4px 0px 0px #000000",
            fontSize: "15px",
            fontWeight: 800,
            fontFamily,
            marginBottom: "6px",
          }}
        >
          <span>✦</span>
          <span>{currentBadge}</span>
        </div>

        {/* Stacked Chunky Tape Strips */}
        {stackedScenes.map(({ scene, isCurrent }) => {
          const sText = scene.layers?.find(l => l.is_hero || l.weight === "900")?.text || scene.content?.find(c => c.is_hero)?.text || scene.content?.[0]?.text || "";
          if (!sText) return null;
          const sStart = scene.frame_range[0];
          const baseSize = stackedScenes.length > 2 ? 42 : (stackedScenes.length === 2 ? 50 : 58);
          const fontSize = sText.length > 25 ? baseSize - 6 : baseSize;

          return (
            <TapeStrip
              key={scene.id}
              text={sText}
              isBlack={!isCurrent}
              fontSize={fontSize}
              fontFamily={fontFamily}
              startFrame={sStart}
            />
          );
        })}
      </div>
    );
  };

  return (
    <div
      style={{
        width: `${width}px`,
        height: `${height}px`,
        backgroundColor: ds.palette.bg,
        position: "relative",
        overflow: "hidden",
        fontFamily,
      }}
    >
      {audioSrc && <Audio src={audioSrc} />}

      {/* Swiss Architectural Outer Margin Grid Box */}
      <div
        style={{
          position: "absolute",
          top: `${margin - 24}px`,
          bottom: `${margin - 24}px`,
          left: `${margin - 24}px`,
          right: `${margin - 24}px`,
          border: `1px solid ${ds.palette.fg}10`,
          pointerEvents: "none",
          zIndex: 10,
        }}
      >
        {/* Sleek corner registration ticks */}
        <span style={{ position: "absolute", top: -8, left: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.4, fontFamily: "monospace" }}>+</span>
        <span style={{ position: "absolute", top: -8, right: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.4, fontFamily: "monospace" }}>+</span>
        <span style={{ position: "absolute", bottom: -8, left: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.4, fontFamily: "monospace" }}>+</span>
        <span style={{ position: "absolute", bottom: -8, right: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.4, fontFamily: "monospace" }}>+</span>
      </div>

      {/* Top Technical Header HUD (Silenced) */}
      <div
        style={{
          position: "absolute",
          top: "28px",
          left: `${margin}px`,
          right: `${margin}px`,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 13,
          fontFamily: "monospace, sans-serif",
          color: ds.palette.muted,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          whiteSpace: "nowrap",
          opacity: 0.28,
          zIndex: 20,
        }}
      >
        {/* Concept / Taxonomy */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: ds.palette.accent, fontWeight: 900 }}>SWISS //</span>
          <span style={{ color: ds.palette.fg, opacity: 0.75 }}>
            {clampBadge(creativeSpec?.creative_dna?.thesis, "KINETIC SPECIMEN")}
          </span>
        </div>

        {/* Scene Index Stamp: 01 // 05 */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 700 }}>
          <span style={{ color: ds.palette.fg }}>
            SCENE [{String(activeSceneIdx + 1).padStart(2, "0")}/{String(scenes.length || 1).padStart(2, "0")}]
          </span>
          <span style={{ color: ds.palette.accent }}>
            // {activeScene?.layout?.toUpperCase().replace("_", " ") || "HERO"}
          </span>
        </div>

        {/* Font Specimen Tag */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <span>{fontFamily.split(",")[0].trim().toUpperCase()}</span>
          <span style={{ opacity: 0.35 }}>|</span>
          <span>[1080×1080]</span>
        </div>
      </div>

      {/* Dynamic Motion Viewport with Camera Dynamic Transforms */}
      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
          zIndex: 5,
          transform: cameraTransform,
          transition: "transform 0.05s linear",
        }}
      >
        {/* Kinetic Typographic Stage (Upper 46% if Bento active, centered 64% otherwise) */}
        <div
          style={{
            position: "absolute",
            top: showBento ? "65px" : "18%",
            left: "5%",
            right: "5%",
            height: showBento ? "46%" : "64%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            textAlign: "center",
            zIndex: 10,
            transition: "all 0.15s ease",
          }}
        >
          {renderLayout()}
        </div>

        {/* Lower Canvas Geometric Bento Matrix (Anchors every 3rd phrase & summary moments) */}
        {showBento && (
          <BentoMatrix style={{ position: "absolute", inset: "54% 5% 6% 5%", zIndex: 5 }} />
        )}
      </div>

      {/* Bottom Technical Footer HUD (Silenced) */}
      <div
        style={{
          position: "absolute",
          bottom: "26px",
          left: `${margin}px`,
          right: `${margin}px`,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: 13,
          fontFamily: "monospace, sans-serif",
          color: ds.palette.muted,
          letterSpacing: "0.06em",
          opacity: 0.28,
          zIndex: 20,
        }}
      >
        {/* Dynamic Motion Readout */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: ds.palette.accent, fontWeight: 900 }}>MOTION:</span>
          <span style={{ color: ds.palette.fg, opacity: 0.85 }}>
            {cameraDynamic.toUpperCase()} // {activeScene?.layers?.[0]?.action_verb?.toUpperCase() || "REVEAL"}
          </span>
        </div>

        {/* Kinetic Bottom Audio Waveform/Tick Scrubber */}
        <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "15px" }}>
          {[35, 70, 25, 90, 50, 85, 30, 95, 60, 40, 80, 20, 75, 45, 65, 35, 80, 50].map((h, i) => {
            const dynamicH = Math.max(15, Math.min(100, h + Math.sin((frame + i * 4) * 0.35) * 35));
            return (
              <span
                key={i}
                style={{
                  width: "2px",
                  height: `${dynamicH}%`,
                  backgroundColor: i % 4 === 0 ? ds.palette.accent : `${ds.palette.fg}44`,
                  display: "inline-block",
                  transition: "height 0.08s ease",
                }}
              />
            );
          })}
        </div>

        {/* Frame Readout */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span>FRM: {String(frame).padStart(4, "0")} / {String(totalFrames).padStart(4, "0")}</span>
          <span style={{ color: ds.palette.accent }}>[30 FPS]</span>
        </div>
      </div>
    </div>
  );
};
