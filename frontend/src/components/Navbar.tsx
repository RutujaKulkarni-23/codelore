import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Code2, GitFork, Sun, Moon } from "lucide-react";
import { useTheme } from "../lib/theme";
import { fetchHealth, fetchProject } from "../api";
import type { ProjectResponse } from "../api";

interface NavbarProps {
  minimal?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({ minimal = false }) => {
  const location = useLocation();
  const isLanding = location.pathname === "/";
  const { theme, toggleTheme } = useTheme();
  const [project, setProject] = useState<ProjectResponse | null>(null);
  const [status, setStatus] = useState<"connecting" | "connected" | "offline">("connecting");

  useEffect(() => {
    if (minimal || isLanding) return;

    let isMounted = true;

    // Never stay on "Connecting…" longer than 5 seconds
    const connectingTimeout = setTimeout(() => {
      if (isMounted) {
        setStatus((prev) => (prev === "connecting" ? "offline" : prev));
      }
    }, 5000);

    const checkStatus = async () => {
      try {
        const health = await fetchHealth();
        if (!health.ok) throw new Error("Health check failed");
        const proj = await fetchProject();
        if (isMounted) {
          setProject(proj);
          setStatus("connected");
        }
      } catch {
        if (isMounted) {
          setStatus("offline");
        }
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 30000);

    return () => {
      isMounted = false;
      clearTimeout(connectingTimeout);
      clearInterval(interval);
    };
  }, [minimal, isLanding]);

  return (
    <header className="sticky top-0 z-40 w-full backdrop-blur-md border-b border-cyan-900/40 bg-[#03111f]/80 px-6 py-3.5 transition-all">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand */}
        <Link to="/" className="flex items-center gap-3 group">
          <div className="flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-400 to-teal-600 text-slate-950 font-bold shadow-md shadow-cyan-900/40 group-hover:scale-105 transition">
            <Code2 className="w-5 h-5 stroke-[2.5]" />
          </div>
          <div className="flex flex-col">
            <span className="font-heading font-extrabold text-xl tracking-tight text-white group-hover:text-cyan-300 transition">
              CodeLore
            </span>
          </div>
          {!isLanding && !minimal && (
            <span className="hidden md:inline-block ml-3 text-xs text-[#9fc3d6] border-l border-cyan-800/60 pl-3 italic font-medium">
              Every codebase hides a story. Lore finds the evidence.
            </span>
          )}
        </Link>

        {/* Center / Right Links */}
        {isLanding ? (
          <nav className="flex items-center gap-4 sm:gap-6 text-sm font-medium text-[#9fc3d6]">
            <a href="#story" className="hover:text-cyan-300 transition hidden sm:inline-block">The story</a>
            <Link to="/board" className="hover:text-cyan-300 transition hidden sm:inline-block">The squad</Link>
            <Link to="/start" className="hover:text-cyan-300 transition hidden sm:inline-block">How it works</Link>
            
            {/* White / Dark Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-white/10 hover:bg-white/15 text-cyan-200 border border-cyan-500/30 transition shadow-sm"
              title={theme === "light" ? "Switch to dark ocean theme" : "Switch to white theme"}
              aria-label="Toggle white theme"
            >
              {theme === "light" ? (
                <>
                  <Moon className="w-3.5 h-3.5 text-cyan-600" />
                  <span>Dark theme</span>
                </>
              ) : (
                <>
                  <Sun className="w-3.5 h-3.5 text-amber-300" />
                  <span>White theme</span>
                </>
              )}
            </button>

            <Link
              to="/signin"
              className="px-4 py-1.5 rounded-full text-xs font-semibold bg-white/10 hover:bg-white/15 text-cyan-200 border border-cyan-500/30 transition shadow-sm"
            >
              Sign in
            </Link>
          </nav>
        ) : (
          <div className="flex items-center gap-3 sm:gap-4 text-xs font-medium">
            {/* Active repository status */}
            <div
              className={`hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full border transition ${
                status === "connected"
                  ? "bg-cyan-950/60 border-cyan-500/20 text-cyan-200"
                  : status === "offline"
                  ? "bg-rose-950/60 border-rose-500/30 text-rose-300"
                  : "bg-cyan-950/40 border-cyan-800/20 text-amber-200"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  status === "connected"
                    ? "bg-emerald-400 animate-pulse"
                    : status === "offline"
                    ? "bg-rose-500"
                    : "bg-amber-400 animate-ping"
                }`}
              />
              <span className="font-mono text-xs">
                {status === "connected" && project
                  ? `Connected · ${project.name} · ${
                      project.files.filter((f) => f.kind === "py").length
                    } files · ${project.total_py_lines.toLocaleString()} lines`
                  : status === "offline"
                  ? "Backend offline — start the API"
                  : "Connecting…"}
              </span>
            </div>

            {/* White / Dark Theme Toggle Button */}
            <button
              onClick={toggleTheme}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/10 hover:bg-white/15 text-cyan-200 border border-cyan-500/30 transition shadow-sm"
              title={theme === "light" ? "Switch to dark ocean theme" : "Switch to white theme"}
              aria-label="Toggle white theme"
            >
              {theme === "light" ? (
                <>
                  <Moon className="w-3.5 h-3.5 text-cyan-600" />
                  <span className="hidden md:inline">Dark</span>
                </>
              ) : (
                <>
                  <Sun className="w-3.5 h-3.5 text-amber-300" />
                  <span className="hidden md:inline">White theme</span>
                </>
              )}
            </button>

            {/* Import codebase coming soon */}
            <button
              onClick={() => alert("Codebase importer is coming in the next release.")}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-cyan-100 border border-cyan-400/20 transition"
              title="Import public GitHub repository"
            >
              <GitFork className="w-3.5 h-3.5 text-cyan-400" />
              <span>Import repo</span>
              <span className="text-[10px] text-cyan-400/70 font-mono ml-1">soon</span>
            </button>

            {/* User profile avatar */}
            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-violet-600 text-white font-bold font-heading text-xs shadow-md border border-violet-400/40">
              R
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
