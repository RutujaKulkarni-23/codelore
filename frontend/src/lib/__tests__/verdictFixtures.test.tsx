import { describe, it, expect } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { StructuredVerdictCard } from "../../components/StructuredVerdictCard";
import type { Verdict } from "../sseReducer";

describe("StructuredVerdictCard fixtures rendering", () => {
  it("renders outline verdict kind correctly", () => {
    const outlineVerdict: Verdict = {
      kind: "outline",
      agent: "Code Explainer",
      data: {
        kind: "outline",
        path: "query_pipeline.py",
        items: [
          {
            name: "embed_query",
            signature: "def embed_query(query: str) -> list[float]",
            start: 27,
            end: 86,
            doc: "Embed the query text using the vector model.",
          },
          {
            name: "execute_query_pipeline",
            signature: "def execute_query_pipeline(query: str)",
            start: 89,
            end: 126,
            doc: "Run the full RAG query pipeline.",
          },
        ],
      },
    };

    const html = renderToString(
      <StructuredVerdictCard
        verdict={outlineVerdict}
        onCitationClick={() => {}}
        activeAgent="Code Explainer"
        durationSeconds={1.5}
      />
    );

    expect(html).toContain("Answered by tool - exact");
    expect(html).toContain("File Outline:");
    expect(html).toContain("query_pipeline.py");
    expect(html).toContain("embed_query");
    expect(html).toContain("execute_query_pipeline");
    expect(html).toContain("query_pipeline.py:27-86");
    expect(html).toContain("query_pipeline.py:89-126");
  });

  it("renders symbol verdict kind correctly", () => {
    const symbolVerdict: Verdict = {
      kind: "symbol",
      agent: "Code Searcher",
      data: {
        kind: "symbol",
        items: [
          {
            name: "embed_query",
            signature: "def embed_query(query: str) -> list[float]:",
            path: "query_pipeline.py",
            start: 27,
            end: 86,
            doc: "Compute embedding vector for search query.",
          },
        ],
      },
    };

    const html = renderToString(
      <StructuredVerdictCard
        verdict={symbolVerdict}
        onCitationClick={() => {}}
        activeAgent="Code Searcher"
        durationSeconds={0.8}
      />
    );

    expect(html).toContain("Answered by tool - exact");
    expect(html).toContain("embed_query");
    expect(html).toContain("query_pipeline.py:27-86");
    expect(html).toContain("Compute embedding vector for search query.");
  });

  it("renders imports verdict kind correctly", () => {
    const importsVerdict: Verdict = {
      kind: "imports",
      agent: "Architecture Mapper",
      data: {
        kind: "imports",
        target: "upsert_to_vector_db",
        defined_in: "vector_store.py",
        importers: [
          {
            path: "indexer.py",
            line: 27,
            statement: "from vector_store import upsert_to_vector_db",
          },
        ],
      },
    };

    const html = renderToString(
      <StructuredVerdictCard
        verdict={importsVerdict}
        onCitationClick={() => {}}
        activeAgent="Architecture Mapper"
        durationSeconds={1.2}
      />
    );

    expect(html).toContain("Answered by tool - exact");
    expect(html).toContain("Defined in");
    expect(html).toContain("vector_store.py");
    expect(html).toContain("indexer.py:27");
    expect(html).toContain("from vector_store import upsert_to_vector_db");
  });

  it("renders overview verdict kind correctly", () => {
    const overviewVerdict: Verdict = {
      kind: "overview",
      agent: "Onboarding Guide",
      data: {
        kind: "overview",
        entry_point: "main.py",
        also_runnable: ["indexer.py"],
        commands: ["python main.py --query 'hello'"],
        stages: [
          {
            name: "1. Ingestion",
            script: "indexer.py",
            purpose: "Indexes docs into Pinecone",
          },
        ],
        reading_order: [
          {
            path: "main.py",
            doc: "Main CLI entry point",
          },
          {
            path: "query_pipeline.py",
            doc: "Core query pipeline",
          },
        ],
        data_files: ["data/documents.json"],
        dependency_files: ["requirements.txt"],
        docs: ["README.md"],
      },
    };

    const html = renderToString(
      <StructuredVerdictCard
        verdict={overviewVerdict}
        onCitationClick={() => {}}
        activeAgent="Onboarding Guide"
        durationSeconds={2.1}
      />
    );

    expect(html).toContain("Answered by tool - exact");
    expect(html).toContain("START HERE (ENTRY POINT)");
    expect(html).toContain("main.py");
    expect(html).toContain("HOW TO RUN");
    expect(html).toContain("python main.py --query &#x27;hello&#x27;");
    expect(html).toContain("PIPELINE STAGES");
    expect(html).toContain("1. Ingestion");
    expect(html).toContain("READ IN THIS ORDER");
    expect(html).toContain("Main CLI entry point");
  });

  it("renders text verdict kind correctly with AI badge", () => {
    const textVerdict: Verdict = {
      kind: "text",
      agent: "Code Explainer",
      text: "The `embed_query` function converts text into vector embeddings.\nCheck query_pipeline.py:27-86 for details.",
      citations: [{ path: "query_pipeline.py", start: 27, end: 86 }],
      sources: ["query_pipeline.py:27-86"],
    };

    const html = renderToString(
      <StructuredVerdictCard
        verdict={textVerdict}
        onCitationClick={() => {}}
        activeAgent="Code Explainer"
        durationSeconds={3.4}
      />
    );

    expect(html).toContain("Written by AI - check evidence");
    expect(html).not.toContain("Verified from code");
    expect(html).toContain("embed_query");
    expect(html).toContain("query_pipeline.py:27-86");
    expect(html).toContain("Evidence:");
  });

  it("renders not_found verdict kind correctly as cold case", () => {
    const notFoundVerdict: Verdict = {
      kind: "not_found",
      agent: "Code Searcher",
      data: {
        kind: "not_found",
        message: "Could not find any symbol named calculate_quantum_score.",
        searches_tried: [
          "find_symbol: calculate_quantum_score",
          "rag_search: calculate_quantum_score",
        ],
      },
    };

    const html = renderToString(
      <StructuredVerdictCard
        verdict={notFoundVerdict}
        onCitationClick={() => {}}
        activeAgent="Code Searcher"
        durationSeconds={1.1}
      />
    );

    expect(html).toContain("Cold case - not found");
    expect(html).toContain("Cold Case — Symbol or Reference Not Found");
    expect(html).toContain("Could not find any symbol named calculate_quantum_score.");
    expect(html).toContain("Searches tried:");
    expect(html).toContain("find_symbol: calculate_quantum_score");
    expect(html).toContain("rag_search: calculate_quantum_score");
  });
});
