"""
Live routing evaluation test suite for CodeLore agent hierarchy.
Executes 8 held-out evaluation questions from docs/target_analysis.md via Runner.
Records:
- Target question and category
- Expected worker vs actual worker (final answer author)
- Full final answer text
- Whether is_final_response was reached vs stopped at max_llm_calls
- Ordered list of tool calls (list, preserving order and duplicates)
- Number of 429/retry events seen
- Number of actual model calls (events with model responses)
- Duration in seconds
- Automated checks: citation validity in Naive_RAG, tool grounding, not-found phrase check, and off-topic cleanliness.
Writes full markdown summary table to eval_runs/routing_eval_<timestamp>.md.
"""
import os
import time
from datetime import datetime
from pathlib import Path
import pytest
from google.genai import types
from google.adk.runners import Runner, RunConfig
from google.adk.sessions import InMemorySessionService
from scripts.verify_routing_answers import verify_routing_answer

# 8 held-out evaluation questions (disjoint from Boss instruction examples)
ROUTING_TEST_CASES = [
    {
        "id": "Q1",
        "question": "What are the 8 architectural stages of the RAG pipeline described in Naive_RAG?",
        "expected_worker": "architecture_mapper",
        "category": "Architecture",
    },
    {
        "id": "Q2",
        "question": "What chunk size and chunk overlap values are used by default when chunking documents?",
        "expected_worker": "code_searcher",
        "category": "Code Search",
    },
    {
        "id": "Q3",
        "question": "Where is Postgres or SQLAlchemy configured in this repository?",
        "expected_worker": "code_searcher",
        "category": "Code Search (Not Found)",
    },
    {
        "id": "Q4",
        "question": "What happens when upsert_to_vector_db in vector_store.py falls back to local storage?",
        "expected_worker": "code_explainer",
        "category": "Code Explainer",
    },
    {
        "id": "Q5",
        "question": "Where is Celery or RabbitMQ configured for background tasks in this codebase?",
        "expected_worker": "code_searcher",
        "category": "Code Search (Not Found)",
    },
    {
        "id": "Q6",
        "question": "How can I run this project without real API keys or internet access?",
        "expected_worker": "onboarding_guide",
        "category": "Onboarding",
    },
    {
        "id": "Q7",
        "question": "What are the CLI flags supported by main.py and what do they do?",
        "expected_worker": "onboarding_guide",
        "category": "Onboarding",
    },
    {
        "id": "Q8",
        "question": "What is the current weather forecast for Tokyo today?",
        "expected_worker": "onboarding_guide",
        "category": "Off-topic fallback",
    },
]


@pytest.mark.live
def test_live_routing_suite():
    if os.getenv("RUN_LIVE") != "1":
        pytest.skip("RUN_LIVE=1 not set. Skipping live routing test suite.")

    from code_helper.agent import root_agent

    runner = Runner(
        agent=root_agent,
        app_name="code_helper",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )
    eval_dir = Path("eval_runs")
    eval_dir.mkdir(exist_ok=True)

    results = []

    print("\n--- Starting Live Held-Out Agent Routing Evaluation Suite (8 questions) ---", flush=True)

    for i, tc in enumerate(ROUTING_TEST_CASES, start=1):
        q = tc["question"]
        expected = tc["expected_worker"]
        session_id = f"eval_session_{tc['id']}_{int(time.time())}"

        print(f"\n[{i}/8] Testing {tc['id']} ({tc['category']}) -> {q[:60]}...", flush=True)
        t_start = time.time()

        events = []
        actual_worker = None
        final_answer = ""
        ordered_tools_called = []
        raw_tool_outputs = []
        model_calls = 0
        retry_count = 0
        reached_final_response = False
        err_msg = ""

        try:
            run_cfg = RunConfig(max_llm_calls=8)
            for event in runner.run(
                user_id="evaluator",
                session_id=session_id,
                new_message=types.Content(parts=[types.Part.from_text(text=q)]),
                run_config=run_cfg,
            ):
                events.append(event)

                # Count model calls (agent events with model response content, excluding tool outputs)
                is_agent = bool(event.author and event.author != "user")
                has_tool_result = bool(event.get_function_responses())
                has_model_response = bool(
                    event.content
                    and event.content.parts
                    and any(p.text or p.function_call for p in event.content.parts)
                    and not has_tool_result
                )
                if is_agent and has_model_response:
                    model_calls += 1

                # Track 429 rate limit or retry signals
                if event.error_code == 429 or (event.error_message and "429" in str(event.error_message)):
                    retry_count += 1

                # Record ordered list of tool calls
                for fc in event.get_function_calls():
                    ordered_tools_called.append(fc.name)

                # Capture raw tool output text for grounding verification
                for fr in event.get_function_responses():
                    if fr.response:
                        raw_tool_outputs.append(str(fr.response))

                # Check if final response reached
                if event.is_final_response():
                    reached_final_response = True
                    if event.author != "user" and event.author != "boss":
                        actual_worker = event.author
                    if event.content and event.content.parts:
                        for p in event.content.parts:
                            if p.text:
                                final_answer += p.text
        except Exception as ex:
            err_msg = str(ex)
            if "Max number of llm calls" in err_msg or "LlmCallsLimitExceededError" in err_msg:
                final_answer = "CAP HIT"
                reached_final_response = False
            if "429" in err_msg:
                retry_count += 1
            print(f"       [EXCEPTION] {err_msg[:100]}", flush=True)

        if not reached_final_response and not final_answer:
            final_answer = "CAP HIT"

        duration = time.time() - t_start

        # Automated grounding and citation verification
        check_res = verify_routing_answer(
            question_id=tc["id"],
            question_text=q,
            category=tc["category"],
            answer_text=final_answer,
            tool_outputs=raw_tool_outputs,
        )

        # Worker routing correctness check
        worker_matched = (actual_worker == expected)
        boss_answered = any(
            e.author == "boss" and e.is_final_response() and e.content and any(p.text for p in e.content.parts)
            for e in events
        )
        passed = worker_matched and not boss_answered and reached_final_response

        status_tag = "PASS" if passed else "FAIL"
        print(f"       -> {status_tag}: actual={actual_worker} (expected={expected}), tools={ordered_tools_called}, calls={model_calls}, final_resp={reached_final_response}, retries={retry_count}, time={duration:.2f}s", flush=True)

        results.append({
            "id": tc["id"],
            "question": q,
            "category": tc["category"],
            "expected": expected,
            "actual": actual_worker or ("error" if err_msg else "none"),
            "tools": ordered_tools_called,
            "model_calls": model_calls,
            "retry_count": retry_count,
            "reached_final_response": reached_final_response,
            "duration": round(duration, 2),
            "boss_answered": boss_answered,
            "passed": passed,
            "final_answer": final_answer,
            "verification": check_res,
            "error_msg": err_msg,
        })

        # Small pause between questions to respect free-tier rate limits
        time.sleep(3.0)

    # Write comprehensive markdown summary report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = eval_dir / f"routing_eval_{timestamp}.md"

    total_passed = sum(1 for r in results if r["passed"])

    md_lines = [
        f"# Live Held-Out Routing Evaluation Report - {timestamp}",
        "",
        f"**Total Cases**: {len(results)} | **Passed**: {total_passed}/{len(results)}",
        "",
        "| ID | Question | Expected Worker | Actual Worker | Ordered Tools Called | Calls | Final? | 429s | Time (s) | Result |",
        "| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        tools_str = ", ".join(r["tools"]) if r["tools"] else "None"
        md_lines.append(
            f"| {r['id']} | {r['question'][:40]}... | `{r['expected']}` | `{r['actual']}` | `{tools_str}` | {r['model_calls']} | {r['reached_final_response']} | {r['retry_count']} | {r['duration']}s | {status} |"
        )

    md_lines.append("\n## Full Answers and Grounding Verification\n")
    for r in results:
        v = r["verification"]
        md_lines.append(f"### {r['id']}: {r['question']}")
        md_lines.append(f"- **Category**: {r['category']}")
        md_lines.append(f"- **Worker**: `{r['actual']}` (Expected: `{r['expected']}`)")
        md_lines.append(f"- **Ordered Tools**: `{r['tools']}`")
        md_lines.append(f"- **Reached Final Response**: `{r['reached_final_response']}`")
        md_lines.append(f"- **Boss Answered Directly**: `{r['boss_answered']}`")
        md_lines.append(f"- **Duration**: {r['duration']}s | **Model Calls**: {r['model_calls']} | **429 Retries**: {r['retry_count']}")
        md_lines.append(f"- **Valid Citations**: `{v['valid_citations']}`")
        if v["invalid_citations"]:
            md_lines.append(f"- **Invalid Citations**: `{v['invalid_citations']}`")
        if v["unsupported_files"]:
            md_lines.append(f"- **Unsupported Files Mentioned**: `{v['unsupported_files']}`")
        if v["not_found_valid"] is not None:
            md_lines.append(f"- **Not-Found Phrase Valid**: `{v['not_found_valid']}`")
        if v["off_topic_clean"] is not None:
            md_lines.append(f"- **Off-Topic Clean**: `{v['off_topic_clean']}`")
        md_lines.append(f"\n**Final Answer Text**:\n```\n{r['final_answer'] or r['error_msg']}\n```\n")

    report_file.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nWritten routing evaluation report to: {report_file}")

    assert total_passed >= 7, f"Routing target is at least 7/8, got {total_passed}/8"
