"""
Google ADK Agent Team Definition for CodeLore.
Defines one shared LiteLlm model, 4 specialized workers, and 1 Boss (root_agent) for routing.
"""
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from google.genai import types
from code_helper.settings import load_settings
from code_helper.tools.search_tools import rag_search, find_symbol
from code_helper.tools.explain_tools import get_file_outline, show_file_outline
from code_helper.tools.architecture_tools import analyze_imports
from code_helper.tools.onboarding_tools import get_project_overview
from code_helper.mcp_config import build_filesystem_toolset
from code_helper import prompts

# Load settings (respecting runtime environment variables or code_helper/.env)
_settings = load_settings()

# Single shared model configured via LiteLlm for NVIDIA NIM
shared_model = LiteLlm(
    model=f"nvidia_nim/{_settings.nvidia_chat_model}",
    api_base=_settings.nvidia_base_url,
    temperature=0.1,
    timeout=90,
    num_retries=1,
)


import json
import re
from typing import Any


def loop_guard_before_tool_callback(tool: Any, args: dict[str, Any], tool_context: Any) -> dict[str, Any] | None:
    """Loop guard callback to block excessive tool repetition within an invocation."""
    if tool_context is None or not hasattr(tool_context, "state") or tool_context.state is None:
        return None

    state = tool_context.state
    tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))
    args_repr = json.dumps(args, sort_keys=True, default=str) if isinstance(args, dict) else str(args)

    raw_history = state.get("temp:tool_calls")
    history: list[tuple[str, str]] = list(raw_history) if isinstance(raw_history, list) else []

    same_tool_count = sum(1 for (t, _) in history if t == tool_name)
    identical_call_count = sum(1 for (t, a) in history if t == tool_name and a == args_repr)

    # Block 3rd call of the same tool (already called 2 times) or 2nd identical call (already called 1 time)
    if same_tool_count >= 2 or identical_call_count >= 1:
        return {
            "result": "STOP: tool limit reached. Do NOT call any more tools. Write your final answer now from the results you already have. If nothing relevant was found, answer exactly: I could not find that in this codebase."
        }

    history.append((tool_name, args_repr))
    try:
        state["temp:tool_calls"] = history
    except Exception:
        pass

    return None


from google.adk.models.llm_response import LlmResponse


def codelore_after_model_callback(callback_context: Any, llm_response: LlmResponse) -> LlmResponse | None:
    """Callback after model call to remove 'Verified from code:' label if response contains 'could not find'."""
    if llm_response and llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if part.text and "could not find" in part.text and "Verified from code:" in part.text:
                cleaned = re.sub(r"^\s*Verified from code:\s*", "", part.text, flags=re.IGNORECASE).strip()
                cleaned = re.sub(r"Verified from code:\s*", "", cleaned, flags=re.IGNORECASE).strip()
                part.text = cleaned
                return llm_response
    return None


def codelore_after_agent_callback(callback_context) -> types.Content | None:
    """Callback for CodeLore agents to deliver final texts and explain-mode citation footers."""
    state = callback_context.state
    # 1. Final text mode: show_file_outline, find_symbol, analyze_imports, or get_project_overview stored temp:final_text
    if state.get("temp:final_text"):
        final_text = state["temp:final_text"]
        state["temp:final_text"] = None
        if "could not find" in final_text:
            final_text = re.sub(r"^\s*Verified from code:\s*", "", final_text, flags=re.IGNORECASE).strip()
            final_text = re.sub(r"Verified from code:\s*", "", final_text, flags=re.IGNORECASE).strip()
        return types.Content(role="model", parts=[types.Part.from_text(text=final_text)])

    # 2. Explain mode footer: check symbols from get_file_outline
    symbol_ranges = state.get("temp:symbol_ranges")
    if symbol_ranges:
        state["temp:symbol_ranges"] = None
        matched = []
        events = getattr(callback_context.session, "events", []) if hasattr(callback_context, "session") else []
        last_text = ""
        current_agent = getattr(callback_context, "agent_name", None)
        for ev in reversed(events):
            if current_agent and ev.author != current_agent:
                continue
            if ev.content and ev.content.parts:
                for p in ev.content.parts:
                    if p.text:
                        last_text = p.text
                        break
                if last_text:
                    break

        if last_text:
            for sym, loc in symbol_ranges.items():
                if sym in last_text:
                    matched.append(f"{sym} -> {loc}")
                if len(matched) >= 5:
                    break
            if matched:
                footer = "\nSources (from tool results): " + ", ".join(matched)
                return types.Content(role="model", parts=[types.Part.from_text(text=footer)])

    return None


# Backward-compatible alias
explainer_after_agent_callback = codelore_after_agent_callback


# 1. Code Searcher Worker
code_searcher = LlmAgent(
    name="code_searcher",
    model=shared_model,
    description=prompts.CODE_SEARCHER_DESCRIPTION,
    instruction=prompts.CODE_SEARCHER_INSTRUCTION,
    tools=[rag_search, find_symbol],
    before_tool_callback=loop_guard_before_tool_callback,
    after_model_callback=codelore_after_model_callback,
    after_agent_callback=codelore_after_agent_callback,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

# 2. Code Explainer Worker
code_explainer = LlmAgent(
    name="code_explainer",
    model=shared_model,
    description=prompts.CODE_EXPLAINER_DESCRIPTION,
    instruction=prompts.CODE_EXPLAINER_INSTRUCTION,
    tools=[get_file_outline, show_file_outline, build_filesystem_toolset(_settings)],
    after_model_callback=codelore_after_model_callback,
    after_agent_callback=codelore_after_agent_callback,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

# 3. Architecture Mapper Worker
architecture_mapper = LlmAgent(
    name="architecture_mapper",
    model=shared_model,
    description=prompts.ARCHITECTURE_MAPPER_DESCRIPTION,
    instruction=prompts.ARCHITECTURE_MAPPER_INSTRUCTION,
    tools=[analyze_imports],
    before_tool_callback=loop_guard_before_tool_callback,
    after_model_callback=codelore_after_model_callback,
    after_agent_callback=codelore_after_agent_callback,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

# 4. Onboarding Guide Worker
onboarding_guide = LlmAgent(
    name="onboarding_guide",
    model=shared_model,
    description=prompts.ONBOARDING_GUIDE_DESCRIPTION,
    instruction=prompts.ONBOARDING_GUIDE_INSTRUCTION,
    tools=[get_project_overview],
    before_tool_callback=loop_guard_before_tool_callback,
    after_model_callback=codelore_after_model_callback,
    after_agent_callback=codelore_after_agent_callback,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

# Root Agent: Boss (Routing Only)
root_agent = LlmAgent(
    name="boss",
    model=shared_model,
    description=prompts.BOSS_DESCRIPTION,
    instruction=prompts.BOSS_INSTRUCTION,
    tools=[],
    sub_agents=[
        code_searcher,
        code_explainer,
        architecture_mapper,
        onboarding_guide,
    ],
)
