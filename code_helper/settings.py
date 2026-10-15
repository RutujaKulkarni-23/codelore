from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

EMBED_DIMENSION: int = 2048
PINECONE_METRIC: str = "cosine"


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


@dataclass(frozen=True)
class Settings:
    nvidia_api_key: str
    nvidia_nim_api_key: str
    nvidia_base_url: str
    nvidia_chat_model: str
    nvidia_embed_model: str
    pinecone_api_key: str
    pinecone_index_name: str
    pinecone_cloud: str
    pinecone_region: str
    pinecone_namespace: str
    target_project_path: Path
    top_k: int
    min_score: float
    pythonutf8: str

    def __repr__(self) -> str:
        def _mask(val: str) -> str:
            if not val:
                return "<unset>"
            if len(val) <= 8:
                return "***"
            return f"{val[:4]}...{val[-4:]}"

        return (
            f"Settings("
            f"nvidia_api_key='{_mask(self.nvidia_api_key)}', "
            f"nvidia_nim_api_key='{_mask(self.nvidia_nim_api_key)}', "
            f"nvidia_base_url='{self.nvidia_base_url}', "
            f"nvidia_chat_model='{self.nvidia_chat_model}', "
            f"nvidia_embed_model='{self.nvidia_embed_model}', "
            f"pinecone_api_key='{_mask(self.pinecone_api_key)}', "
            f"pinecone_index_name='{self.pinecone_index_name}', "
            f"pinecone_cloud='{self.pinecone_cloud}', "
            f"pinecone_region='{self.pinecone_region}', "
            f"pinecone_namespace='{self.pinecone_namespace}', "
            f"target_project_path='{self.target_project_path}', "
            f"top_k={self.top_k}, "
            f"min_score={self.min_score}, "
            f"pythonutf8='{self.pythonutf8}'"
            f")"
        )


def load_settings(env_file_path: Path | None = None) -> Settings:
    """
    Loads and validates settings strictly from code_helper/.env.
    No parent-folder traversal and no fallback/mock modes.
    """
    if env_file_path is None:
        env_file_path = Path(__file__).resolve().parent / ".env"

    if env_file_path.exists():
        # override=False preserves any explicitly set runtime environment variables
        load_dotenv(dotenv_path=env_file_path, override=False)

    required_vars = [
        "NVIDIA_API_KEY",
        "NVIDIA_BASE_URL",
        "NVIDIA_CHAT_MODEL",
        "NVIDIA_EMBED_MODEL",
        "PINECONE_API_KEY",
        "PINECONE_INDEX_NAME",
        "PINECONE_CLOUD",
        "PINECONE_REGION",
        "TARGET_PROJECT_PATH",
    ]

    for var in required_vars:
        val = os.getenv(var, "").strip()
        if not val:
            raise ConfigError(f"Missing required environment variable: {var}")

    # Synchronize NVIDIA_NIM_API_KEY for LiteLLM if absent but NVIDIA_API_KEY is present
    nvidia_key = os.getenv("NVIDIA_API_KEY", "").strip()
    nim_key = os.getenv("NVIDIA_NIM_API_KEY", "").strip()
    if not nim_key and nvidia_key:
        os.environ["NVIDIA_NIM_API_KEY"] = nvidia_key
        nim_key = nvidia_key

    target_path_str = os.getenv("TARGET_PROJECT_PATH", "").strip()
    target_path = Path(target_path_str)
    if not target_path.exists():
        raise ConfigError(f"TARGET_PROJECT_PATH does not exist: {target_path_str}")
    if not target_path.is_dir():
        raise ConfigError(f"TARGET_PROJECT_PATH is not a directory: {target_path_str}")

    top_k_str = os.getenv("TOP_K", "5").strip()
    try:
        top_k = int(top_k_str)
    except ValueError:
        raise ConfigError(f"Invalid integer value for TOP_K: {top_k_str}")

    min_score_str = os.getenv("MIN_SCORE", "0.0").strip()
    try:
        min_score = float(min_score_str)
    except ValueError:
        raise ConfigError(f"Invalid float value for MIN_SCORE: {min_score_str}")

    return Settings(
        nvidia_api_key=nvidia_key,
        nvidia_nim_api_key=nim_key,
        nvidia_base_url=os.getenv("NVIDIA_BASE_URL", "").strip(),
        nvidia_chat_model=os.getenv("NVIDIA_CHAT_MODEL", "").strip(),
        nvidia_embed_model=os.getenv("NVIDIA_EMBED_MODEL", "").strip(),
        pinecone_api_key=os.getenv("PINECONE_API_KEY", "").strip(),
        pinecone_index_name=os.getenv("PINECONE_INDEX_NAME", "").strip(),
        pinecone_cloud=os.getenv("PINECONE_CLOUD", "").strip(),
        pinecone_region=os.getenv("PINECONE_REGION", "").strip(),
        pinecone_namespace=os.getenv("PINECONE_NAMESPACE", "naive-rag").strip(),
        target_project_path=target_path,
        top_k=top_k,
        min_score=min_score,
        pythonutf8=os.getenv("PYTHONUTF8", "1").strip(),
    )
