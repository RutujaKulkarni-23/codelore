import React, { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
} from "@xyflow/react";
import type { Node, Edge } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

interface ImportGraphProps {
  nodesData: Array<{ id: string; lines?: number }>;
  edgesData: Array<{
    from: string;
    to: string;
    line: number;
    symbols: string[];
  }>;
  highlightedFiles?: string[];
  onSelectFile?: (file: string) => void;
  className?: string;
}

function computeLayeredLayout(
  nodes: Array<{ id: string; lines?: number }>,
  edges: Array<{ from: string; to: string }>
): Record<string, { x: number; y: number }> {
  const nodeIds = nodes.map((n) => n.id);
  const inDegree: Record<string, number> = {};
  const adj: Record<string, string[]> = {};

  for (const id of nodeIds) {
    inDegree[id] = 0;
    adj[id] = [];
  }

  for (const e of edges) {
    if (adj[e.from] && inDegree[e.to] !== undefined) {
      adj[e.from].push(e.to);
      inDegree[e.to]++;
    }
  }

  const rank: Record<string, number> = {};
  const queue: string[] = [];

  for (const id of nodeIds) {
    if (inDegree[id] === 0) {
      rank[id] = 0;
      queue.push(id);
    }
  }

  if (queue.length === 0 && nodeIds.length > 0) {
    rank[nodeIds[0]] = 0;
    queue.push(nodeIds[0]);
  }

  while (queue.length > 0) {
    const curr = queue.shift()!;
    const currRank = rank[curr] ?? 0;
    for (const neighbor of adj[curr] || []) {
      const nextRank = currRank + 1;
      if (rank[neighbor] === undefined || nextRank > rank[neighbor]) {
        rank[neighbor] = nextRank;
        queue.push(neighbor);
      }
    }
  }

  for (const id of nodeIds) {
    if (rank[id] === undefined) {
      rank[id] = 0;
    }
  }

  const layers: Record<number, string[]> = {};
  for (const [id, r] of Object.entries(rank)) {
    if (!layers[r]) layers[r] = [];
    layers[r].push(id);
  }

  const positions: Record<string, { x: number; y: number }> = {};
  const layerKeys = Object.keys(layers).map(Number).sort((a, b) => a - b);

  for (const l of layerKeys) {
    const layerNodes = layers[l];
    const totalInLayer = layerNodes.length;
    const startX = 260 - ((totalInLayer - 1) * 200) / 2;
    layerNodes.forEach((nodeId, idx) => {
      positions[nodeId] = {
        x: Math.max(40, startX + idx * 200),
        y: 50 + l * 120,
      };
    });
  }

  return positions;
}

export const ImportGraph: React.FC<ImportGraphProps> = ({
  nodesData,
  edgesData,
  highlightedFiles = [],
  onSelectFile,
  className = "",
}) => {
  const layout = useMemo(() => {
    return computeLayeredLayout(nodesData, edgesData);
  }, [nodesData, edgesData]);

  const nodes: Node[] = useMemo(() => {
    return nodesData.map((n) => {
      const isHighlighted = highlightedFiles.includes(n.id);
      const pos = layout[n.id] || { x: 100, y: 100 };

      return {
        id: n.id,
        position: pos,
        data: { label: n.id },
        style: {
          background: isHighlighted ? "rgba(34, 211, 238, 0.2)" : "rgba(3, 21, 38, 0.85)",
          color: isHighlighted ? "#22d3ee" : "#e6f6ff",
          border: isHighlighted
            ? "2px solid #22d3ee"
            : "1px solid rgba(186, 230, 253, 0.2)",
          borderRadius: "14px",
          padding: "10px 16px",
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: "12px",
          fontWeight: isHighlighted ? "600" : "500",
          boxShadow: isHighlighted
            ? "0 0 20px rgba(34, 211, 238, 0.45)"
            : "0 4px 12px rgba(0, 0, 0, 0.3)",
          cursor: "pointer",
        },
      };
    });
  }, [nodesData, highlightedFiles, layout]);

  const edges: Edge[] = useMemo(() => {
    return edgesData.map((e, idx) => {
      const isClue =
        highlightedFiles.includes(e.from) && highlightedFiles.includes(e.to);
      return {
        id: `e-${idx}-${e.from}-${e.to}`,
        source: e.from,
        target: e.to,
        label: `L${e.line}${isClue ? " · the clue" : ""}`,
        labelStyle: {
          fill: isClue ? "#22d3ee" : "#9fc3d6",
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10,
          fontWeight: isClue ? 700 : 400,
        },
        labelBgStyle: {
          fill: "rgba(3, 17, 31, 0.85)",
          rx: 6,
          ry: 6,
        },
        style: {
          stroke: isClue ? "#22d3ee" : "rgba(186, 230, 253, 0.25)",
          strokeWidth: isClue ? 2.5 : 1.5,
        },
        animated: isClue,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: isClue ? "#22d3ee" : "rgba(186, 230, 253, 0.35)",
        },
      };
    });
  }, [edgesData, highlightedFiles]);

  return (
    <div className={`h-full w-full rounded-2xl bg-[#020b14] border border-cyan-900/40 overflow-hidden relative ${className}`}>
      <div className="absolute top-3 left-3 z-10 px-3 py-1 rounded-full bg-cyan-950/80 border border-cyan-500/20 text-[11px] font-mono text-cyan-200">
        IMPORT MAP from analyze_imports
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodeClick={(_, node) => onSelectFile && onSelectFile(node.id)}
        fitView
      >
        <Background color="#0e7490" gap={16} size={1} />
        <Controls className="!bg-[#031526] !border-cyan-900/60 !text-cyan-200 rounded-lg overflow-hidden shadow-lg" />
      </ReactFlow>
    </div>
  );
};
