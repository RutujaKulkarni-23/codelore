import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Navbar } from "../components/Navbar";
import { MascotBubble } from "../components/MascotBubble";
import { Lock } from "lucide-react";

export const SignInPage: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("rutuja@example.com");
  const [password, setPassword] = useState("••••••••••");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    navigate("/board");
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#03111f] text-[#e6f6ff]">
      <Navbar minimal />

      <main className="flex-1 max-w-6xl mx-auto px-6 py-12 flex flex-col md:flex-row items-center justify-center gap-12 lg:gap-20">
        {/* Left Detective Greeting */}
        <div className="flex-1 flex flex-col items-center text-center space-y-4">
          <MascotBubble
            quote="Welcome back, partner. The case files are where you left them."
            size="lg"
          />
          <p className="text-xs text-[#9fc3d6]/70 font-mono flex items-center gap-1.5 pt-2">
            <Lock className="w-3.5 h-3.5 text-cyan-400" />
            <span>Your keys stay on the server. The browser never sees them.</span>
          </p>
        </div>

        {/* Right Sign-in Card */}
        <div className="w-full max-w-md glass-panel p-8 sm:p-10 border-cyan-800/40 shadow-2xl">
          <div className="mb-6">
            <h2 className="font-heading font-extrabold text-2xl text-white">Sign in</h2>
            <p className="text-sm text-[#9fc3d6] mt-1">Continue your investigations.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase font-mono tracking-wider text-[#9fc3d6] mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-[#020b14] border border-cyan-900/60 text-white text-sm focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 transition"
                required
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold uppercase font-mono tracking-wider text-[#9fc3d6]">
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => alert("Password reset is managed by server admin.")}
                  className="text-xs text-cyan-400 hover:underline"
                >
                  Forgot password?
                </button>
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-[#020b14] border border-cyan-900/60 text-white text-sm focus:outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 transition"
                required
              />
            </div>

            <button
              type="submit"
              className="w-full py-3 px-4 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-heading font-bold text-sm tracking-wide shadow-lg shadow-cyan-500/25 transition active:scale-[0.98] mt-2"
            >
              Sign in
            </button>
          </form>

          <div className="relative my-6 text-center">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-cyan-900/40"></div>
            </div>
            <span className="relative px-3 bg-[#0a1828] text-xs text-[#9fc3d6]/60 uppercase font-mono">
              or
            </span>
          </div>

          <button
            onClick={() => navigate("/board")}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl glass-card hover:bg-white/10 text-white text-sm font-medium transition"
          >
            <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
            </svg>
            <span>Continue with GitHub</span>
          </button>

          <div className="mt-6 text-center text-xs text-[#9fc3d6]">
            <span>New detective? </span>
            <button
              onClick={() => navigate("/board")}
              className="text-cyan-400 font-semibold hover:underline"
            >
              Create an account
            </button>
          </div>
        </div>
      </main>
    </div>
  );
};
