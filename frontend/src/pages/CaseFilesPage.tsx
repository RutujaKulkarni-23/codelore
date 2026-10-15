import React, { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Navbar } from "../components/Navbar";
import { CodeViewer } from "../components/CodeViewer";
import { ImportGraph } from "../components/ImportGraph";
import {
  FileCode,
  FileText,
  ChevronRight,
  ChevronDown,
  ArrowRight,
  Lock,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import {
  fetchProject,
  fetchFile,
  fetchOutline,
  fetchGraph,
  fetchOverview,
  BACKEND_OFFLINE_MSG,
} from "../api";
import type {
  OutlineItem,
  ProjectResponse,
  GraphResponse,
} from "../api";

export const CaseFilesPage: React.FC = () => {
  const navigate = useNavigate();
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [projectLoading, setProjectLoading] = useState(true);
  const [projectError, setProjectError] = useState<string | null>(null);

  const [activeFile, setActiveFile] = useState<string>("");
  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [fileLines, setFileLines] = useState<string[]>([]);
  const [fileLoading, setFileLoading] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);

  const [outline, setOutline] = useState<OutlineItem[]>([]);
  const [outlineLoading, setOutlineLoading] = useState(false);

  const [highlightRange, setHighlightRange] = useState<{ start: number; end: number } | undefined>(undefined);
  const [viewMode, setViewMode] = useState<"code" | "graph">("code");
  const [graphData, setGraphData] = useState<GraphResponse>({ nodes: [], edges: [] });

  useEffect(() => {
    setProjectLoading(true);
    Promise.allSettled([fetchProject(), fetchOverview(), fetchGraph()])
      .then(([projRes, overviewRes, graphRes]) => {
        if (projRes.status === "fulfilled") {
          const data = projRes.value;
          setProject(data);
          setProjectError(null);

          // Auto-select entry point from /api/overview if available, else first py file, else first file
          let fileToSelect: string | null = null;
          if (overviewRes.status === "fulfilled" && overviewRes.value.entry_point) {
            const entry = overviewRes.value.entry_point;
            if (data.files.some((f) => f.path === entry)) {
              fileToSelect = entry;
            }
          }
          if (!fileToSelect && data.files.length > 0) {
            const firstPy = data.files.find((f) => f.kind === "py") || data.files[0];
            fileToSelect = firstPy.path;
          }

          if (fileToSelect) {
            setActiveFile(fileToSelect);
            setOpenTabs([fileToSelect]);
          }
        } else {
          setProjectError(projRes.reason?.message || BACKEND_OFFLINE_MSG);
        }

        if (graphRes.status === "fulfilled") {
          setGraphData(graphRes.value);
        }
      })
      .finally(() => {
        setProjectLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!activeFile) {
      setFileLines([]);
      setOutline([]);
      return;
    }

    setFileLoading(true);
    setFileError(null);
    fetchFile(activeFile)
      .then((res) => setFileLines(res.lines))
      .catch((err) => {
        setFileLines([]);
        setFileError(err.message || BACKEND_OFFLINE_MSG);
      })
      .finally(() => {
        setFileLoading(false);
      });

    if (activeFile.endsWith(".py")) {
      setOutlineLoading(true);
      fetchOutline(activeFile)
        .then((res) => setOutline(res.items || []))
        .catch(() => setOutline([]))
        .finally(() => setOutlineLoading(false));
    } else {
      setOutline([]);
    }
  }, [activeFile]);

  const handleSelectFile = (file: string) => {
    setActiveFile(file);
    setHighlightRange(undefined);
    if (!openTabs.includes(file)) {
      setOpenTabs([...openTabs, file]);
    }
  };

  const handleAskAboutFile = (question: string) => {
    const caseId = `case-${Date.now()}`;
    navigate(`/case/${caseId}?q=${encodeURIComponent(question)}`);
  };

  const dataFiles = project?.files.filter((f) => f.path.startsWith("data/")) || [];
  const rootFiles = project?.files.filter((f) => !f.path.startsWith("data/")) || [];

  return (
    <div className="min-h-screen flex flex-col bg-[#03111f] text-[#e6f6ff]">
      <Navbar />

      <main className="flex-1 max-w-[1920px] w-full mx-auto p-4 flex flex-col lg:flex-row gap-4 overflow-hidden">
        {/* 1. Left Column: File Tree */}
        <aside className="w-full lg:w-72 flex-shrink-0 flex flex-col justify-between glass-panel p-4 border-cyan-800/30">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-cyan-900/40 mb-3">
              <span className="font-heading font-bold text-sm text-white">Case files</span>
              <Link
                to="/board"
                className="text-xs text-cyan-400 hover:text-cyan-300 font-medium transition"
              >
                Board →
              </Link>
            </div>

            <p className="text-[11px] font-mono text-[#9fc3d6]/70 mb-3">
              {project ? `${project.name} @ ${project.commit || "HEAD"}` : "Loading repository..."}
            </p>

            {projectError ? (
              <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/40 text-xs text-rose-300 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span>{projectError}</span>
              </div>
            ) : projectLoading ? (
              <div className="py-8 flex items-center justify-center gap-2 text-xs text-cyan-400 font-mono">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading file tree...</span>
              </div>
            ) : (
              <div className="space-y-1 text-xs font-mono">
                <div className="flex items-center gap-1.5 py-1 text-cyan-300 font-bold">
                  <ChevronDown className="w-3.5 h-3.5 text-cyan-400" />
                  <span>{project?.name || "root"}</span>
                </div>

                <div className="pl-4 space-y-1">
                  {dataFiles.length > 0 && (
                    <>
                      <div className="flex items-center justify-between py-1 text-slate-400">
                        <div className="flex items-center gap-1.5">
                          <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
                          <span>data</span>
                        </div>
                        <span className="text-[10px] text-slate-600">{dataFiles.length} files</span>
                      </div>
                      {dataFiles.map((f) => (
                        <button
                          key={f.path}
                          onClick={() => handleSelectFile(f.path)}
                          className={`w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-left transition pl-4 ${
                            activeFile === f.path
                              ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                              : "text-[#9fc3d6] hover:bg-white/5 hover:text-white"
                          }`}
                        >
                          <div className="flex items-center gap-2 truncate">
                            <FileText className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                            <span className="truncate">{f.path.replace("data/", "")}</span>
                          </div>
                          <span className="text-[10px] text-slate-500">{f.lines || ""}</span>
                        </button>
                      ))}
                    </>
                  )}

                  {rootFiles.map((f) => {
                    const isCurrent = activeFile === f.path;
                    return (
                      <button
                        key={f.path}
                        onClick={() => handleSelectFile(f.path)}
                        className={`w-full flex items-center justify-between px-2 py-1.5 rounded-lg text-left transition ${
                          isCurrent
                            ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                            : "text-[#9fc3d6] hover:bg-white/5 hover:text-white"
                        }`}
                      >
                        <div className="flex items-center gap-2 truncate">
                          {f.kind === "py" ? (
                            <FileCode className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
                          ) : (
                            <FileText className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                          )}
                          <span className="truncate">{f.path}</span>
                        </div>
                        <span className="text-[10px] text-slate-500">{f.lines || ""}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Footer Safety Notice */}
          <div className="pt-4 border-t border-cyan-900/40 text-[11px] text-[#9fc3d6]/70 leading-snug flex items-center gap-2">
            <Lock className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
            <span>Read-only. Secrets are masked. Nothing here is ever executed.</span>
          </div>
        </aside>

        {/* 2. Center Column: File Tabs & Code / Graph Viewer */}
        <section className="flex-1 flex flex-col glass-panel border-cyan-800/30 overflow-hidden">
          {/* File Tabs & View Switcher */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-cyan-900/40 bg-[#03111f]/80">
            <div className="flex items-center gap-1 overflow-x-auto">
              {openTabs.map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveFile(t)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-mono transition flex items-center gap-1.5 ${
                    activeFile === t
                      ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                      : "text-[#9fc3d6] hover:bg-white/5 hover:text-white"
                  }`}
                >
                  <FileCode className="w-3.5 h-3.5 text-cyan-400" />
                  <span>{t}</span>
                </button>
              ))}
            </div>

            <div className="flex items-center gap-1 bg-[#020b14] p-1 rounded-xl border border-cyan-900/60">
              <button
                onClick={() => setViewMode("code")}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                  viewMode === "code"
                    ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                    : "text-[#9fc3d6] hover:text-white"
                }`}
              >
                Code
              </button>
              <button
                onClick={() => setViewMode("graph")}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition ${
                  viewMode === "graph"
                    ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                    : "text-[#9fc3d6] hover:text-white"
                }`}
              >
                Import graph
              </button>
            </div>
          </div>

          {/* Main Viewer Body */}
          <div className="flex-1 p-3 bg-[#020b14]/50 overflow-hidden">
            {projectError ? (
              <div className="h-full flex flex-col items-center justify-center p-6 text-center">
                <div className="max-w-md p-6 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs font-mono space-y-2">
                  <AlertTriangle className="w-6 h-6 text-rose-400 mx-auto" />
                  <p className="font-semibold text-rose-200">The CodeLore API is offline.</p>
                  <p className="text-rose-300/80">Start it with: uvicorn server.app:app --port 8000</p>
                </div>
              </div>
            ) : !activeFile ? (
              <div className="h-full flex flex-col items-center justify-center p-8 text-center text-[#9fc3d6] font-mono text-sm space-y-3">
                <FileCode className="w-8 h-8 text-cyan-400/50" />
                <p>Select a file</p>
              </div>
            ) : fileLoading ? (
              <div className="h-full flex items-center justify-center p-6 text-center text-cyan-400 font-mono text-xs gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Reading file...</span>
              </div>
            ) : fileError ? (
              <div className="h-full flex flex-col items-center justify-center p-6">
                <div className="max-w-md p-6 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-xs font-mono text-center space-y-3">
                  <AlertTriangle className="w-6 h-6 text-rose-400 mx-auto" />
                  <p className="font-semibold text-rose-200">Unable to load file</p>
                  <p className="text-rose-300/80">{fileError}</p>
                </div>
              </div>
            ) : viewMode === "code" ? (
              <CodeViewer
                path={activeFile}
                lines={fileLines}
                highlightRange={highlightRange}
              />
            ) : (
              <ImportGraph
                nodesData={graphData.nodes}
                edgesData={graphData.edges}
                highlightedFiles={activeFile ? [activeFile] : []}
                onSelectFile={(f) => {
                  handleSelectFile(f);
                  setViewMode("code");
                }}
              />
            )}
          </div>
        </section>

        {/* 3. Right Column: Outline & Ask about this file */}
        <aside className="w-full lg:w-80 flex-shrink-0 flex flex-col justify-between glass-panel p-4 border-cyan-800/30 space-y-6">
          <div className="space-y-4">
            <div>
              <span className="text-[11px] font-mono uppercase tracking-wider text-cyan-400 font-semibold block mb-2">
                OUTLINE · {activeFile ? activeFile.toUpperCase() : "NO FILE"}
              </span>

              {!activeFile ? (
                <p className="text-xs text-[#9fc3d6]/60 italic font-mono">
                  Select a file
                </p>
              ) : outlineLoading ? (
                <div className="py-4 flex items-center justify-center gap-2 text-xs text-cyan-400 font-mono">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Parsing outline...</span>
                </div>
              ) : outline.length === 0 ? (
                <p className="text-xs text-[#9fc3d6]/60 italic font-mono">
                  No functions or classes
                </p>
              ) : (
                <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                  {outline.map((item) => (
                    <button
                      key={`${item.name}-${item.start}`}
                      onClick={() => setHighlightRange({ start: item.start, end: item.end })}
                      className="w-full flex items-center justify-between p-2 rounded-lg bg-[#020b14]/60 hover:bg-cyan-500/10 border border-cyan-900/40 text-left text-xs font-mono transition group"
                    >
                      <span className="font-semibold text-white group-hover:text-cyan-300 truncate pr-2">
                        {item.name}()
                      </span>
                      <span className="text-[11px] text-cyan-400/80 flex-shrink-0">
                        {item.start}–{item.end}
                      </span>
                    </button>
                  ))}
                </div>
              )}
              <span className="text-[10px] text-slate-500 font-mono block mt-2">
                from get_file_outline · exact syntax-tree ranges
              </span>
            </div>

            {/* Ask About This File Section - only when activeFile is selected */}
            {activeFile && (
              <div className="pt-4 border-t border-cyan-900/40">
                <span className="text-[11px] font-mono uppercase tracking-wider text-cyan-300 font-semibold block mb-3">
                  ASK ABOUT THIS FILE
                </span>

                <div className="space-y-2">
                  {[
                    `What does ${activeFile} do?`,
                    `Which files does ${activeFile} import?`,
                    `Explain ${activeFile} from top to bottom.`,
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => handleAskAboutFile(q)}
                      className="w-full text-left p-2.5 rounded-xl bg-white/5 hover:bg-cyan-500/15 border border-cyan-800/40 text-xs text-[#e6f6ff] transition flex items-center justify-between group"
                    >
                      <span>{q}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-cyan-400 group-hover:translate-x-1 transition" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Lore Mascot Thumbnail */}
          <div className="pt-4 border-t border-cyan-900/40 flex justify-end">
            <img
              src="/lore.png"
              alt="Detective Lore"
              className="h-20 w-auto object-contain drop-shadow-md opacity-85"
            />
          </div>
        </aside>
      </main>
    </div>
  );
};
