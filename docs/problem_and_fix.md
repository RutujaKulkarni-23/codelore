# Engineering Problem & Fix Report

## 1. The Core Problem: Small-Model Tool Refusal and Hallucinatory Looping

During live multi-agent evaluation against the target codebase (`Naive_RAG`), workers `code_searcher` and `architecture_mapper` encountered severe failure modes when answering lookup questions:
- **Observed Failure**: When tools returned completely accurate, verifiable AST data (e.g., `find_symbol` returning `query_pipeline.py:27-86` for `embed_query`, or `analyze_imports` returning `indexer.py:27` for `upsert_to_vector_db`), the small chat model (`meta/llama-3.2-11b-vision-instruct` via NVIDIA NIM) frequently ignored the tool result.
- **Looping & Denial**: Instead of citing the tool output, the model either:
  1. Initiated repetitive hallucination loops, making up to 11 redundant `rag_search` calls until hitting ADK's maximum LLM call limit (e.g., 15 calls in `EVAL_01`, 338 seconds in `EVAL_02`).
  2. Concluded with false negative refusals: *"I could not find that in this codebase. Searches tried: ..."*.
- **Failed Prompt-Only Fix**: An initial attempt to resolve this via stricter system prompt instructions alone (`eval_runs/re_eval_after_fix.md`) completely failed (**0 / 3 passed**). The model continued looping or hitting call limits regardless of prompt warnings.

---

## 2. Root Cause Analysis

1. **Weak In-Context Attention in Small Models**: The 11B parameter vision-instruct model struggles to retain instruction grounding when tool outputs are passed back into multi-turn dialogue context. Instead of copying exact code coordinates, it defaults to conversational speculation or attempts new search queries.
2. **Type Coercion Failures**: The model frequently passed `top_k="3"` (a string) instead of an integer to `rag_search`, triggering input validation exceptions that caused further conversational derailment.
3. **Lack of Loop Interception**: Without execution guards, the agent runtime had no mechanism to halt an agent that invoked the exact same tool with identical or near-identical arguments multiple times in a single turn.

---

## 3. The Multi-Layered Deterministic Fix

To resolve this without altering model weights or upgrading to costly large models, an architectural hybrid pattern was implemented:

1. **Tool State Writing & Summarization Bypass (`temp:final_text` + `skip_summarization`)**:
   Exact lookup tools (`find_symbol`, `show_file_outline`, `analyze_imports`) format copy-ready citations and store the result in `tool_context.state["temp:final_text"]`. Simultaneously, the tool sets `tool_context.actions.skip_summarization = True` to prevent the model from rewriting or distorting the data.
2. **Shared `after_agent_callback` Delivery**:
   A deterministic ADK `after_agent_callback` (`codelore_after_agent_callback`) intercepts the agent cycle before completion. If `temp:final_text` is present in state, it delivers this text directly as the final model response part, completely bypassing model generation.
3. **`before_tool_callback` Loop Guard**:
   A deterministic guard (`loop_guard_before_tool_callback`) tracks invocation history per turn:
   - Blocks the **3rd call** of the same tool within a single user request.
   - Blocks the **2nd call** of identical arguments to the same tool.
   - Injects an immediate stop instruction returning already-retrieved context if a loop is detected.
4. **Input Type Coercion**:
   In `rag_search`, string-encoded integers for `top_k` (e.g., `"5"`) are automatically coerced to integer values (`top_k = int(top_k.strip())`), with strict boundaries enforced [1, 20].

---

## 4. Empirical Evaluation of the Fix

The fix was evaluated by re-running the diagnostic failures (`eval_runs/re_eval_after_fix_2.md`):

| Evaluation ID | Question | Pre-Fix Duration & Calls | Post-Fix Duration & Calls | Result (Post-Fix) |
| :--- | :--- | :---: | :---: | :--- |
| **EVAL_01** | Default `top_k` in `get_rag_config()` | 54.92s (6 calls) / 55.49s (15 calls) | 15.52s (4 calls) | Valid citation `config.py:80-154`, but body truncated `top_k=3` |
| **EVAL_02** | Where is `embed_query` defined & parameters | 338.52s (7 calls) / 22.85s (8 calls) | 1.68s (3 calls) | **PASS** (Fully correct, cited `query_pipeline.py:27-86`) |
| **EVAL_05** | Files importing `upsert_to_vector_db` | 24.48s (4 calls) / 9.28s (7 calls) | 3.21s (3 calls) | **PASS** (Fully correct, cited `indexer.py:27-27`) |

### Outcomes and Methodology Note
- **Score**: **2 / 3 fully correct** and grounded; **1 / 3 cited but incomplete** (EVAL_01 cited the correct function definition but truncated before the default argument value).
- **Latency Reduction**: Query times dropped from hundreds of seconds to between **1.68s and 15.52s**.
- **Evaluation Disclaimer**: Note clearly that this re-evaluation was performed on the same diagnostic question set to isolate the fix, and is **not a clean held-out evaluation**.

---

## 5. Note on Prior Routing Contamination

During earlier development phases, an initial routing evaluation yielded a score of **8 / 8 (100%)**. However, code review revealed that the Boss router prompt contained verbatim example query phrases that directly matched the test cases. 

Once prompt contamination was removed and the router was evaluated against a genuinely held-out, unseen query set (`eval_runs/routing_eval_20261015_200406.md`), the true baseline routing accuracy was measured at **5 / 8 (62.5%)**. Subsequent tie-break rule additions in Phase 6d/7 restored routing accuracy to **5 / 5 (100%)** on the first 5 questions of the final evaluation suite.
