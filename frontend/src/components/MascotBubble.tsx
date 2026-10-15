import React from "react";

interface MascotBubbleProps {
  quote?: string;
  subtext?: string;
  size?: "sm" | "md" | "lg";
  thinking?: boolean;
  className?: string;
}

export const MascotBubble: React.FC<MascotBubbleProps> = ({
  quote,
  subtext,
  size = "md",
  thinking = false,
  className = "",
}) => {
  const imgSizeClass = {
    sm: "h-28 w-auto",
    md: "h-48 w-auto",
    lg: "h-72 w-auto",
  }[size];

  return (
    <div className={`relative flex flex-col items-center justify-center ${className}`}>
      {quote && (
        <div className="relative mb-3 max-w-sm rounded-2xl bg-cyan-950/70 border border-cyan-400/30 px-4 py-3 shadow-xl backdrop-blur-md">
          <p className="text-sm font-medium text-cyan-100 italic leading-snug">
            "{quote}"
          </p>
          {subtext && (
            <p className="mt-1 text-xs text-cyan-300/70 font-mono">
              {subtext}
            </p>
          )}
          {/* Speech bubble tail pointing down */}
          <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-0 h-0 border-l-[8px] border-l-transparent border-r-[8px] border-r-transparent border-t-[8px] border-t-cyan-950/80" />
        </div>
      )}

      {thinking && (
        <div className="relative mb-3 flex items-center gap-2 rounded-full bg-cyan-950/80 border border-cyan-400/40 px-4 py-2 shadow-lg backdrop-blur-md">
          <span className="flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-cyan-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400"></span>
          </span>
          <span className="text-xs font-mono text-cyan-200">Investigating the crime scene...</span>
        </div>
      )}

      <div className="relative group">
        {/* Soft radial glow behind Lore */}
        <div className="absolute -inset-4 rounded-full bg-gradient-to-r from-teal-500/20 to-violet-500/20 blur-xl opacity-75 group-hover:opacity-100 transition duration-500" />
        <img
          src="/lore.png"
          alt="Detective Lore"
          className={`relative object-contain drop-shadow-[0_15px_25px_rgba(3,17,31,0.8)] ${imgSizeClass}`}
        />
      </div>
    </div>
  );
};
