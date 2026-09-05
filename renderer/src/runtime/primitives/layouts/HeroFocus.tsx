import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { GlitchDecode } from "../reveals/GlitchDecode";
import { BlockWipe } from "../reveals/BlockWipe";

export interface HeroFocusProps {
  content: Array<{ text: string; weight?: string; is_hero?: boolean }>;
  reveal: {
    primitive?: string;
    channel_offset_px?: number;
    stagger_frames?: number;
    direction?: "forward" | "reverse";
  };
  designSystem: {
    palette: { bg: string; fg: string; accent: string; muted: string };
    type_scale: { family: string; weights: string[]; ratio: number };
    grid: { alignment: string; margin: number };
  };
  startFrame: number;
  endFrame: number;
}

export const HeroFocus: React.FC<HeroFocusProps> = ({
  content,
  reveal,
  designSystem,
  startFrame,
  endFrame,
}) => {
  const frame = useCurrentFrame();
  const sceneFrame = Math.max(0, frame - startFrame);
  const totalSceneFrames = Math.max(1, endFrame - startFrame);

  // Reveal takes 40% of scene duration, clamped between 8 and 24 frames
  const revealDuration = Math.min(24, Math.max(8, Math.round(totalSceneFrames * 0.4)));
  const progress = interpolate(sceneFrame, [0, revealDuration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const mainText = content.map((c) => c.text).join(" ") || " ";
  const fontFamily = designSystem.type_scale.family || "Vazirmatn, sans-serif";
  const fgColor = designSystem.palette.fg;
  const accentColor = designSystem.palette.accent;
  const alignment = designSystem.grid.alignment || "left";
  const margin = designSystem.grid.margin || 80;

  // Responsive font size calculation based on text length to prevent overflow
  const charCount = mainText.length;
  const baseFontSize = charCount <= 12 ? 96 : charCount <= 24 ? 76 : 56;

  const isRtl = /[\u0600-\u06FF]/.test(mainText);

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: alignment === "center" ? "center" : isRtl ? "flex-end" : "flex-start",
        padding: `${margin}px`,
        boxSizing: "border-box",
        direction: isRtl ? "rtl" : "ltr",
      }}
    >
      {reveal.primitive === "block_wipe" ? (
        <BlockWipe
          text={mainText}
          progress={progress}
          color={fgColor}
          accentColor={accentColor}
          fontFamily={fontFamily}
          fontWeight={900}
          fontSize={baseFontSize}
        />
      ) : (
        <GlitchDecode
          text={mainText}
          progress={progress}
          channelOffsetPx={reveal.channel_offset_px ?? 6}
          color={fgColor}
          accentColor={accentColor}
          fontFamily={fontFamily}
          fontWeight={900}
          fontSize={baseFontSize}
          direction={reveal.direction}
        />
      )}
    </div>
  );
};
