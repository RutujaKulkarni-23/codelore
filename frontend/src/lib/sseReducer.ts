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

export interface CaseState {
  status: "idle" | "investigating" | "completed" | "error" | "rate_limited";
  sessionId: string | null;
  activeAgent: string | null;
  timeline: TimelineItem[];
  answer: string;
  citations: Array<{ path: string; start: number; end: number }>;
  durationSeconds: number;
  errorMessage: string | null;
  errorCode: string | number | null;
}

export type SSEEvent =
  | { type: "start"; data?: { question?: string } }
  | { type: "session"; data: { session_id: string } }
  | { type: "routed"; data: { agent: string } }
  | { type: "tool_call"; data: { agent: string; tool: string; args: Record<string, string> } }
  | { type: "tool_done"; data: { agent: string; tool: string } }
  | { type: "answer"; data: { agent: string; text: string } }
  | { type: "citations"; data: { items: Array<{ path: string; start: number; end: number }> } }
  | { type: "done"; data: { seconds: number } }
  | { type: "error"; data: { message: string; code?: string | number } };

export const initialCaseState: CaseState = {
  status: "idle",
  sessionId: null,
  activeAgent: null,
  timeline: [],
  answer: "",
  citations: [],
  durationSeconds: 0,
  errorMessage: null,
  errorCode: null,
};

export function sseReducer(state: CaseState, event: SSEEvent): CaseState {
  switch (event.type) {
    case "start": {
      return {
        ...state,
        status: "investigating",
        answer: "",
        errorMessage: null,
        errorCode: null,
      };
    }

    case "session": {
      return {
        ...state,
        status: "investigating",
        sessionId: event.data.session_id,
      };
    }

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

      return {
        ...state,
        status: "investigating",
        activeAgent: isSpecialist ? agent : state.activeAgent || agent,
        timeline: [...state.timeline, newItem],
      };
    }

    case "tool_call": {
      const { agent, tool, args } = event.data;
      const argsEntries = Object.entries(args || {});
      const argsStr = argsEntries.length > 0
        ? argsEntries.map(([k, v]) => `${k}="${v}"`).join(", ")
        : "";
      const newItem: TimelineItem = {
        id: `tool-${tool}-${Date.now()}-${Math.random()}`,
        type: "tool",
        agent,
        title: argsStr ? `${tool}(${argsStr})` : `${tool}()`,
        detail: `Running ${tool} on codebase`,
        status: "running",
        timestamp: Date.now(),
      };

      return {
        ...state,
        timeline: [...state.timeline, newItem],
      };
    }

    case "tool_done": {
      const { tool } = event.data;
      let found = false;
      const newTimeline = [...state.timeline].reverse().map((item) => {
        if (!found && item.type === "tool" && item.title.startsWith(tool) && item.status === "running") {
          found = true;
          return {
            ...item,
            status: "completed" as const,
            detail: `Verified from code`,
          };
        }
        return item;
      }).reverse();

      return {
        ...state,
        timeline: newTimeline,
      };
    }

    case "answer": {
      const { agent, text } = event.data;
      return {
        ...state,
        activeAgent: agent || state.activeAgent,
        answer: text,
      };
    }

    case "citations": {
      return {
        ...state,
        citations: event.data.items,
      };
    }

    case "done": {
      return {
        ...state,
        status: "completed",
        durationSeconds: event.data.seconds,
      };
    }

    case "error": {
      const isRateLimit = event.data.code === 429 || event.data.code === "429";
      return {
        ...state,
        status: isRateLimit ? "rate_limited" : "error",
        errorMessage: event.data.message,
        errorCode: event.data.code || (isRateLimit ? 429 : "error"),
      };
    }

    default:
      return state;
  }
}
