import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";

describe("Frontend Mock & Fact Leakage Guard", () => {
  const srcDir = path.resolve(__dirname, "../../");

  function getFiles(dir: string): string[] {
    const subdirs = fs.readdirSync(dir);
    const files: string[] = [];
    for (const file of subdirs) {
      const fullPath = path.join(dir, file);
      if (fs.statSync(fullPath).isDirectory()) {
        files.push(...getFiles(fullPath));
      } else {
        files.push(fullPath);
      }
    }
    return files;
  }

  it("ensures no target facts or mock data exist outside test files and suggested question lists", () => {
    const allFiles = getFiles(srcDir);
    const nonTestFiles = allFiles.filter(
      (f) => !f.includes("__tests__") && !f.endsWith(".test.ts") && !f.endsWith(".test.tsx")
    );

    const forbiddenTerms = [
      "DEFAULT_CASES",
      "1219",
      "6caa614",
      "voidgremlin19",
      "case-027",
      "Naive_RAG",
      "upsert_to_vector_db",
      "query_pipeline",
    ];

    const allowedSuggestedQuestions = [
      "Which files import upsert_to_vector_db?",
      "Explain the functions in query_pipeline.py",
    ];

    const violations: Array<{ file: string; line: number; term: string; content: string }> = [];

    for (const file of nonTestFiles) {
      const relPath = path.relative(srcDir, file).replace(/\\/g, "/");
      const content = fs.readFileSync(file, "utf-8");
      const lines = content.split("\n");

      lines.forEach((line, index) => {
        for (const term of forbiddenTerms) {
          if (line.includes(term)) {
            const isAllowedQuestion = allowedSuggestedQuestions.some((q) => line.includes(q));
            if (!isAllowedQuestion) {
              violations.push({
                file: relPath,
                line: index + 1,
                term,
                content: line.trim(),
              });
            }
          }
        }
      });
    }

    expect(
      violations,
      `Found forbidden hardcoded target facts or mock data:\n${JSON.stringify(violations, null, 2)}`
    ).toEqual([]);
  });
});
