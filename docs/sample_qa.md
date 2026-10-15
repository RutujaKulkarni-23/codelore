# Verified Sample Questions & Answers

This document records three empirical question-and-answer pairs executed by the CodeLore multi-agent system against the target repository (`d:\CodeLore\targets\Naive_RAG`). Answers are copied verbatim from the evaluation logs, with citations verified directly against source code lines.

---

## Sample 1: EVAL_02 (Symbol Definition)

- **Source Run**: `eval_runs/re_eval_after_fix_2.md`
- **Question**: Where is the function embed_query defined in this codebase, and what parameters does it take?
- **Worker**: `code_searcher`
- **Tools Called in Order**: `transfer_to_agent`, `find_symbol`
- **Execution Time**: 1.68s (3 model calls)
- **Answer Written By**: tool/callback (`find_symbol` writes `temp:final_text` with `skip_summarization`; `codelore_after_agent_callback` returns it directly)
- **Checker Result**: PASS (Valid Citations: `['query_pipeline.py:27-86']`, Invalid Citations: `[]`, Errors: `[]`)

### Verbatim Answer
```text
Found 1 definition(s) for symbol 'embed_query':

[1] embed_query(query: str, config: RAGConfig) - query_pipeline.py:27-86
    Signature: def embed_query(
```

### Citation Verification
- **Target File**: `d:\CodeLore\targets\Naive_RAG\query_pipeline.py` (lines 27 to 86)
- **Cited Lines from Target**:
```python
def embed_query(
    query: str,
    config: RAGConfig,
) -> list[float]:
    """
    Stage 5: Query Embedding
    Embeds the user's live query into the same 2048-dimensional mathematical
    space used during the offline chunk indexing stage.

    [TEACHING NOTE]
    Why must the query embedding model match the chunk embedding model?
    If you index your documents with Model A (e.g. 2048-dim) and embed your query with
    Model B (e.g. 1536-dim or different semantic coordinate system), the vector dimensions
    and coordinate meanings will not match! Always use the exact same embedding model.
    """
    cleaned_query = query.strip()
    if len(cleaned_query) == 0:
        raise ValueError("User query cannot be empty.")

    print("\n" + "=" * 60)
    print("STAGE 5: QUERY EMBEDDING (NVIDIA NIM)")
    print("=" * 60)
    print(f"[*] Live User Query : \"{cleaned_query}\"")
    print(f"[*] Embedding Model : {config.embed_model}")

    # Branch 1: Live NVIDIA NIM Embedding API
    if not config.use_mock_ai:
        client = OpenAI(
            base_url=config.nvidia_base_url,
            api_key=config.nvidia_api_key,
        )

        response = client.embeddings.create(
            input=[cleaned_query],
            model=config.embed_model,
        )

        query_vector = response.data[0].embedding
        vector_dim = len(query_vector)
        sample_coords = [round(val, 4) for val in query_vector[:4]]
        
        print(f"[OK] Generated query vector ({vector_dim} dimensions).")
        print(f"[*] Sample Coordinates : {sample_coords} ...")
        return query_vector

    # Branch 2: Offline Mock Simulation
    print("[!] Offline mode active. Generating simulated query vector...")
    sim_vector = []
    seed = 0
    for ch in cleaned_query:
        seed = seed + ord(ch)

    dim_index = 0
    while dim_index < 64:
        val = math.sin(seed + dim_index) * 0.5
        sim_vector.append(round(val, 4))
        dim_index = dim_index + 1

    print("[OK] Generated simulated 64-dim query vector.")
    return sim_vector
```
- **Verification Status**: Lines match exactly. Lines 27 to 86 contain the full definition and signature of `embed_query`.

---

## Sample 2: EVAL_05 (Import Dependency Analysis)

- **Source Run**: `eval_runs/re_eval_after_fix_2.md`
- **Question**: Which files in this repository import upsert_to_vector_db?
- **Worker**: `architecture_mapper`
- **Tools Called in Order**: `transfer_to_agent`, `analyze_imports`
- **Execution Time**: 3.21s (3 model calls)
- **Answer Written By**: tool/callback (`analyze_imports` writes `temp:final_text` with `skip_summarization`; `codelore_after_agent_callback` returns it directly)
- **Checker Result**: PASS (Valid Citations: `['indexer.py:27-27']`, Invalid Citations: `[]`, Errors: `[]`)
- **Note on Output Label**: "Module Type: Third-party / External" is a wrong label produced by `analyze_imports` because `upsert_to_vector_db` is a function imported from the project module `vector_store` (`from vector_store import upsert_to_vector_db`). The tool looked for a file named `upsert_to_vector_db.py`, did not find it, and fell back to labeling it External. The cited file and line (`indexer.py:27-27`) is completely correct.

### Verbatim Answer
```text
Import Analysis for module 'upsert_to_vector_db':

Module Type: Third-party / External

Imported by (1 reference(s)):
  - indexer.py:27-27
```

### Citation Verification
- **Target File**: `d:\CodeLore\targets\Naive_RAG\indexer.py` (line 27)
- **Cited Lines from Target**:
```python
from vector_store import upsert_to_vector_db
```
- **Verification Status**: Line matches exactly. Line 27 in `indexer.py` imports `upsert_to_vector_db` from `vector_store`.

---

## Sample 3: EVAL_04 (Deep Code Explanation with MCP)

- **Source Run**: `eval_runs/final_eval_20261015_224242.md`
- **Question**: Explain how build_prompt_with_context in query_pipeline.py formats the retrieved chunks and anti-hallucination instructions.
- **Worker**: `code_explainer`
- **Tools Called in Order**: `transfer_to_agent`, `get_file_outline`, `read_text_file` (MCP filesystem)
- **Execution Time**: 87.51s (5 model calls)
- **Answer Written By**: by the model (The model read the function text via MCP filesystem tool `read_text_file`, synthesized the explanation, and `codelore_after_agent_callback` appended the verified citation footer)
- **Checker Result**: PASS (Valid Citations: `['query_pipeline.py:129-176']`, Invalid Citations: `[]`, Errors: `[]`)

### Verbatim Answer
```text
The function `build_prompt_with_context` in `query_pipeline.py` formats the retrieved chunks and anti-hallucination instructions by assembling a structured system prompt combining the retrieved context passages with strict grounding instructions and the user's question. It formats the retrieved context blocks explicitly, combines them into a single context, and then injects the context into an augmented prompt with strict grounding instructions. The function returns the augmented prompt as a string.
Sources (from tool results): build_prompt_with_context -> query_pipeline.py:129-176
```

### Citation Verification
- **Target File**: `d:\CodeLore\targets\Naive_RAG\query_pipeline.py` (lines 129 to 176)
- **Cited Lines from Target**:
```python
def build_prompt_with_context(
    query: str,
    retrieved_chunks: list[dict],
) -> str:
    """
    Stage 7: Context Injection (Prompt Augmentation)
    Assembles a structured system prompt combining the retrieved context passages
    with strict grounding instructions and the user's question.

    [TEACHING NOTE]
    The Grounding Instruction is the secret sauce of RAG. We explicitly instruct the
    LLM to ONLY use the provided context and never speculate. This anchors the model's
    probabilistic decoder to real facts.
    """
    print("\n" + "=" * 60)
    print("STAGE 7: CONTEXT INJECTION (AUGMENTED PROMPT)")
    print("=" * 60)

    # Format the retrieved context blocks explicitly
    context_blocks = []
    chunk_num = 1
    for chunk in retrieved_chunks:
        header = f"--- CONTEXT DOCUMENT {chunk_num} (ID: {chunk['id']}, Relevance: {chunk['score']:.4f}) ---"
        body = chunk["text"]
        context_blocks.append(f"{header}\n{body}")
        chunk_num = chunk_num + 1

    combined_context = "\n\n".join(context_blocks)

    augmented_prompt = f"""You are the official HR & Workplace AI assistant for AstraTech Solutions.
Answer the user's inquiry accurately, professionally, and EXCLUSIVELY based on the verified reference context below.
If the answer cannot be determined strictly from the context, respond: "I do not have sufficient information in the AstraTech employee handbook to answer that question."
Do not speculate, assume, or hallucinate outside the given text.

=== BEGIN VERIFIED REFERENCE CONTEXT ===
{combined_context}
=== END VERIFIED REFERENCE CONTEXT ===

USER QUESTION:
{query}

GROUNDED ANSWER:"""

    print(f"[*] Combined Context Length : {len(combined_context)} characters across {len(retrieved_chunks)} passages")
    print(f"[*] Total Augmented Prompt   : {len(augmented_prompt)} characters")
    print("[OK] Prompt assembled with grounded context injection.")
    
    return augmented_prompt
```
- **Verification Status**: Lines match exactly. Lines 129 to 176 define `build_prompt_with_context`, formatting context document blocks, prompt construction, and strict grounding instructions.
