"""
Google ADK Agent Team Definition for CodeLore.
Defines one shared LiteLlm model, 4 specialized workers, and 1 Boss (root_agent) for routing.
"""
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

from code_helper.settings import load_settings
from code_helper.tools.search_tools import rag_search, find_symbol
from code_helper.tools.explain_tools import get_file_outline
from code_helper.tools.architecture_tools import analyze_imports
from code_helper.tools.onboarding_tools import get_project_overview
from code_helper import prompts

# Load settings (respecting runtime environment variables or code_helper/.env)
_settings = load_settings()

# Single shared model configured via LiteLlm for NVIDIA NIM
shared_model = LiteLlm(
    model=f"nvidia_nim/{_settings.nvidia_chat_model}",
    api_base=_settings.nvidia_base_url,
    temperature=0.1,
)

# 1. Code Searcher Worker
code_searcher = LlmAgent(
    name="code_searcher",
    model=shared_model,
    description=prompts.CODE_SEARCHER_DESCRIPTION,
    instruction=prompts.CODE_SEARCHER_INSTRUCTION,
    tools=[rag_search, find_symbol],
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)

# 2. Code Explainer Worker
code_explainer = LlmAgent(
    name="code_explainer",
    model=shared_model,
    description=prompts.CODE_EXPLAINER_DESCRIPTION,
    instruction=prompts.CODE_EXPLAINER_INSTRUCTION,
    tools=[get_file_outline],
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
