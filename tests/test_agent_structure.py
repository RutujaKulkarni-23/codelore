from pathlib import Path
"""
Offline structural tests for Google ADK agent architecture in CodeLore.
Validates:
- Exactly 1 root agent and 4 sub-agents with unique names
- Boss has NO tools
- Each worker has at least one tool
- Tool assignment matches least-privilege matrix
- Workers cannot transfer to parent or peers (disallow flags set)
- Instructions enforce 'NOT FOUND', 'Verified from code', and citation rules
- Custom tool count >= 5 and at least one non-AI tool
"""
import pytest
from code_helper.agent import (
    root_agent,
    code_searcher,
    code_explainer,
    architecture_mapper,
    onboarding_guide,
)
from code_helper.tools.search_tools import rag_search, find_symbol
from code_helper.tools.explain_tools import get_file_outline
from code_helper.tools.architecture_tools import analyze_imports
from code_helper.tools.onboarding_tools import get_project_overview


def test_agent_hierarchy_and_unique_names():
    assert root_agent is not None
    assert root_agent.name == "boss"
    assert len(root_agent.sub_agents) == 4

    sub_agent_names = [agent.name for agent in root_agent.sub_agents]
    expected_names = [
        "code_searcher",
        "code_explainer",
        "architecture_mapper",
        "onboarding_guide",
    ]
    assert sorted(sub_agent_names) == sorted(expected_names)
    assert len(sub_agent_names) == len(set(sub_agent_names)), "Agent names must be unique"


def test_boss_has_no_tools():
    assert len(root_agent.tools) == 0, "The Boss must have no tools (routing only)"


def test_least_privilege_tool_assignments():
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

    # code_searcher: rag_search, find_symbol
    assert code_searcher.tools == [rag_search, find_symbol]

    # code_explainer: get_file_outline, show_file_outline plus MCP toolset
    from code_helper.tools.explain_tools import show_file_outline
    assert len(code_explainer.tools) == 3
    assert code_explainer.tools[0] == get_file_outline
    assert code_explainer.tools[1] == show_file_outline
    assert isinstance(code_explainer.tools[2], McpToolset)

    # architecture_mapper: analyze_imports
    assert architecture_mapper.tools == [analyze_imports]

    # onboarding_guide: get_project_overview
    assert onboarding_guide.tools == [get_project_overview]


def test_workers_disallow_transfer_flags():
    workers = [code_searcher, code_explainer, architecture_mapper, onboarding_guide]
    for w in workers:
        assert w.disallow_transfer_to_parent is True, f"{w.name} must disallow transfer to parent"
        assert w.disallow_transfer_to_peers is True, f"{w.name} must disallow transfer to peers"


def test_worker_instructions_contain_required_rules():
    workers = [code_searcher, code_explainer, architecture_mapper, onboarding_guide]
    for w in workers:
        inst = w.instruction if isinstance(w.instruction, str) else ""
        assert "Verified from code" in inst, f"{w.name} instruction missing 'Verified from code'"
        assert "General knowledge (not verified)" in inst, f"{w.name} instruction missing 'General knowledge (not verified)'"
        assert "I could not find that in this codebase" in inst or "NOT FOUND" in inst, f"{w.name} instruction missing not found rule"
        assert "path:start-end" in inst, f"{w.name} instruction missing citation rule"


def test_boss_instruction_routing_rules():
    inst = root_agent.instruction if isinstance(root_agent.instruction, str) else ""
    assert "You are a router" in inst
    assert "You never answer the question yourself" in inst
    assert "code_searcher" in inst
    assert "code_explainer" in inst
    assert "architecture_mapper" in inst
    assert "onboarding_guide" in inst


def test_custom_tools_count_and_non_ai():
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

    # The 6 custom project tools (excluding MCP toolset)
    worker_lists = [
        code_searcher.tools,
        code_explainer.tools,
        architecture_mapper.tools,
        onboarding_guide.tools,
    ]
    custom_tools = [
        tool for tools in worker_lists for tool in tools if not isinstance(tool, McpToolset)
    ]
    assert len(custom_tools) == 6, f"Expected 6 custom tools, got {len(custom_tools)}"
    # Exactly one worker per custom tool (no shared tools)
    assert len(custom_tools) == len(set(custom_tools)), "Each custom tool must be used by exactly one worker"

    # Non-AI deterministic custom tools
    from code_helper.tools.explain_tools import show_file_outline
    non_ai_tools = [analyze_imports, find_symbol, get_file_outline, show_file_outline, get_project_overview]
    assert any(tool in custom_tools for tool in non_ai_tools)

def test_prompts_loop_limits_and_honest_label():
    from code_helper import prompts
    common = prompts.COMMON_WORKER_RULES
    assert "at most 3 times" in common, "COMMON_WORKER_RULES must contain 'at most 3 times' loop limit"
    assert "Never put 'I could not find that'" in common, "COMMON_WORKER_RULES must contain honest-label rule"


def test_no_not_found_terms_in_prompts():
    prompts_path = Path(__file__).resolve().parent.parent / "code_helper" / "prompts.py"
    prompts_text = prompts_path.read_text(encoding="utf-8")
    forbidden = ["Redis", "Slack", "Postgres", "Celery", "RabbitMQ"]
    for term in forbidden:
        assert term.lower() not in prompts_text.lower(), f"Forbidden target test term '{term}' leaked into prompts.py"



def test_explainer_instruction_rules():
    inst = code_explainer.instruction if isinstance(code_explainer.instruction, str) else ""
    assert "WITHOUT line numbers" in inst, "code_explainer missing 'WITHOUT line numbers' directive"
    assert "get_file_outline" in inst, "code_explainer missing 'get_file_outline' reference"


def test_every_worker_instruction_names_all_tools():
    expected_tools = [
        (code_searcher, ["rag_search", "find_symbol"]),
        (
            code_explainer,
            [
                "show_file_outline",
                "get_file_outline",
                "read_text_file",
                "list_directory",
                "directory_tree",
                "search_files",
                "get_file_info",
            ],
        ),
        (architecture_mapper, ["analyze_imports"]),
        (onboarding_guide, ["get_project_overview"]),
    ]
    for agent, tool_names in expected_tools:
        inst = agent.instruction if isinstance(agent.instruction, str) else ""
        for tool_name in tool_names:
            assert tool_name in inst, f"Agent {agent.name} instruction does not name tool '{tool_name}'"


def test_worker_hardening_against_function_calls():
    from code_helper import prompts
    rules = prompts.COMMON_WORKER_RULES
    assert "The ONLY tools you may call are the ones listed in your instructions" in rules
    assert "Names of functions, classes or variables you see inside code are NOT tools; never call them" in rules
    assert "If a tool call fails with 'not found', do NOT conclude the code is missing" in rules


def test_shared_model_timeout_and_retries():
    from code_helper.agent import shared_model
    assert shared_model._additional_args.get("timeout") == 90
    assert shared_model._additional_args.get("num_retries") == 1


def test_onboarding_instruction_rules():
    from code_helper.prompts import ONBOARDING_GUIDE_INSTRUCTION
    assert "ENTRY POINT" in ONBOARDING_GUIDE_INSTRUCTION
    assert "Never expand acronyms" in ONBOARDING_GUIDE_INSTRUCTION


def test_explainer_explain_mode_rules():
    from code_helper.prompts import CODE_EXPLAINER_INSTRUCTION
    assert "Only describe what the code does" in CODE_EXPLAINER_INSTRUCTION
    assert "No opinions about code quality" in CODE_EXPLAINER_INSTRUCTION
    assert "name (file:start-end): what it does" in CODE_EXPLAINER_INSTRUCTION
