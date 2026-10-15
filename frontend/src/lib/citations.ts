export interface Citation {
  raw: string;
  file: string;
  start: number;
  end: number;
}

export interface TextSegment {
  type: "text" | "citation";
  content: string;
  citation?: Citation;
}

/**
 * Regex matching file.py:start-end or file.py:line
 */
export const CITATION_REGEX = /\b([a-zA-Z0-9_\-./\\]+\.py):(\d+)(?:-(\d+))?\b/g;

/**
 * Parses markdown/text and extracts all citation chips as structured tokens
 */
export function parseCitations(text: string): Citation[] {
  const citations: Citation[] = [];
  const seen = new Set<string>();
  const regex = new RegExp(CITATION_REGEX);
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    const raw = match[0];
    const file = match[1].replace(/\\/g, "/");
    const start = parseInt(match[2], 10);
    const end = match[3] ? parseInt(match[3], 10) : start;
    const key = `${file}:${start}-${end}`;

    if (!seen.has(key)) {
      seen.add(key);
      citations.push({
        raw,
        file,
        start: Math.min(start, end),
        end: Math.max(start, end),
      });
    }
  }

  return citations;
}

/**
 * Splits text into string parts and interactive citation chip tokens
 */
export function splitTextWithCitations(text: string): TextSegment[] {
  if (!text) return [];

  const segments: TextSegment[] = [];
  let lastIndex = 0;
  const regex = new RegExp(CITATION_REGEX);
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({
        type: "text",
        content: text.slice(lastIndex, match.index),
      });
    }

    const raw = match[0];
    const file = match[1].replace(/\\/g, "/");
    const start = parseInt(match[2], 10);
    const end = match[3] ? parseInt(match[3], 10) : start;

    segments.push({
      type: "citation",
      content: raw,
      citation: {
        raw,
        file,
        start: Math.min(start, end),
        end: Math.max(start, end),
      },
    });

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    segments.push({
      type: "text",
      content: text.slice(lastIndex),
    });
  }

  return segments;
}
