from pathlib import Path
from code_helper.settings import load_settings


def get_project_root() -> Path:
    """Returns the target project root directory configured in settings."""
    settings = load_settings()
    return settings.target_project_path


def get_namespace() -> str:
    """Returns the Pinecone namespace configured in settings."""
    settings = load_settings()
    return settings.pinecone_namespace
