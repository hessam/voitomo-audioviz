import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface RectBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface AssetSpecInput {
  geometry?: "particle_field" | "connected_graph" | "vector_ribbon" | "concentric_contours" | string;
  operator?: "align" | "attract" | "draw" | "cluster" | "accelerate" | "expand" | "pulse" | "radiate" | "flow" | string;
  primary_color?: string;
  accent_color?: string;
  params?: Record<string, any>;
  label?: string;
  entity_id?: string;
  asset_type?: string;
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
  durationInFrames?: number;
}

/**
 * 1. ParticleField: operator="align" | "attract"
 * Scattered particles attract or align into a coherent focused beam.
 */
export const ParticleField: React.FC<{
  count?: number;
  operator?: string;
  primaryColor: string;
  accentColor: string;
  frame: number;
}> = ({ count = 36, operator = "align", primaryColor, accentColor, frame }) => {
  const isAlign = operator === "align";
  return (
    <svg width="100%" height="100%" viewBox="0 0 800 450" style={{ overflow: "visible" }}>
      {/* Central focus guideline */}
      {isAlign && (
        <line
          x1="100"
          y1="225"
          x2="700"
          y2="225"
          stroke={accentColor}
          strokeWidth="2"
          strokeDasharray="8,6"
          opacity="0.6"
        />
      )}
      {[...Array(count)].map((_, i) => {
        const seedX = ((i * 127 + 53) % 650) + 75;
        const seedY = ((i * 191 + 41) % 350) + 50;

        // Attract toward center point (400, 225) or align onto horizontal beam (y=225)
        const progress = Math.min(1, Math.max(0, frame / 30));
        const targetY = isAlign ? 225 + (Math.sin(frame * 0.1 + i) * 12) : 225;
        const targetX = isAlign ? seedX : 400 + Math.cos(i * 0.5 + frame * 0.05) * 120;

        const currentX = interpolate(progress, [0, 1], [seedX, targetX]);
        const currentY = interpolate(progress, [0, 1], [seedY, targetY]);
        const isAccent = i % 4 === 0;

        return (
          <g key={i}>
            <circle
              cx={currentX}
              cy={currentY}
              r={isAccent ? 5 : 3.5}
              fill={isAccent ? accentColor : primaryColor}
              opacity={0.85}
            />
            {isAccent && (
              <circle
                cx={currentX}
                cy={currentY}
                r={10}
                stroke={accentColor}
                strokeWidth="1"
                fill="none"
                opacity={0.4}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
};

/**
 * 2. ConnectedGraph: operator="draw" | "cluster"
 * Isolated nodes draw dynamic vector edges between each other.
 */
export const ConnectedGraph: React.FC<{
  nodes?: number;
  edges?: number;
  operator?: string;
  primaryColor: string;
  accentColor: string;
  frame: number;
}> = ({ nodes = 8, primaryColor, accentColor, frame }) => {
  const nodeCoords = [
    { x: 180, y: 120, label: "01" },
    { x: 380, y: 90, label: "02" },
    { x: 580, y: 140, label: "03" },
    { x: 680, y: 280, label: "04" },
    { x: 480, y: 340, label: "05" },
    { x: 260, y: 320, label: "06" },
    { x: 390, y: 215, label: "HUB" },
  ];

  const edgePairs = [
    [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0],
    [6, 0], [6, 1], [6, 2], [6, 3], [6, 4], [6, 5]
  ];

  // Draw-in animation for edges
  const drawProgress = Math.min(1, Math.max(0, frame / 20));

  return (
    <svg width="100%" height="100%" viewBox="0 0 800 450">
      {/* Connecting animated edges */}
      {edgePairs.map(([fromIdx, toIdx], idx) => {
        const from = nodeCoords[fromIdx];
        const to = nodeCoords[toIdx];
        const curToX = interpolate(drawProgress, [0, 1], [from.x, to.x]);
        const curToY = interpolate(drawProgress, [0, 1], [from.y, to.y]);
        const isHub = fromIdx === 6 || toIdx === 6;

        return (
          <line
            key={idx}
            x1={from.x}
            y1={from.y}
            x2={curToX}
            y2={curToY}
            stroke={isHub ? accentColor : primaryColor}
            strokeWidth={isHub ? "3" : "1.8"}
            strokeDasharray={isHub ? "none" : "6,4"}
            opacity={0.7}
          />
        );
      })}

      {/* Nodes */}
      {nodeCoords.map((n, idx) => {
        const isHub = idx === 6;
        return (
          <g key={idx} transform={`translate(${n.x}, ${n.y})`}>
            <circle
              r={isHub ? 22 : 14}
              fill={isHub ? accentColor : "#000000"}
              stroke="#FFFFFF"
              strokeWidth="2.5"
            />
            <text
              textAnchor="middle"
              dy="5"
              fill={isHub ? "#000000" : "#FFFFFF"}
              fontSize={isHub ? "12px" : "10px"}
              fontWeight="900"
              fontFamily="monospace"
            >
              {n.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

/**
 * 3. VectorRibbon: flow="accelerate" | "expand"
 * Tight geometric bottleneck expands as flowing ribbons accelerate through.
 */
export const VectorRibbon: React.FC<{
  waveFreq?: number;
  flow?: string;
  primaryColor: string;
  accentColor: string;
  frame: number;
}> = ({ waveFreq = 2.0, primaryColor, accentColor, frame }) => {
  const speed = frame * 0.12;
  const paths = [
    { offset: 0, color: accentColor, width: 4 },
    { offset: 25, color: primaryColor, width: 2.5 },
    { offset: -25, color: primaryColor, width: 2 },
  ];

  return (
    <svg width="100%" height="100%" viewBox="0 0 800 450" style={{ overflow: "visible" }}>
      {paths.map((p, idx) => {
        const d = `M 60 ${225 + p.offset} Q 220 ${
          225 + p.offset + Math.sin(speed + idx) * 75
        }, 400 ${225 + p.offset} T 740 ${225 + p.offset}`;
        return (
          <path
            key={idx}
            d={d}
            fill="none"
            stroke={p.color}
            strokeWidth={p.width}
            opacity={0.85}
          />
        );
      })}
      {/* Bottleneck indicator frame */}
      <rect
        x="370"
        y="160"
        width="60"
        height="130"
        fill="none"
        stroke={accentColor}
        strokeWidth="2"
        strokeDasharray="4,4"
        opacity="0.5"
      />
    </svg>
  );
};

/**
 * 4. ConcentricContours: pulseRate={P} | "radiate"
 * Acoustic and social resonance rings radiating outwards.
 */
export const ConcentricContours: React.FC<{
  pulseRate?: number;
  primaryColor: string;
  accentColor: string;
  frame: number;
}> = ({ pulseRate = 1.6, primaryColor, accentColor, frame }) => {
  const rings = [1, 2, 3, 4, 5];
  return (
    <svg width="100%" height="100%" viewBox="0 0 800 450" style={{ overflow: "visible" }}>
      <g transform="translate(400, 225)">
        {rings.map((r) => {
          const rBase = r * 35;
          const dynamicR = rBase + ((frame * pulseRate * 2) % 40);
          const opacity = Math.max(0.1, 1 - dynamicR / 220);
          const isAccent = r % 2 === 1;

          return (
            <ellipse
              key={r}
              rx={dynamicR * 1.5}
              ry={dynamicR * 0.9}
              fill="none"
              stroke={isAccent ? accentColor : primaryColor}
              strokeWidth={isAccent ? "2.5" : "1.5"}
              strokeDasharray={r === 3 ? "6,4" : "none"}
              opacity={opacity}
            />
          );
        })}
        {/* Core focal pulse */}
        <circle r="8" fill={accentColor} />
      </g>
    </svg>
  );
};

export const AssetLayer: React.FC<AssetLayerProps> = ({
  spec,
  box,
  saliency,
  startFrame = 0,
  durationInFrames = 45,
}) => {
  const frame = useCurrentFrame();
  const relFrame = Math.max(0, frame - startFrame);

  if (!spec || !box || box.w <= 0 || box.h <= 0) {
    return null;
  }

  const geom = spec.geometry || spec.asset_type || "particle_field";
  const operator = spec.operator || "align";
  const primary = spec.primary_color || "#FFFFFF";
  const accent = spec.accent_color || "#FF5500";
  const label = spec.label || "PERSISTENT KINETIC ENTITY";

  // Directional whip exit & enter motion momentum:
  // Enter: translateX from 100px -> 0
  // Exit: translateX from 0 -> -100px
  const isEntering = relFrame < 8;
  const isExiting = relFrame > Math.max(1, durationInFrames - 8);

  const enterX = interpolate(relFrame, [0, 8], [100, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitX = interpolate(relFrame, [durationInFrames - 8, durationInFrames], [0, -100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const currentX = isExiting ? exitX : isEntering ? enterX : 0;

  const baseScale = saliency?.asset_scale ?? 1.0;
  const targetOpacity = Math.max(0.7, saliency?.asset_opacity ?? 0.95);

  return (
    <div
      style={{
        position: "absolute",
        left: `${box.x}px`,
        top: `${box.y}px`,
        width: `${box.w}px`,
        height: `${box.h}px`,
        opacity: targetOpacity,
        transform: `translateX(${currentX}px) scale(${baseScale})`,
        transformOrigin: "center center",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 5,
        pointerEvents: "none",
      }}
    >
      {/* Procedural Entity Container Header */}
      <div
        style={{
          width: "90%",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "12px",
          borderBottom: `1px solid ${accent}44`,
          paddingBottom: "6px",
        }}
      >
        <span style={{ color: accent, fontSize: "12px", fontWeight: 900, fontFamily: "monospace" }}>
          ✦ {spec.entity_id || "ENTITY_01"} // {operator.toUpperCase()}
        </span>
        <span style={{ color: primary, fontSize: "11px", fontWeight: 700, fontFamily: "monospace", opacity: 0.8 }}>
          {label}
        </span>
      </div>

      {/* 4 Procedural Generative Primitives */}
      <div style={{ width: "95%", height: "82%", position: "relative" }}>
        {geom === "particle_field" && (
          <ParticleField
            count={spec.params?.count || 36}
            operator={operator}
            primaryColor={primary}
            accentColor={accent}
            frame={relFrame}
          />
        )}

        {geom === "connected_graph" && (
          <ConnectedGraph
            nodes={spec.params?.nodes || 7}
            operator={operator}
            primaryColor={primary}
            accentColor={accent}
            frame={relFrame}
          />
        )}

        {geom === "vector_ribbon" && (
          <VectorRibbon
            waveFreq={spec.params?.wave_freq || 2.0}
            flow={operator}
            primaryColor={primary}
            accentColor={accent}
            frame={relFrame}
          />
        )}

        {geom === "concentric_contours" && (
          <ConcentricContours
            pulseRate={spec.params?.pulse_rate || 1.6}
            primaryColor={primary}
            accentColor={accent}
            frame={relFrame}
          />
        )}
      </div>
    </div>
  );
};
