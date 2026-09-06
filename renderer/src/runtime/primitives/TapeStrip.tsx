import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

export interface TapeStripProps {
  text: string;
  isBlack?: boolean;
  fontSize?: number | string;
  startFrame?: number;
  fontFamily?: string;
  style?: React.CSSProperties;
  className?: string;
}

export const TapeStrip: React.FC<TapeStripProps> = ({
  text,
  isBlack = false,
  fontSize = 58,
  startFrame = 0,
  fontFamily = '"Vazirmatn", "Dana", sans-serif',
  style = {},
  className = "",
}) => {
  const frame = useCurrentFrame();
  const relFrame = Math.max(0, frame - startFrame);

  // Pure vertical slide with zero scaleX distortion
  const y = interpolate(relFrame, [0, 10], [40, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(relFrame, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        transform: `translateY(${y}px)`,
        opacity,
        display: "inline-block",
        margin: "8px 0",
        ...style,
      }}
      className={className}
    >
      <span
        dir="rtl"
        lang="fa"
        className={`tape-strip ${isBlack ? "black" : ""}`}
        style={{
          display: "inline-block",
          background: isBlack ? "#000000" : "#FFFFFF",
          color: isBlack ? "#FFFFFF" : "#000000",
          boxShadow: "12px 12px 0px 0px #000000", // Hard Canva/Cavalry block shadow
          padding: "10px 24px 14px",
          fontFamily,
          fontWeight: 800,
          fontSize,
          lineHeight: 1.6,
          direction: "rtl",
          unicodeBidi: "isolate",
          letterSpacing: "normal",
          WebkitFontSmoothing: "antialiased",
          borderRadius: "0px",
        }}
      >
        {text}
      </span>
    </div>
  );
};
