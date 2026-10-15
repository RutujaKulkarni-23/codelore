import React, { useEffect, useRef } from "react";
import { FileCode, Copy, Check, Download } from "lucide-react";

interface CodeViewerProps {
  path: string;
  lines: string[];
  highlightRange?: { start: number; end: number };
  className?: string;
}

export const CodeViewer: React.FC<CodeViewerProps> = ({
  path,
  lines,
  highlightRange,
  className = "",
}) => {
  const highlightRef = useRef<HTMLDivElement>(null);
  const [copied, setCopied] = React.useState(false);

  useEffect(() => {
    if (highlightRange && highlightRef.current) {
      highlightRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [highlightRange, path]);

  const handleCopy = () => {
    navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const filename = path.split("/").pop() || "file.txt";
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className={`flex flex-col h-full bg-[#020b14] rounded-2xl border border-cyan-900/40 overflow-hidden font-code text-xs ${className}`}>
      {/* File Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#031526] border-b border-cyan-900/40 text-[#9fc3d6]">
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-cyan-400" />
          <span className="font-semibold text-white tracking-wide">{path}</span>
          {highlightRange && (
            <span className="px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-400/40 text-[11px] text-cyan-300 font-mono">
              L{highlightRange.start}–{highlightRange.end}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-[#9fc3d6]/70 mr-1">{lines.length} lines</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 rounded bg-white/5 hover:bg-white/10 text-cyan-200 transition"
            title="Copy code"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span className="text-[10px]">{copied ? "Copied" : "Copy"}</span>
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-1 px-2 py-1 rounded bg-white/5 hover:bg-white/10 text-cyan-200 transition"
            title="Download file"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[10px]">Download</span>
          </button>
        </div>
      </div>

      {/* Code Lines Viewer */}
      <div className="flex-1 overflow-auto p-2 leading-relaxed">
        {lines.length === 0 ? (
          <div className="p-6 text-center text-[#9fc3d6]/60 italic font-body">
            Loading file contents...
          </div>
        ) : (
          lines.map((line, idx) => {
            const lineNum = idx + 1;
            const isHighlighted =
              highlightRange &&
              lineNum >= highlightRange.start &&
              lineNum <= highlightRange.end;
            const isFirstHighlighted =
              highlightRange && lineNum === highlightRange.start;

            return (
              <div
                key={lineNum}
                ref={isFirstHighlighted ? highlightRef : undefined}
                className={`flex items-start transition-colors duration-150 ${
                  isHighlighted
                    ? "bg-cyan-500/15 border-l-2 border-cyan-400 text-cyan-100"
                    : "hover:bg-white/[0.02] text-[#d6e9f5]"
                }`}
              >
                {/* Line number gutter */}
                <span
                  className={`select-none w-12 flex-shrink-0 text-right pr-4 py-0.5 font-mono text-[11px] ${
                    isHighlighted ? "text-cyan-300 font-bold" : "text-slate-600"
                  }`}
                >
                  {lineNum}
                </span>

                {/* Line content */}
                <pre className="py-0.5 pr-4 whitespace-pre font-code flex-1 overflow-x-visible">
                  {line || " "}
                </pre>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
