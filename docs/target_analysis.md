# Target Project Analysis: Naive_RAG

## a. Purpose of the Project
The `targets/Naive_RAG` repository is an educational implementation of an 8-stage Naive Retrieval-Augmented Generation (RAG) architecture ([Day4_Naive_RAG_Project_Build_Spec.md:L8-L10](file:///d:/CodeLore/targets/Naive_RAG/Day4_Naive_RAG_Project_Build_Spec.md#L8-L10)). Its goal is to ingest proprietary corporate policy text, embed and store chunks in Pinecone (or a local JSON fallback), and answer queries with factually grounded responses generated via NVIDIA NIM LLMs ([indexer.py:L10-L20](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L10-L20), [query_pipeline.py:L5-L16](file:///d:/CodeLore/targets/Naive_RAG/query_pipeline.py#L5-L16)). It specifically provides a live comparative demonstration contrasting hallucinations from a raw LLM against verified answers from a RAG-augmented model ([main.py:L10-L24](file:///d:/CodeLore/targets/Naive_RAG/main.py#L10-L24)).

---

## b. File Table
Roles and line ranges extracted via AST parsing ([scripts/outline_target.py](file:///d:/CodeLore/codelore/scripts/outline_target.py)):

| File Path | Role | Key Classes & Functions with Exact Line Ranges |
| :--- | :--- | :--- |
| `config.py` | Configuration dataclass and environment variable loader with priority-ordered `.env` discovery. | • `def load_environment_variables()`: L21-L53<br>• `class RAGConfig`: L61-L77<br>• `def get_rag_config(force_mock_ai, force_local_db)`: L80-L154 |
| `indexer.py` | Offline indexing pipeline: file reading, text chunking, embedding generation, and vector store dispatch. | • `def load_document(file_path)`: L30-L52<br>• `def chunk_document(text, chunk_size, chunk_overlap)`: L55-L111<br>• `def embed_chunks(chunks, config)`: L114-L195<br>• `def store_in_vector_db(chunks_with_embeddings, config)`: L198-L221<br>• `def run_indexing_pipeline(file_path, config)`: L224-L268 |
| `vector_store.py` | Storage layer: manages Pinecone serverless index lifecycle/upsert and local JSON file fallback with cosine similarity math. | • `def calculate_cosine_similarity(vec_a, vec_b)`: L28-L59<br>• `def get_pinecone_client(api_key)`: L62-L66<br>• `def ensure_pinecone_index_exists(client, index_name, dimension, cloud, region)`: L69-L94<br>• `def upsert_to_vector_db(chunks_with_embeddings, config)`: L97-L162<br>• `def query_vector_db(query_vector, top_k, config)`: L165-L233 |
| `query_pipeline.py` | Online query pipeline: query embedding, top-k retrieval, prompt augmentation, and grounded LLM generation. | • `def embed_query(query, config)`: L27-L86<br>• `def retrieve_top_k(query_vector, config)`: L89-L126<br>• `def build_prompt_with_context(query, retrieved_chunks)`: L129-L176<br>• `def generate_answer(prompt, config)`: L179-L240<br>• `def generate_answer_without_rag(query, config)`: L243-L309<br>• `def run_query_pipeline(query, config)`: L312-L358 |
| `main.py` | Demonstration CLI router: parses CLI flags and runs offline indexing, custom queries, or side-by-side comparison scorecards. | • `def print_banner(title)`: L45-L52<br>• `def print_scorecard(query, raw_answer, rag_answer, chunks)`: L55-L90<br>• `def run_full_demo(config)`: L93-L127<br>• `def main()`: L130-L180 |

---

## c. Import Graph
Constructed directly from top-level import statements:

```
[main.py]
  │──> from config import RAGConfig, get_rag_config (L31)
  │──> from indexer import run_indexing_pipeline (L32)
  └──> from query_pipeline import generate_answer_without_rag, run_query_pipeline (L33-L36)

[indexer.py]
  │──> from config import RAGConfig, get_rag_config (L26)
  └──> from vector_store import upsert_to_vector_db (L27)

[query_pipeline.py]
  │──> from config import RAGConfig, get_rag_config (L23)
  └──> from vector_store import query_vector_db (L24)

[vector_store.py]
  └──> from config import RAGConfig (L22)

[config.py]
  └──> (No internal project dependencies; standard library + dotenv)
```

---

## d. Indexing Flow and Query Flow

### Indexing Flow (Stages 1–4)
1. **Document Loading**: `run_indexing_pipeline()` invokes `load_document(file_path)` ([indexer.py:L224-L237](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L224-L237)), which reads raw UTF-8 text from disk and asserts the file is non-empty ([indexer.py:L30-L52](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L30-L52)).
2. **Text Chunking**: `chunk_document(text, chunk_size, chunk_overlap)` loops over the text using fixed character slices with step `chunk_size - chunk_overlap`, assigning each piece an incremental chunk ID and text metadata ([indexer.py:L55-L111](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L55-L111)).
3. **Batch Embedding**: `embed_chunks(chunks, config)` collects all chunk strings into `texts_to_embed = [c["text"] for c in chunks]` and invokes NVIDIA NIM via `client.embeddings.create(input=texts_to_embed, model=config.embed_model)` ([indexer.py:L142-L150](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L142-L150)). In offline mock mode (`config.use_mock_ai=True`), it computes deterministic pseudo-random 64-dimensional vectors ([indexer.py:L173-L195](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L173-L195)).
4. **Vector Store Ingestion**: `store_in_vector_db()` forwards the vectors to `upsert_to_vector_db()` ([indexer.py:L198-L221](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L198-L221)).
5. **Pinecone / Local Ingestion**: `upsert_to_vector_db()` ensures the serverless index exists ([vector_store.py:L69-L94](file:///d:/CodeLore/targets/Naive_RAG/vector_store.py#L69-L94)) and upserts the batch to Pinecone ([vector_store.py:L109-L138](file:///d:/CodeLore/targets/Naive_RAG/vector_store.py#L109-L138)). If Pinecone fails or local storage is selected, it overwrites `data/local_vector_db.json` with formatted records containing `id`, `embedding`, and `metadata` ([vector_store.py:L144-L162](file:///d:/CodeLore/targets/Naive_RAG/vector_store.py#L144-L162)).

### Query Flow (Stages 5–8)
6. **Query Embedding**: `run_query_pipeline(query, config)` invokes `embed_query(query, config)` ([query_pipeline.py:L312-L331](file:///d:/CodeLore/targets/Naive_RAG/query_pipeline.py#L312-L331)), which sends `input=[cleaned_query]` to NVIDIA NIM `client.embeddings.create()` to produce a 2048-dim vector ([query_pipeline.py:L59-L64](file:///d:/CodeLore/targets/Naive_RAG/query_pipeline.py#L59-L64)).
7. **Top-K Retrieval**: `retrieve_top_k(query_vector, config)` invokes `query_vector_db(query_vector, top_k, config)` ([query_pipeline.py:L89-L126](file:///d:/CodeLore/targets/Naive_RAG/query_pipeline.py#L89-L126)), retrieving matches from Pinecone ([vector_store.py:L176-L197](file:///d:/CodeLore/targets/Naive_RAG/vector_store.py#L176-L197)) or calculating pairwise cosine similarity over `data/local_vector_db.json` ([vector_store.py:L199-L226](file:///d:/CodeLore/targets/Naive_RAG/vector_store.py#L199-L226)).
8. **Context Injection**: `build_prompt_with_context(query, retrieved_chunks)` wraps the retrieved chunk texts into formatted blocks (`--- CONTEXT DOCUMENT {i} ---`) and injects them between `=== BEGIN VERIFIED REFERENCE CONTEXT ===` and `=== END VERIFIED REFERENCE CONTEXT ===` with explicit anti-hallucination instructions ([query_pipeline.py:L129-L176](file:///d:/CodeLore/targets/Naive_RAG/query_pipeline.py#L129-L176)).
9. **Grounded Generation**: `generate_answer(prompt, config)` dispatches the augmented prompt to NVIDIA NIM chat completions (`meta/llama-3.2-11b-vision-instruct`) with `temperature=0.1` and `max_tokens=600` ([query_pipeline.py:L179-L226](file:///d:/CodeLore/targets/Naive_RAG/query_pipeline.py#L179-L226)).
10. **Baseline Contrast**: `main.py` runs `generate_answer_without_rag()` (prompting the chat model with zero context) and prints a side-by-side scorecard illustrating raw hallucinations vs RAG precision ([main.py:L55-L90](file:///d:/CodeLore/targets/Naive_RAG/main.py#L55-L90), [query_pipeline.py:L243-L309](file:///d:/CodeLore/targets/Naive_RAG/query_pipeline.py#L243-L309)).

---

## e. How to Run It (Documented, Not Executed)
Per `main.py` CLI parser definition ([main.py:L134-L180](file:///d:/CodeLore/targets/Naive_RAG/main.py#L134-L180)):

- **Default Complete Demo Walkthrough**:
  ```powershell
  python main.py
  ```
  *(Executes full demo: indexes `astratech_employee_handbook.txt`, runs baseline query without RAG, runs RAG query on canonical question, and prints scorecard).*
- **Offline Indexing Pipeline Only**:
  ```powershell
  python main.py --index
  ```
- **Custom Question Query Pipeline**:
  ```powershell
  python main.py --query "What is the policy for medical leave?"
  ```
- **Side-by-Side Comparison Scorecard**:
  ```powershell
  python main.py --compare
  ```
- **Offline Mock Simulation Mode**:
  ```powershell
  python main.py --mock
  # Can be combined with other flags, e.g.:
  python main.py --query "What is project Chronos?" --mock
  ```

---

## f. Configuration Variables & Defaults
Read inside `get_rag_config()` ([config.py:L80-L154](file:///d:/CodeLore/targets/Naive_RAG/config.py#L80-L154)):

| Variable Name | Default Value in Code | Purpose |
| :--- | :--- | :--- |
| `NVIDIA_API_KEY` | `""` | Primary API key for NVIDIA NIM |
| `NVIDIA_NIM_API_KEY` | `""` | Fallback environment variable for NVIDIA key |
| `NVIDIA_BASE_URL` | `"https://integrate.api.nvidia.com/v1"` | Base endpoint for NVIDIA NIM API |
| `NVIDIA_CHAT_MODEL` | `"meta/llama-3.2-11b-vision-instruct"` | Chat completion LLM |
| `NVIDIA_EMBED_MODEL` | `"nvidia/nemotron-3-embed-1b"` | Embedding model (2048 dimensions) |
| `PINECONE_API_KEY` | `""` | Authentication key for Pinecone vector DB |
| `PINECONE_INDEX_NAME` | `"naive-rag-demo"` | Pinecone serverless index name |
| `PINECONE_CLOUD` | `"aws"` | Cloud provider for serverless index |
| `PINECONE_REGION` | `"us-east-1"` | Region for serverless index |
| `CHUNK_SIZE` | `500` (integer) | Document character chunk size |
| `CHUNK_OVERLAP` | `100` (integer) | Character overlap between consecutive chunks |
| `TOP_K` | `3` (integer) | Number of vector chunks retrieved per query |

---

## g. Notable Behaviours & Design Nuances
1. **Multi-tier Parent `.env` Traversal**: `config.py` searches 4 different `.env` file locations on import. Crucially, `.env.local` in current folder (`L31`) and workspace root `.env.local` (`L46`) are loaded with `override=True`, allowing higher-level workspace files to overwrite local configuration silently.
2. **Silent Degradation to Mocks**: If `NVIDIA_API_KEY` is empty, `config.py:L130-L131` silently toggles `use_mock_ai = True` (generating pseudo-random 64-dim math vectors and mock canned answers) rather than failing loudly.
3. **Silent Degradation to Local JSON Store**: If `PINECONE_API_KEY` is empty, `config.py:L137-L138` silently toggles `use_local_vector_db = True`.
4. **Pinecone Index Name Default Mismatch**: `config.py:L105` defaults to `"naive-rag-demo"`, whereas CodeLore's multi-agent specification expects `"code-helper"`.
5. **Monolithic Embedding Batch**: `indexer.py:L142-L150` loads all chunks into a single Python list and sends them in one `client.embeddings.create()` request with no pagination or chunk batching.
6. **Local JSON Database File Overwrite**: When writing to `data/local_vector_db.json`, `vector_store.py:L158` opens the file with `"w"` mode, completely overwriting prior stored vectors.
7. **Embed Model `input_type` Parameter**: Omitted in both `indexer.py:L147-L150` and `query_pipeline.py:L59-L62` (unverified whether needed until Phase 4 checks model card specifications).

---

## h. Draft Evaluation Questions (12 Verified Questions)

### Category 1: Architecture Mapper
1. **Question**: *What are the top-level module dependencies between the 5 Python files in Naive_RAG?*
   - **Expected Worker**: Architecture Mapper
   - **Expected Answer Facts**: `main.py` is the top-level coordinator importing `config.py`, `indexer.py`, and `query_pipeline.py`. Both `indexer.py` and `query_pipeline.py` depend on `config.py` and `vector_store.py`. `vector_store.py` depends on `config.py`. `config.py` has no internal project dependencies.
   - **Evidence**: [main.py:L31-L36](file:///d:/CodeLore/targets/Naive_RAG/main.py#L31-L36), [indexer.py:L26-L27](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L26-L27), [query_pipeline.py:L23-L24](file:///d:/CodeLore/targets/Naive_RAG/query_pipeline.py#L23-L24), [vector_store.py:L22](file:///d:/CodeLore/targets/Naive_RAG/vector_store.py#L22).
2. **Question**: *What are the 8 architectural stages of the RAG pipeline described in Naive_RAG?*
   - **Expected Worker**: Architecture Mapper
   - **Expected Answer Facts**: Stage 1: Document Ingestion, Stage 2: Chunking, Stage 3: Embedding Generation, Stage 4: Storage, Stage 5: Live Query Embedding, Stage 6: Vector Retrieval, Stage 7: Context Augmentation, Stage 8: Grounded Generation.
   - **Evidence**: [main.py:L99-L102](file:///d:/CodeLore/targets/Naive_RAG/main.py#L99-L102), [Day4_Naive_RAG_Project_Build_Spec.md:L24-L37](file:///d:/CodeLore/targets/Naive_RAG/Day4_Naive_RAG_Project_Build_Spec.md#L24-L37).

### Category 2: Code Searcher
3. **Question**: *Where is the default Pinecone index name defined, and what is its value?*
   - **Expected Worker**: Code Searcher
   - **Expected Answer Facts**: Defined in `config.py` on line 105 as `os.getenv("PINECONE_INDEX_NAME", "naive-rag-demo")`.
   - **Evidence**: [config.py:L105](file:///d:/CodeLore/targets/Naive_RAG/config.py#L105).
4. **Question**: *What chunk size and chunk overlap values are used by default when chunking documents?*
   - **Expected Worker**: Code Searcher
   - **Expected Answer Facts**: `chunk_size = 500` characters and `chunk_overlap = 100` characters.
   - **Evidence**: [config.py:L110-L115](file:///d:/CodeLore/targets/Naive_RAG/config.py#L110-L115), [indexer.py:L55-L66](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L55-L66).
5. **Question**: *Where is Redis configured or connected in this repository?*
   - **Expected Worker**: Code Searcher
   - **Expected Answer Facts**: Not found in this codebase. The repository contains no Redis client or connection configuration.
   - **Evidence**: Verified codebase search across all repository files.

### Category 3: Code Explainer
6. **Question**: *How does `chunk_document` in `indexer.py` partition text, and what metadata does each chunk receive?*
   - **Expected Worker**: Code Explainer
   - **Expected Answer Facts**: Uses a character-sliding window starting at index `0` and advancing by `step = chunk_size - chunk_overlap`. Strips each slice and appends a dictionary with keys `"id"` (formatted as `chunk-0001`), `"text"`, `"start_char"`, `"end_char"`, and `"char_count"`.
   - **Evidence**: [indexer.py:L55-L111](file:///d:/CodeLore/targets/Naive_RAG/indexer.py#L55-L111).
7. **Question**: *What happens when `upsert_to_vector_db` in `vector_store.py` falls back to local storage?*
   - **Expected Worker**: Code Explainer
   - **Expected Answer Facts**: It iterates through the chunks, builds records with `"id"`, `"embedding"`, and `"metadata"` (containing `"text"` and `"chunk_id"`), and writes them to `data/local_vector_db.json` by opening the file in `"w"` mode, completely replacing existing contents with `json.dump()`.
   - **Evidence**: [vector_store.py:L144-L162](file:///d:/CodeLore/targets/Naive_RAG/vector_store.py#L144-L162).
8. **Question**: *How does `query_vector_db` compute similarity when running in local offline mode?*
   - **Expected Worker**: Code Explainer
   - **Expected Answer Facts**: Loads all records from `data/local_vector_db.json`, computes cosine similarity between the query vector and candidate vector using `calculate_cosine_similarity()`, sorts results descending by score, and slices the top `top_k` matches.
   - **Evidence**: [vector_store.py:L199-L233](file:///d:/CodeLore/targets/Naive_RAG/vector_store.py#L199-L233).
9. **Question**: *Where is the Slack webhook notification dispatched after indexing finishes?*
   - **Expected Worker**: Code Explainer
   - **Expected Answer Facts**: Not found in this codebase. There is no Slack webhook integration or notification dispatcher implemented in `targets/Naive_RAG`.
   - **Evidence**: Verified codebase search across all repository files.

### Category 4: Onboarding Guide
10. **Question**: *How do I run the full side-by-side comparison demo from the command line?*
    - **Expected Worker**: Onboarding Guide
    - **Expected Answer Facts**: Run `python main.py` for the complete default walkthrough, or `python main.py --compare` to execute only the baseline vs RAG comparison scorecard.
    - **Evidence**: [main.py:L149-L152](file:///d:/CodeLore/targets/Naive_RAG/main.py#L149-L152), [main.py:L170-L180](file:///d:/CodeLore/targets/Naive_RAG/main.py#L170-L180).
11. **Question**: *How can I run this project without real API keys or internet access?*
    - **Expected Worker**: Onboarding Guide
    - **Expected Answer Facts**: Execute `python main.py --mock`. This forces `force_mock_ai=True`, using deterministic offline 64-dimensional embeddings, mock LLM answers, and `data/local_vector_db.json`.
    - **Evidence**: [main.py:L154-L160](file:///d:/CodeLore/targets/Naive_RAG/main.py#L154-L160), [config.py:L127-L128](file:///d:/CodeLore/targets/Naive_RAG/config.py#L127-L128).

### Category 5: Off-Topic Handling
12. **Question**: *Can you write me a recipe for chocolate chip cookies?*
    - **Expected Worker**: Code Helper (Boss Agent filter / router)
    - **Expected Answer Facts**: Refuse or politely redirect. The Code Helper is strictly scoped to answering questions about and analyzing the `targets/Naive_RAG` codebase.
    - **Evidence**: Assignment scope specification and safety guidelines.

---

## i. Appendix: Full Real Output of `scripts/outline_target.py`

```text
==================================================
File: config.py
==================================================
  L15-L15: from dataclasses import dataclass
  L16-L16: import os
  L17-L17: from pathlib import Path
  L18-L18: from dotenv import load_dotenv
  L21-L53: def load_environment_variables()
  L61-L77: class RAGConfig
  L80-L154: def get_rag_config(force_mock_ai, force_local_db)

==================================================
File: indexer.py
==================================================
  L22-L22: import math
  L23-L23: import os
  L24-L24: from pathlib import Path
  L25-L25: from openai import OpenAI
  L26-L26: from config import RAGConfig, get_rag_config
  L27-L27: from vector_store import upsert_to_vector_db
  L30-L52: def load_document(file_path)
  L55-L111: def chunk_document(text, chunk_size, chunk_overlap)
  L114-L195: def embed_chunks(chunks, config)
  L198-L221: def store_in_vector_db(chunks_with_embeddings, config)
  L224-L268: def run_indexing_pipeline(file_path, config)

==================================================
File: main.py
==================================================
  L28-L28: import argparse
  L29-L29: import sys
  L30-L30: from pathlib import Path
  L31-L31: from config import RAGConfig, get_rag_config
  L32-L32: from indexer import run_indexing_pipeline
  L33-L36: from query_pipeline import generate_answer_without_rag, run_query_pipeline
  L45-L52: def print_banner(title)
  L55-L90: def print_scorecard(query, raw_answer, rag_answer, chunks)
  L93-L127: def run_full_demo(config)
  L130-L180: def main()

==================================================
File: query_pipeline.py
==================================================
  L21-L21: import math
  L22-L22: from openai import OpenAI
  L23-L23: from config import RAGConfig, get_rag_config
  L24-L24: from vector_store import query_vector_db
  L27-L86: def embed_query(query, config)
  L89-L126: def retrieve_top_k(query_vector, config)
  L129-L176: def build_prompt_with_context(query, retrieved_chunks)
  L179-L240: def generate_answer(prompt, config)
  L243-L309: def generate_answer_without_rag(query, config)
  L312-L358: def run_query_pipeline(query, config)

==================================================
File: vector_store.py
==================================================
  L17-L17: import json
  L18-L18: import math
  L19-L19: import os
  L20-L20: from pathlib import Path
  L21-L21: from pinecone import Pinecone, ServerlessSpec
  L22-L22: from config import RAGConfig
  L28-L59: def calculate_cosine_similarity(vec_a, vec_b)
  L62-L66: def get_pinecone_client(api_key)
  L69-L94: def ensure_pinecone_index_exists(client, index_name, dimension, cloud, region)
  L97-L162: def upsert_to_vector_db(chunks_with_embeddings, config)
  L165-L233: def query_vector_db(query_vector, top_k, config)
```
