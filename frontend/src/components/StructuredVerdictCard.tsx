import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ShieldCheck,
  Sparkles,
  AlertTriangle,
  Copy,
  Check,
  Terminal,
  FileCode,
  ArrowRight,
  GitCommit,
  ExternalLink,
} from "lucide-react";
import type { Verdict } from "../lib/sseReducer";

interface StructuredVerdictCardProps {
  verdict: Verdict;
  onCitationClick: (path: string, start: number, end: number) => void;
  activeAgent?: string;
  durationSeconds?: number;
}

export const StructuredVerdictCard: React.FC<StructuredVerdictCardProps> = ({
  verdict,
  onCitationClick,
  activeAgent,
  durationSeconds,
}) => {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const isDeterministic = ["outline", "symbol", "imports", "overview"].includes(verdict.kind);
  const badgeLabel = isDeterministic
    ? "Answered by tool - exact"
    : verdict.kind === "not_found"
    ? "Cold case - not found"
    : "Written by AI - check evidence";

  const badgeColor = isDeterministic
    ? "bg-emerald-500/20 text-emerald-300 border-emerald-400/40"
    : verdict.kind === "not_found"
    ? "bg-amber-500/20 text-amber-300 border-amber-400/40"
    : "bg-cyan-500/20 text-cyan-300 border-cyan-400/40";

  return (
    <div
      className={`p-5 rounded-2xl border transition shadow-xl space-y-4 ${
        verdict.kind === "not_found"
          ? "bg-amber-950/30 border-amber-500/40"
          : "bg-[#031526]/90 border-cyan-500/40"
      }`}
    >
      {/* Header with Honest Badges */}
      <div className="flex flex-wrap items-center justify-between pb-3 border-b border-cyan-900/40 gap-2">
        <div className="flex items-center gap-2">
          {activeAgent && (
            <span className="px-2.5 py-0.5 rounded font-mono font-bold text-xs bg-cyan-950 text-cyan-300 border border-cyan-500/30">
              {activeAgent}
            </span>
          )}
          <span className={`px-2.5 py-0.5 rounded-full font-mono font-bold text-xs border flex items-center gap-1.5 ${badgeColor}`}>
            {isDeterministic ? (
              <ShieldCheck className="w-3.5 h-3.5" />
            ) : verdict.kind === "not_found" ? (
              <AlertTriangle className="w-3.5 h-3.5" />
            ) : (
              <Sparkles className="w-3.5 h-3.5" />
            )}
            <span>{badgeLabel}</span>
          </span>
        </div>
        {durationSeconds !== undefined && durationSeconds > 0 && (
          <span className="text-[11px] font-mono text-slate-400">
            {durationSeconds}s
          </span>
        )}
      </div>

      {/* 1. Outline Kind -> Table */}
      {verdict.kind === "outline" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-xs font-mono text-cyan-300">
            <FileCode className="w-4 h-4 text-cyan-400" />
            <span>File Outline: <strong className="text-white">{verdict.data?.path}</strong></span>
          </div>
          <div className="overflow-x-auto rounded-xl border border-cyan-900/40 bg-[#020b14]/60">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-cyan-950/60 border-b border-cyan-900/40 text-cyan-300/80">
                <tr>
                  <th className="py-2.5 px-3">Function / Class</th>
                  <th className="py-2.5 px-3">Signature</th>
                  <th className="py-2.5 px-3">Doc</th>
                  <th className="py-2.5 px-3 text-right">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cyan-900/30">
                {(verdict.data?.items || []).map((item: any, idx: number) => (
                  <tr key={idx} className="hover:bg-cyan-950/30 transition">
                    <td className="py-2.5 px-3 font-semibold text-white">{item.name}</td>
                    <td className="py-2.5 px-3 text-cyan-200/90 font-mono text-[11px] max-w-xs truncate" title={item.signature}>
                      {item.signature}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400 text-[11px] max-w-xs truncate" title={item.doc}>
                      {item.doc || "—"}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <button
                        onClick={() => onCitationClick(verdict.data.path, item.start, item.end)}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-cyan-950 border border-cyan-400/40 hover:bg-cyan-500/20 text-cyan-300 font-mono text-[10px] transition"
                        title={`View ${verdict.data.path}:${item.start}-${item.end}`}
                      >
                        <span>{`${verdict.data.path}:${item.start}-${item.end}`}</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 2. Symbol Kind -> Card per definition */}
      {verdict.kind === "symbol" && (
        <div className="space-y-3">
          {(verdict.data?.items || []).map((item: any, idx: number) => (
            <div
              key={idx}
              className="p-3.5 rounded-xl border border-cyan-900/50 bg-[#020b14]/70 space-y-2 hover:border-cyan-500/40 transition"
            >
              <div className="flex items-center justify-between">
                <span className="font-heading font-bold text-white text-sm">{item.name}</span>
                <button
                  onClick={() => onCitationClick(item.path, item.start, item.end)}
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-cyan-950 border border-cyan-400/40 hover:bg-cyan-500/20 text-cyan-300 font-mono text-xs transition"
                >
                  <span>{`${item.path}:${item.start}-${item.end}`}</span>
                  <ExternalLink className="w-3 h-3" />
                </button>
              </div>
              <div className="p-2 rounded bg-black/40 border border-cyan-950 font-mono text-xs text-cyan-200">
                <code>{item.signature}</code>
              </div>
              {item.doc && (
                <p className="text-xs text-slate-400 italic font-body">{item.doc}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 3. Imports Kind -> Defined in + Importers list */}
      {verdict.kind === "imports" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-mono text-slate-400">Target:</span>
            <span className="px-2 py-0.5 rounded bg-cyan-950 font-mono text-xs text-cyan-300 font-bold border border-cyan-500/30">
              {verdict.data?.target}
            </span>
            {verdict.data?.defined_in && (
              <>
                <span className="text-xs font-mono text-slate-400">· Defined in:</span>
                <button
                  onClick={() => onCitationClick(verdict.data.defined_in, 1, 30)}
                  className="px-2 py-0.5 rounded bg-blue-950 font-mono text-xs text-blue-300 font-semibold border border-blue-500/40 hover:underline"
                >
                  {verdict.data.defined_in}
                </button>
              </>
            )}
          </div>

          <div className="space-y-2">
            <span className="text-[11px] font-mono uppercase tracking-wider text-cyan-400 font-semibold block">
              Importers ({(verdict.data?.importers || []).length} reference(s))
            </span>
            {(verdict.data?.importers || []).length === 0 ? (
              <p className="text-xs text-slate-400 italic">No files import this target.</p>
            ) : (
              <div className="space-y-2">
                {(verdict.data?.importers || []).map((imp: any, idx: number) => (
                  <div
                    key={idx}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-2.5 rounded-xl border border-cyan-900/40 bg-[#020b14]/70"
                  >
                    <div className="flex items-center gap-2 font-mono text-xs text-white">
                      <GitCommit className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
                      <code className="text-cyan-200">{imp.statement || `import ${verdict.data.target}`}</code>
                    </div>
                    <button
                      onClick={() => onCitationClick(imp.path, imp.line, imp.line)}
                      className="self-start sm:self-auto inline-flex items-center gap-1 px-2.5 py-0.5 rounded bg-cyan-950 border border-cyan-400/40 hover:bg-cyan-500/20 text-cyan-300 font-mono text-xs transition"
                    >
                      <span>{`${imp.path}:${imp.line}`}</span>
                      <ExternalLink className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. Overview Kind -> Structured Sections */}
      {verdict.kind === "overview" && (
        <div className="space-y-5 text-xs font-mono">
          {/* Start Here */}
          {verdict.data?.entry_point && (
            <div className="p-3 rounded-xl bg-cyan-950/40 border border-cyan-500/30 flex items-center justify-between">
              <div>
                <span className="text-[10px] text-cyan-400 uppercase tracking-wider font-semibold block">
                  START HERE (ENTRY POINT)
                </span>
                <span className="font-bold text-white text-sm">{verdict.data.entry_point}</span>
                {verdict.data.also_runnable?.length > 0 && (
                  <span className="text-[11px] text-slate-400 block mt-0.5">
                    Also runnable: {verdict.data.also_runnable.join(", ")}
                  </span>
                )}
              </div>
              <button
                onClick={() => onCitationClick(verdict.data.entry_point, 1, 30)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-cyan-400 hover:bg-cyan-300 text-slate-950 font-bold transition shadow-sm"
              >
                <span>View file</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* How to Run */}
          {(verdict.data?.commands || []).length > 0 && (
            <div className="space-y-2">
              <span className="text-[11px] uppercase tracking-wider text-cyan-400 font-semibold block">
                HOW TO RUN
              </span>
              <div className="space-y-1.5">
                {(verdict.data.commands || []).map((cmd: string, idx: number) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded-lg bg-black/50 border border-cyan-900/40"
                  >
                    <div className="flex items-center gap-2">
                      <Terminal className="w-3.5 h-3.5 text-cyan-400" />
                      <code className="text-cyan-200">{cmd}</code>
                    </div>
                    <button
                      onClick={() => handleCopy(cmd, idx)}
                      className="p-1 rounded hover:bg-white/10 text-slate-400 hover:text-white transition"
                      title="Copy command"
                    >
                      {copiedIndex === idx ? (
                        <Check className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="w-3.5 h-3.5" />
                      )}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Stages */}
          {(verdict.data?.stages || []).length > 0 && (
            <div className="space-y-2">
              <span className="text-[11px] uppercase tracking-wider text-cyan-400 font-semibold block">
                PIPELINE STAGES
              </span>
              <div className="space-y-1">
                {(verdict.data.stages || []).map((stage: any, idx: number) => {
                  const stageText =
                    typeof stage === "string"
                      ? stage
                      : stage.name
                      ? `${stage.name}${stage.script ? ` (${stage.script})` : ""}${stage.purpose ? `: ${stage.purpose}` : ""}`
                      : JSON.stringify(stage);
                  return (
                    <div key={idx} className="flex items-center gap-2 p-1.5 rounded bg-cyan-950/20 text-slate-200">
                      <span className="w-5 h-5 rounded-full bg-cyan-900/60 border border-cyan-500/30 text-cyan-300 flex items-center justify-center font-bold text-[10px] flex-shrink-0">
                        {idx + 1}
                      </span>
                      <span>{stageText}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Reading Order */}
          {(verdict.data?.reading_order || []).length > 0 && (
            <div className="space-y-2">
              <span className="text-[11px] uppercase tracking-wider text-cyan-400 font-semibold block">
                READ IN THIS ORDER
              </span>
              <div className="space-y-1.5">
                {(verdict.data.reading_order || []).map((item: any, idx: number) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded-lg border border-cyan-900/30 bg-[#020b14]/50"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500 text-[10px]">{idx + 1}.</span>
                      <button
                        onClick={() => onCitationClick(item.path, 1, 30)}
                        className="font-bold text-cyan-300 hover:underline"
                      >
                        {item.path}
                      </button>
                      {item.doc && (
                        <span className="text-slate-400 text-[11px] hidden sm:inline">
                          — {item.doc}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Other Files */}
          <div className="pt-2 border-t border-cyan-900/30 grid grid-cols-1 sm:grid-cols-3 gap-2 text-[11px]">
            <div>
              <span className="text-slate-500 block">Data Files:</span>
              <span className="text-slate-300">{(verdict.data?.data_files || []).join(", ") || "None"}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Dependency Files:</span>
              <span className="text-slate-300">{(verdict.data?.dependency_files || []).join(", ") || "None"}</span>
            </div>
            <div>
              <span className="text-slate-500 block">Documentation:</span>
              <span className="text-slate-300">{(verdict.data?.docs || []).join(", ") || "None"}</span>
            </div>
          </div>
        </div>
      )}

      {/* 5. Text Kind -> Markdown formatting + Evidence row */}
      {verdict.kind === "text" && (
        <div className="space-y-4">
          <div className="prose prose-invert prose-sm max-w-none text-[#e6f6ff] leading-relaxed font-body">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }) {
                  return (
                    <code className="px-1.5 py-0.5 rounded bg-black/40 text-cyan-300 font-mono text-xs border border-cyan-900/40" {...props}>
                      {children}
                    </code>
                  );
                },
              }}
            >
              {verdict.data?.text || verdict.text || ""}
            </ReactMarkdown>
          </div>

          {/* Evidence Chip Row at the bottom */}
          {((verdict.data?.citations || verdict.citations || []).length > 0 || (verdict.data?.sources || []).length > 0) && (
            <div className="pt-3 border-t border-cyan-900/40 flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] font-mono text-cyan-400 font-semibold mr-1">
                Evidence:
              </span>
              {(verdict.data?.citations || verdict.citations || []).map((c: any, idx: number) => (
                <button
                  key={idx}
                  onClick={() => onCitationClick(c.path, c.start, c.end)}
                  className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-cyan-950 border border-cyan-400/40 hover:bg-cyan-500/20 text-cyan-300 font-mono text-xs transition hover:scale-105 active:scale-95"
                >
                  <span>{`${c.path}:${c.start}-${c.end}`}</span>
                  <ExternalLink className="w-2.5 h-2.5" />
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 6. Not Found Kind -> Cold Case Card */}
      {verdict.kind === "not_found" && (
        <div className="space-y-3 text-amber-200">
          <div className="flex items-center gap-2 text-amber-400 font-mono font-bold text-xs uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Cold Case — Symbol or Reference Not Found</span>
          </div>
          <p className="text-sm font-medium leading-relaxed">
            {verdict.data?.message || "I could not find that in this codebase."}
          </p>
          {(verdict.data?.searches_tried || []).length > 0 && (
            <div className="space-y-1.5 pt-2 border-t border-amber-500/30">
              <span className="text-[11px] font-mono uppercase tracking-wider text-amber-400 font-semibold block">
                Searches tried:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {(verdict.data.searches_tried || []).map((s: string, idx: number) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded bg-amber-950/80 border border-amber-500/30 font-mono text-xs text-amber-300"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
