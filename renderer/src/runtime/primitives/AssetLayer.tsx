import React from "react";
import { interpolate, spring, useCurrentFrame } from "remotion";

export interface RectBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface VectorEntityInput {
  id: string;
  primitive: "path" | "circle" | "line" | "polygon" | "arc_strip" | string;
  geometry_props: Record<string, any>;
  style: {
    fill?: "accent" | "bg" | "fg" | "black" | "none" | string;
    stroke?: "accent" | "fg" | "black" | "none" | string;
    strokeWidth?: number;
  };
  behavior: {
    operator?: "attract" | "align" | "twist" | "trim" | "extrude" | "shatter" | string;
    target_pos?: [number, number];
    spring_physics?: { damping: number; mass: number; stiffness: number };
  };
}

export interface VectorIRAssemblyInput {
  metaphor_name: string;
  canvas_role?: "hero_anchor" | "spatial_counterpoint" | "framing_aperture" | string;
  entities: VectorEntityInput[];
}

export interface AssetLayerProps {
  spec?: {
    vector_ir?: VectorIRAssemblyInput;
    primary_color?: string;
    accent_color?: string;
    label?: string;
    entity_id?: string;
  };
  vectorIR?: VectorIRAssemblyInput;
  box?: RectBox;
  saliency?: {
    hero_layer?: string;
    asset_opacity?: number;
    asset_scale?: number;
  };
  startFrame?: number;
  durationInFrames?: number;
  palette?: { bg?: string; fg?: string; accent?: string; muted?: string };
}

export const AssetLayer: React.FC<AssetLayerProps> = ({
  spec,
  vectorIR,
  box,
  saliency,
  startFrame = 0,
  durationInFrames = 45,
  palette,
}) => {
  const frame = useCurrentFrame();
  const relFrame = Math.max(0, frame - startFrame);

  if (!box || box.w <= 0 || box.h <= 0) {
    return null;
  }

  const assembly = vectorIR || spec?.vector_ir;
  const entities = assembly?.entities || [];
  if (entities.length === 0) {
    return null;
  }

  // Inter-Scene Directional Whip Exit & Enter Motion Momentum
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
  const targetOpacity = Math.max(0.75, saliency?.asset_opacity ?? 0.95);

  const resolveColor = (c?: string): string => {
    if (!c || c === "none") return "none";
    if (c === "accent") return palette?.accent || spec?.accent_color || "#FF5500";
    if (c === "fg") return palette?.fg || spec?.primary_color || "#FFFFFF";
    if (c === "bg") return palette?.bg || "#5537ED";
    if (c === "black") return "#000000";
    return c;
  };

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
        pointerEvents: "none",
        zIndex: 5,
        overflow: "visible",
      }}
    >
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 800 450"
        style={{ width: "100%", height: "100%", overflow: "visible" }}
      >
        {entities.map((entity) => {
          const behavior = entity.behavior || {};
          const operator = behavior.operator || "align";
          const props = entity.geometry_props || {};
          const style = entity.style || {};

          const fillColor = resolveColor(style.fill);
          const strokeColor = resolveColor(style.stroke);
          const strokeWidth = style.strokeWidth ?? 2;

          const springVal = spring({
            frame: relFrame,
            fps: 30,
            config: behavior.spring_physics || { damping: 12, mass: 0.5, stiffness: 160 },
          });

          // Operator 1: attract (move towards target_pos)
          let cx = Number(props.cx || 400);
          let cy = Number(props.cy || 225);
          if (operator === "attract" && behavior.target_pos) {
            cx = interpolate(springVal, [0, 1], [cx, behavior.target_pos[0]]);
            cy = interpolate(springVal, [0, 1], [cy, behavior.target_pos[1]]);
          }

          // Operator 2: align (snap along alignment axis)
          if (operator === "align") {
            const initialOffset = (Number(entity.id.charCodeAt(0) || 0) % 30) - 15;
            cy = interpolate(springVal, [0, 1], [cy + initialOffset, cy]);
          }

          // Operator 3: twist (rotational spin)
          const twistAngle = operator === "twist"
            ? interpolate(springVal, [0, 1], [-55, 0])
            : 0;

          // Operator 4: trim (vector stroke draw-in)
          const isTrim = operator === "trim";
          const trimLength = 600;
          const strokeDashoffset = isTrim
            ? interpolate(springVal, [0, 1], [trimLength, 0])
            : undefined;

          // Operator 5: extrude (scale dilation)
          const extrudeScale = operator === "extrude"
            ? interpolate(springVal, [0, 1], [0.25, 1.0])
            : 1.0;

          // Operator 6: shatter (recoil bounce)
          const shatterScale = operator === "shatter"
            ? interpolate(springVal, [0, 0.4, 1], [0.7, 1.15, 1.0])
            : 1.0;

          const entityScale = extrudeScale * shatterScale;
          const transformOrigin = `${cx}px ${cy}px`;

          const gTransform = twistAngle !== 0 || entityScale !== 1.0
            ? `rotate(${twistAngle} ${cx} ${cy}) scale(${entityScale})`
            : undefined;

          return (
            <g
              key={entity.id}
              transform={gTransform}
              style={{ transformOrigin }}
            >
              {/* Primitive: circle */}
              {entity.primitive === "circle" && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={Number(props.r || 16)}
                  fill={fillColor}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeDasharray={isTrim ? trimLength : undefined}
                  strokeDashoffset={strokeDashoffset}
                />
              )}

              {/* Primitive: line */}
              {entity.primitive === "line" && (
                <line
                  x1={Number(props.x1 || 100)}
                  y1={Number(props.y1 || 225)}
                  x2={Number(props.x2 || 700)}
                  y2={Number(props.y2 || 225)}
                  fill={fillColor}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeDasharray={isTrim ? trimLength : undefined}
                  strokeDashoffset={strokeDashoffset}
                />
              )}

              {/* Primitive: path or arc_strip */}
              {(entity.primitive === "path" || entity.primitive === "arc_strip") && (
                <path
                  d={String(props.d || "M 100 225 L 700 225")}
                  fill={fillColor}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeDasharray={isTrim ? trimLength : undefined}
                  strokeDashoffset={strokeDashoffset}
                />
              )}

              {/* Primitive: polygon */}
              {entity.primitive === "polygon" && (
                <polygon
                  points={String(props.points || "380,180 420,180 400,260")}
                  fill={fillColor}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeDasharray={isTrim ? trimLength : undefined}
                  strokeDashoffset={strokeDashoffset}
                />
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};
