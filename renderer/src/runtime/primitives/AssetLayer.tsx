import React from "react";
import { interpolate, spring, useCurrentFrame } from "remotion";

export interface RectBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface AssetSpecInput {
  topic?: "tech_career" | "poetry_music" | "finance_business";
  asset_type?: string;
  primary_color?: string;
  accent_color?: string;
  label?: string;
  data_points?: number[];
  svg_data?: Record<string, any>;
}

export interface AssetLayerProps {
  spec?: AssetSpecInput;
  box?: RectBox;
  saliency?: {
    hero_layer?: string;
    asset_opacity?: number;
    asset_scale?: number;
  };
  startFrame?: number;
}

export const AssetLayer: React.FC<AssetLayerProps> = ({
  spec,
  box,
  saliency,
  startFrame = 0,
}) => {
  const frame = useCurrentFrame();
  const relFrame = Math.max(0, frame - startFrame);

  if (!spec || !box || box.w <= 0 || box.h <= 0) {
    return null;
  }

  const assetType = spec.asset_type || "search_console";
  const primary = spec.primary_color || "#FFFFFF";
  const accent = spec.accent_color || "#FF5500";
  const label = spec.label || "KINETIC INTELLIGENCE";

  // Spring entrance physics
  const springVal = spring({
    frame: relFrame,
    fps: 30,
    config: { damping: 12, mass: 0.6, stiffness: 150 },
  });

  const baseScale = saliency?.asset_scale ?? 1.0;
  const targetOpacity = saliency?.asset_opacity ?? 1.0;
  const currentScale = interpolate(springVal, [0, 1], [0.88, baseScale]);
  const currentOpacity = interpolate(relFrame, [0, 5], [0, targetOpacity], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        left: `${box.x}px`,
        top: `${box.y}px`,
        width: `${box.w}px`,
        height: `${box.h}px`,
        opacity: currentOpacity,
        transform: `scale(${currentScale})`,
        transformOrigin: "center center",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 5,
        pointerEvents: "none",
      }}
    >
      {/* 1. Tech: Generative Search Console */}
      {assetType === "search_console" && (
        <div
          style={{
            width: "88%",
            backgroundColor: "#000000",
            border: "3px solid #FFFFFF",
            boxShadow: "10px 10px 0px 0px #FFFFFF",
            padding: "24px 32px",
            display: "flex",
            flexDirection: "column",
            gap: "16px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", gap: "8px" }}>
              <span style={{ width: "12px", height: "12px", borderRadius: "50%", backgroundColor: accent }} />
              <span style={{ width: "12px", height: "12px", borderRadius: "50%", backgroundColor: "#FFFFFF" }} />
              <span style={{ width: "12px", height: "12px", borderRadius: "50%", backgroundColor: "#555555" }} />
            </div>
            <span style={{ color: accent, fontSize: "12px", fontWeight: 800, fontFamily: "monospace" }}>
              {label}
            </span>
          </div>
          <div
            style={{
              backgroundColor: "#111111",
              border: "1px solid #333333",
              padding: "12px 18px",
              color: "#FFFFFF",
              fontFamily: "monospace",
              fontSize: "18px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <span style={{ color: accent }}>&gt;</span>
            <span>{spec.svg_data?.query || "opportunity.reach(quality=high)"}</span>
            <span style={{ opacity: relFrame % 15 < 8 ? 1 : 0, color: accent }}>_</span>
          </div>
        </div>
      )}

      {/* 2. Tech: Interactive Node Graph */}
      {assetType === "node_graph" && (
        <div
          style={{
            width: "88%",
            height: "75%",
            backgroundColor: "#000000CC",
            border: "2px solid #FFFFFF",
            boxShadow: "8px 8px 0px 0px #000000",
            position: "relative",
            padding: "16px",
          }}
        >
          <svg width="100%" height="100%" style={{ position: "absolute", inset: 0 }}>
            {/* Connecting lines */}
            <line x1="25%" y1="35%" x2="75%" y2="35%" stroke={primary} strokeWidth="2" strokeDasharray="4,4" />
            <line x1="50%" y1="75%" x2="25%" y2="35%" stroke={accent} strokeWidth="2" />
            <line x1="50%" y1="75%" x2="75%" y2="35%" stroke={accent} strokeWidth="2" />
          </svg>
          {/* Node 1 */}
          <div
            style={{
              position: "absolute",
              left: "20%",
              top: "25%",
              backgroundColor: accent,
              color: "#000000",
              fontWeight: 900,
              fontSize: "14px",
              padding: "8px 16px",
              border: "2px solid #FFFFFF",
            }}
          >
            ● CORE
          </div>
          {/* Node 2 */}
          <div
            style={{
              position: "absolute",
              left: "70%",
              top: "25%",
              backgroundColor: "#FFFFFF",
              color: "#000000",
              fontWeight: 900,
              fontSize: "14px",
              padding: "8px 16px",
              border: "2px solid #000000",
            }}
          >
            ◆ SYNC
          </div>
          {/* Node 3 */}
          <div
            style={{
              position: "absolute",
              left: "44%",
              top: "65%",
              backgroundColor: "#000000",
              color: "#FFFFFF",
              fontWeight: 900,
              fontSize: "14px",
              padding: "8px 16px",
              border: `2px solid ${accent}`,
            }}
          >
            ▲ NETWORK
          </div>
        </div>
      )}

      {/* 3. Poetry / Music: Organic Fluid Waveform */}
      {assetType === "fluid_waveform" && (
        <div style={{ width: "90%", height: "70%", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <svg width="100%" height="160" viewBox="0 0 600 160">
            <path
              d={`M 0 80 Q 75 ${80 + Math.sin(relFrame * 0.15) * 45}, 150 80 T 300 80 T 450 80 T 600 80`}
              fill="none"
              stroke={accent}
              strokeWidth="4"
            />
            <path
              d={`M 0 80 Q 75 ${80 - Math.cos(relFrame * 0.12) * 35}, 150 80 T 300 80 T 450 80 T 600 80`}
              fill="none"
              stroke={primary}
              strokeWidth="2.5"
              strokeDasharray="6,4"
              opacity="0.8"
            />
          </svg>
        </div>
      )}

      {/* 4. Poetry / Music: Lunar Orbit */}
      {assetType === "lunar_orbit" && (
        <div style={{ position: "relative", width: "160px", height: "160px" }}>
          <div
            style={{
              position: "absolute",
              inset: 0,
              border: `2px dashed ${accent}`,
              borderRadius: "50%",
              transform: `rotate(${relFrame * 1.5}deg)`,
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: "25px",
              backgroundColor: "#FFFFFF",
              borderRadius: "50%",
              boxShadow: `0 0 30px ${accent}`,
            }}
          />
          <div
            style={{
              position: "absolute",
              right: "-8px",
              top: "50%",
              width: "16px",
              height: "16px",
              backgroundColor: accent,
              borderRadius: "50%",
              border: "2px solid #000000",
            }}
          />
        </div>
      )}

      {/* 5. Finance / Business: Candlestick Chart */}
      {assetType === "candlestick_chart" && (
        <div
          style={{
            width: "85%",
            height: "70%",
            backgroundColor: "#000000DD",
            border: "2px solid #FFFFFF",
            boxShadow: "8px 8px 0px 0px #000000",
            padding: "20px",
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-around",
          }}
        >
          {[45, 65, 55, 80, 70, 95].map((h, i) => {
            const isUp = i % 2 === 0;
            return (
              <div key={i} style={{ display: "flex", flexDirection: "column", alignItems: "center", width: "12%" }}>
                <div style={{ width: "2px", height: "18px", backgroundColor: isUp ? accent : primary }} />
                <div
                  style={{
                    width: "100%",
                    height: `${h}px`,
                    backgroundColor: isUp ? accent : "#FFFFFF",
                    border: "2px solid #000000",
                  }}
                />
                <div style={{ width: "2px", height: "18px", backgroundColor: isUp ? accent : primary }} />
              </div>
            );
          })}
        </div>
      )}

      {/* 6. Finance / Business: Metric Dial */}
      {assetType === "metric_dial" && (
        <div
          style={{
            backgroundColor: "#FFFFFF",
            border: "3px solid #000000",
            boxShadow: "10px 10px 0px 0px #000000",
            padding: "20px 36px",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span style={{ fontSize: "14px", fontWeight: 800, color: "#000000" }}>{label}</span>
          <span style={{ fontSize: "52px", fontWeight: 900, color: accent, lineHeight: 1 }}>+42%</span>
          <span style={{ fontSize: "13px", fontWeight: 700, color: "#555555" }}>● OUTPERFORMING MEDIAN</span>
        </div>
      )}
    </div>
  );
};
