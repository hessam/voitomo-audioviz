import React, { useMemo } from "react";
import { useCurrentFrame } from "remotion";
import { LyricLine } from "../types/manifest";
import { TapeStrip } from "../runtime/primitives/TapeStrip";

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

    // Filter to lines that haven't expired too long ago (persist up to 15 frames after endFrame)
    const activeOrRecent = started.filter((l) => frame <= l.endFrame + 15);

    // Keep at most 2 lines in lower third (current active + previous transitioning)
    const clamped = activeOrRecent.slice(-2);

    return clamped.map((item, idx) => ({
      ...item,
      lineIndex: idx,
      isLatest: idx === clamped.length - 1,
      // Subtle alternating tactile rotation jitter (-0.8deg / +0.8deg)
      rotation: idx % 2 === 0 ? -0.8 : 0.8,
    }));
  }, [lines, frame]);

  if (visibleLines.length === 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        left: 80,
        right: 80,
        bottom: 75, // Anchored elegantly in lower safe area, keeping 3D canvas clear
        display: "flex",
        flexDirection: "column",
        justifyContent: "flex-end",
        alignItems: "center",
        pointerEvents: "none",
        zIndex: 50,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          alignItems: "center",
          maxWidth: "100%",
          direction: "rtl",
        }}
      >
        {visibleLines.map((line, idx) => {
          const duration = Math.max(15, line.endFrame - line.startFrame);
          return (
            <TapeStrip
              key={`${line.text}-${line.startFrame}-${idx}`}
              text={line.text}
              fontSize={visibleLines.length === 1 ? 34 : 28}
              startFrame={line.startFrame}
              durationInFrames={duration}
              isBlack={line.isLatest ? false : true}
              isEmphasis={Boolean(line.isHero)}
              fontFamily='"Vazirmatn", "Dana", "PeydaWeb", "Shabnam", sans-serif'
              tiltAngle={line.rotation}
              singleLine={false}
              maxLines={2}
            />
          );
        })}
      </div>
    </div>
  );
};
