import React, { useState, useEffect } from "react";
import { Code2, GitFork, FileText } from "lucide-react";
import { CodeViewer } from "./CodeViewer";
import { ImportGraph } from "./ImportGraph";
import { fetchFile, fetchGraph } from "../api";
import type { GraphResponse } from "../api";

interface EvidencePanelProps {
  activeFile: string;
  highlightRange?: { start: number; end: number };
  allCitedFiles?: string[];
  onSelectFile?: (file: string) => void;
  className?: string;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({
  activeFile,
  highlightRange,
  allCitedFiles = [],
  onSelectFile,
  className = "",
}) => {
  const [tab, setTab] = useState<"code" | "graph">("code");
  const [fileLines, setFileLines] = useState<string[]>([]);
  const [graphData, setGraphData] = useState<GraphResponse>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeFile) return;
    setLoading(true);
    setError(null);
    fetchFile(activeFile)
      .then((res) => {
        setFileLines(res.lines);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [activeFile]);

  useEffect(() => {
    fetchGraph()
      .then((res) => setGraphData(res))
      .catch(() => {});
  }, []);

  return (
    <div className={`flex flex-col h-full glass-panel border-cyan-800/40 overflow-hidden ${className}`}>
      {/* Tabs Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-cyan-900/40 bg-[#03111f]/60">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-cyan-400" />
          <span className="font-heading font-bold text-xs uppercase tracking-wider text-cyan-200">
            Evidence · {activeFile}
          </span>
          {highlightRange && (
            <span className="text-[11px] font-mono text-cyan-400/80">
              L{highlightRange.start}–{highlightRange.end}
            </span>
          )}
        </div>

        {/* View Switcher: Code vs Import map */}
        <div className="flex items-center gap-1 bg-[#020b14] p-1 rounded-xl border border-cyan-900/60">
          <button
            onClick={() => setTab("code")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition ${
              tab === "code"
                ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                : "text-[#9fc3d6] hover:text-white"
            }`}
          >
            <Code2 className="w-3.5 h-3.5" />
            <span>Code</span>
          </button>
          <button
            onClick={() => setTab("graph")}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition ${
              tab === "graph"
                ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                : "text-[#9fc3d6] hover:text-white"
            }`}
          >
            <GitFork className="w-3.5 h-3.5" />
            <span>Import map</span>
          </button>
        </div>
      </div>

      {/* Panel Content */}
      <div className="flex-1 overflow-hidden p-3 bg-[#020b14]/50">
        {loading ? (
          <div className="h-full flex items-center justify-center p-6 text-center text-cyan-400 font-mono text-xs">
            Loading file evidence...
          </div>
        ) : tab === "code" ? (
          error ? (
            <div className="h-full flex items-center justify-center p-6 text-center text-rose-300 font-mono text-xs">
              {error}
            </div>
          ) : (
            <CodeViewer
              path={activeFile}
              lines={fileLines}
              highlightRange={highlightRange}
            />
          )
        ) : (
          <ImportGraph
            nodesData={graphData.nodes}
            edgesData={graphData.edges}
            highlightedFiles={allCitedFiles.length > 0 ? allCitedFiles : [activeFile]}
            onSelectFile={(f) => {
              if (onSelectFile) onSelectFile(f);
              setTab("code");
            }}
          />
        )}
      </div>
    </div>
  );
};
