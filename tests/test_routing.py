"""
Live routing evaluation test suite for CodeLore agent hierarchy.
Executes 8 questions from docs/target_analysis.md via Runner, recording:
- Target question
- Expected worker
- Actual worker (final answer author)
- Boss transfer event verification
- Tools called
- Total model calls
- Execution duration in seconds
- Resulting answer excerpt and citations
Writes full markdown summary table to eval_runs/routing_eval_<timestamp>.md.
"""
import os
import time
from datetime import datetime
from pathlib import Path
import pytest
from google.genai import types
from google.adk.runners import InMemoryRunner

# 8 representative evaluation questions selected from docs/target_analysis.md
ROUTING_TEST_CASES = [
    {
        "id": "Q1",
        "question": "What are the top-level module dependencies between the 5 Python files in Naive_RAG?",
        "expected_worker": "architecture_mapper",
        "category": "Architecture",
    },
    {
        "id": "Q2",
        "question": "Where is the default Pinecone index name defined, and what is its value?",
        "expected_worker": "code_searcher",
        "category": "Code Search",
    },
    {
        "id": "Q3",
        "question": "Where is Redis configured or connected in this repository?",
        "expected_worker": "code_searcher",
        "category": "Code Search (Not Found)",
    },
    {
        "id": "Q4",
        "question": "Can you provide an outline of query_pipeline.py and explain what functions it contains?",
        "expected_worker": "code_explainer",
        "category": "Code Explainer",
    },
    {
        "id": "Q5",
        "question": "Where is the Slack webhook notification dispatched after indexing finishes?",
        "expected_worker": "code_searcher",
        "category": "Not Found",
    },
    {
        "id": "Q6",
        "question": "How do I run the full side-by-side comparison demo from the command line?",
        "expected_worker": "onboarding_guide",
        "category": "Onboarding",
    },
    {
        "id": "Q7",
        "question": "How can I run this project without real API keys or internet access?",
        "expected_worker": "onboarding_guide",
        "category": "Onboarding",
    },
    {
        "id": "Q8",
        "question": "Can you write me a recipe for chocolate chip cookies?",
        "expected_worker": "onboarding_guide",
        "category": "Off-topic fallback",
    },
]


@pytest.mark.live
def test_live_routing_suite():
    if os.getenv("RUN_LIVE") != "1":
        pytest.skip("RUN_LIVE=1 not set. Skipping live routing test suite.")

    from code_helper.agent import root_agent

    runner = InMemoryRunner(agent=root_agent)
    eval_dir = Path("eval_runs")
    eval_dir.mkdir(exist_ok=True)

    results = []

    print("\n--- Starting Live Agent Routing Test Suite (8 questions) ---")

    for i, tc in enumerate(ROUTING_TEST_CASES, start=1):
        q = tc["question"]
        expected = tc["expected_worker"]
        session_id = f"eval_session_{tc['id']}_{int(time.time())}"

        print(f"\n[{i}/8] Testing {tc['id']} -> {q[:60]}...")
        t_start = time.time()

        events = []
        actual_worker = None
        final_answer = ""
        tools_called = []
        model_calls = 0

        # Run generator
        for event in runner.run(
            user_id="evaluator",
            session_id=session_id,
            new_message=types.Content(parts=[types.Part.from_text(text=q)]),
        ):
            events.append(event)
            # Count model interactions (events with function calls or text from agent)
            if event.author != "user":
                model_calls += 1

            for fc in event.get_function_calls():
                tools_called.append(fc.name)

            if event.is_final_response():
                if event.author != "user" and event.author != "boss":
                    actual_worker = event.author
                if event.content and event.content.parts:
                    for p in event.content.parts:
                        if p.text:
                            final_answer += p.text

        duration = time.time() - t_start

        # Check if actual worker matches expected
        passed = (actual_worker == expected)
        # Boss must NEVER be the author of final text
        boss_answered = any(
            e.author == "boss" and e.is_final_response() and e.content and any(p.text for p in e.content.parts)
            for e in events
        )

        results.append({
            "id": tc["id"],
            "question": q,
            "expected": expected,
            "actual": actual_worker or "none",
            "tools": list(set(tools_called)),
            "model_calls": model_calls,
            "duration": round(duration, 2),
            "boss_answered": boss_answered,
            "passed": passed and not boss_answered,
            "answer_preview": final_answer.strip().replace("\n", " ")[:150],
        })

        # Small pause between questions to respect free-tier rate limits
        time.sleep(2.0)

    # Write markdown summary report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = eval_dir / f"routing_eval_{timestamp}.md"

    table_rows = []
    total_passed = sum(1 for r in results if r["passed"])

    md_lines = [
        f"# Live Routing Evaluation Report - {timestamp}",
        "",
        f"**Total Cases**: {len(results)} | **Passed**: {total_passed}/{len(results)}",
        "",
        "| ID | Question | Expected Worker | Actual Worker | Tools Called | Calls | Time (s) | Result |",
        "| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :---: |",
    ]

    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        tools_str = ", ".join(r["tools"]) if r["tools"] else "None"
        md_lines.append(
            f"| {r['id']} | {r['question'][:45]}... | `{r['expected']}` | `{r['actual']}` | `{tools_str}` | {r['model_calls']} | {r['duration']}s | {status} |"
        )

    md_lines.append("\n## Answer Summaries\n")
    for r in results:
        md_lines.append(f"### {r['id']}: {r['question']}")
        md_lines.append(f"- **Worker**: `{r['actual']}` (Expected: `{r['expected']}`)")
        md_lines.append(f"- **Tools Called**: `{r['tools']}`")
        md_lines.append(f"- **Boss Answered Directly**: `{r['boss_answered']}`")
        md_lines.append(f"- **Preview**: {r['answer_preview']}...\n")

    report_file.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nWritten routing evaluation report to: {report_file}")

    assert total_passed >= 7, f"Routing target is at least 7/8, got {total_passed}/8"
