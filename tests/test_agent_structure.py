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
    # code_searcher: rag_search, find_symbol
    assert code_searcher.tools == [rag_search, find_symbol]

    # code_explainer: get_file_outline
    assert code_explainer.tools == [get_file_outline]

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
    all_assigned_tools = (
        code_searcher.tools
        + code_explainer.tools
        + architecture_mapper.tools
        + onboarding_guide.tools
    )
    assert len(all_assigned_tools) >= 5
    # analyze_imports and find_symbol and get_file_outline are deterministic non-AI tools
    non_ai_tools = [analyze_imports, find_symbol, get_file_outline, get_project_overview]
    assert any(tool in all_assigned_tools for tool in non_ai_tools)
