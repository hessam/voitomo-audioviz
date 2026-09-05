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
}

export const SwissRuntime: React.FC<SwissRuntimeProps> = ({ creativeSpec, audioSrc }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  // Fallback defaults if creativeSpec is missing (100% dynamic, zero hardcoded content)
  const ds = creativeSpec?.design_system ?? {
    palette: { bg: "#0A0B0E", fg: "#F8FAFC", accent: "#E11D48", muted: "#64748B" },
    type_scale: { family: "Vazirmatn, sans-serif", weights: ["300", "500", "700", "900"], ratio: 1.333 },
    grid: { alignment: "left", margin: 80, columns: 12 },
  };

  const scenes = creativeSpec?.timeline?.scenes ?? [];

  // Determine active scene based on current frame
  let activeScene = scenes.find((s) => frame >= s.frame_range[0] && frame < s.frame_range[1]);
  if (!activeScene && scenes.length > 0) {
    activeScene = frame < scenes[0].frame_range[0] ? scenes[0] : scenes[scenes.length - 1];
  }

  const renderLayout = () => {
    if (!activeScene) {
      return null;
    }

    const startFrame = activeScene.frame_range[0];
    const endFrame = activeScene.frame_range[1];

    switch (activeScene.layout) {
      case "hero_focus":
        return (
          <HeroFocus
            content={activeScene.content}
            reveal={activeScene.reveal}
            designSystem={ds}
            startFrame={startFrame}
            endFrame={endFrame}
          />
        );
      case "specimen_ladder":
        return (
          <SpecimenLadder
            content={activeScene.content}
            reveal={activeScene.reveal}
            designSystem={ds}
            startFrame={startFrame}
            endFrame={endFrame}
          />
        );
      case "paragraph_stack":
        return (
          <ParagraphStack
            content={activeScene.content}
            reveal={activeScene.reveal}
            designSystem={ds}
            startFrame={startFrame}
            endFrame={endFrame}
          />
        );
      case "caption_panel":
        return (
          <CaptionPanel
            content={activeScene.content}
            designSystem={ds}
            startFrame={startFrame}
            endFrame={endFrame}
          />
        );
      default:
        return (
          <HeroFocus
            content={activeScene.content}
            reveal={activeScene.reveal}
            designSystem={ds}
            startFrame={startFrame}
            endFrame={endFrame}
          />
        );
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
      }}
    >
      {audioSrc && <Audio src={audioSrc} />}
      {renderLayout()}
    </div>
  );
};
