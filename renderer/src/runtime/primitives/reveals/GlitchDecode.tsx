import React from "react";

export interface GlitchDecodeProps {
  text?: string;
  children?: React.ReactNode;
  progress: number; // 0 (fully corrupted) -> 1 (fully clean)
  channelOffsetPx?: number;
  color: string;
  accentColor?: string;
  fontFamily?: string;
  fontWeight?: string | number;
  fontSize?: number | string;
  direction?: "forward" | "reverse";
  style?: React.CSSProperties;
}

export const GlitchDecode: React.FC<GlitchDecodeProps> = ({
  text = "",
  children,
  progress: rawProgress,
  channelOffsetPx = 6,
  color,
  accentColor = "#E11D48",
  fontFamily = "Vazirmatn, sans-serif",
  fontWeight = 700,
  fontSize = 72,
  direction = "forward",
  style = {},
}) => {
  // Clamp progress between 0 and 1
  const cleanProgress = Math.max(0, Math.min(1, rawProgress));
  // If direction is reverse, progress 0 = clean, progress 1 = corrupted
  const effectiveProgress = direction === "reverse" ? 1 - cleanProgress : cleanProgress;

  const contentToRender = children !== undefined ? children : text;

  // When fully clean (progress = 1), render standard crisp typography with zero overhead
  if (effectiveProgress >= 0.99) {
    return (
      <div
        style={{
          fontFamily,
          fontWeight,
          fontSize,
          color,
          lineHeight: 1.15,
          letterSpacing: "-0.02em",
          ...style,
        }}
      >
        {contentToRender}
      </div>
    );
  }

  // Calculate corruption offset decaying to 0
  const corruptionFactor = 1 - effectiveProgress;
  const currentOffset = channelOffsetPx * corruptionFactor;
  const opacity = Math.min(1, effectiveProgress * 1.5 + 0.15);

  // SVG displacement noise intensity
  const filterId = `glitch-filter-${Math.abs(text.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0)) % 1000}`;
  const baseFrequency = 0.05 + corruptionFactor * 0.15;
  const scale = corruptionFactor * 24;

  return (
    <div
      style={{
        position: "relative",
        fontFamily,
        fontWeight,
        fontSize,
        color,
        opacity,
        lineHeight: 1.15,
        letterSpacing: "-0.02em",
        ...style,
      }}
    >
      {/* Hidden SVG Filter Definition */}
      <svg style={{ position: "absolute", width: 0, height: 0 }} aria-hidden="true">
        <filter id={filterId}>
          <feTurbulence type="fractalNoise" baseFrequency={baseFrequency} numOctaves="2" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale={scale} xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>

      {/* Red/Cyan Chromatic Channel Splits */}
      {currentOffset > 0.5 && (
        <>
          <span
            aria-hidden="true"
            style={{
              position: "absolute",
              top: 0,
              left: -currentOffset,
              color: accentColor,
              opacity: corruptionFactor * 0.75,
              filter: `url(#${filterId})`,
              mixBlendMode: "screen",
              pointerEvents: "none",
              userSelect: "none",
            }}
          >
            {contentToRender}
          </span>
          <span
            aria-hidden="true"
            style={{
              position: "absolute",
              top: 0,
              left: currentOffset,
              color: "#06B6D4",
              opacity: corruptionFactor * 0.75,
              filter: `url(#${filterId})`,
              mixBlendMode: "screen",
              pointerEvents: "none",
              userSelect: "none",
            }}
          >
            {contentToRender}
          </span>
        </>
      )}

      {/* Base Primary Glyphs */}
      <span style={{ position: "relative", filter: currentOffset > 1 ? `url(#${filterId})` : "none" }}>
        {contentToRender}
      </span>
    </div>
  );
};
