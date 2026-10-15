import { describe, it, expect } from "vitest";
import { parseCitations, splitTextWithCitations } from "../citations";

describe("Citation chip parsing", () => {
  it("extracts exact line citations", () => {
    const text = "Found the clue in indexer.py:27.";
    const citations = parseCitations(text);
    expect(citations).toHaveLength(1);
    expect(citations[0]).toEqual({
      raw: "indexer.py:27",
      file: "indexer.py",
      start: 27,
      end: 27,
    });
  });

  it("extracts range citations", () => {
    const text = "Defined at vector_store.py:69-94 and query_pipeline.py:27-86.";
    const citations = parseCitations(text);
    expect(citations).toHaveLength(2);
    expect(citations[0].file).toBe("vector_store.py");
    expect(citations[0].start).toBe(69);
    expect(citations[0].end).toBe(94);

    expect(citations[1].file).toBe("query_pipeline.py");
    expect(citations[1].start).toBe(27);
    expect(citations[1].end).toBe(86);
  });

  it("splits text into text and citation tokens for interactive chips", () => {
    const text = "See indexer.py:27 for the import.";
    const segments = splitTextWithCitations(text);
    expect(segments).toHaveLength(3);
    expect(segments[0]).toEqual({ type: "text", content: "See " });
    expect(segments[1].type).toBe("citation");
    expect(segments[1].content).toBe("indexer.py:27");
    expect(segments[2]).toEqual({ type: "text", content: " for the import." });
  });

  it("deduplicates identical citations", () => {
    const text = "Mentioned in indexer.py:27 and later again in indexer.py:27.";
    const citations = parseCitations(text);
    expect(citations).toHaveLength(1);
  });
});
