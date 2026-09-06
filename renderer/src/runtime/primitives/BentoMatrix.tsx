import React from "react";
import { useCurrentFrame } from "remotion";

export type GraphicTileKind = "disc" | "bars" | "orbit" | "checker" | "star" | "wave" | "dots";
export type GraphicTileMotion = "still" | "rotate" | "pulse";

export interface GraphicTile {
  kind: GraphicTileKind;
  motion: GraphicTileMotion;
  periodFrames: number;
}

const DEFAULT_TILES: GraphicTile[] = [
  { kind: "checker", motion: "still", periodFrames: 30 },
  { kind: "bars", motion: "pulse", periodFrames: 24 },
  { kind: "disc", motion: "rotate", periodFrames: 45 },
  { kind: "star", motion: "rotate", periodFrames: 60 },
  { kind: "orbit", motion: "rotate", periodFrames: 36 },
  { kind: "dots", motion: "pulse", periodFrames: 30 },
  { kind: "wave", motion: "pulse", periodFrames: 28 },
  { kind: "checker", motion: "still", periodFrames: 30 },
];

export const BentoMatrix: React.FC<{ tiles?: GraphicTile[]; style?: React.CSSProperties }> = ({
  tiles = DEFAULT_TILES,
  style = {},
}) => {
  const frame = useCurrentFrame();

  const renderTileGraphic = (tile: GraphicTile, index: number) => {
    const { kind, motion, periodFrames } = tile;
    let transform = "none";

    if (motion === "rotate") {
      const deg = ((frame % periodFrames) / periodFrames) * 360;
      transform = `rotate(${deg.toFixed(1)}deg)`;
    } else if (motion === "pulse") {
      const scale = 1 + 0.12 * Math.sin(((frame % periodFrames) / periodFrames) * Math.PI * 2);
      transform = `scale(${scale.toFixed(3)})`;
    }

    const svgWrapStyle: React.CSSProperties = {
      width: "60px",
      height: "60px",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      transform,
      transition: "transform 0.05s linear",
    };

    switch (kind) {
      case "checker":
        return (
          <div style={svgWrapStyle}>
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <rect x="0" y="0" width="24" height="24" fill="#000000" />
              <rect x="24" y="0" width="24" height="24" fill="#FFFFFF" />
              <rect x="0" y="24" width="24" height="24" fill="#FFFFFF" />
              <rect x="24" y="24" width="24" height="24" fill="#000000" />
              <rect x="0" y="0" width="48" height="48" stroke="#000000" strokeWidth="2" fill="none" />
            </svg>
          </div>
        );

      case "bars":
        return (
          <div style={svgWrapStyle}>
            <svg width="52" height="48" viewBox="0 0 52 48" fill="none">
              {[0, 1, 2, 3, 4].map((i) => {
                const osc = Math.sin(((frame + i * 8) / (periodFrames || 24)) * Math.PI * 2);
                const h = 14 + Math.round(18 * (osc * 0.5 + 0.5));
                const y = 44 - h;
                return (
                  <rect
                    key={i}
                    x={i * 10 + 4}
                    y={y}
                    width="6"
                    height={h}
                    fill="#000000"
                    rx="1"
                  />
                );
              })}
            </svg>
          </div>
        );

      case "disc":
        return (
          <div style={svgWrapStyle}>
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="21" stroke="#000000" strokeWidth="3" />
              <circle cx="24" cy="24" r="12" stroke="#000000" strokeWidth="2" strokeDasharray="3 3" />
              <circle cx="24" cy="24" r="4" fill="#000000" />
              <line x1="24" y1="0" x2="24" y2="48" stroke="#000000" strokeWidth="1.5" />
              <line x1="0" y1="24" x2="48" y2="24" stroke="#000000" strokeWidth="1.5" />
            </svg>
          </div>
        );

      case "star":
        return (
          <div style={svgWrapStyle}>
            <svg width="48" height="48" viewBox="0 0 48 48" fill="#000000">
              <path d="M24 0 L27 19 L48 24 L27 29 L24 48 L21 29 L0 24 L21 19 Z" />
            </svg>
          </div>
        );

      case "orbit":
        return (
          <div style={svgWrapStyle}>
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="18" stroke="#000000" strokeWidth="2" strokeDasharray="4 4" />
              <circle cx="24" cy="24" r="7" fill="#000000" />
              <circle cx="24" cy="6" r="3.5" fill="#000000" />
            </svg>
          </div>
        );

      case "dots":
        return (
          <div style={svgWrapStyle}>
            <svg width="48" height="48" viewBox="0 0 48 48" fill="#000000">
              {[0, 1, 2].map((r) =>
                [0, 1, 2].map((c) => (
                  <circle key={`${r}-${c}`} cx={10 + c * 14} cy={10 + r * 14} r="3.5" />
                ))
              )}
            </svg>
          </div>
        );

      case "wave":
        return (
          <div style={svgWrapStyle}>
            <svg width="50" height="32" viewBox="0 0 50 32" fill="none">
              <path
                d="M 2 16 Q 8 4, 14 16 T 26 16 T 38 16 T 48 16"
                stroke="#000000"
                strokeWidth="4"
                strokeLinecap="round"
              />
            </svg>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div
      className="bento-matrix"
      style={{
        position: "absolute",
        inset: "55% 5% 5% 5%",
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gridTemplateRows: "repeat(2, 1fr)",
        gap: "16px",
        zIndex: 5,
        ...style,
      }}
    >
      {tiles.slice(0, 8).map((tile, idx) => (
        <div
          key={idx}
          style={{
            backgroundColor: "#FFFFFF",
            border: "3px solid #000000",
            boxShadow: "6px 6px 0px 0px #000000", // Hard Cavalry offset block shadow
            borderRadius: "8px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden",
            position: "relative",
          }}
        >
          {renderTileGraphic(tile, idx)}
        </div>
      ))}
    </div>
  );
};
