"""
Re-run script for EVAL_01, EVAL_02, EVAL_05 only (AFTER FIX, same questions, not a clean test).
Timeout: 300s per question. Never repeats.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.genai import types
from google.adk.runners import Runner, RunConfig
from google.adk.sessions import InMemorySessionService
from code_helper.agent import root_agent
from scripts.verify_routing_answers import verify_routing_answer


TARGET_IDS = ["EVAL_01", "EVAL_02", "EVAL_05"]


async def run_single_question(runner: Runner, question_item: dict, timeout_seconds: int = 300) -> dict:
    q_id = question_item["id"]
    q_text = question_item["question"]
    exp_worker = question_item["expected_worker"]
    q_type = question_item.get("type", "")

    print(f"\n{'='*70}", flush=True)
    print(f"[{q_id}] ({q_type}) Expected: {exp_worker}", flush=True)
    print(f"Question: {q_text}", flush=True)
    print(f"{'='*70}", flush=True)

    ordered_tools = []
    raw_tool_outputs = []
    final_answer = ""
    actual_worker = "boss"
    model_calls = 0
    t0 = time.time()

    async def _execute_turn():
        nonlocal ordered_tools, raw_tool_outputs, final_answer, actual_worker, model_calls
        session_id = f"fix_eval_sess_{q_id}_{int(time.time()*1000)}"
        new_msg = types.Content(parts=[types.Part.from_text(text=q_text)])

        async for event in runner.run_async(
            user_id="user",
            session_id=session_id,
            new_message=new_msg,
            run_config=RunConfig(max_llm_calls=15),
        ):
            if event.author != "user":
                has_fc = bool(event.get_function_calls())
                has_text = bool(event.content and any(p.text for p in event.content.parts if p.text))
                has_tool_res = bool(event.get_function_responses())
                if (has_fc or has_text) and not has_tool_res:
                    model_calls += 1

            for fc in event.get_function_calls():
                ordered_tools.append(fc.name)
                print(f"  [Tool Call]: {fc.name}({fc.args})", flush=True)

            for fr in event.get_function_responses():
                if fr.response:
                    resp_str = str(fr.response)
                    raw_tool_outputs.append(resp_str)
                    print(f"  [Tool Result]: {resp_str[:150]}...", flush=True)

            if event.is_final_response():
                if event.author != "user" and event.author != "boss":
                    actual_worker = event.author
                if event.content and event.content.parts:
                    for p in event.content.parts:
                        if p.text:
                            final_answer += p.text

    try:
        await asyncio.wait_for(_execute_turn(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        print(f"\n[TIMEOUT]: Question {q_id} timed out after {timeout_seconds}s", flush=True)
        final_answer = "TIMEOUT"
    except Exception as e:
        print(f"\n[EXCEPTION]: {e}", flush=True)
        final_answer = f"[ERROR]: {e}"

    duration = time.time() - t0

    if not final_answer.strip() and raw_tool_outputs:
        for ro in reversed(raw_tool_outputs):
            if ro.strip():
                final_answer = ro.strip()
                break

    routing_pass = (actual_worker == exp_worker)

    category_map = {
        "searcher_default_value": "Code Searcher",
        "searcher_where_defined": "Code Searcher",
        "mapper_who_imports": "Architecture",
    }
    cat = category_map.get(q_type, "Code Searcher")

    checker_res = verify_routing_answer(
        question_id=q_id,
        question_text=q_text,
        category=cat,
        answer_text=final_answer,
        tool_outputs=raw_tool_outputs,
    )

    has_valid_citations = len(checker_res.get("valid_citations", [])) > 0
    no_invalid = len(checker_res.get("invalid_citations", [])) == 0
    grounding_pass = has_valid_citations and no_invalid

    record = {
        "id": q_id,
        "type": q_type,
        "question": q_text,
        "expected_worker": exp_worker,
        "actual_worker": actual_worker,
        "routing_pass": routing_pass,
        "ordered_tools": ordered_tools,
        "model_calls": model_calls,
        "duration": round(duration, 2),
        "grounding_pass": grounding_pass,
        "strict_checker": checker_res,
        "final_answer": final_answer,
    }

    print(f"\nResult for {q_id}:", flush=True)
    print(f"  Worker: {actual_worker} (Routing: {routing_pass})", flush=True)
    print(f"  Tools: {ordered_tools}", flush=True)
    print(f"  Model Calls: {model_calls} | Time: {duration:.2f}s | Grounding: {grounding_pass}", flush=True)
    print(f"  Valid Citations: {checker_res.get('valid_citations', [])}", flush=True)
    print(f"  Invalid Citations: {checker_res.get('invalid_citations', [])}", flush=True)
    print(f"  Errors: {checker_res.get('errors', [])}", flush=True)
    print(f"  Final Answer:\n{final_answer.strip()}\n", flush=True)

    return record


async def main():
    questions_file = PROJECT_ROOT / "tests" / "eval_questions.json"
    with open(questions_file, "r", encoding="utf-8") as f:
        all_questions = json.load(f)

    questions = [q for q in all_questions if q["id"] in TARGET_IDS]

    eval_dir = PROJECT_ROOT / "eval_runs"
    eval_dir.mkdir(parents=True, exist_ok=True)
    report_path = eval_dir / "re_eval_after_fix.md"

    print(f"Running AFTER FIX re-evaluation on {len(questions)} questions...", flush=True)

    runner = Runner(
        agent=root_agent,
        app_name="code_helper",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    records = []
    report_path = eval_dir / "re_eval_after_fix_2.md"
    json_path = eval_dir / "re_eval_after_fix_2.json"

    def _save_current_reports():
        json_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
        lines = [
            "# Re-evaluation Report (AFTER FIX 2, same questions, not a clean test)",
            "",
            f"- **Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "- **Note**: Re-run of diagnostic questions EVAL_01, EVAL_02, EVAL_05 only.",
            "",
            "## Summary Results Table (AFTER FIX 2, same questions, not a clean test)",
            "",
            "| ID | Question | Expected Worker | Actual Worker | Routing | Tools Called | Calls | Time (s) | Grounding | Checker Status |",
            "| :--- | :--- | :--- | :--- | :---: | :--- | :---: | :---: | :---: | :--- |",
        ]
        for r in records:
            short_q = r["question"][:50] + "..." if len(r["question"]) > 50 else r["question"]
            tools_str = ", ".join(r["ordered_tools"])
            g_pass = "PASS" if r["grounding_pass"] else "FAIL"
            c_status = "OK" if r["grounding_pass"] else "; ".join(r["strict_checker"].get("errors", ["Check failed"]))
            lines.append(
                f"| {r['id']} | {short_q} | `{r['expected_worker']}` | `{r['actual_worker']}` | {r['routing_pass']} | `{tools_str}` | {r['model_calls']} | {r['duration']} | {g_pass} | {c_status} |"
            )
        lines.extend([
            "",
            "## Detailed Question Responses & Checker Outputs",
            "",
        ])
        for r in records:
            lines.extend([
                f"### Question `{r['id']}`: {r['question']}",
                f"- **Expected Worker**: `{r['expected_worker']}` | **Actual Worker**: `{r['actual_worker']}`",
                f"- **Tools Called**: `{r['ordered_tools']}` | **Model Calls**: {r['model_calls']} | **Time**: {r['duration']}s",
                f"- **Routing Pass**: {r['routing_pass']} | **Grounding Pass**: {r['grounding_pass']}",
                f"- **Strict Checker Output**:",
                f"  - Valid Citations: `{r['strict_checker'].get('valid_citations', [])}`",
                f"  - Invalid Citations: `{r['strict_checker'].get('invalid_citations', [])}`",
                f"  - Errors: `{r['strict_checker'].get('errors', [])}`",
                "",
                "**Full Final Answer**:",
                "```text",
                r["final_answer"].strip(),
                "```",
                "",
                "---",
                "",
            ])
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    for q_item in questions:
        res = await run_single_question(runner, q_item, timeout_seconds=300)
        records.append(res)
        _save_current_reports()
        print(f"Results saved after {q_item['id']} to {report_path}", flush=True)
        await asyncio.sleep(2.0)

    print(f"\nFinal report written to: {report_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
