import React from "react";
import { interpolate, useCurrentFrame } from "remotion";

export interface EnvironmentSpecInput {
  style?: "isometric_grid" | "gradient_mesh" | "halftone_dots" | "celestial_dust" | "studio_minimal";
  bg_color?: string;
  accent_color?: string;
  fg_color?: string;
  contrast?: number;
  grid_size?: number;
  grain_intensity?: number;
  lighting_angle?: number;
  gradient_stops?: string[];
}

export interface EnvironmentLayerProps {
  spec?: EnvironmentSpecInput;
  defaultBg?: string;
}

export const EnvironmentLayer: React.FC<EnvironmentLayerProps> = ({
  spec,
  defaultBg = "#5537ED",
}) => {
  const frame = useCurrentFrame();
  const bg = spec?.bg_color || defaultBg;
  const accent = spec?.accent_color || "#FF5500";
  const fg = spec?.fg_color || "#FFFFFF";
  const style = spec?.style || "isometric_grid";
  const contrast = spec?.contrast ?? 0.22;
  const gridSize = spec?.grid_size || 52;

  // Gentle subtle camera drift for procedural atmosphere
  const driftY = interpolate(frame % 180, [0, 180], [0, 12]);
  const pulse = Math.sin(frame * 0.05) * 0.04;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: bg,
        overflow: "hidden",
        pointerEvents: "none",
        zIndex: 1,
      }}
    >
      {/* 1. Isometric Blueprint Grid */}
      {style === "isometric_grid" && (
        <svg
          width="100%"
          height="100%"
          style={{
            position: "absolute",
            inset: 0,
            opacity: Math.max(0.12, Math.min(0.35, contrast + pulse)),
            transform: `translateY(${driftY}px)`,
          }}
        >
          <defs>
            <pattern
              id="isoGrid"
              width={gridSize}
              height={gridSize}
              patternUnits="userSpaceOnUse"
            >
              <path
                d={`M ${gridSize} 0 L 0 ${gridSize} M 0 0 L ${gridSize} ${gridSize}`}
                fill="none"
                stroke={fg}
                strokeWidth="1.2"
                strokeDasharray="3,3"
              />
              <circle cx={gridSize / 2} cy={gridSize / 2} r="1.5" fill={accent} />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#isoGrid)" />
          {/* Accent Crosshairs */}
          <line x1="80" y1="0" x2="80" y2="1080" stroke={accent} strokeWidth="1" opacity="0.3" />
          <line x1="1000" y1="0" x2="1000" y2="1080" stroke={accent} strokeWidth="1" opacity="0.3" />
        </svg>
      )}

      {/* 2. Organic Gradient Mesh */}
      {style === "gradient_mesh" && (
        <div
          style={{
            position: "absolute",
            inset: -40,
            background: `radial-gradient(circle at 75% 25%, ${accent}44 0%, transparent 60%), radial-gradient(circle at 20% 80%, #00000066 0%, transparent 70%), ${bg}`,
            opacity: Math.max(0.2, Math.min(0.5, contrast * 1.5)),
            filter: "blur(40px)",
            transform: `rotate(${frame * 0.05}deg)`,
          }}
        />
      )}

      {/* 3. Halftone Dot Noise Matrix */}
      {style === "halftone_dots" && (
        <svg
          width="100%"
          height="100%"
          style={{
            position: "absolute",
            inset: 0,
            opacity: Math.max(0.1, Math.min(0.3, contrast)),
          }}
        >
          <defs>
            <pattern
              id="halftone"
              width="36"
              height="36"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="18" cy="18" r="2.5" fill={fg} />
              <circle cx="0" cy="0" r="1.5" fill={accent} />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#halftone)" />
        </svg>
      )}

      {/* 4. Celestial Dust & Orbital Glow */}
      {style === "celestial_dust" && (
        <div style={{ position: "absolute", inset: 0, opacity: contrast + 0.1 }}>
          {[...Array(14)].map((_, i) => {
            const x = ((i * 73 + 45) % 100);
            const y = ((i * 91 + 30) % 100);
            const size = (i % 3) + 2;
            const starPulse = Math.sin((frame + i * 15) * 0.08) * 0.5 + 0.5;
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: `${x}%`,
                  top: `${y}%`,
                  width: `${size}px`,
                  height: `${size}px`,
                  backgroundColor: i % 4 === 0 ? accent : fg,
                  borderRadius: "50%",
                  boxShadow: `0 0 8px ${i % 4 === 0 ? accent : fg}`,
                  opacity: starPulse,
                  transform: `translateY(${Math.sin((frame + i * 10) * 0.03) * 6}px)`,
                }}
              />
            );
          })}
        </div>
      )}

      {/* 5. Studio Minimal Vignette with Directional Key Light */}
      {style === "studio_minimal" && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(circle at 50% 35%, transparent 20%, #00000088 100%)`,
            opacity: Math.max(0.2, Math.min(0.6, contrast * 1.6)),
          }}
        />
      )}

      {/* Subtle Film Grain Noise Texture */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `radial-gradient(${fg} 0.75px, transparent 0.75px)`,
          backgroundSize: "24px 24px",
          opacity: 0.07,
        }}
      />
    </div>
  );
};
