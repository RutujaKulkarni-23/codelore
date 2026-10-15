import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Navbar } from "../components/Navbar";
import { Sidebar } from "../components/Sidebar";
import { ArrowRight, Search, AlertTriangle, Loader2 } from "lucide-react";
import { fetchProject, BACKEND_OFFLINE_MSG } from "../api";
import type { ProjectResponse } from "../api";
import { saveRecentCase } from "../lib/storage";

export const CaseBoardPage: React.FC = () => {
  const navigate = useNavigate();
  const [projectData, setProjectData] = useState<ProjectResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [inputQuestion, setInputQuestion] = useState("");

  useEffect(() => {
    setLoading(true);
    fetchProject()
      .then((data) => {
        setProjectData(data);
        setError(null);
      })
      .catch((err) => {
        setError(err.message || BACKEND_OFFLINE_MSG);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const pyFiles = projectData ? projectData.files.filter((f) => f.kind === "py") : [];
  const totalLines = projectData ? projectData.total_py_lines : 0;
  const totalFiles = pyFiles.length;
  const projectName = projectData ? projectData.name : "";
  const commitHash = projectData?.commit || (loading ? "..." : "HEAD");

  const handleStartCase = (question: string, defaultTitle?: string) => {
    if (!question.trim()) return;
    const caseId = `case-${Date.now()}`;
    saveRecentCase({
      id: caseId,
      title: defaultTitle || question.slice(0, 32),
      question: question.trim(),
      timestamp: Date.now(),
    });
    navigate(`/case/${caseId}?q=${encodeURIComponent(question.trim())}`);
  };

  const leads = [
    {
      category: "SEARCHER",
      color: "#60a5fa",
      title: "Where embed_query lives",
      question: "Where is embed_query defined, and what does it take?",
    },
    {
      category: "EXPLAINER",
      color: "#f0abfc",
      title: "Inside vector_store.py",
      question: "Explain vector_store.py from top to bottom.",
    },
    {
      category: "MAPPER",
      color: "#a78bfa",
      title: "The Missing Import",
      question: "Which files import upsert_to_vector_db?",
    },
    {
      category: "GUIDE",
      color: "#fbbf24",
      title: "Where do I start?",
      question: "Where should a beginner start?",
    },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-[#03111f] text-[#e6f6ff]">
      <Navbar />

      <div className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 flex flex-col lg:flex-row gap-6">
        {/* Left Sidebar */}
        <Sidebar onNewCase={() => document.getElementById("case-input")?.focus()} />

        {/* Main Content Dashboard */}
        <main className="flex-1 flex flex-col gap-6">
          {/* Greeting Hero Card */}
          <div className="relative glass-panel p-6 sm:p-8 border-cyan-800/40 overflow-hidden flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            <div className="max-w-xl space-y-2 z-10">
              <span className="text-[11px] font-mono tracking-widest uppercase text-cyan-400 font-semibold">
                DETECTIVE DASHBOARD
              </span>
              <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-white tracking-tight">
                What mystery are we solving tonight?
              </h1>
              <p className="text-sm text-[#9fc3d6]">
                {loading
                  ? "The squad is connecting to the codebase..."
                  : projectName
                  ? `The squad is standing by on ${projectName}. Pick a lead below or open a new case.`
                  : "The squad is standing by. Pick a lead below or open a new case."}
              </p>
            </div>

            {/* Lore Avatar */}
            <div className="relative flex-shrink-0 z-10 self-center">
              <div className="absolute inset-0 rounded-full bg-cyan-400/20 blur-xl animate-pulse-subtle" />
              <img
                src="/lore.png"
                alt="Detective Lore"
                className="relative h-24 sm:h-28 w-auto object-contain drop-shadow-xl"
              />
            </div>
          </div>

          {/* Squad Cards Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* 1. Code Searcher */}
            <div className="glass-card p-4 rounded-2xl border-blue-500/20 hover:border-blue-400/50 transition flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="w-7 h-7 rounded-lg bg-blue-500/20 border border-blue-400/40 text-blue-300 flex items-center justify-center font-heading font-bold text-xs">
                    S
                  </div>
                  <span className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    on duty
                  </span>
                </div>
                <h3 className="font-heading font-bold text-sm text-white mb-1">Code Searcher</h3>
                <p className="text-xs text-[#9fc3d6] leading-relaxed mb-3">
                  Finds definitions, values and concepts across the code.
                </p>
              </div>
              <div className="pt-2 border-t border-cyan-900/40 text-[10px] font-mono text-blue-300/80">
                rag_search · find_symbol
              </div>
            </div>

            {/* 2. Code Explainer */}
            <div className="glass-card p-4 rounded-2xl border-fuchsia-500/20 hover:border-fuchsia-400/50 transition flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="w-7 h-7 rounded-lg bg-fuchsia-500/20 border border-fuchsia-400/40 text-fuchsia-300 flex items-center justify-center font-heading font-bold text-xs">
                    E
                  </div>
                  <span className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    on duty
                  </span>
                </div>
                <h3 className="font-heading font-bold text-sm text-white mb-1">Code Explainer</h3>
                <p className="text-xs text-[#9fc3d6] leading-relaxed mb-3">
                  Reads a file and explains it, line range by line range.
                </p>
              </div>
              <div className="pt-2 border-t border-cyan-900/40 text-[10px] font-mono text-fuchsia-300/80">
                outline · MCP read_text_file
              </div>
            </div>

            {/* 3. Architecture Mapper */}
            <div className="glass-card p-4 rounded-2xl border-purple-500/20 hover:border-purple-400/50 transition flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="w-7 h-7 rounded-lg bg-purple-500/20 border border-purple-400/40 text-purple-300 flex items-center justify-center font-heading font-bold text-xs">
                    M
                  </div>
                  <span className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    on duty
                  </span>
                </div>
                <h3 className="font-heading font-bold text-sm text-white mb-1">Architecture Mapper</h3>
                <p className="text-xs text-[#9fc3d6] leading-relaxed mb-3">
                  Maps who imports whom across every file.
                </p>
              </div>
              <div className="pt-2 border-t border-cyan-900/40 text-[10px] font-mono text-purple-300/80">
                analyze_imports
              </div>
            </div>

            {/* 4. Onboarding Guide */}
            <div className="glass-card p-4 rounded-2xl border-amber-500/20 hover:border-amber-400/50 transition flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="w-7 h-7 rounded-lg bg-amber-500/20 border border-amber-400/40 text-amber-300 flex items-center justify-center font-heading font-bold text-xs">
                    G
                  </div>
                  <span className="flex items-center gap-1.5 text-[11px] font-mono text-emerald-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    on duty
                  </span>
                </div>
                <h3 className="font-heading font-bold text-sm text-white mb-1">Onboarding Guide</h3>
                <p className="text-xs text-[#9fc3d6] leading-relaxed mb-3">
                  Finds the entry point and how to run it.
                </p>
              </div>
              <div className="pt-2 border-t border-cyan-900/40 text-[10px] font-mono text-amber-300/80">
                get_project_overview
              </div>
            </div>
          </div>

          {/* Bottom Grid: Leads Worth Following + Codebase at a glance */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left 2 Cols: Leads Worth Following */}
            <div className="lg:col-span-2 glass-panel p-6 border-cyan-800/30 flex flex-col justify-between">
              <h2 className="font-heading font-bold text-base text-white mb-4">
                Leads worth following
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {leads.map((lead) => (
                  <button
                    key={lead.title}
                    onClick={() => handleStartCase(lead.question, lead.title)}
                    className="glass-card p-4 rounded-xl text-left border-cyan-900/40 hover:border-cyan-400/40 transition group"
                  >
                    <span
                      className="text-[10px] font-mono font-bold tracking-wider uppercase block mb-1.5"
                      style={{ color: lead.color }}
                    >
                      {lead.category}
                    </span>
                    <p className="text-xs text-[#e6f6ff] group-hover:text-cyan-300 transition line-clamp-2">
                      {lead.question}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {/* Right 1 Col: Codebase at a Glance */}
            <div className="glass-panel p-6 border-cyan-800/30 flex flex-col justify-between">
              <div>
                <h2 className="font-heading font-bold text-base text-white mb-4">
                  Codebase at a glance
                </h2>

                {error ? (
                  <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/40 text-xs text-rose-300 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                ) : loading ? (
                  <div className="py-8 flex items-center justify-center gap-2 text-xs text-cyan-400 font-mono">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Scanning codebase...</span>
                  </div>
                ) : (
                  <div className="grid grid-cols-3 gap-2 text-center pb-4 border-b border-cyan-900/40">
                    <div className="p-2 rounded-xl bg-cyan-950/40 border border-cyan-800/30">
                      <span className="font-heading font-extrabold text-2xl text-cyan-400 block">
                        {totalFiles}
                      </span>
                      <span className="text-[10px] text-[#9fc3d6] uppercase font-mono">files</span>
                    </div>

                    <div className="p-2 rounded-xl bg-cyan-950/40 border border-cyan-800/30">
                      <span className="font-heading font-extrabold text-2xl text-teal-300 block">
                        {totalLines.toLocaleString()}
                      </span>
                      <span className="text-[10px] text-[#9fc3d6] uppercase font-mono">lines</span>
                    </div>

                    <div className="p-2 rounded-xl bg-cyan-950/40 border border-cyan-800/30">
                      <span className="font-heading font-extrabold text-2xl text-amber-400 block">
                        4
                      </span>
                      <span className="text-[10px] text-[#9fc3d6] uppercase font-mono">agents</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Active Codebase Footer */}
              <div className="pt-4">
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#9fc3d6]/70 block mb-1">
                  ACTIVE CODEBASE
                </span>
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-heading font-bold text-sm text-white">
                      {projectName || (loading ? "..." : "Codebase")}
                    </h4>
                    <p className="text-xs text-[#9fc3d6]/80 font-mono">
                      commit {commitHash} · {totalFiles} files · indexed
                    </p>
                  </div>
                  <button
                    onClick={() => alert("Switching repositories is enabled for admin.")}
                    className="text-xs text-cyan-400 font-semibold hover:underline"
                  >
                    Switch
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Bottom Case Composer Bar */}
          <div className="glass-panel p-2.5 pl-4 border-cyan-500/30 shadow-xl flex items-center gap-3">
            <Search className="w-4 h-4 text-cyan-400 flex-shrink-0" />
            <input
              id="case-input"
              type="text"
              placeholder="Open a new case — ask anything about this codebase…"
              value={inputQuestion}
              onChange={(e) => setInputQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleStartCase(inputQuestion);
              }}
              className="flex-1 bg-transparent text-sm text-white placeholder-[#9fc3d6]/60 focus:outline-none"
            />
            <button
              onClick={() => handleStartCase(inputQuestion)}
              className="flex items-center justify-center w-9 h-9 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 transition shadow-md flex-shrink-0"
              title="Open case"
            >
              <ArrowRight className="w-4 h-4 stroke-[2.5]" />
            </button>
          </div>
        </main>
      </div>
    </div>
  );
};
