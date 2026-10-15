import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Navbar } from "../components/Navbar";
import { MascotBubble } from "../components/MascotBubble";
import { Copy, Check, ArrowRight, Loader2, AlertTriangle } from "lucide-react";
import { fetchOverview, BACKEND_OFFLINE_MSG } from "../api";
import type { OverviewResponse } from "../api";

export const StartHerePage: React.FC = () => {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchOverview()
      .then((data) => {
        setOverview(data);
        setError(null);
      })
      .catch((err) => {
        setError(err.message || BACKEND_OFFLINE_MSG);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const handleCopy = (cmd: string) => {
    navigator.clipboard.writeText(cmd);
    setCopiedCmd(cmd);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#03111f] text-[#e6f6ff]">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 lg:p-10 space-y-8">
        {/* Header Ribbon */}
        <div className="space-y-2">
          <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 font-semibold">
            ONBOARDING GUIDE · YOUR FIRST HOUR
          </span>
          <h1 className="font-heading font-extrabold text-3xl sm:text-4xl text-white">
            New here? Follow the trail.
          </h1>
          <p className="text-sm text-[#9fc3d6]">
            Understand how this codebase executes, what files to read first, and how to run it.
          </p>
        </div>

        {error ? (
          <div className="p-6 rounded-2xl bg-rose-950/40 border border-rose-500/40 text-rose-300 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400 flex-shrink-0" />
            <span className="text-sm font-mono">{error}</span>
          </div>
        ) : loading ? (
          <div className="py-20 flex flex-col items-center justify-center gap-3 text-cyan-400 font-mono text-sm">
            <Loader2 className="w-8 h-8 animate-spin" />
            <span>Analyzing codebase architecture and entry points...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left 2 Cols: Trail & Stages */}
            <div className="lg:col-span-2 space-y-6">
              {/* Entry Point Card */}
              <div className="glass-panel p-5 border-cyan-800/40 flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-400 font-bold block mb-1">
                    ENTRY POINT
                  </span>
                  <h3 className="font-heading font-bold text-lg text-white">
                    {overview?.entry_point || "No executable entry point found"}
                  </h3>
                  <p className="text-xs text-[#9fc3d6] font-mono mt-0.5">
                    {overview?.also_runnable && overview.also_runnable.length > 0
                      ? `Also runnable: ${overview.also_runnable.join(", ")}`
                      : "Primary executable with command-line interface"}
                  </p>
                </div>
                <Link
                  to="/files"
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-cyan-500/20 text-cyan-200 border border-cyan-400/30 text-xs font-semibold hover:bg-cyan-500/30 transition"
                >
                  <span>Inspect in Files</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>

              {/* Reading Order Trail */}
              <div className="glass-panel p-6 border-cyan-800/30 space-y-3">
                <h3 className="font-heading font-bold text-base text-white mb-2">
                  Reading Order Trail
                </h3>

                {overview?.reading_order && overview.reading_order.length > 0 ? (
                  <div className="space-y-3">
                    {overview.reading_order.map((item, idx) => (
                      <div
                        key={item.path}
                        className="flex items-start gap-4 p-3 rounded-xl bg-[#020b14]/60 border border-cyan-900/40 hover:border-cyan-400/30 transition"
                      >
                        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-cyan-500/20 border border-cyan-400/40 text-cyan-300 font-heading font-bold text-xs flex items-center justify-center">
                          {idx + 1}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="font-mono font-bold text-sm text-white">
                              {item.path}
                            </span>
                          </div>
                          {item.doc && (
                            <p className="text-xs text-[#9fc3d6] mt-0.5">
                              {item.doc}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-[#9fc3d6]/70 italic font-mono">
                    No reading order defined for this project.
                  </p>
                )}
              </div>

              {/* The Execution Stages */}
              {overview?.stages && overview.stages.length > 0 && (
                <div className="glass-panel p-6 border-cyan-800/30">
                  <h3 className="font-heading font-bold text-xs uppercase font-mono tracking-wider text-cyan-400 mb-4">
                    EXECUTION STAGES
                  </h3>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    {overview.stages.map((st, i) => (
                      <div
                        key={st}
                        className="p-3 rounded-xl bg-cyan-950/40 border border-cyan-800/30 text-xs font-mono"
                      >
                        <span className="text-cyan-400 font-bold block mb-1">
                          0{i + 1}
                        </span>
                        <span className="text-white text-xs">{st}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Right 1 Col: Mascot & How To Run It */}
            <div className="space-y-6">
              {/* Lore Speech Bubble */}
              <div className="glass-panel p-6 border-cyan-800/40 flex flex-col items-center text-center">
                <MascotBubble
                  quote="Every detective starts with the entry point. Inspect the flags and follow the clues."
                  size="md"
                />
              </div>

              {/* How To Run It Box */}
              <div className="glass-panel p-6 border-cyan-800/30 space-y-4">
                <h3 className="font-heading font-bold text-base text-white">
                  How to run it
                </h3>

                {overview?.commands && overview.commands.length > 0 ? (
                  <div className="space-y-3">
                    {overview.commands.map((cmd) => {
                      const isCopied = copiedCmd === cmd;
                      return (
                        <div
                          key={cmd}
                          className="p-3 rounded-xl bg-[#020b14] border border-cyan-900/50 flex items-center justify-between font-mono text-xs text-cyan-200"
                        >
                          <span className="truncate pr-2">{cmd}</span>
                          <button
                            onClick={() => handleCopy(cmd)}
                            className="p-1 rounded bg-white/5 hover:bg-white/10 text-cyan-300 transition flex-shrink-0"
                            title="Copy command"
                          >
                            {isCopied ? (
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs text-[#9fc3d6]/70 italic font-mono">
                    No run commands detected in the entry point.
                  </p>
                )}

                {overview?.dependency_files && overview.dependency_files.length > 0 && (
                  <div className="pt-2 border-t border-cyan-900/40 text-[11px] text-[#9fc3d6] font-mono">
                    <span>Dependencies: {overview.dependency_files.join(", ")}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
