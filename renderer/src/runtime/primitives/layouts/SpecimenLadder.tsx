import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { GlitchDecode } from "../reveals/GlitchDecode";
import { BlockWipe } from "../reveals/BlockWipe";

export interface SpecimenLadderProps {
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
  currentTime?: number;
  words?: Array<{ word: string; start: number; end: number }>;
  isExiting?: boolean;
}

export const SpecimenLadder: React.FC<SpecimenLadderProps> = ({
  content,
  reveal,
  designSystem,
  startFrame,
  endFrame,
  currentTime = 0,
  words = [],
  isExiting = false,
}) => {
  const frame = useCurrentFrame();
  const sceneFrame = Math.max(0, frame - startFrame);
  const totalSceneFrames = Math.max(1, endFrame - startFrame);

  const fontFamily = designSystem?.type_scale?.family || "Vazirmatn, sans-serif";
  const defaultWeights = ["300", "500", "700", "900"];
  const fgColor = designSystem.palette.fg;
  const accentColor = designSystem.palette.accent;
  const mutedColor = designSystem.palette.muted;
  const margin = designSystem.grid.margin || 80;
  const alignment = designSystem.grid.alignment || "left";

  // Pick core focus phrase
  const focusText = content.length > 0 ? content[0].text : "SWISS SPECIMEN";
  const supportingText = content.length > 1 ? content.slice(1).map((c) => c.text).join(" ") : "";

  // 4 rows escalating in weight
  const ladderRows = [
    { text: focusText, weight: "300", isHero: false, color: mutedColor },
    { text: focusText, weight: "500", isHero: false, color: fgColor },
    { text: focusText, weight: "700", isHero: false, color: fgColor },
    { text: focusText, weight: "900", isHero: true, color: accentColor },
  ];

  const stagger = reveal.stagger_frames ?? 6;
  const rowDuration = 16;
  const isRtl = /[\u0600-\u06FF]/.test(focusText);

  // Font size calibrated for punchy specimen display
  const fontSize = focusText.length <= 15 ? 74 : focusText.length <= 30 ? 58 : 46;

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
        gap: "10px",
      }}
    >
      {/* Specimen Category Eyebrow */}
      <div
        style={{
          fontFamily,
          fontSize: 24,
          fontWeight: 700,
          color: mutedColor,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          marginBottom: "12px",
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <span style={{ color: accentColor }}>//</span>
        WEIGHT SPECIMEN LADDER [300 - 900]
      </div>

      {/* Escalating Weight Rows */}
      {ladderRows.map((row, idx) => {
        const rowStart = idx * stagger;
        const progress = isExiting
          ? interpolate(sceneFrame, [totalSceneFrames - 15, totalSceneFrames], [1, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })
          : interpolate(sceneFrame, [rowStart, rowStart + rowDuration], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

        return (
          <div key={idx} style={{ width: "100%", lineHeight: 1.05 }}>
            <GlitchDecode
              text={row.text}
              progress={progress}
              channelOffsetPx={reveal.channel_offset_px ?? 5}
              color={row.color}
              accentColor={accentColor}
              fontFamily={fontFamily}
              fontWeight={row.weight}
              fontSize={fontSize}
              direction={isExiting ? "reverse" : reveal.direction}
            />
          </div>
        );
      })}

      {/* Supporting Editorial Caption Block */}
      {supportingText && (
        <div
          style={{
            marginTop: "24px",
            paddingTop: "16px",
            borderTop: `1px solid ${mutedColor}33`,
            width: "100%",
            fontFamily,
            fontSize: 28,
            fontWeight: 500,
            color: mutedColor,
            lineHeight: 1.4,
            opacity: interpolate(sceneFrame, [4 * stagger, 4 * stagger + 15], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {supportingText}
        </div>
      )}
    </div>
  );
};
