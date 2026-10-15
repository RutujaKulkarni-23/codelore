import React from "react";
import { Link } from "react-router-dom";
import { Navbar } from "../components/Navbar";
import { ArrowRight, Play, Sparkles } from "lucide-react";

export const LandingPage: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-[#03111f] text-[#e6f6ff]">
      <Navbar />

      <main className="flex-1 max-w-7xl mx-auto px-6 py-12 lg:py-20 flex flex-col lg:flex-row items-center justify-between gap-12">
        {/* Left Hero Column */}
        <div className="flex-1 max-w-2xl space-y-8">
          {/* Pill Badge */}
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-cyan-950/70 border border-cyan-400/30 text-cyan-300 font-mono text-xs tracking-wider uppercase font-semibold shadow-inner">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span>MULTI-AGENT CODE INTELLIGENCE</span>
          </div>

          {/* Headline */}
          <h1 className="font-heading font-extrabold text-4xl sm:text-6xl lg:text-7xl tracking-tight leading-[1.08] text-white">
            Every codebase <br />
            hides a story. <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-cyan-300 via-teal-400 to-sky-300">
              Lore finds it.
            </span>
          </h1>

          {/* Subtext */}
          <p className="text-lg text-[#9fc3d6] leading-relaxed">
            Ask anything about a Python project. A detective squad of AI agents searches, reads and maps the real code — and every answer comes with the exact file and line as evidence.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-wrap items-center gap-4 pt-2">
            <Link
              to="/board"
              className="flex items-center gap-2.5 px-6 py-3.5 rounded-2xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-heading font-bold text-sm tracking-wide shadow-lg shadow-cyan-500/25 transition active:scale-[0.98]"
            >
              <span>Open your first case</span>
              <ArrowRight className="w-4 h-4 stroke-[2.5]" />
            </Link>

            <Link
              to="/board"
              className="flex items-center gap-2 px-6 py-3.5 rounded-2xl glass-pill hover:bg-white/10 text-cyan-200 border border-cyan-400/30 font-heading font-semibold text-sm transition"
            >
              <Play className="w-4 h-4 fill-cyan-400 text-cyan-400" />
              <span>Watch Lore work</span>
            </Link>
          </div>

          {/* Technology Badges */}
          <div className="pt-8 border-t border-cyan-900/40 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-medium text-[#9fc3d6]">
            <div className="flex items-center gap-2">
              <span className="text-cyan-400">•</span>
              <span>RAG with NVIDIA embeddings</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-400">•</span>
              <span>Pinecone vector search</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-400">•</span>
              <span>Filesystem MCP</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-cyan-400">•</span>
              <span>Line-exact citations</span>
            </div>
          </div>
        </div>

        {/* Right Mascot & Floating Squad Cards Column */}
        <div className="flex-1 relative flex items-center justify-center max-w-lg lg:max-w-none w-full">
          {/* Ambient Glow */}
          <div className="absolute w-96 h-96 rounded-full bg-cyan-500/15 blur-3xl -z-10 animate-pulse-subtle" />
          <div className="absolute w-80 h-80 rounded-full bg-violet-600/15 blur-3xl -z-10 translate-x-12 translate-y-12" />

          {/* Central Mascot Image */}
          <div className="relative z-10 flex flex-col items-center">
            <img
              src="/lore.png"
              alt="Detective Lore"
              className="h-[380px] sm:h-[460px] w-auto object-contain drop-shadow-[0_25px_35px_rgba(0,0,0,0.85)]"
            />
          </div>

          {/* Floating Glass Badges */}
          {/* 1. Code Searcher */}
          <div className="absolute -top-4 right-8 z-20 glass-card p-3 rounded-2xl border-blue-400/30 max-w-[180px] shadow-xl">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full bg-[#60a5fa]" />
              <span className="text-[11px] font-heading font-bold text-[#60a5fa] tracking-wider uppercase">
                CODE SEARCHER
              </span>
            </div>
            <p className="text-xs text-[#9fc3d6]">Finds where things live</p>
          </div>

          {/* 2. Code Explainer */}
          <div className="absolute top-20 -left-6 z-20 glass-card p-3 rounded-2xl border-fuchsia-400/30 max-w-[180px] shadow-xl">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full bg-[#f0abfc]" />
              <span className="text-[11px] font-heading font-bold text-[#f0abfc] tracking-wider uppercase">
                CODE EXPLAINER
              </span>
            </div>
            <p className="text-xs text-[#9fc3d6]">Reads files, explains them</p>
          </div>

          {/* 3. Architecture Mapper */}
          <div className="absolute bottom-24 -left-8 z-20 glass-card p-3 rounded-2xl border-purple-400/30 max-w-[190px] shadow-xl">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full bg-[#a78bfa]" />
              <span className="text-[11px] font-heading font-bold text-[#a78bfa] tracking-wider uppercase">
                ARCHITECTURE MAPPER
              </span>
            </div>
            <p className="text-xs text-[#9fc3d6]">Who imports whom</p>
          </div>

          {/* 4. Onboarding Guide */}
          <div className="absolute bottom-32 -right-4 z-20 glass-card p-3 rounded-2xl border-amber-400/30 max-w-[180px] shadow-xl">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 rounded-full bg-[#fbbf24]" />
              <span className="text-[11px] font-heading font-bold text-[#fbbf24] tracking-wider uppercase">
                ONBOARDING GUIDE
              </span>
            </div>
            <p className="text-xs text-[#9fc3d6]">Shows where to start</p>
          </div>

          {/* 5. Evidence Badge */}
          <div className="absolute bottom-4 right-12 z-20 glass-pill px-4 py-2 border-cyan-400/40 font-mono text-xs text-cyan-300 shadow-xl flex items-center gap-2">
            <span>evidence</span>
            <span>→</span>
            <span className="font-bold underline text-white">file.py:27</span>
          </div>
        </div>
      </main>
    </div>
  );
};
