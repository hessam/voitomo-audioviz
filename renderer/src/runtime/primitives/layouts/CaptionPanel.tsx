import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

export interface CaptionPanelProps {
  content: Array<{ text: string; weight?: string; is_hero?: boolean }>;
  designSystem: {
    palette: { bg: string; fg: string; accent: string; muted: string };
    type_scale: { family: string; weights: string[]; ratio: number };
    grid: { alignment: string; margin: number };
  };
  startFrame: number;
  endFrame: number;
}

export const CaptionPanel: React.FC<CaptionPanelProps> = ({
  content,
  designSystem,
  startFrame,
  endFrame,
}) => {
  const frame = useCurrentFrame();
  const sceneFrame = Math.max(0, frame - startFrame);

  // Clean fade in over 10 frames
  const opacity = interpolate(sceneFrame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const fontFamily = designSystem.type_scale.family || "Vazirmatn, sans-serif";
  const fgColor = designSystem.palette.fg;
  const mutedColor = designSystem.palette.muted;
  const margin = designSystem.grid.margin || 80;
  const alignment = designSystem.grid.alignment || "left";

  const isRtl = content.some((c) => /[\u0600-\u06FF]/.test(c.text));

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
        alignItems: alignment === "center" ? "center" : isRtl ? "flex-end" : "flex-start",
        padding: `${margin}px`,
        boxSizing: "border-box",
        direction: isRtl ? "rtl" : "ltr",
        opacity,
      }}
    >
      <div
        style={{
          borderLeft: isRtl ? "none" : `3px solid ${designSystem.palette.accent}`,
          borderRight: isRtl ? `3px solid ${designSystem.palette.accent}` : "none",
          paddingLeft: isRtl ? 0 : "24px",
          paddingRight: isRtl ? "24px" : 0,
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        {content.map((item, idx) => (
          <div
            key={idx}
            style={{
              fontFamily,
              fontWeight: 400,
              fontSize: 24,
              color: idx === 0 ? fgColor : mutedColor,
              letterSpacing: "0.04em",
              textTransform: isRtl ? "none" : "uppercase",
              fontStyle: "italic",
            }}
          >
            {item.text}
          </div>
        ))}
      </div>
    </div>
  );
};
