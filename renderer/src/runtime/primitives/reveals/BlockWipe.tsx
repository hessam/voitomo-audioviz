import React from "react";

export interface BlockWipeProps {
  text: string;
  progress: number; // 0 -> 1
  color: string;
  accentColor?: string;
  fontFamily?: string;
  fontWeight?: string | number;
  fontSize?: number | string;
  direction?: "left_to_right" | "right_to_left";
  style?: React.CSSProperties;
}

export const BlockWipe: React.FC<BlockWipeProps> = ({
  text,
  progress: rawProgress,
  color,
  accentColor = "#E11D48",
  fontFamily = "Vazirmatn, sans-serif",
  fontWeight = 700,
  fontSize = 64,
  direction = "left_to_right",
  style = {},
}) => {
  const p = Math.max(0, Math.min(1, rawProgress));

  // The text reveal clip path (uncovers from 0% to 100%)
  const clipPercent = p * 100;
  const clipPath =
    direction === "right_to_left"
      ? `polygon(${100 - clipPercent}% 0, 100% 0, 100% 100%, ${100 - clipPercent}% 100%)`
      : `polygon(0 0, ${clipPercent}% 0, ${clipPercent}% 100%, 0 100%)`;

  // The leading solid accent block wipe bar
  const blockLeadPercent = Math.min(100, clipPercent);
  const blockWidth = p < 0.95 ? 12 : 0; // disappears once reveal finishes

  return (
    <div
      style={{
        position: "relative",
        fontFamily,
        fontWeight,
        fontSize,
        color,
        lineHeight: 1.2,
        letterSpacing: "-0.015em",
        display: "inline-block",
        ...style,
      }}
    >
      {/* Revealed Text Layer */}
      <span style={{ clipPath, display: "inline-block" }}>{text}</span>

      {/* Leading Geometric Wipe Bar */}
      {blockWidth > 0 && (
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            top: "10%",
            bottom: "10%",
            left: direction === "right_to_left" ? `${100 - blockLeadPercent}%` : `${blockLeadPercent}%`,
            width: `${blockWidth}px`,
            backgroundColor: accentColor,
            transform: "translateX(-50%)",
            transition: "none",
          }}
        />
      )}
    </div>
  );
};
