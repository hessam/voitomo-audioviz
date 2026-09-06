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

  // Render Scene-Shot-Layer Graph IR
  const renderGraphLayers = () => {
    if (!activeScene) return null;

    const layers = activeScene.layers || [];
    const layout = activeScene.layout || "hero_focus";
    const sceneBadge = clampBadge(activeScene.badge || layers.find((l) => l.type === "kinetic_badge")?.text);
    const heroLayer = layers.find((l) => l.is_hero || l.weight === "900") || layers[0];
    const nonHeroLayers = layers.filter((l) => l !== heroLayer && l.type !== "kinetic_badge");
    const primaryVerb = heroLayer?.action_verb || creativeSpec?.creative_dna?.transformation_verbs?.[0] || "reveal";
    const heroVerbStyle = getVerbMotionStyle(primaryVerb, sceneProgress, springVal, ds.palette.accent, ds.palette.fg);

    // 1. BENTO GRID: Elevated 2x2 cards with subtle borders, glassmorphism, and data anchors
    if (layout === "bento_grid") {
      const bentoItems = nonHeroLayers.length > 0 ? nonHeroLayers : [
        { id: "b1", text: heroLayer?.text?.slice(0, 22) || "رویکرد ساختاری", type: "typography" },
        { id: "b2", text: "همگرایی سیگنال‌ها", type: "typography" }
      ];

      return (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            padding: "80px",
            boxSizing: "border-box",
            direction: "rtl",
            gap: "28px",
          }}
        >
          {/* Header pill & Hero */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", ...heroVerbStyle }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "6px 18px",
                borderRadius: "999px",
                border: `1px solid ${ds.palette.accent}66`,
                backgroundColor: `${ds.palette.accent}18`,
                color: ds.palette.accent,
                fontSize: "17px",
                fontWeight: 700,
                fontFamily,
              }}
            >
              <span>✦</span>
              <span>{sceneBadge}</span>
            </div>

            {heroLayer && (
              <div style={{ textAlign: "center", maxWidth: "880px" }}>
                <PersianText
                  text={heroLayer.text || ""}
                  fontFamily={fontFamily}
                  fontSize={heroLayer.text && heroLayer.text.length > 30 ? 46 : 58}
                  fontWeight={900}
                  color={ds.palette.fg}
                  startFrame={startFrame}
                  durationInFrames={18}
                />
              </div>
            )}
          </div>

          {/* 2x2 Bento Elevated Matrix */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(2, 1fr)",
              gap: "16px",
              width: "100%",
              maxWidth: "860px",
            }}
          >
            {bentoItems.slice(0, 4).map((item, idx) => {
              const itemSpring = spring({
                frame: Math.max(0, relFrame - (idx * 3 + 4)),
                fps,
                config: { damping: 12, mass: 0.7, stiffness: 140 },
              });
              const itemScale = interpolate(itemSpring, [0, 1], [0.75, 1.0], { extrapolateRight: "clamp" });
              const itemY = interpolate(itemSpring, [0, 1], [30, 0], { extrapolateRight: "clamp" });

              return (
                <div
                  key={item.id || idx}
                  style={{
                    backgroundColor: `${ds.palette.fg}0D`,
                    backdropFilter: "blur(16px)",
                    WebkitBackdropFilter: "blur(16px)",
                    border: `1px solid ${ds.palette.fg}1C`,
                    borderRadius: "16px",
                    padding: "20px 24px",
                    boxShadow: "0 12px 32px rgba(0,0,0,0.18)",
                    display: "flex",
                    alignItems: "center",
                    gap: "14px",
                    transform: `translateY(${itemY}px) scale(${itemScale})`,
                  }}
                >
                  <div
                    style={{
                      width: "40px",
                      height: "40px",
                      borderRadius: "10px",
                      backgroundColor: `${ds.palette.accent}22`,
                      border: `1px solid ${ds.palette.accent}55`,
                      color: ds.palette.accent,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "15px",
                      fontWeight: 900,
                      flexShrink: 0,
                    }}
                  >
                    ✦ {String(idx + 1).padStart(2, "0")}
                  </div>
                  <div style={{ flex: 1, overflow: "hidden" }}>
                    <PersianText
                      text={item.text || ""}
                      fontFamily={fontFamily}
                      fontSize={22}
                      fontWeight={700}
                      color={ds.palette.fg}
                      startFrame={startFrame + (idx * 3 + 4)}
                      durationInFrames={16}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    }

    // 2. SPLIT VIEWPORT: Asymmetrical dual-zone with elevated card
    if (layout === "split_viewport") {
      const cardText = nonHeroLayers[0]?.text || "تمرکز و شفافیت در تصمیم‌گیری";

      return (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "80px",
            boxSizing: "border-box",
            direction: "rtl",
            gap: "36px",
          }}
        >
          {/* Primary Hero Column */}
          <div style={{ flex: 1.2, display: "flex", flexDirection: "column", gap: "16px", ...heroVerbStyle }}>
            <div
              style={{
                alignSelf: "flex-start",
                padding: "6px 16px",
                borderRadius: "4px",
                backgroundColor: ds.palette.accent,
                color: ds.palette.bg,
                fontSize: "16px",
                fontWeight: 900,
                fontFamily,
                letterSpacing: "0.05em",
              }}
            >
              {sceneBadge}
            </div>

            {heroLayer && (
              <TapeStrip
                text={heroLayer.text || ""}
                isBlack={false}
                fontSize={heroLayer.text && heroLayer.text.length > 25 ? 46 : 56}
                fontFamily={fontFamily}
                startFrame={startFrame}
              />
            )}
          </div>

          {/* Elevated Glassmorphic Card */}
          <div
            style={{
              flex: 0.9,
              backgroundColor: `${ds.palette.fg}0C`,
              backdropFilter: "blur(18px)",
              WebkitBackdropFilter: "blur(18px)",
              border: `1px solid ${ds.palette.fg}22`,
              borderRadius: "18px",
              padding: "32px 28px",
              boxShadow: "0 18px 44px rgba(0,0,0,0.22)",
              display: "flex",
              flexDirection: "column",
              gap: "16px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: "14px", color: ds.palette.muted, fontFamily: "monospace" }}>ANCHOR // 01</span>
              <div style={{ width: "36px", height: "3px", backgroundColor: ds.palette.accent }} />
            </div>

            <PersianText
              text={cardText}
              fontFamily={fontFamily}
              fontSize={28}
              fontWeight={700}
              color={ds.palette.fg}
              startFrame={startFrame + 6}
              durationInFrames={20}
            />
          </div>
        </div>
      );
    }

    // 3. SPECIMEN LADDER: Stepped architectural typography hierarchy
    if (layout === "specimen_ladder") {
      return (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "flex-start",
            padding: "90px",
            boxSizing: "border-box",
            direction: "rtl",
            gap: "20px",
            ...heroVerbStyle,
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 18px",
              borderRadius: "999px",
              border: `1px solid ${ds.palette.accent}66`,
              backgroundColor: `${ds.palette.accent}18`,
              color: ds.palette.accent,
              fontSize: "17px",
              fontWeight: 700,
            }}
          >
            <span>✦</span>
            <span>{sceneBadge}</span>
          </div>

          {layers.filter(l => l.type === "typography").map((layer, lIdx) => {
            const isH = layer.is_hero || lIdx === 0;
            return (
              <TapeStrip
                key={layer.id}
                text={layer.text || ""}
                isBlack={!isH}
                fontSize={isH ? 50 : 34}
                fontFamily={fontFamily}
                startFrame={startFrame + lIdx * 4}
              />
            );
          })}
        </div>
      );
    }

    // 4. METRIC PUNCH: High-contrast metric/punch card
    if (layout === "metric_punch") {
      const punchVal = layers.find(l => l.weight === "900")?.text?.slice(0, 12) || "100%";
      const descVal = layers.find(l => l !== heroLayer)?.text || heroLayer?.text || "";

      return (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            padding: "80px",
            boxSizing: "border-box",
            direction: "rtl",
            gap: "24px",
            ...heroVerbStyle,
          }}
        >
          <div
            style={{
              backgroundColor: `${ds.palette.accent}16`,
              border: `2px solid ${ds.palette.accent}`,
              borderRadius: "20px",
              padding: "36px 48px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "14px",
              boxShadow: `0 16px 40px ${ds.palette.accent}22`,
            }}
          >
            <span style={{ fontSize: "76px", fontWeight: 900, color: ds.palette.accent, fontFamily }}>
              {punchVal}
            </span>
            <span style={{ fontSize: "20px", color: ds.palette.muted, fontWeight: 700 }}>
              {sceneBadge}
            </span>
          </div>

          <div style={{ maxWidth: "700px", textAlign: "center" }}>
            <PersianText
              text={descVal}
              fontFamily={fontFamily}
              fontSize={34}
              fontWeight={700}
              color={ds.palette.fg}
              startFrame={startFrame + 6}
              durationInFrames={18}
            />
          </div>
        </div>
      );
    }

    // 5. HERO FOCUS / ANCHORED CAVALRY ARCHETYPE:
    // Upper canvas (top 0-52%): Centered tape-strip typography + kinetic badge
    // Lower canvas (bottom 45%): 4x2 geometric bento matrix (Cavalry anchor)
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
          direction: "rtl",
          ...heroVerbStyle,
        }}
      >
        {/* Upper Centered Typography Block */}
        <div
          style={{
            position: "absolute",
            top: "80px",
            left: "5%",
            right: "5%",
            height: "44%",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            alignItems: "center",
            textAlign: "center",
            gap: "12px",
            zIndex: 10,
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "4px 16px",
              backgroundColor: "#000000",
              color: "#FFFFFF",
              boxShadow: "4px 4px 0px 0px #000000",
              fontSize: "16px",
              fontWeight: 800,
              fontFamily,
            }}
          >
            <span>✦</span>
            <span>{sceneBadge}</span>
          </div>

          {heroLayer && (
            <TapeStrip
              text={heroLayer.text || ""}
              isBlack={false}
              fontSize={heroLayer.text && heroLayer.text.length > 25 ? 50 : 64}
              fontFamily={fontFamily}
              startFrame={startFrame}
            />
          )}

          {nonHeroLayers[0] && (
            <TapeStrip
              text={nonHeroLayers[0].text || ""}
              isBlack={true}
              fontSize={28}
              fontFamily={fontFamily}
              startFrame={startFrame + 6}
            />
          )}
        </div>

        {/* Lower Canvas Geometric Bento Matrix (Cavalry Anchor) */}
        <BentoMatrix />
      </div>
    );
  };

  // Fallback layout renderer for standard scenes
  const renderLayout = () => {
    if (!activeScene) return null;

    // Prefer Graph IR layers
    if (activeScene.layers && activeScene.layers.length > 0) {
      return renderGraphLayers();
    }

    const commonProps = {
      content: activeScene.content,
      reveal: activeScene.reveal,
      designSystem: ds,
      startFrame,
      endFrame,
      currentTime,
      words,
      isExiting,
    };

    switch (activeScene.layout) {
      case "split_viewport":
      case "hero_focus":
        return <HeroFocus {...commonProps} />;
      case "bento_grid":
      case "specimen_ladder":
        return <SpecimenLadder {...commonProps} />;
      case "paragraph_stack":
        return <ParagraphStack {...commonProps} />;
      case "caption_panel":
        return <CaptionPanel {...commonProps} />;
      default:
        return <HeroFocus {...commonProps} />;
    }
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
          border: `1px solid ${ds.palette.fg}14`,
          pointerEvents: "none",
          zIndex: 10,
        }}
      >
        {/* Sleek corner registration ticks */}
        <span style={{ position: "absolute", top: -8, left: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.6, fontFamily: "monospace" }}>+</span>
        <span style={{ position: "absolute", top: -8, right: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.6, fontFamily: "monospace" }}>+</span>
        <span style={{ position: "absolute", bottom: -8, left: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.6, fontFamily: "monospace" }}>+</span>
        <span style={{ position: "absolute", bottom: -8, right: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.6, fontFamily: "monospace" }}>+</span>
      </div>

      {/* Top Technical Header HUD (Without REC) */}
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
        {renderLayout()}
      </div>

      {/* Bottom Technical Footer HUD with Audio Waveform Scrubber */}
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
