import React, { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Plus,
  LayoutDashboard,
  FolderCode,
  Compass,
  GitBranch,
  Settings,
  FolderOpen,
} from "lucide-react";
import { getRecentCases } from "../lib/storage";
import type { SavedCase } from "../lib/storage";
import { fetchProject } from "../api";
import type { ProjectResponse } from "../api";

interface SidebarProps {
  onNewCase?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onNewCase }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [recentCases, setRecentCases] = useState<SavedCase[]>([]);
  const [project, setProject] = useState<ProjectResponse | null>(null);

  useEffect(() => {
    setRecentCases(getRecentCases());
  }, [location.pathname]);

  useEffect(() => {
    fetchProject()
      .then(setProject)
      .catch(() => {});
  }, []);

  const navItems = [
    { label: "Case board", path: "/board", icon: LayoutDashboard },
    { label: "Case files", path: "/files", icon: FolderCode },
    { label: "Start here", path: "/start", icon: Compass },
  ];

  const handleNewCase = () => {
    if (onNewCase) {
      onNewCase();
    } else {
      navigate("/board");
    }
  };

  return (
    <aside className="w-64 flex-shrink-0 flex flex-col justify-between p-4 glass-panel border-cyan-800/30 min-h-[calc(100vh-5rem)]">
      <div className="space-y-6">
        {/* Action Button: + New Case */}
        <button
          onClick={handleNewCase}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-gradient-to-r from-cyan-400 to-teal-500 hover:from-cyan-300 hover:to-teal-400 text-slate-950 font-bold text-sm tracking-wide shadow-lg shadow-cyan-950/50 transition active:scale-[0.98]"
        >
          <Plus className="w-4 h-4 stroke-[3]" />
          <span>New case</span>
        </button>

        {/* Main Navigation */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition ${
                  isActive
                    ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30 shadow-sm"
                    : "text-[#9fc3d6] hover:bg-white/5 hover:text-white"
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? "text-cyan-400" : "text-[#9fc3d6]"}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}

          {/* Disabled / Coming soon items */}
          <button
            onClick={() => alert("Importing external repositories is coming soon!")}
            className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:bg-white/5 transition opacity-75"
          >
            <div className="flex items-center gap-3">
              <GitBranch className="w-4 h-4" />
              <span>Import codebase</span>
            </div>
            <span className="text-[10px] font-mono text-cyan-400/70 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/20">soon</span>
          </button>

          <button
            onClick={() => alert("Settings panel is coming soon!")}
            className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:bg-white/5 transition opacity-75"
          >
            <div className="flex items-center gap-3">
              <Settings className="w-4 h-4" />
              <span>Settings</span>
            </div>
            <span className="text-[10px] font-mono text-cyan-400/70 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/20">soon</span>
          </button>
        </nav>

        {/* Recent Cases */}
        <div className="pt-4 border-t border-cyan-900/40">
          <div className="flex items-center gap-2 px-2 mb-3">
            <FolderOpen className="w-3.5 h-3.5 text-cyan-400/80" />
            <h4 className="text-[11px] font-mono tracking-wider font-semibold text-cyan-300 uppercase">
              Recent Cases
            </h4>
          </div>

          <div className="space-y-1 max-h-60 overflow-y-auto pr-1">
            {recentCases.length === 0 ? (
              <p className="text-xs text-[#9fc3d6]/60 italic font-mono px-2 py-1">
                No cases opened yet.
              </p>
            ) : (
              recentCases.map((rc) => {
                const isCurrent = location.pathname === `/case/${rc.id}`;
                return (
                  <Link
                    key={rc.id}
                    to={`/case/${rc.id}`}
                    className={`group flex items-center justify-between px-3 py-2 rounded-lg text-xs transition ${
                      isCurrent
                        ? "bg-cyan-500/15 text-cyan-200 font-medium"
                        : "text-[#9fc3d6] hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <span className="truncate pr-2">{rc.title}</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400/50 group-hover:bg-cyan-400 transition" />
                  </Link>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Footer Info */}
      <div className="pt-4 border-t border-cyan-900/30 text-[11px] text-[#9fc3d6]/70 font-mono">
        <p>Target: {project ? project.name : "Loading..."} (read-only)</p>
        <p className="text-[10px] text-cyan-400/50">Protected by Detective Lore</p>
      </div>
    </aside>
  );
};
