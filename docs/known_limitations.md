# Known Limitations & Empirical Observations

This document records observed system limitations, failure modes, and hardware/API constraints discovered during empirical testing of the CodeLore multi-agent system.

---

### 1. Free-Tier NVIDIA NIM Latency & Connection Variance
- Under sequential API calls across multi-turn agent interactions, upstream NVIDIA NIM inference latency can vary significantly.
- Single questions have exhibited response latencies of up to **~22.7 minutes** (1363.26 seconds on Question a), caused by remote queuing and free-tier rate limits.
- Other queries complete in ~40–68 seconds when remote queues are clear.

### 2. Tool Invocation Loops & Function Hallucination as Tools
- **Function Name as Tool Execution Failure (Phase 7 Critical Finding)**:
  When `code_explainer` reads Python source code or receives an outline mentioning a function name (e.g. `chunk_document` in `indexer.py` or `calculate_cosine_similarity` in `vector_store.py`), the small chat model repeatedly mistakes the analyzed target function for an available ADK agent tool and attempts to invoke it as a tool call (e.g. calling `chunk_document()` or `calculate_cosine_similarity()`).
- Because these functions belong to the target project and are not registered ADK tools, ADK returns:
  `Tool '<function_name>' not found. Available tools: get_file_outline, directory_tree, get_file_info, list_directory, read_text_file, search_files`.
- Upon receiving this unknown-tool error from ADK, the model fails to recover and instead outputs:
  `"I could not find that in this codebase. I searched for <function_name>..."`.

### 3. Routing Accuracy on Unseen Queries (5/8 Baseline)
- On an initial held-out test suite with zero prompt contamination, the Boss router achieved **5 / 8 (62.5%)** routing accuracy prior to the Phase 6d prompt overhaul.
- Mismatches stemmed primarily from naming bias:
  - Routing questions mentioning a file (e.g. `main.py`) to `code_explainer` even when the user requested CLI options.
  - Routing questions mentioning a function name (e.g. `upsert_to_vector_db`) to `code_searcher` even when deep behavioral explanation was expected.
- Tie-break rules added in Phase 6d/7 now instruct routing based on the data each worker holds and clarify that questions naming a single function to explain go to `code_explainer`.

### 4. Answer Quality & Explanation Depth (Phase 7 Final Outcome)
- **Phase 7 Final Live Evaluation Outcome**:
  - Question (a) (`"Explain what chunk_document in indexer.py does"`): **FAIL**
    - Ordered tools: `['transfer_to_agent', 'get_file_outline', 'read_text_file', 'chunk_document']`
    - Model calls: 5 | Duration: 1363.26s
    - Output: `"I could not find that in this codebase..."`
    - Checker: `Passed: False`, `Errors: ['No code citations found in answer']`.
  - Question (b) (`"Outline vector_store.py"`): **FAIL**
    - Ordered tools: `['transfer_to_agent', 'get_file_outline', 'read_text_file', 'calculate_cosine_similarity']`
    - Model calls: 5 | Duration: 40.01s
    - Output: `"I could not find that in this codebase. I searched for calculate_cosine_similarity in the codebase."`
    - Checker: `Passed: False`, `Errors: ['No code citations found in answer', "Outline missing top-level definitions in vector_store.py: ['get_pinecone_client', 'ensure_pinecone_index_exists', 'upsert_to_vector_db', 'query_vector_db']"]`.

### 5. Automated Citation & Outline Checker Scope
- The AST-backed checker (`scripts/verify_routing_answers.py`) deterministically enforces:
  - Exact top-level function, class, method, import, or assignment line ranges.
  - Rejection of unverifiable sub-ranges inside functions.
  - Full top-level definition presence for outline queries.
- In both live test cases, the checker accurately caught and flagged the hallucinations and missing definitions without false positives.

### 6. Empirical MIN_SCORE Calibration & Score Thresholding
- **Default Value**: `MIN_SCORE = 0.35` (set in `code_helper/settings.py`, env-overridable).
- **Calibration Rationale**:
  - Across 16 empirical queries (10 answerable, 6 not-found/off-topic) on namespace `naive-rag`:
    - Highest not-found query score: **0.3016** (Slack webhook query matching arbitrary chunk in `indexer.py`).
    - Lowest code-search query score: **0.4049** (`A1` module dependencies).
    - `0.35` is selected as the midpoint of the gap between `0.3016` and `0.4049`.
  - **Empirical Boundary Constraint**:
    A technology not present in the codebase can still score as high as **0.30** via semantic drift (e.g. Slack webhook: 0.3016, Celery/RabbitMQ: 0.2809, Postgres/SQLAlchemy: 0.2702).
    Therefore, thresholding alone cannot guarantee semantic absence: the worker's instruction rule ("The exact concept must appear in the retrieved excerpt; never extrapolate presence from high semantic similarity") remains an essential anti-hallucination defense.

### 7. Hit@K Retrieval Performance on Naive_RAG
- Evaluated on the 10 answerable target analysis questions from `docs/target_analysis.md` (top-5 retrieved chunks from Pinecone with `min_score=0.0`):
  - **Hit@1**: **8 / 10 (80.0%)** (Target evidence file appears as the #1 ranked chunk).
  - **Hit@3**: **9 / 10 (90.0%)** (Target evidence file appears within the top 3 chunks; includes `config.py` for A3).
  - **Hit@5**: **10 / 10 (100.0%)** (Target evidence file appears within the top 5 chunks for all 10 questions; includes `main.py` for A2).

### 8. MCP Filesystem Server Security Boundary on Environment Files
- **Empirical Gap Probe (`scripts/mcp_probe_env.py`)**:
  Testing verified that `@modelcontextprotocol/server-filesystem` successfully permits `read_text_file` on `.env` files located inside its configured allowed root directory (call succeeded: `True`, content length > 0).
- **Security Implication**:
  While agent prompts and instruction boundaries instruct workers never to inspect `.env` files or reveal secrets, the underlying MCP server enforces no path-pattern or file-extension blacklists on its own.
  Consequently, for imported user projects or arbitrary external repositories (Phase 10), the directory exposed to the MCP filesystem server must be a sanitized replica from which `.env`, private keys, and credential stores have been strictly scrubbed prior to mounting.

---

### 9. Small Model Answer Synthesis Failures from Semantic Search (EVAL_01)
- The small 11B chat model (`llama-3.2-11b-vision-instruct`) exhibits poor reliability when synthesizing specific variable values from retrieved code passages or AST definitions.
- In `EVAL_01` ("What is the default top_k value configured in get_rag_config() in config.py?"), `find_symbol` successfully located `get_rag_config` at `config.py:80-154`, but the callback output truncated the inner function body (`Signature: def get_rag_config(...)`). The model failed to synthesize the actual default value (`top_k = 3`), leaving the question functionally unanswered despite providing a valid citation.

### 10. Fixed Lookup Tool Outputs: Deterministic but Plain
- Exact lookup tools (`find_symbol`, `show_file_outline`, `analyze_imports`) bypass model summarization by routing answers through `temp:final_text` and `codelore_after_agent_callback`.
- While this completely eliminates model hallucination, looping, and refusal loops, the answers are deterministic and plain tool outputs without conversational explanation or commentary.

### 11. Citation Checker Validation vs. Question Completeness
- Automated AST checking validates that citations correspond to real, verifiable line spans in the target codebase.
- However, as demonstrated in `EVAL_01`, an automated check confirming that `config.py:80-154` exists does not prove that the underlying question was substantively answered (the answer omitted `top_k = 3`).

### 12. AST Import Analysis Misclassification of Function Names (EVAL_05)
- In `analyze_imports`, querying a function symbol imported via `from vector_store import upsert_to_vector_db` results in a classification of `"Module Type: Third-party / External"`.
- This occurs because `analyze_imports` attempts module-level AST resolution; when `upsert_to_vector_db.py` does not exist as a standalone module file, it defaults to external classification. While the citation (`indexer.py:27-27`) is perfectly accurate, the classification label is misleading.

### 13. Retrieval Score Margin near MIN_SCORE Threshold
- Several valid, answerable query chunks scored between `0.36` and `0.42` in calibration (e.g. `A1` module dependencies at `0.4049`, secondary chunks for `A3` at `0.3730`).
- Because `MIN_SCORE` is configured at `0.35`, the margin between legitimate code matches and the highest false-positive not-found query (`N2` Slack webhook at `0.3016`) is narrow (~0.05). Sub-optimal phrasing on legitimate questions risks falling below threshold.

### 14. Untested Vectors & Cloud Infrastructure Limits
- **Prompt Injection Testing**: Adversarial prompt injection attacks (eval questions 8–10 in the full suite) were stopped and not tested during the final evaluation round.
- **Pinecone Free-Tier Constraints**: Cloud index operations, vector eviction thresholds, and burst rate limits under sustained enterprise indexing loads have not been verified beyond the 23-chunk Naive_RAG test target.



