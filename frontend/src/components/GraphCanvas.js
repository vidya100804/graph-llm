import React, { useCallback, useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { getNodeColor } from "../lib/graphBuilder";

export default function GraphCanvas({ graphData, highlightNodes, onNodeClick, width, height, showGranularOverlay }) {
  const fgRef = useRef();
  const [hoveredNode, setHoveredNode] = useState(null);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;

    fg.d3Force("center")?.strength(0.04);
    fg.d3Force("charge")?.strength(-235);
    fg.d3Force("link")?.distance(62).strength(0.85);

    const { forceCollide } = require("d3-force");
    fg.d3Force(
      "collide",
      forceCollide()
        .radius(() => 11)
        .strength(1)
        .iterations(4)
    );

    fg.d3ReheatSimulation();

    const timer = setTimeout(() => {
      fg.zoomToFit(800, 70);
    }, 2200);

    return () => clearTimeout(timer);
  }, [graphData]);

  useEffect(() => {
    if (!highlightNodes || highlightNodes.size === 0) return;
    const fg = fgRef.current;
    if (!fg) return;

    const highlighted = graphData.nodes.filter((node) => highlightNodes.has(node.id));
    if (highlighted.length === 1) {
      const node = highlighted[0];
      if (node.x != null && node.y != null) {
        fg.centerAt(node.x, node.y, 600);
        fg.zoom(4, 600);
      }
    } else if (highlighted.length > 1) {
      fg.zoomToFit(600, 80, (node) => highlightNodes.has(node.id));
    }
  }, [highlightNodes, graphData.nodes]);

  const paintNode = useCallback(
    (node, ctx, globalScale) => {
      if (node.x == null || node.y == null) return;

      const isHighlighted = highlightNodes?.has(node.id);
      const isHovered = hoveredNode === node.id;
      const color = getNodeColor(node.type);
      const radius = isHighlighted ? 6 : isHovered ? 5 : 4;

      if (isHighlighted) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius + 4, 0, 2 * Math.PI);
        ctx.fillStyle = `${color}30`;
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      if (isHighlighted) {
        ctx.strokeStyle = "rgba(0,0,0,0.3)";
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      if ((isHovered || isHighlighted) && node.label) {
        const fontSize = Math.max(10 / globalScale, 3);
        ctx.font = `600 ${fontSize}px "Segoe UI", system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";

        const textWidth = ctx.measureText(node.label).width;
        const pad = fontSize * 0.35;
        const backgroundY = node.y + radius + 4;
        const x1 = node.x - textWidth / 2 - pad;
        const x2 = node.x + textWidth / 2 + pad;
        const y1 = backgroundY - pad * 0.5;
        const y2 = backgroundY + fontSize + pad;
        const curve = pad;

        ctx.fillStyle = "rgba(255,255,255,0.96)";
        ctx.beginPath();
        ctx.moveTo(x1 + curve, y1);
        ctx.arcTo(x2, y1, x2, y2, curve);
        ctx.arcTo(x2, y2, x1, y2, curve);
        ctx.arcTo(x1, y2, x1, y1, curve);
        ctx.arcTo(x1, y1, x2, y1, curve);
        ctx.closePath();
        ctx.fill();

        ctx.strokeStyle = "rgba(15,23,42,0.08)";
        ctx.lineWidth = 0.5;
        ctx.stroke();

        ctx.fillStyle = "#17253d";
        ctx.fillText(node.label, node.x, backgroundY);
      }
    },
    [highlightNodes, hoveredNode]
  );

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={graphData}
      width={width}
      height={height}
      backgroundColor="rgba(0,0,0,0)"
      nodeCanvasObject={paintNode}
      nodeCanvasObjectMode={() => "replace"}
      nodePointerAreaPaint={(node, color, ctx) => {
        if (node.x == null || node.y == null) return;
        ctx.beginPath();
        ctx.arc(node.x, node.y, 7, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
      }}
      linkColor={() => "rgba(148,163,184,0.3)"}
      linkWidth={(link) => {
        const sourceId = typeof link.source === "object" ? link.source.id : link.source;
        const targetId = typeof link.target === "object" ? link.target.id : link.target;
        if (highlightNodes?.has(sourceId) && highlightNodes?.has(targetId)) return 2;
        if (highlightNodes?.has(sourceId) || highlightNodes?.has(targetId)) return 1.2;
        return 0.4;
      }}
      linkDirectionalArrowLength={0}
      linkDirectionalParticles={showGranularOverlay ? 1 : 0}
      linkDirectionalParticleWidth={1.8}
      linkDirectionalParticleColor={(link) => getNodeColor(link.source?.type || "SalesOrder")}
      onNodeHover={(node) => setHoveredNode(node?.id || null)}
      onNodeClick={(node) => onNodeClick?.(node)}
      cooldownTicks={200}
      enableNodeDrag
      minZoom={0.1}
      maxZoom={12}
    />
  );
}
