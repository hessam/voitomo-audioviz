import React from "react";
import { interpolate, spring, useCurrentFrame } from "remotion";

export interface TapeStripProps {
  text: string;
  isBlack?: boolean;
  fontSize?: number | string;
  startFrame?: number;
  fontFamily?: string;
  style?: React.CSSProperties;
  className?: string;
  tiltAngle?: number;
}

export const TapeStrip: React.FC<TapeStripProps> = ({
  text,
  isBlack = false,
  fontSize = 76,
  startFrame = 0,
  fontFamily = '"Vazirmatn", "Dana", sans-serif',
  style = {},
  className = "",
  tiltAngle = 0,
}) => {
  const frame = useCurrentFrame();
  const relFrame = Math.max(0, frame - startFrame);

  // Snappy spring motion with overshoot (Kill flat linear translateY)
  const springVal = spring({
    frame: relFrame,
    fps: 30,
    config: { damping: 10, mass: 0.5, stiffness: 180 }, // Snappy pop with overshoot
  });

  // Scale from 0.85 -> 1.05 -> 1.0 on enter
  const scale = interpolate(springVal, [0, 1], [0.85, 1.0]);
  const y = interpolate(springVal, [0, 1], [45, 0]);
  const opacity = interpolate(relFrame, [0, 4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        transform: `translateY(${y}px) rotate(${tiltAngle}deg) scale(${scale})`,
        opacity,
        display: "inline-block",
        margin: "10px 0",
        transformOrigin: "center center",
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
          padding: "12px 28px 16px",
          fontFamily,
          fontWeight: 800,
          fontSize,
          lineHeight: 1.5,
          direction: "rtl",
          unicodeBidi: "isolate",
          whiteSpace: "pre-wrap",
          wordBreak: "keep-all",
          maxWidth: "960px",
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
