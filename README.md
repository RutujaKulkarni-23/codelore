# CodeLore: Multi-Agent Code Helper

## (a) What the Helper Does
CodeLore is a multi-agent code assistant that answers architectural, code-location, and deep explanatory questions about a Python codebase (analyzing the read-only target `Naive_RAG`). It routes user questions to specialized agents that use AST parsing, vector search, and secure filesystem inspection to produce answers backed by verified line-number citations.

---

## (b) Table of Agents

| Agent Name | Primary Job | Tools Available |
| :--- | :--- | :--- |
| **`Boss`** (Root Router) | Classifies intent and routes query to the appropriate specialist; performs no tool calls or code analysis directly. | *(None — routing via agent transfers only)* |
| **`code_searcher`** | Locates function and class definitions by symbol name or semantic search. | `find_symbol`, `rag_search` |
| **`code_explainer`** | Explains how functions and modules work and provides file outlines. | `get_file_outline`, `show_file_outline`, MCP Filesystem tools (`read_text_file`, `list_directory`, `directory_tree`, `search_files`, `get_file_info`) |
| **`architecture_mapper`**| Analyzes import structures and cross-file dependencies. | `analyze_imports` |
| **`onboarding_guide`** | Answers repository high-level questions, entry points, and quick-start workflow questions. | `get_project_overview` |

---

## (c) Table of Tools

| Tool Name | Assigned Worker | Implementation Type | Description |
| :--- | :--- | :--- | :--- |
| `rag_search` | `code_searcher` | Uses AI (Embeddings + Pinecone) | Semantic search over indexed code chunks using NVIDIA embeddings (`nvidia/nemotron-3-embed-1b`) and Pinecone vector similarity. |
| `find_symbol` | `code_searcher` | Plain Python (AST) | Exact AST symbol search returning matching function, class, or method definitions with exact line ranges. |
| `get_file_outline` | `code_explainer` | Plain Python (AST) | Returns AST symbol-to-line range mappings used internally by the explainer before reading source code. |
| `show_file_outline`| `code_explainer` | Plain Python (AST) | Produces a copy-ready outline listing all top-level classes and functions in a file with line citations. |
| `analyze_imports` | `architecture_mapper` | Plain Python (AST) | Inspects the target's import graph to determine which local files import a specific module or function. |
| `get_project_overview` | `onboarding_guide` | Plain Python | Analyzes project file tree, docstrings, and entry points to summarize repository architecture. |
| **Filesystem MCP** | `code_explainer` | Plain External Process (Node.js) | Official `@modelcontextprotocol/server-filesystem@1.0.0` running in a sub-process with read-only tool filtering (`read_text_file`, `list_directory`, `directory_tree`, `search_files`, `get_file_info`). |

---

## (d) Your Chunk Size and Why

### Chunk Configuration
- **Chunk Strategy**: `ast_hybrid` (configured in `code_helper/settings.py` and `code_helper/rag/chunker.py`)
- **Maximum Chunk Lines (`max_chunk_lines`)**: 60 lines
- **Chunk Overlap Lines (`chunk_overlap_lines`)**: 8 lines
- **Maximum Chunk Characters (`max_chunk_chars`)**: 3000 characters

### Rationale
In code search, chunk boundaries must preserve semantic units. The `ast_hybrid` strategy creates one chunk per top-level function, class, or method, ensuring that complete definitions stay intact so citations reflect exact line numbers. When a function or code block exceeds 60 lines or 3000 characters, it is partitioned using a sliding window with an 8-line overlap to preserve local context across chunk boundaries. 

A second chunking strategy (`fixed_window`, 1200 characters with 200 character overlap) is implemented in `code_helper/rag/chunker.py` but was not evaluated empirically.

---

## (e) The MCP Server Used and Why

- **MCP Server Package**: `@modelcontextprotocol/server-filesystem@1.0.0`
- **Why It Is Used**: To answer deep conceptual questions about code mechanics (e.g., explaining `build_prompt_with_context`), the `code_explainer` agent must inspect actual file text. Using the official Model Context Protocol (MCP) filesystem server provides robust, standardized file reading without requiring custom filesystem traversal scripts.
- **Security Boundary**: ADK's client toolset filter enforces a strict read-only boundary (`read_text_file`, `list_directory`, `directory_tree`, `search_files`, `get_file_info`), completely blocking write and delete operations. Furthermore, host process environment variables (such as NVIDIA and Pinecone API keys) are explicitly excluded from the subprocess environment.

---

## (f) Exact Commands to Run It

### 1. Prerequisites and Setup (Windows PowerShell)
```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install project dependencies
pip install -r requirements.txt

# Configure environment variables
# Copy .env.example to code_helper/.env and fill in required keys (NEVER commit .env)
# Note: Node.js (npx) must be installed on your PATH for the MCP server.
```

### 2. Index the Target Codebase
```powershell
python code_helper/index_codebase.py
```

### 3. Run the Assistant Web UI
```powershell
cd d:\CodeLore\codelore
.\.venv\Scripts\Activate.ps1
adk web
```
Open the URL printed in the console (typically `http://localhost:8000`) and select **`code_helper`** from the agent dropdown.

### 4. Run Test Suite
```powershell
python -m pytest -q
```
*Current test suite status*: **86 passed, 4 skipped in ~6 seconds** (all offline unit and integration tests; skips require live cloud API credentials).

---

## System Architecture

```text
User Query
    │
    ▼
[Boss Router] (LLM routing only, no tools)
    │
    ├──► [code_searcher]        ──► find_symbol (AST), rag_search (Vector DB)
    ├──► [code_explainer]       ──► get/show_file_outline (AST), MCP filesystem (read_text_file)
    ├──► [architecture_mapper]  ──► analyze_imports (AST)
    └──► [onboarding_guide]     ──► get_project_overview (AST & file scanner)
```

- **RAG Pipeline**: `scanner.py` (file scanning) ➔ `chunker.py` (`ast_hybrid` AST chunking) ➔ `masker.py` (regex secret masking) ➔ `embedder.py` (NVIDIA `nvidia/nemotron-3-embed-1b`, 2048 dimensions) ➔ Pinecone Serverless Index (`cosine` distance) ➔ `search.py` (filtered vector retrieval).
- **Framework Independence**: Built using standard Python and Google ADK; contains **no LangChain and no LlamaIndex**.

---

## Chat Model Configuration

- **Orchestration**: Google ADK (Agent Development Kit) with LiteLLM proxy connector.
- **Model**: `meta/llama-3.2-11b-vision-instruct` served via NVIDIA NIM.
- **Sampling Temperature**: `0.1` (low temperature to minimize hallucination and maximize citation determinism).

---

## Reliability Design

During live trials, the compact 11B parameter chat model frequently ignored valid tool outputs, resulting in infinite retrieval loops or erroneous "could not find that" denials. To ensure operational reliability, a deterministic dual-callback architecture was implemented:
1. **Tool State Writing & Summarization Bypass**: Exact lookup tools (`find_symbol`, `show_file_outline`, `analyze_imports`) store copy-ready citation strings directly into session state under `temp:final_text` and mark `skip_summarization = True`.
2. **`after_agent_callback` Return**: A shared ADK callback (`codelore_after_agent_callback`) checks for `temp:final_text` and delivers it directly to the user as the final response, preventing the model from rephrasing or discarding the data. For explanations, it appends AST-verified line citations from `get_file_outline`.
3. **`before_tool_callback` Loop Guard**: A deterministic guard (`loop_guard_before_tool_callback`) halts execution if the agent attempts a 3rd call to the same tool or repeats identical tool arguments within a single turn.

---

## Security Design

- **No Arbitrary Code Execution**: The assistant parses ASTs and reads text; it never invokes `eval()`, `exec()`, or executes target code.
- **Secret Masking**: Before text chunks are submitted for vector embedding, `masker.py` redacts API keys, bearer tokens, and credentials.
- **Path Traversal Prevention**: Tool utilities reject directory traversal attempts (`..`) and absolute paths outside the target folder.
- **Bounded Output**: Tool responses are capped at 6,000 characters and enclosed in untrusted-code delimiters.
- **Subprocess Isolation**: The MCP filesystem subprocess does not inherit host environment API keys.

---

## Evaluation Results (Empirical Data Only)

- **Vector Retrieval Calibration (`eval_runs/min_score_calibration.md`)**:
  - `Hit@1`: **8 / 10 (80.0%)** on answerable target queries.
  - `Hit@3`: **9 / 10 (90.0%)**.
  - `Hit@5`: **10 / 10 (100.0%)**.
  - `MIN_SCORE`: Calibrated to **0.35** (midpoint separating the highest false-positive not-found query at `0.3016` from the lowest answerable search query at `0.4049`).
- **Routing Accuracy**:
  - **5 / 8 (62.5%)** on held-out evaluation queries prior to prompt rule refinement (`eval_runs/routing_eval_20261015_200406.md`).
  - **5 / 5 (100.0%)** on the first 5 questions of the final evaluation run (`eval_runs/final_eval_20261015_224242.md`).
- **Final Evaluation (First 5 Questions)**:
  - Grounded Pass Rate: **2 / 5 (40.0%)** (both explainer questions passed: EVAL_03 outline, EVAL_04 explanation).
  - Diagnostic Re-Evaluation After Fix 2 (`eval_runs/re_eval_after_fix_2.md` — evaluated on the same 3 failed questions, not a clean held-out test):
    - `EVAL_02` (`embed_query` definition): **PASS** (1.68s, cited `query_pipeline.py:27-86`).
    - `EVAL_05` (`upsert_to_vector_db` imports): **PASS** (3.21s, cited `indexer.py:27-27`).
    - `EVAL_01` (default `top_k` value): Cited `config.py:80-154` but truncated signature before stating `top_k = 3`, failing substantive question completeness.
- **Stopped Evaluation**: Questions 6–10 of the final evaluation suite (covering not-found concepts, out-of-scope queries, and adversarial prompt injections) were stopped and not measured.

---

## Sample Questions & Answers

Complete transcripts, execution timings, and line citations verified against `targets/Naive_RAG` are documented in [docs/sample_qa.md](file:///d:/CodeLore/codelore/docs/sample_qa.md):

1. **Symbol Lookup (Agent: `code_searcher`)**:
   - *Question*: Where is the function `embed_query` defined in this codebase, and what parameters does it take?
   - *Tools*: `transfer_to_agent`, `find_symbol` (Time: 1.68s)
   - *Answer*: `Found 1 definition(s) for symbol 'embed_query': [1] embed_query(query: str, config: RAGConfig) - query_pipeline.py:27-86`
2. **Dependency Mapping (Agent: `architecture_mapper`)**:
   - *Question*: Which files in this repository import `upsert_to_vector_db`?
   - *Tools*: `transfer_to_agent`, `analyze_imports` (Time: 3.21s)
   - *Answer*: `Import Analysis for module 'upsert_to_vector_db': Module Type: Third-party / External. Imported by (1 reference(s)): indexer.py:27-27` *(Note: "External" is an AST label artifact; citation is exact).*
3. **Code Explanation (Agent: `code_explainer`)**:
   - *Question*: Explain how `build_prompt_with_context` in `query_pipeline.py` formats the retrieved chunks and anti-hallucination instructions.
   - *Tools*: `transfer_to_agent`, `get_file_outline`, `read_text_file` (Time: 87.51s)
   - *Answer*: Explains prompt assembly and grounding instructions, with verified citation `query_pipeline.py:129-176`.

---

## Key Problem & Architectural Fix

- **Problem**: Small chat models regularly ignored successful AST tool responses, initiating runaway loops (up to 15 LLM calls) or issuing false "could not find that" denials. A prompt-only fix achieved 0/3.
- **Fix**: Bypassed model generation for deterministic lookups by storing tool outputs in `temp:final_text` with `skip_summarization`, returned via `codelore_after_agent_callback`, protected by a `before_tool_callback` loop guard and input type coercion.
- **Full Report**: See [docs/problem_and_fix.md](file:///d:/CodeLore/codelore/docs/problem_and_fix.md).

---

## Known Limitations

A complete analysis of failure modes and edge cases is maintained in [docs/known_limitations.md](file:///d:/CodeLore/codelore/docs/known_limitations.md):
- Free-text answers (overview, explain) are written by the small 11b model and can contain mistakes; lookups are answered by the tools and checked by scripts/tool_smoke_test.py.
- **Model Synthesis Limits**: The small model struggles to synthesize specific variable values from code passages (as seen in `EVAL_01`).
- **Plain Lookup Output**: Callback-delivered answers are exact and deterministic, but plain tool text without conversational prose.
- **Checker Scope**: Automated line citation verification proves citation accuracy, but does not guarantee that every sub-question was answered (e.g. `EVAL_01`).
- **AST Classification Artifacts**: `analyze_imports` mislabels imported functions as "Third-party / External" when they do not map to separate standalone filenames.
- **Narrow Score Margin**: Legitimate code chunks scored between `0.36` and `0.42` in calibration, presenting a narrow margin above `MIN_SCORE = 0.35`.
- **NVIDIA NIM Free-Tier Latency**: Inference latency ranged from ~2 seconds to ~22 minutes under remote API queuing.
- **MCP `.env` Read Access**: The filesystem MCP server does not enforce file extension filters and can read `.env` files if they exist within its allowed root directory.
- **Unverified Constraints**: Adversarial prompt injection defenses and high-load Pinecone free-tier rate limits were not evaluated in final testing.

---

## Documentation

Comprehensive, presentation-quality technical documentation with architectural diagrams is available in the `docs/` folder:

- **[Product Requirements Document (PRD)](file:///d:/CodeLore/codelore/docs/PRD.md)**: Product definition, user personas, acceptance criteria, user journey, empirical metrics, risks, and release roadmap.
- **[System Architecture](file:///d:/CodeLore/codelore/docs/ARCHITECTURE.md)**: Container breakdown, multi-agent hierarchy, deterministic callbacks, reliability guards, RAG pipeline, and Architecture Decision Records (ADRs).
- **[MVP Specification & Technology Stack](file:///d:/CodeLore/codelore/docs/MVP_TECH.md)**: MVP scope, exact package versions, REST and SSE API contracts, local setup runbook, test coverage, and cloud deployment guide.
- **[System Design for Scale & Safety](file:///d:/CodeLore/codelore/docs/SYSTEM_DESIGN.md)**: Pinecone and CaseState data models, sequence flows, scaling blueprint, failure mode matrix, and STRIDE-light threat analysis.

