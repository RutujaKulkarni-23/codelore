import type { SSEEvent } from "./lib/sseReducer";

const API_BASE = import.meta.env.VITE_API_URL || "";

export interface ProjectFile {
  path: string;
  lines: number;
  kind: "py" | "md" | "txt" | "data";
}

export interface ProjectResponse {
  name: string;
  commit: string | null;
  files: ProjectFile[];
  total_py_lines: number;
}

export interface FileResponse {
  path: string;
  lines: string[];
}

export interface OutlineItem {
  name: string;
  kind: "class" | "method" | "function";
  params: string;
  start: number;
  end: number;
  doc: string;
}

export interface OutlineResponse {
  path: string;
  items: OutlineItem[];
}

export interface GraphNode {
  id: string;
  lines: number;
}

export interface GraphEdge {
  from: string;
  to: string;
  line: number;
  symbols: string[];
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ReadingOrderItem {
  path: string;
  doc: string;
}

export interface OverviewResponse {
  entry_point: string | null;
  also_runnable: string[];
  commands: string[];
  stages: string[];
  reading_order: ReadingOrderItem[];
  data_files: string[];
  dependency_files: string[];
  docs: string[];
}

export const BACKEND_OFFLINE_MSG =
  "The CodeLore API is offline. Start it with: uvicorn server.app:app --port 8000";

async function requestJson<T>(url: string, timeoutMs: number = 10000): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, { signal: controller.signal });
    clearTimeout(timeoutId);

    if (!res.ok) {
      if (res.status === 502 || res.status === 503 || res.status === 504) {
        throw new Error(BACKEND_OFFLINE_MSG);
      }
      if (res.status === 400) throw new Error("Invalid request or forbidden file path.");
      if (res.status === 403) throw new Error("Access to secret or forbidden file blocked.");
      if (res.status === 404) throw new Error("Requested file or resource not found.");
      if (res.status === 429) throw new Error("Rate limit exceeded. Please wait a few minutes.");
      throw new Error(`Server returned status ${res.status}: ${res.statusText}`);
    }

    return await res.json();
  } catch (err: any) {
    clearTimeout(timeoutId);
    if (err.name === "AbortError") {
      throw new Error("Request timed out. Please verify your connection.");
    }
    if (
      err instanceof TypeError ||
      err.message?.includes("Failed to fetch") ||
      err.message?.includes("NetworkError") ||
      err.message?.includes("ERR_CONNECTION_REFUSED") ||
      err.message?.includes("Load failed")
    ) {
      throw new Error(BACKEND_OFFLINE_MSG);
    }
    throw err;
  }
}

export async function fetchHealth(): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`${API_BASE}/api/health`, 5000);
}

export async function fetchProject(): Promise<ProjectResponse> {
  return requestJson<ProjectResponse>(`${API_BASE}/api/project`);
}

export async function fetchFile(path: string): Promise<FileResponse> {
  return requestJson<FileResponse>(`${API_BASE}/api/file?path=${encodeURIComponent(path)}`);
}

export async function fetchOutline(path: string): Promise<OutlineResponse> {
  return requestJson<OutlineResponse>(`${API_BASE}/api/outline?path=${encodeURIComponent(path)}`);
}

export async function fetchGraph(): Promise<GraphResponse> {
  return requestJson<GraphResponse>(`${API_BASE}/api/graph`);
}

export async function fetchOverview(): Promise<OverviewResponse> {
  return requestJson<OverviewResponse>(`${API_BASE}/api/overview`);
}

/**
 * Connects to /api/ask using fetch and reader to parse Server-Sent Events stream.
 * Supports AbortController signal for cancellation.
 * Ignores ": ping" comments and handles 429, timeout, and busy error states.
 */
export async function streamAsk(
  question: string,
  sessionId: string | null | undefined,
  onEvent: (event: SSEEvent) => void,
  onError: (err: { message: string; code?: string | number }) => void,
  signal?: AbortSignal
): Promise<void> {
  try {
    const res = await fetch(`${API_BASE}/api/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question, session_id: sessionId || null }),
      signal,
    });

    if (res.status === 429) {
      const errJson = await res.json().catch(() => ({ detail: "Rate limit exceeded." }));
      onError({
        message: errJson.detail || "Too many case requests. Please wait a few minutes before opening a new case.",
        code: 429,
      });
      return;
    }

    if (!res.ok) {
      const errText = await res.text().catch(() => "Unknown server error");
      onError({
        message: `Server returned error (${res.status}): ${errText}`,
        code: res.status,
      });
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onError({ message: "Response stream is not readable." });
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    const processBuffer = (flushAll = false) => {
      // Normalize CRLF and CR to LF
      const normalized = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
      const parts = normalized.split("\n\n");

      // If not flushing everything, the last part might be incomplete
      if (!flushAll) {
        buffer = parts.pop() || "";
      } else {
        buffer = "";
      }

      for (const block of parts) {
        const trimmed = block.trim();
        if (!trimmed) continue;

        let eventType = "message";
        const dataLines: string[] = [];

        for (const rawLine of trimmed.split("\n")) {
          const line = rawLine.trimEnd();
          if (line.startsWith(":") || line === ": ping") {
            continue;
          }
          if (line.startsWith("event:")) {
            eventType = line.slice(6).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trimStart());
          }
        }

        if (dataLines.length > 0) {
          const dataStr = dataLines.join("\n");
          try {
            const parsedData = JSON.parse(dataStr);
            onEvent({ type: eventType as any, data: parsedData } as SSEEvent);
          } catch (e) {
            console.error("Failed to parse SSE data JSON", dataStr, e);
          }
        }
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        processBuffer(true);
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      processBuffer(false);
    }
  } catch (err: any) {
    if (signal?.aborted || err?.name === "AbortError") {
      return;
    }
    const isOffline =
      err instanceof TypeError ||
      err?.message?.includes("Failed to fetch") ||
      err?.message?.includes("NetworkError") ||
      err?.message?.includes("ERR_CONNECTION_REFUSED") ||
      err?.message?.includes("Load failed");
    onError({
      message: isOffline ? BACKEND_OFFLINE_MSG : err instanceof Error ? err.message : String(err),
      code: isOffline ? "offline" : "network_error",
    });
  }
}
