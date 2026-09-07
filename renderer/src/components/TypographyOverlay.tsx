import React, { useMemo } from "react";
import { useCurrentFrame } from "remotion";
import { LyricLine } from "../types/manifest";

interface TypographyOverlayProps {
  lines: LyricLine[];
}

export const TypographyOverlay: React.FC<TypographyOverlayProps> = ({ lines }) => {
  const frame = useCurrentFrame();

  // Find active and recent lines up to the current frame
  const visibleLines = useMemo(() => {
    if (!lines || lines.length === 0) return [];

    // Find all lines that have started on or before current frame
    const started = lines.filter((l) => l.startFrame <= frame);
    if (started.length === 0) return [];

    // Filter to lines that haven't expired too long ago (persist up to 30 frames after endFrame)
    const activeOrRecent = started.filter((l) => frame <= l.endFrame + 30);

    // Apply strict 3-line FIFO clamp: roll off older lines when count exceeds 3
    const clamped = activeOrRecent.slice(-3);

    return clamped.map((item, idx) => ({
      ...item,
      lineIndex: idx,
      isLatest: idx === clamped.length - 1,
      // Subtle alternating tactile rotation jitter
      rotation: idx % 2 === 0 ? -1.2 : 1.2,
      // Alternating tape strip contrast
      tapeBg: idx % 2 === 0 ? "#FFFFFF" : "#000000",
      tapeText: idx % 2 === 0 ? "#000000" : "#FFFFFF",
    }));
  }, [lines, frame]);

  if (visibleLines.length === 0) return null;

  // Dynamic font sizing based on line count:
  // 1 line: 68px, 2 lines: 56px, 3 lines: 46px
  const fontSize = visibleLines.length === 1 ? 68 : visibleLines.length === 2 ? 56 : 46;

  return (
    <div
      style={{
        position: "absolute",
        top: 160,
        left: 160,
        right: 160,
        bottom: 160,
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end", // Anchored elegantly in lower safe third
        alignItems: "center",
        pointerEvents: "none",
        zIndex: 50,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          alignItems: "center",
          maxWidth: "100%",
          direction: "rtl",
        }}
      >
        {visibleLines.map((line, idx) => (
          <div
            key={`${line.text}-${line.startFrame}-${idx}`}
            style={{
              backgroundColor: line.tapeBg,
              color: line.tapeText,
              padding: "10px 24px",
              borderRadius: 6,
              fontFamily: "PeydaWeb, Shabnam, sans-serif",
              fontSize,
              fontWeight: 800,
              lineHeight: 1.25,
              textAlign: "center",
              transform: `rotate(${line.rotation}deg)`,
              boxShadow: "0 8px 30px rgba(0,0,0,0.6)",
              transition: "transform 0.15s ease-out",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
              maxWidth: 720,
            }}
          >
            {line.text}
          </div>
        ))}
      </div>
    </div>
  );
};
