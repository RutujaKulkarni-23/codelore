"""
Runner script for executing a single live question through the CodeLore agent team.
Prints:
- Ordered tool calls
- Which agent wrote the final answer
- Whether the MCP read tool was used
- Number of real model calls
- Execution duration in seconds
- Full final answer
"""
import os
import sys
import time
from pathlib import Path

# Ensure RUN_LIVE=1
os.environ["RUN_LIVE"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.runners import Runner, RunConfig
from google.adk.sessions import InMemorySessionService
from google.genai import types
from code_helper.agent import root_agent
from scripts.verify_routing_answers import verify_routing_answer


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_live_question.py \"<question>\"")
        sys.exit(1)

    question = sys.argv[1]
    print(f"=== Running Live Question ===")
    print(f"Question: {question}")
    print("===============================\n")

    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        session_service=session_service,
        app_name="code_helper",
        auto_create_session=True,
    )

    session_id = f"live_{int(time.time())}"
    ordered_tools = []
    raw_tool_outputs = []
    final_worker = "boss"
    final_answer = ""
    model_calls = 0

    t_start = time.time()
    try:
        for event in runner.run(
            user_id="user",
            session_id=session_id,
            new_message=types.Content(parts=[types.Part.from_text(text=question)]),
            run_config=RunConfig(max_llm_calls=8),
        ):
            # Count model interactions (events with function calls or text from agent)
            if event.author != "user":
                has_fc = bool(event.get_function_calls())
                has_text = bool(event.content and any(p.text for p in event.content.parts if p.text))
                has_tool_res = bool(event.get_function_responses())
                if (has_fc or has_text) and not has_tool_res:
                    model_calls += 1

            for fc in event.get_function_calls():
                ordered_tools.append(fc.name)

            for fr in event.get_function_responses():
                if fr.response:
                    raw_tool_outputs.append(str(fr.response))

            if event.is_final_response():
                if event.author != "user" and event.author != "boss":
                    final_worker = event.author
                if event.content and event.content.parts:
                    for p in event.content.parts:
                        if p.text:
                            final_answer += p.text
    except Exception as e:
        print(f"\n[EXCEPTION DURING RUN]: {e}")
        if not final_answer:
            final_answer = f"[ERROR]: {e}"

    # Fallback to function_response if no text exists
    if not final_answer.strip() and raw_tool_outputs:
        for ro in reversed(raw_tool_outputs):
            if ro.strip():
                final_answer = ro.strip()
                break

    # Clean 'Verified from code:' label if answer contains 'could not find'
    import re
    if "could not find" in final_answer:
        final_answer = re.sub(r"^\s*Verified from code:\s*", "", final_answer, flags=re.IGNORECASE).strip()
        final_answer = re.sub(r"Verified from code:\s*", "", final_answer, flags=re.IGNORECASE).strip()

    duration = time.time() - t_start
    mcp_read_used = "read_text_file" in ordered_tools

    print(f"Ordered tools called: {ordered_tools}")
    print(f"Final answering agent: {final_worker}")
    print(f"MCP read tool used (read_text_file): {mcp_read_used}")
    print(f"Number of real model calls: {model_calls}")
    print(f"Duration: {duration:.2f}s")
    print(f"\nFull final answer:\n----------------------------------------\n{final_answer.strip()}\n----------------------------------------")

    checker_res = verify_routing_answer(
        question_id="live_check",
        question_text=question,
        category="Code Explainer",
        answer_text=final_answer,
        tool_outputs=raw_tool_outputs,
    )
    print("\nCitation Checker Result:")
    print(f"  Passed: {checker_res['passed']}")
    print(f"  Valid Citations: {checker_res['valid_citations']}")
    print(f"  Invalid Citations: {checker_res['invalid_citations']}")
    print(f"  Unsupported Files: {checker_res['unsupported_files']}")
    if checker_res['errors']:
        print(f"  Errors: {checker_res['errors']}")


if __name__ == "__main__":
    main()
