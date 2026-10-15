export interface TimelineItem {
  id: string;
  type: "routed" | "tool";
  agent: string;
  title: string;
  detail?: string;
  status: "running" | "completed" | "error";
  duration?: number;
  timestamp: number;
}

export type VerdictKind = "outline" | "symbol" | "imports" | "overview" | "text" | "not_found";

export interface Verdict {
  kind: VerdictKind;
  agent?: string;
  data: any;
  text?: string;
  citations?: Array<{ path: string; start: number; end: number }>;
  sources?: string[];
}

export interface TurnStats {
  durationSeconds: number;
  evidenceCount: number;
}

export interface CaseTurn {
  turn_id: string;
  question: string;
  status: "idle" | "investigating" | "completed" | "error" | "rate_limited";
  timeline: TimelineItem[];
  answer: string;
  verdict: Verdict | null;
  citations: Array<{ path: string; start: number; end: number }>;
  stats: TurnStats;
  activeAgent: string | null;
  errorMessage: string | null;
  errorCode: string | number | null;
}

export interface CaseState {
  status: "idle" | "investigating" | "completed" | "error" | "rate_limited";
  sessionId: string | null;
  turns: CaseTurn[];
  activeAgent: string | null;
  timeline: TimelineItem[];
  answer: string;
  verdict: Verdict | null;
  citations: Array<{ path: string; start: number; end: number }>;
  durationSeconds: number;
  errorMessage: string | null;
  errorCode: string | number | null;
}

export type SSEEvent =
  | { type: "start"; data?: { turn_id?: string; question?: string } }
  | { type: "session"; data: { turn_id?: string; session_id: string } }
  | { type: "routed"; data: { turn_id?: string; agent: string } }
  | { type: "tool_call"; data: { turn_id?: string; agent: string; tool: string; args: Record<string, string> } }
  | { type: "tool_done"; data: { turn_id?: string; agent: string; tool: string } }
  | { type: "answer"; data: { turn_id?: string; agent: string; text: string } }
  | { type: "verdict"; data: { turn_id?: string; agent?: string; kind: VerdictKind; data: any; text?: string; citations?: any[]; sources?: string[] } }
  | { type: "citations"; data: { turn_id?: string; items: Array<{ path: string; start: number; end: number }> } }
  | { type: "done"; data: { turn_id?: string; seconds: number } }
  | { type: "error"; data: { turn_id?: string; message: string; code?: string | number } };

export const initialCaseState: CaseState = {
  status: "idle",
  sessionId: null,
  turns: [],
  activeAgent: null,
  timeline: [],
  answer: "",
  verdict: null,
  citations: [],
  durationSeconds: 0,
  errorMessage: null,
  errorCode: null,
};

const CODE_READING_TOOLS = new Set([
  "find_symbol",
  "analyze_imports",
  "get_file_outline",
  "show_file_outline",
  "get_project_overview",
  "read_text_file",
  "rag_search",
]);

function syncCaseState(state: CaseState): CaseState {
  if (state.turns.length === 0) {
    return state;
  }
  const latestTurn = state.turns[state.turns.length - 1];
  return {
    ...state,
    status: latestTurn.status,
    activeAgent: latestTurn.activeAgent,
    timeline: latestTurn.timeline,
    answer: latestTurn.answer,
    verdict: latestTurn.verdict,
    citations: latestTurn.citations,
    durationSeconds: latestTurn.stats.durationSeconds,
    errorMessage: latestTurn.errorMessage,
    errorCode: latestTurn.errorCode,
  };
}

export function sseReducer(state: CaseState, event: SSEEvent): CaseState {
  if (event.type === "start") {
    const turnId =
      event.data?.turn_id ||
      `turn-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const newTurn: CaseTurn = {
      turn_id: turnId,
      question: event.data?.question || "",
      status: "investigating",
      timeline: [],
      answer: "",
      verdict: null,
      citations: [],
      stats: { durationSeconds: 0, evidenceCount: 0 },
      activeAgent: null,
      errorMessage: null,
      errorCode: null,
    };
    return syncCaseState({
      ...state,
      status: "investigating",
      turns: [...state.turns, newTurn],
    });
  }

  if (event.type === "session") {
    return {
      ...state,
      sessionId: event.data.session_id,
    };
  }

  // Determine target turn
  const evTurnId = (event as any).data?.turn_id;
  let targetIdx = -1;
  if (evTurnId) {
    targetIdx = state.turns.findIndex((t) => t.turn_id === evTurnId);
  }
  if (targetIdx === -1) {
    targetIdx = state.turns.length > 0 ? state.turns.length - 1 : -1;
  }

  let turns = [...state.turns];
  if (targetIdx === -1) {
    // Create turn on the fly if none existed
    const fallbackTurn: CaseTurn = {
      turn_id: evTurnId || `turn-${Date.now()}`,
      question: "",
      status: "investigating",
      timeline: [],
      answer: "",
      verdict: null,
      citations: [],
      stats: { durationSeconds: 0, evidenceCount: 0 },
      activeAgent: null,
      errorMessage: null,
      errorCode: null,
    };
    turns = [fallbackTurn];
    targetIdx = 0;
  }

  const currentTurn = { ...turns[targetIdx] };

  switch (event.type) {
    case "routed": {
      const agent = event.data.agent;
      const isSpecialist = agent !== "Boss" && agent !== "root_agent";
      const newItem: TimelineItem = {
        id: `routed-${agent}-${Date.now()}-${Math.random()}`,
        type: "routed",
        agent,
        title: isSpecialist ? `${agent} took the case` : "Boss read the question",
        detail: isSpecialist ? "Chosen specialist for this investigation" : "Evaluating case lead",
        status: "completed",
        timestamp: Date.now(),
      };

      currentTurn.status = "investigating";
      currentTurn.activeAgent = isSpecialist ? agent : currentTurn.activeAgent || agent;
      currentTurn.timeline = [...currentTurn.timeline, newItem];
      break;
    }

    case "tool_call": {
      const { agent, tool, args } = event.data;
      const argsEntries = Object.entries(args || {});
      const argsStr = argsEntries.length > 0
        ? argsEntries.map(([k, v]) => `${k}="${v}"`).join(", ")
        : "";

      let itemTitle = "";
      let itemDetail = "";
      if (tool === "transfer_to_agent") {
        const destAgentRaw = args?.agent_name || args?.target || "specialist";
        const destDisplay =
          destAgentRaw === "code_searcher" ? "Code Searcher" :
          destAgentRaw === "code_explainer" ? "Code Explainer" :
          destAgentRaw === "architecture_mapper" ? "Architecture Mapper" :
          destAgentRaw === "onboarding_guide" ? "Onboarding Guide" :
          destAgentRaw;
        itemTitle = `Boss chose ${destDisplay}`;
        itemDetail = "Routing to specialist";
      } else {
        itemTitle = argsStr ? `${tool}(${argsStr})` : `${tool}()`;
        itemDetail = CODE_READING_TOOLS.has(tool) ? "Inspecting code" : `Running ${tool}`;
      }

      const newItem: TimelineItem = {
        id: `tool-${tool}-${Date.now()}-${Math.random()}`,
        type: "tool",
        agent,
        title: itemTitle,
        detail: itemDetail,
        status: "running",
        timestamp: Date.now(),
      };

      currentTurn.timeline = [...currentTurn.timeline, newItem];
      break;
    }

    case "tool_done": {
      const { tool } = event.data;
      let found = false;
      const now = Date.now();
      const newTimeline = [...currentTurn.timeline].reverse().map((item) => {
        if (!found && item.type === "tool" && item.status === "running") {
          // Check if title starts with tool or transfer
          const matches =
            item.title.startsWith(tool) ||
            (tool === "transfer_to_agent" && item.title.startsWith("Boss chose"));
          if (matches) {
            found = true;
            const dur = Math.max(0.1, Math.round(((now - item.timestamp) / 1000) * 10) / 10);
            let honestDetail = "Completed";
            if (CODE_READING_TOOLS.has(tool)) {
              honestDetail = "Verified from code";
            } else if (tool === "transfer_to_agent") {
              honestDetail = "Transferred";
            }
            return {
              ...item,
              status: "completed" as const,
              detail: honestDetail,
              duration: dur,
            };
          }
        }
        return item;
      }).reverse();

      currentTurn.timeline = newTimeline;
      break;
    }

    case "answer": {
      const { agent, text } = event.data;
      currentTurn.activeAgent = agent || currentTurn.activeAgent;
      currentTurn.answer = text;
      break;
    }

    case "verdict": {
      const { agent, kind, data, text, citations, sources } = event.data;
      const verdictObj: Verdict = {
        kind,
        agent: agent || currentTurn.activeAgent || undefined,
        data: data || {},
        text: text || currentTurn.answer,
        citations: citations || currentTurn.citations,
        sources: sources || [],
      };
      currentTurn.verdict = verdictObj;
      if (text) {
        currentTurn.answer = text;
      }
      break;
    }

    case "citations": {
      currentTurn.citations = event.data.items || [];
      currentTurn.stats = {
        ...currentTurn.stats,
        evidenceCount: currentTurn.citations.length,
      };
      break;
    }

    case "done": {
      currentTurn.status = "completed";
      currentTurn.stats = {
        ...currentTurn.stats,
        durationSeconds: event.data.seconds,
        evidenceCount: currentTurn.citations.length,
      };
      break;
    }

    case "error": {
      const isRateLimit = event.data.code === 429 || event.data.code === "429";
      currentTurn.status = isRateLimit ? "rate_limited" : "error";
      currentTurn.errorMessage = event.data.message;
      currentTurn.errorCode = event.data.code || (isRateLimit ? 429 : "error");
      break;
    }

    default:
      break;
  }

  turns[targetIdx] = currentTurn;
  return syncCaseState({
    ...state,
    turns,
  });
}
