import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

export interface PersianTextProps {
  text: string;
  fontFamily?: string;
  fontWeight?: string | number;
  fontSize?: number | string;
  color?: string;
  lineHeight?: number | string;
  letterSpacing?: string;
  startFrame?: number;
  durationInFrames?: number;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Tokenizes text to wrap digits, percentages, and Latin words in <bdi dir="ltr">
 * while leaving Persian words in continuous flow to preserve native cursive ligatures.
 */
function renderShapedRtlContent(text: string): React.ReactNode[] {
  if (!text) return [];

  // Match sequences of Latin characters, digits, percentages, or English symbols
  const regex = /([a-zA-Z0-9$€£¥%+\-/*#@:_.]+|[^\sa-zA-Z0-9$€£¥%+\-/*#@:_.]+|\s+)/g;
  const parts = text.match(regex) || [text];

  return parts.map((part, index) => {
    const isLatinOrNumeric = /^[a-zA-Z0-9$€£¥%+\-/*#@:_.]+$/.test(part);
    if (isLatinOrNumeric) {
      return (
        <bdi
          key={index}
          dir="ltr"
          style={{
            display: "inline-block",
            unicodeBidi: "isolate",
            margin: "0 2px",
          }}
        >
          {part}
        </bdi>
      );
    }
    return <span key={index}>{part}</span>;
  });
}

export const PersianText: React.FC<PersianTextProps> = ({
  text,
  fontFamily = "Dana, Vazirmatn, sans-serif",
  fontWeight = 700,
  fontSize = 48,
  color = "#FFFFFF",
  lineHeight = 1.35,
  letterSpacing = "-0.01em",
  startFrame = 0,
  durationInFrames = 20,
  className,
  style = {},
}) => {
  const frame = useCurrentFrame();
  const relFrame = Math.max(0, frame - startFrame);

  // Smooth ease-out reveal progression: 0 (masked) to 1 (fully revealed)
  const progress = interpolate(relFrame, [0, Math.max(1, durationInFrames)], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // RTL horizontal clip-path uncover:
  // In RTL, text reads from Right (100%) to Left (0%).
  // At progress = 0: polygon(100% 0, 100% 0, 100% 100%, 100% 100%) -> fully hidden
  // At progress = 1: polygon(0% 0, 100% 0, 100% 100%, 0% 100%) -> fully visible
  const leftBound = ((1 - progress) * 100).toFixed(2);
  const clipPath = `polygon(${leftBound}% 0%, 100% 0%, 100% 100%, ${leftBound}% 100%)`;

  // Subtle leading edge accent glow / slight translation
  const translateY = interpolate(relFrame, [0, Math.max(1, durationInFrames)], [12, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      dir="rtl"
      className={className}
      style={{
        direction: "rtl",
        textAlign: "right",
        fontFamily,
        fontWeight,
        fontSize,
        color,
        lineHeight,
        letterSpacing,
        position: "relative",
        display: "inline-block",
        clipPath,
        WebkitClipPath: clipPath,
        transform: `translateY(${translateY}px)`,
        textRendering: "geometricPrecision",
        WebkitFontSmoothing: "antialiased",
        fontFeatureSettings: '"kern" 1, "liga" 1',
        ...style,
      }}
    >
      {renderShapedRtlContent(text)}
    </div>
  );
};
