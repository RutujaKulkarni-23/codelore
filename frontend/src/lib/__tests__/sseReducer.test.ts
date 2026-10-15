import { describe, it, expect } from "vitest";
import { sseReducer, initialCaseState } from "../sseReducer";
import type { SSEEvent } from "../sseReducer";

describe("SSE Event Reducer", () => {
  it("handles routed event", () => {
    const event: SSEEvent = {
      type: "routed",
      data: { agent: "Code Searcher" },
    };
    const state = sseReducer(initialCaseState, event);
    expect(state.status).toBe("investigating");
    expect(state.activeAgent).toBe("Code Searcher");
    expect(state.timeline).toHaveLength(1);
    expect(state.timeline[0].agent).toBe("Code Searcher");
  });

  it("handles tool_call and tool_done transitions", () => {
    let state = initialCaseState;

    state = sseReducer(state, {
      type: "tool_call",
      data: {
        agent: "Code Searcher",
        tool: "find_symbol",
        args: { symbol: "embed_query" },
      },
    });

    expect(state.timeline).toHaveLength(1);
    expect(state.timeline[0].status).toBe("running");
    expect(state.timeline[0].title).toContain("find_symbol");

    state = sseReducer(state, {
      type: "tool_done",
      data: { agent: "Code Searcher", tool: "find_symbol" },
    });

    expect(state.timeline[0].status).toBe("completed");
  });

  it("accumulates answer text and parses citations", () => {
    let state = initialCaseState;

    state = sseReducer(state, {
      type: "answer",
      data: {
        agent: "Architecture Mapper",
        text: "indexer.py:27 imports upsert_to_vector_db.",
      },
    });

    expect(state.answer).toBe("indexer.py:27 imports upsert_to_vector_db.");

    state = sseReducer(state, {
      type: "citations",
      data: { items: [{ path: "indexer.py", start: 27, end: 27 }] },
    });

    expect(state.citations).toEqual([{ path: "indexer.py", start: 27, end: 27 }]);

    state = sseReducer(state, {
      type: "done",
      data: { seconds: 3.2 },
    });

    expect(state.status).toBe("completed");
    expect(state.durationSeconds).toBe(3.2);
  });

  it("handles error event", () => {
    const state = sseReducer(initialCaseState, {
      type: "error",
      data: { message: "The AI service is slow or busy. Try again." },
    });

    expect(state.status).toBe("error");
    expect(state.errorMessage).toBe("The AI service is slow or busy. Try again.");
  });

  it("processes recorded event sequence with routed, tool_call, tool_done, answer, and citations", () => {
    const recordedEvents: SSEEvent[] = [
      { type: "session", data: { session_id: "test-sess-99" } },
      { type: "routed", data: { agent: "Boss" } },
      { type: "routed", data: { agent: "Architecture Mapper" } },
      {
        type: "tool_call",
        data: {
          agent: "Architecture Mapper",
          tool: "analyze_imports",
          args: { module_name: "upsert_to_vector_db" },
        },
      },
      {
        type: "tool_done",
        data: { agent: "Architecture Mapper", tool: "analyze_imports" },
      },
      {
        type: "answer",
        data: {
          agent: "Architecture Mapper",
          text: "Found at indexer.py:27-27",
        },
      },
      {
        type: "citations",
        data: { items: [{ path: "indexer.py", start: 27, end: 27 }] },
      },
      { type: "done", data: { seconds: 1.45 } },
    ];

    let state = initialCaseState;
    for (const evt of recordedEvents) {
      state = sseReducer(state, evt);
    }

    expect(state.sessionId).toBe("test-sess-99");
    expect(state.status).toBe("completed");
    expect(state.activeAgent).toBe("Architecture Mapper");
    // Verify timeline contains routed Boss, routed Architecture Mapper, and analyze_imports tool
    expect(state.timeline).toHaveLength(3);
    expect(state.timeline[0].agent).toBe("Boss");
    expect(state.timeline[0].type).toBe("routed");
    expect(state.timeline[1].agent).toBe("Architecture Mapper");
    expect(state.timeline[1].type).toBe("routed");
    expect(state.timeline[2].agent).toBe("Architecture Mapper");
    expect(state.timeline[2].type).toBe("tool");
    expect(state.timeline[2].title).toContain("analyze_imports");
    expect(state.timeline[2].status).toBe("completed");
    expect(state.answer).toBe("Found at indexer.py:27-27");
    expect(state.citations).toEqual([{ path: "indexer.py", start: 27, end: 27 }]);
    expect(state.durationSeconds).toBe(1.45);
  });

  it("streamAsk parses SSE stream with CRLF line endings correctly", async () => {
    const { streamAsk } = await import("../../api");

    const events: SSEEvent[] = [];
    const mockSSEText =
      "event: routed\r\ndata: {\"agent\": \"Boss\"}\r\n\r\n" +
      ": ping\r\n\r\n" +
      "event: tool_call\r\ndata: {\"agent\": \"Boss\", \"tool\": \"transfer_to_agent\", \"args\": {\"agent_name\": \"code_explainer\"}}\r\n\r\n" +
      "event: answer\r\ndata: {\"agent\": \"Code Explainer\", \"text\": \"Line 1\\nLine 2\"}\r\n\r\n" +
      "event: done\r\ndata: {\"seconds\": 2.5}\r\n\r\n";

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(mockSSEText.slice(0, 40)));
        controller.enqueue(encoder.encode(mockSSEText.slice(40)));
        controller.close();
      },
    });

    const mockResponse = new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
    const originalFetch = globalThis.fetch;
    globalThis.fetch = () => Promise.resolve(mockResponse);

    try {
      await streamAsk("explain vector_store.py", "test-sess", (ev) => events.push(ev), () => {});
    } finally {
      globalThis.fetch = originalFetch;
    }

    expect(events).toHaveLength(4);
    expect(events[0]).toEqual({ type: "routed", data: { agent: "Boss" } });
    expect(events[1]).toEqual({
      type: "tool_call",
      data: { agent: "Boss", tool: "transfer_to_agent", args: { agent_name: "code_explainer" } },
    });
    expect(events[2]).toEqual({
      type: "answer",
      data: { agent: "Code Explainer", text: "Line 1\nLine 2" },
    });
    expect(events[3]).toEqual({ type: "done", data: { seconds: 2.5 } });
  });

  it("handles two turns of recorded events with isolated timelines and verdicts", () => {
    let state = initialCaseState;

    // Turn 1
    const turn1Id = "turn-1-guid";
    state = sseReducer(state, {
      type: "start",
      data: { turn_id: turn1Id, question: "Where should a beginner start?" },
    });
    state = sseReducer(state, {
      type: "routed",
      data: { turn_id: turn1Id, agent: "Boss" },
    });
    state = sseReducer(state, {
      type: "tool_call",
      data: {
        turn_id: turn1Id,
        agent: "Boss",
        tool: "transfer_to_agent",
        args: { agent_name: "onboarding_guide" },
      },
    });
    state = sseReducer(state, {
      type: "tool_done",
      data: { turn_id: turn1Id, agent: "Boss", tool: "transfer_to_agent" },
    });
    state = sseReducer(state, {
      type: "routed",
      data: { turn_id: turn1Id, agent: "Onboarding Guide" },
    });
    state = sseReducer(state, {
      type: "tool_call",
      data: {
        turn_id: turn1Id,
        agent: "Onboarding Guide",
        tool: "get_project_overview",
        args: {},
      },
    });
    state = sseReducer(state, {
      type: "tool_done",
      data: {
        turn_id: turn1Id,
        agent: "Onboarding Guide",
        tool: "get_project_overview",
      },
    });
    state = sseReducer(state, {
      type: "verdict",
      data: {
        turn_id: turn1Id,
        agent: "Onboarding Guide",
        kind: "overview",
        data: {
          kind: "overview",
          entry_point: "main.py",
          reading_order: [{ path: "main.py", doc: "CLI entry point" }],
        },
      },
    });
    state = sseReducer(state, {
      type: "citations",
      data: { turn_id: turn1Id, items: [{ path: "main.py", start: 1, end: 50 }] },
    });
    state = sseReducer(state, {
      type: "done",
      data: { turn_id: turn1Id, seconds: 2.1 },
    });

    // Verify Turn 1 state
    expect(state.turns).toHaveLength(1);
    expect(state.turns[0].turn_id).toBe(turn1Id);
    expect(state.turns[0].question).toBe("Where should a beginner start?");
    expect(state.turns[0].timeline).toHaveLength(4); // Boss routed, transfer call, Guide routed, overview call
    expect(state.turns[0].verdict?.kind).toBe("overview");
    expect(state.turns[0].stats.durationSeconds).toBe(2.1);
    expect(state.turns[0].stats.evidenceCount).toBe(1);

    // Turn 2
    const turn2Id = "turn-2-guid";
    state = sseReducer(state, {
      type: "start",
      data: { turn_id: turn2Id, question: "Explain the functions in query_pipeline.py" },
    });
    state = sseReducer(state, {
      type: "routed",
      data: { turn_id: turn2Id, agent: "Code Explainer" },
    });
    state = sseReducer(state, {
      type: "tool_call",
      data: {
        turn_id: turn2Id,
        agent: "Code Explainer",
        tool: "show_file_outline",
        args: { file_path: "query_pipeline.py" },
      },
    });
    state = sseReducer(state, {
      type: "tool_done",
      data: {
        turn_id: turn2Id,
        agent: "Code Explainer",
        tool: "show_file_outline",
      },
    });
    state = sseReducer(state, {
      type: "verdict",
      data: {
        turn_id: turn2Id,
        agent: "Code Explainer",
        kind: "outline",
        data: {
          kind: "outline",
          path: "query_pipeline.py",
          items: [{ name: "embed_query", start: 27, end: 86, signature: "def embed_query()" }],
        },
      },
    });
    state = sseReducer(state, {
      type: "citations",
      data: { turn_id: turn2Id, items: [{ path: "query_pipeline.py", start: 27, end: 86 }] },
    });
    state = sseReducer(state, {
      type: "done",
      data: { turn_id: turn2Id, seconds: 1.4 },
    });

    // Verify Both Turns are completely isolated
    expect(state.turns).toHaveLength(2);

    // Turn 1 has ONLY its own steps
    const t1 = state.turns[0];
    expect(t1.turn_id).toBe(turn1Id);
    expect(t1.question).toBe("Where should a beginner start?");
    expect(t1.timeline).toHaveLength(4);
    expect(t1.timeline.map((x) => x.title)).toEqual([
      "Boss read the question",
      "Boss chose Onboarding Guide",
      "Onboarding Guide took the case",
      "get_project_overview()",
    ]);
    expect(t1.verdict?.kind).toBe("overview");
    expect(t1.stats.durationSeconds).toBe(2.1);
    expect(t1.citations[0].path).toBe("main.py");

    // Turn 2 has ONLY its own steps (NO Boss or Onboarding Guide from turn 1!)
    const t2 = state.turns[1];
    expect(t2.turn_id).toBe(turn2Id);
    expect(t2.question).toBe("Explain the functions in query_pipeline.py");
    expect(t2.timeline).toHaveLength(2);
    expect(t2.timeline.map((x) => x.title)).toEqual([
      "Code Explainer took the case",
      'show_file_outline(file_path="query_pipeline.py")',
    ]);
    expect(t2.verdict?.kind).toBe("outline");
    expect(t2.stats.durationSeconds).toBe(1.4);
    expect(t2.citations[0].path).toBe("query_pipeline.py");
  });
});


