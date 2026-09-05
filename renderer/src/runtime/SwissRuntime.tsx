import React from "react";
import { Audio, useCurrentFrame, useVideoConfig } from "remotion";
import { HeroFocus } from "./primitives/layouts/HeroFocus";
import { SpecimenLadder } from "./primitives/layouts/SpecimenLadder";
import { ParagraphStack } from "./primitives/layouts/ParagraphStack";
import { CaptionPanel } from "./primitives/layouts/CaptionPanel";

export interface CreativeSpecInput {
  meta?: {
    duration?: number;
    fps?: number;
    width?: number;
    height?: number;
    total_frames?: number;
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
    motion_signature?: {
      chunking?: string;
      stagger_frames?: number;
      reveal_direction?: string;
      corruption_density?: number;
    };
  };
  timeline: {
    scenes: Array<{
      id: string;
      layout: string;
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
      motion?: Record<string, any>;
    }>;
  };
}

export interface SwissRuntimeProps {
  creativeSpec?: CreativeSpecInput;
  audioSrc?: string;
  words?: Array<{ word: string; start: number; end: number }>;
}

export const SwissRuntime: React.FC<SwissRuntimeProps> = ({ creativeSpec, audioSrc, words = [] }) => {
  const frame = useCurrentFrame();
  const { width, height, fps } = useVideoConfig();

  // Fallback defaults if creativeSpec is missing (100% dynamic, zero hardcoded content)
  const ds = creativeSpec?.design_system ?? {
    concept: "Swiss Kinetic Specimen",
    palette: { bg: "#0A0B0E", fg: "#F8FAFC", accent: "#E11D48", muted: "#64748B" },
    type_scale: { family: "Vazirmatn, sans-serif", weights: ["300", "500", "700", "900"], ratio: 1.333 },
    grid: { alignment: "left", margin: 80, columns: 12 },
  };

  const scenes = creativeSpec?.timeline?.scenes ?? [];
  const totalFrames = creativeSpec?.meta?.total_frames || 300;
  const totalSec = (totalFrames / fps).toFixed(1);
  const currentSec = (frame / fps).toFixed(1);

  // Determine active scene based on current frame
  let activeSceneIdx = scenes.findIndex((s) => frame >= s.frame_range[0] && frame < s.frame_range[1]);
  if (activeSceneIdx === -1 && scenes.length > 0) {
    activeSceneIdx = frame < scenes[0].frame_range[0] ? 0 : scenes.length - 1;
  }
  const activeScene = scenes[activeSceneIdx];

  const margin = ds.grid.margin || 80;
  const isExiting = activeScene ? (activeScene.frame_range[1] - frame) <= 15 : false;
  const currentTime = frame / fps;

  const renderLayout = () => {
    if (!activeScene) {
      return null;
    }

    const startFrame = activeScene.frame_range[0];
    const endFrame = activeScene.frame_range[1];

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
      case "hero_focus":
        return <HeroFocus {...commonProps} />;
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
        fontFamily: ds.type_scale.family || "Vazirmatn, sans-serif",
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
        {/* Corner Crosshair Registration Marks */}
        <span style={{ position: "absolute", top: -8, left: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.6, fontFamily: "monospace" }}>+</span>
        <span style={{ position: "absolute", top: -8, right: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.6, fontFamily: "monospace" }}>+</span>
        <span style={{ position: "absolute", bottom: -8, left: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.6, fontFamily: "monospace" }}>+</span>
        <span style={{ position: "absolute", bottom: -8, right: -5, fontSize: 13, color: ds.palette.muted, opacity: 0.6, fontFamily: "monospace" }}>+</span>
      </div>

      {/* Top Technical Header HUD */}
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
        {/* Timecode & Alignment */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px", whiteSpace: "nowrap" }}>
          <span style={{ color: ds.palette.accent, fontWeight: 900 }}>● REC</span>
          <span>{currentSec}s / {totalSec}s</span>
          <span style={{ opacity: 0.35 }}>|</span>
          <span>ALIGN // {ds.grid.alignment.toUpperCase()}</span>
        </div>

        {/* Scene Indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontWeight: 700, whiteSpace: "nowrap" }}>
          <span style={{ color: ds.palette.fg }}>
            SCENE [{String(activeSceneIdx + 1).padStart(2, "0")}/{String(scenes.length || 1).padStart(2, "0")}]
          </span>
          <span style={{ color: ds.palette.accent }}>
            // {activeScene?.layout.toUpperCase().replace("_", " ") || "HERO"}
          </span>
        </div>

        {/* Specimen Tag */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", whiteSpace: "nowrap" }}>
          <span>VAZIRMATN</span>
          <span style={{ opacity: 0.4 }}>[1080×1080]</span>
        </div>
      </div>

      {/* Active Scene Layout */}
      <div style={{ width: "100%", height: "100%", position: "relative", zIndex: 5 }}>
        {renderLayout()}
      </div>

      {/* Bottom Technical Footer HUD */}
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
        {/* Concept Moniker */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", maxWidth: "450px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          <span style={{ color: ds.palette.accent, fontWeight: 900 }}>ARCHIVE:</span>
          <span style={{ color: ds.palette.fg, opacity: 0.85 }}>{ds.concept || "SWISS KINETIC SPECIMEN"}</span>
        </div>

        {/* Dynamic Audio Rhythmic Tick Meter */}
        <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "14px" }}>
          {[35, 70, 25, 90, 50, 85, 30, 95, 60, 40, 80, 20, 75, 45].map((h, i) => {
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
