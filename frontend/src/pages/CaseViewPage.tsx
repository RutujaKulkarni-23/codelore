import React, { useState, useEffect, useReducer, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Navbar } from "../components/Navbar";
import { EvidencePanel } from "../components/EvidencePanel";
import { MascotBubble } from "../components/MascotBubble";
import {
  CheckCircle2,
  ArrowRight,
  Search,
  Square,
  AlertTriangle,
  RotateCcw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { streamAsk, fetchProject, BACKEND_OFFLINE_MSG } from "../api";
import type { ProjectResponse } from "../api";
import { sseReducer, initialCaseState } from "../lib/sseReducer";
import { saveRecentCase, getCaseById } from "../lib/storage";
import { StructuredVerdictCard } from "../components/StructuredVerdictCard";

function formatCaseNumber(id: string): string {
  if (id.startsWith("#") && id.length <= 6) return id.toUpperCase();
  const clean = id.replace(/^case-/, "");
  let hash = 0;
  for (let i = 0; i < clean.length; i++) {
    hash = (hash * 31 + clean.charCodeAt(i)) & 0xffffffff;
  }
  const hex = Math.abs(hash).toString(16).toUpperCase().padStart(4, "0");
  return `#${hex.slice(0, 4)}`;
}

export const CaseViewPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();

  const caseId = id || `case-${Date.now()}`;
  const queryParam = searchParams.get("q");

  const [currentQuestion, setCurrentQuestion] = useState<string>("");
  const [composerInput, setComposerInput] = useState<string>("");
  const [projectData, setProjectData] = useState<ProjectResponse | null>(null);
  const [projectError, setProjectError] = useState<string | null>(null);

  const [activeFile, setActiveFile] = useState<string>("");
  const [highlightRange, setHighlightRange] = useState<{ start: number; end: number } | undefined>(undefined);

  const [state, dispatch] = useReducer(sseReducer, initialCaseState);
  const [expandedTurnIds, setExpandedTurnIds] = useState<Set<string>>(new Set());
  const abortControllerRef = useRef<AbortController | null>(null);

  const toggleExpandTurn = (turnId: string) => {
    setExpandedTurnIds((prev) => {
      const next = new Set(prev);
      if (next.has(turnId)) {
        next.delete(turnId);
      } else {
        next.add(turnId);
      }
      return next;
    });
  };

  // Fetch project files for left panel
  useEffect(() => {
    fetchProject()
      .then((data) => {
        setProjectData(data);
        setProjectError(null);
        if (data.files.length > 0) {
          const firstPy = data.files.find((f) => f.kind === "py") || data.files[0];
          setActiveFile((curr) => curr || firstPy.path);
        }
      })
      .catch((err) => {
        setProjectError(err.message || BACKEND_OFFLINE_MSG);
      });
  }, []);

  // Primary Investigation Runner or Saved Case Loader
  useEffect(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    if (queryParam) {
      // Run live streaming investigation
      setCurrentQuestion(queryParam);
      runInvestigation(queryParam, state.sessionId || undefined);
    } else {
      // Check for saved case in localStorage
      const saved = getCaseById(caseId);
      if (saved) {
        setCurrentQuestion(saved.question);
        if (saved.answer) {
          dispatch({ type: "start", data: { question: saved.question } });
          if (saved.agent) {
            dispatch({ type: "routed", data: { agent: saved.agent } });
          }
          dispatch({
            type: "answer",
            data: { agent: saved.agent || "Specialist", text: saved.answer },
          });
          if (saved.citations && saved.citations.length > 0) {
            dispatch({ type: "citations", data: { items: saved.citations } });
            const first = saved.citations[0];
            setActiveFile(first.path);
            setHighlightRange({ start: first.start, end: first.end });
          }
          dispatch({ type: "done", data: { seconds: 1.0 } });
        } else if (saved.question) {
          // Saved case has question but no answer yet — launch investigation!
          runInvestigation(saved.question, undefined);
        }
      } else {
        setCurrentQuestion("");
      }
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [caseId, queryParam]);

  // Persist case to localStorage when answer/done arrives
  useEffect(() => {
    if (state.answer && currentQuestion) {
      try {
        saveRecentCase({
          id: caseId,
          title: currentQuestion.slice(0, 32),
          question: currentQuestion,
          agent: state.activeAgent || undefined,
          answer: state.answer,
          citations: state.citations,
          timestamp: Date.now(),
        });
      } catch (err) {
        console.error("Failed to save case to localStorage", err);
      }
    }
  }, [state.status, state.answer, state.citations, currentQuestion, caseId, state.activeAgent]);

  const runInvestigation = (questionText: string, currentSessionId?: string) => {
    const controller = new AbortController();
    abortControllerRef.current = controller;

    dispatch({ type: "start", data: { question: questionText } });

    streamAsk(
      questionText,
      currentSessionId,
      (ev) => {
        dispatch(ev);
        if (ev.type === "citations" && ev.data.items.length > 0) {
          const first = ev.data.items[0];
          setActiveFile(first.path);
          setHighlightRange({ start: first.start, end: first.end });
        }
      },
      (err) => {
        dispatch({
          type: "error",
          data: {
            message: err.message,
            code: err.code,
          },
        });
      },
      controller.signal
    );
  };

  const handleStopStream = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    dispatch({ type: "done", data: { seconds: state.durationSeconds || 0 } });
  };

  const handleFollowUpQuestion = (text: string) => {
    const q = text.trim();
    if (!q) return;

    setComposerInput("");
    setCurrentQuestion(q);
    // Reuse existing session id so LLM retains context!
    runInvestigation(q, state.sessionId || undefined);
  };

  const handleCitationClick = (file: string, start: number, end: number) => {
    setActiveFile(file);
    setHighlightRange({ start, end });
  };

  const isColdCase = state.answer.toLowerCase().includes("could not find");
  const caseStatus =
    state.status === "investigating"
      ? "INVESTIGATING"
      : isColdCase
      ? "COLD CASE"
      : state.status === "error" || state.status === "rate_limited"
      ? "INTERRUPTED"
      : state.answer
      ? "SOLVED"
      : "READY";

  return (
    <div className="min-h-screen flex flex-col bg-[#03111f] text-[#e6f6ff]">
      <Navbar />

      <main className="flex-1 max-w-[1920px] w-full mx-auto p-4 flex flex-col lg:flex-row gap-4 overflow-hidden">
        {/* 1. Left Column: Case Files & Lore */}
        <div className="w-full lg:w-64 flex-shrink-0 flex flex-col justify-between gap-4 glass-panel p-4 border-cyan-800/30">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-cyan-900/40 mb-3">
              <span className="text-[11px] font-mono uppercase tracking-wider text-cyan-300 font-semibold">
                CASE FILES
              </span>
              <span className="text-[10px] font-mono text-cyan-400/60 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/20">
                read-only
              </span>
            </div>

            {projectError ? (
              <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-500/40 text-xs text-rose-300 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0" />
                <span className="font-mono text-[11px]">{projectError}</span>
              </div>
            ) : (
              <div className="space-y-1 max-h-[420px] overflow-y-auto pr-1">
                {(projectData?.files.filter((f) => f.kind === "py") || []).map((file) => {
                  const isSelected = activeFile === file.path;
                  return (
                    <button
                      key={file.path}
                      onClick={() => {
                        setActiveFile(file.path);
                        setHighlightRange({ start: 1, end: 15 });
                      }}
                      className={`w-full flex items-center justify-between px-2.5 py-2 rounded-lg text-xs font-mono transition ${
                        isSelected
                          ? "bg-cyan-500/20 text-cyan-200 border border-cyan-400/30"
                          : "text-[#9fc3d6] hover:bg-white/5 hover:text-white"
                      }`}
                    >
                      <span className="truncate pr-2">{file.path}</span>
                      <span className="text-[10px] text-slate-500">{file.lines} lines</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Lore Detective Mascot Speech Bubble */}
          <div className="pt-4 border-t border-cyan-900/40 flex flex-col items-center text-center">
            <span className="text-[10px] font-mono uppercase tracking-wider text-cyan-400/80 mb-2">
              DETECTIVE LORE
            </span>
            <MascotBubble
              quote={
                state.status === "rate_limited"
                  ? "Too many questions at once, detective. Let's take a quick breather."
                  : state.status === "error"
                  ? "Something interrupted our lead. Check the report card."
                  : state.status === "investigating"
                  ? "Reading every line before I say a word."
                  : isColdCase
                  ? "No evidence, no accusation. Not found in this codebase."
                  : "Every claim backed by exact line evidence. Case closed."
              }
              size="sm"
              thinking={state.status === "investigating"}
            />
          </div>
        </div>

        {/* 2. Center Column: Live Timeline, Verdict, and Case Feed */}
        <div className="flex-1 flex flex-col justify-between glass-panel p-4 sm:p-6 border-cyan-800/30 overflow-y-auto space-y-6">
          <div className="space-y-6">
            {/* Case Header */}
            <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-cyan-900/40">
              <div>
                <span className="text-[11px] font-mono text-cyan-400 font-semibold tracking-wider">
                  CASE {formatCaseNumber(caseId)} · {caseStatus}
                </span>
                <h1 className="font-heading font-extrabold text-2xl text-white mt-1">
                  {currentQuestion || "Investigation Board"}
                </h1>
              </div>

              {/* Action Buttons & Status */}
              <div className="flex items-center gap-2">
                {state.status === "investigating" && (
                  <button
                    onClick={handleStopStream}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-300 text-xs font-mono font-semibold transition"
                    title="Stop AI investigation"
                  >
                    <Square className="w-3.5 h-3.5 fill-current" />
                    <span>Stop</span>
                  </button>
                )}

                <div className="flex items-center gap-1.5 text-xs font-heading font-semibold">
                  <span className="px-2.5 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-400/30">
                    Searcher
                  </span>
                  <span className="px-2.5 py-1 rounded-full bg-fuchsia-500/20 text-fuchsia-300 border border-fuchsia-400/30">
                    Explainer
                  </span>
                  <span className="px-2.5 py-1 rounded-full bg-purple-500/20 text-purple-300 border border-purple-400/30">
                    Mapper
                  </span>
                  <span className="px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-300 border border-amber-400/30">
                    Guide
                  </span>
                </div>
              </div>
            </div>

            {/* Error Card (Friendly Lore Card for 429 / timeout / busy) */}
            {(state.status === "error" || state.status === "rate_limited") && (
              <div className="p-5 rounded-2xl bg-amber-950/40 border border-amber-500/50 text-[#e6f6ff] space-y-3 shadow-xl">
                <div className="flex items-center gap-2 text-amber-300 font-heading font-bold text-sm">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span>
                    {state.status === "rate_limited" || state.errorCode === 429
                      ? "Rate limit reached — Lore needs a quick breather"
                      : state.errorCode === "timeout"
                      ? "Investigation timed out"
                      : "Investigation Interrupted"}
                  </span>
                </div>
                <p className="text-xs text-[#9fc3d6] leading-relaxed">
                  {state.errorMessage ||
                    (state.status === "rate_limited" || state.errorCode === 429
                      ? "Too many case requests. Please wait a few minutes before opening a new case."
                      : "The AI specialist was busy or encountered an error. Click below to retry.")}
                </p>
                <button
                  onClick={() => currentQuestion && runInvestigation(currentQuestion, state.sessionId || undefined)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-400/40 text-amber-200 text-xs font-mono font-semibold transition"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Retry investigation</span>
                </button>
              </div>
            )}

            {state.turns.length === 0 ? (
              <>
                {currentQuestion && (
                  <div className="flex justify-end">
                    <div className="max-w-xl p-4 rounded-2xl bg-cyan-500/20 border border-cyan-400/40 text-white font-medium text-sm shadow-md">
                      {currentQuestion}
                    </div>
                  </div>
                )}
                <div className="space-y-2">
                  <span className="text-[11px] font-mono uppercase tracking-wider text-cyan-400/80 font-semibold block mb-2">
                    INVESTIGATION TIMELINE
                  </span>
                  <p className="text-xs text-[#9fc3d6]/60 italic font-mono p-3 bg-[#020b14]/40 rounded-xl border border-cyan-900/30">
                    Ready to investigate. Type a question below or pick a suggested lead.
                  </p>
                </div>
              </>
            ) : (
              state.turns.map((turn, turnIdx) => {
                const isCurrentTurn = turnIdx === state.turns.length - 1;
                const isExpanded = isCurrentTurn || expandedTurnIds.has(turn.turn_id);
                const turnAgent = turn.activeAgent || (turn.verdict && turn.verdict.agent) || "Specialist";
                const durText = turn.stats.durationSeconds ? `${turn.stats.durationSeconds} s` : "completed";
                const evidenceCount = turn.citations.length || turn.stats.evidenceCount || 0;
                const shortQ = turn.question.length > 60 ? `${turn.question.slice(0, 57)}…` : turn.question;

                if (!isExpanded) {
                  return (
                    <div
                      key={turn.turn_id}
                      onClick={() => toggleExpandTurn(turn.turn_id)}
                      className="flex items-center justify-between p-3 rounded-xl bg-[#020b14]/60 hover:bg-[#031526]/80 border border-cyan-900/40 hover:border-cyan-500/40 text-xs font-mono cursor-pointer transition select-none group"
                      title="Click to expand previous turn"
                    >
                      <div className="flex items-center gap-2 truncate flex-1 mr-3">
                        <span className="text-cyan-300 font-semibold truncate">
                          Q: {shortQ}
                        </span>
                        <span className="text-cyan-800">·</span>
                        <span className="text-cyan-400 font-medium whitespace-nowrap">
                          {turnAgent}
                        </span>
                        <span className="text-cyan-800">·</span>
                        <span className="text-slate-400 whitespace-nowrap">
                          {durText}
                        </span>
                        <span className="text-cyan-800">·</span>
                        <span className="text-emerald-400 whitespace-nowrap">
                          {evidenceCount} evidence
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 text-cyan-400 group-hover:text-cyan-300 text-xs flex-shrink-0">
                        <span className="text-[11px] font-mono text-cyan-500/70">Expand</span>
                        <ChevronDown className="w-3.5 h-3.5" />
                      </div>
                    </div>
                  );
                }

                return (
                  <div key={turn.turn_id} className="space-y-4 pt-2">
                    {!isCurrentTurn && (
                      <div
                        onClick={() => toggleExpandTurn(turn.turn_id)}
                        className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-cyan-950/40 border border-cyan-800/30 text-[11px] font-mono text-cyan-400/80 cursor-pointer hover:bg-cyan-950/60 transition"
                      >
                        <span className="font-semibold uppercase tracking-wider">Earlier Question ({turnIdx + 1})</span>
                        <div className="flex items-center gap-1">
                          <span>Collapse</span>
                          <ChevronUp className="w-3 h-3" />
                        </div>
                      </div>
                    )}

                    {turn.question && (
                      <div className="flex justify-end">
                        <div className="max-w-xl p-4 rounded-2xl bg-cyan-500/20 border border-cyan-400/40 text-white font-medium text-sm shadow-md">
                          {turn.question}
                        </div>
                      </div>
                    )}

                    <div className="space-y-2">
                      <span className="text-[11px] font-mono uppercase tracking-wider text-cyan-400/80 font-semibold block mb-2">
                        INVESTIGATION TIMELINE
                      </span>

                      {turn.status === "investigating" && turn.timeline.length === 0 && (
                        <div className="flex items-center gap-3 p-3 rounded-xl bg-[#020b14]/70 border border-cyan-500/40 text-xs font-mono">
                          <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                          <div className="flex-1">
                            <span className="font-bold text-white pr-2">Boss:</span>
                            <span className="text-cyan-300">Reading question and routing to specialist…</span>
                          </div>
                        </div>
                      )}

                      {turn.timeline.map((item) => {
                        const isBossTransfer = item.title.startsWith("Boss chose");
                        const isTookCase = item.title.includes("took the case");
                        const showDirect = isBossTransfer || isTookCase;
                        return (
                          <div
                            key={item.id}
                            className="flex items-center gap-3 p-3 rounded-xl bg-[#020b14]/70 border border-cyan-900/40 text-xs font-mono"
                          >
                            {item.status === "running" ? (
                              <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                            ) : (
                              <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                            )}
                            <div className="flex-1 truncate">
                              {!showDirect && <span className="font-bold text-white pr-2">{item.agent}:</span>}
                              <span className="text-cyan-300">{item.title}</span>
                            </div>
                            <div className="flex items-center gap-2 text-[10px] text-slate-400 font-mono flex-shrink-0">
                              {item.duration !== undefined && (
                                <span className="text-cyan-400/80">{item.duration}s</span>
                              )}
                              {item.detail && (
                                <span className={item.detail === "Verified from code" ? "text-emerald-400/90 font-semibold" : "text-slate-400"}>
                                  {item.detail}
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {(turn.status === "error" || turn.status === "rate_limited") && (
                      <div className="p-4 rounded-xl bg-amber-950/40 border border-amber-500/50 text-[#e6f6ff] space-y-2">
                        <div className="flex items-center gap-2 text-amber-300 font-heading font-bold text-sm">
                          <AlertTriangle className="w-4 h-4 text-amber-400" />
                          <span>
                            {turn.status === "rate_limited" || turn.errorCode === 429
                              ? "Rate limit reached — Lore needs a quick breather"
                              : turn.errorCode === "timeout"
                              ? "Investigation timed out"
                              : "Investigation Interrupted"}
                          </span>
                        </div>
                        <p className="text-xs text-[#9fc3d6] leading-relaxed">
                          {turn.errorMessage || "The AI specialist encountered an issue."}
                        </p>
                      </div>
                    )}

                    {turn.verdict ? (
                      <StructuredVerdictCard
                        verdict={turn.verdict}
                        onCitationClick={handleCitationClick}
                        activeAgent={turn.activeAgent || turn.verdict.agent || undefined}
                        durationSeconds={turn.stats.durationSeconds}
                      />
                    ) : turn.answer ? (
                      <StructuredVerdictCard
                        verdict={{
                          kind: "text",
                          data: { text: turn.answer },
                          text: turn.answer,
                          citations: turn.citations,
                        }}
                        onCitationClick={handleCitationClick}
                        activeAgent={turn.activeAgent || undefined}
                        durationSeconds={turn.stats.durationSeconds}
                      />
                    ) : null}
                  </div>
                );
              })
            )}
          </div>

          {/* Follow-up suggestions & composer */}
          <div className="pt-4 space-y-3 border-t border-cyan-900/40">
            {/* Suggested Follow-up Chips */}
            <div className="flex flex-wrap items-center gap-2">
              {[
                "Which files import upsert_to_vector_db?",
                "Explain the functions in query_pipeline.py",
                "Where should a beginner start?",
                "Where is embed_query defined?",
              ].map((chip) => (
                <button
                  key={chip}
                  onClick={() => handleFollowUpQuestion(chip)}
                  className="px-3 py-1 rounded-full bg-white/5 hover:bg-white/10 text-cyan-200 border border-cyan-400/20 text-xs font-medium transition"
                >
                  {chip}
                </button>
              ))}
            </div>

            {/* Bottom Composer */}
            <div className="glass-panel p-2 pl-4 border-cyan-500/30 shadow-xl flex items-center gap-3">
              <Search className="w-4 h-4 text-cyan-400 flex-shrink-0" />
              <input
                type="text"
                placeholder="Ask a follow-up in this case or explore new evidence…"
                value={composerInput}
                onChange={(e) => setComposerInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleFollowUpQuestion(composerInput);
                }}
                className="flex-1 bg-transparent text-sm text-white placeholder-[#9fc3d6]/60 focus:outline-none"
              />
              <button
                onClick={() => handleFollowUpQuestion(composerInput)}
                className="flex items-center justify-center w-8 h-8 rounded-xl bg-cyan-400 hover:bg-cyan-300 text-slate-950 transition shadow-md flex-shrink-0"
                title="Send inquiry"
              >
                <ArrowRight className="w-4 h-4 stroke-[2.5]" />
              </button>
            </div>
          </div>
        </div>

        {/* 3. Right Column: Evidence Panel (Code & Import Map) */}
        <div className="w-full lg:w-[480px] xl:w-[540px] flex-shrink-0 h-[650px] lg:h-auto">
          <EvidencePanel
            activeFile={activeFile}
            highlightRange={highlightRange}
            allCitedFiles={state.citations.map((c) => c.path)}
            onSelectFile={(f) => {
              setActiveFile(f);
              setHighlightRange({ start: 1, end: 20 });
            }}
          />
        </div>
      </main>
    </div>
  );
};
