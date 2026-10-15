import pytest
from pathlib import Path
from code_helper.settings import Settings, ConfigError, load_settings, EMBED_DIMENSION, PINECONE_METRIC


def test_constants():
    assert EMBED_DIMENSION == 2048
    assert PINECONE_METRIC == "cosine"


def test_missing_variable_raises_config_error(monkeypatch, tmp_path):
    # Ensure environment is isolated with fake values
    fake_target = tmp_path / "fake_target"
    fake_target.mkdir()

    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("PINECONE_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://example.com")
    monkeypatch.setenv("TARGET_PROJECT_PATH", str(fake_target))

    dummy_env = tmp_path / ".env"
    dummy_env.write_text("DUMMY=1\n")

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env_file_path=dummy_env)

    assert "Missing required environment variable" in str(exc_info.value)
    assert "NVIDIA_API_KEY" in str(exc_info.value)


def test_target_project_path_must_exist(monkeypatch, tmp_path):
    non_existent = tmp_path / "does_not_exist"

    monkeypatch.setenv("NVIDIA_API_KEY", "fake_nv_key_123456789")
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NVIDIA_CHAT_MODEL", "meta/llama-3.2-11b-vision-instruct")
    monkeypatch.setenv("NVIDIA_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")
    monkeypatch.setenv("PINECONE_API_KEY", "fake_pc_key_123456789")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "code-helper")
    monkeypatch.setenv("PINECONE_CLOUD", "aws")
    monkeypatch.setenv("PINECONE_REGION", "us-east-1")
    monkeypatch.setenv("TARGET_PROJECT_PATH", str(non_existent))

    dummy_env = tmp_path / ".env"
    dummy_env.write_text("")

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env_file_path=dummy_env)

    assert "TARGET_PROJECT_PATH does not exist" in str(exc_info.value)


def test_settings_repr_masks_keys(monkeypatch, tmp_path):
    target_dir = tmp_path / "test_target"
    target_dir.mkdir()

    raw_nv_key = "test_synthetic_nvidia_secret_key_12345"
    raw_pc_key = "test_synthetic_pinecone_secret_key_67890"

    monkeypatch.setenv("NVIDIA_API_KEY", raw_nv_key)
    monkeypatch.setenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setenv("NVIDIA_CHAT_MODEL", "meta/llama-3.2-11b-vision-instruct")
    monkeypatch.setenv("NVIDIA_EMBED_MODEL", "nvidia/nemotron-3-embed-1b")
    monkeypatch.setenv("PINECONE_API_KEY", raw_pc_key)
    monkeypatch.setenv("PINECONE_INDEX_NAME", "code-helper")
    monkeypatch.setenv("PINECONE_CLOUD", "aws")
    monkeypatch.setenv("PINECONE_REGION", "us-east-1")
    monkeypatch.setenv("TARGET_PROJECT_PATH", str(target_dir))

    dummy_env = tmp_path / ".env"
    dummy_env.write_text("")

    settings = load_settings(env_file_path=dummy_env)
    repr_str = repr(settings)

    # Keys must NOT appear in full in repr
    assert raw_nv_key not in repr_str
    assert raw_pc_key not in repr_str
    assert "..." in repr_str


def test_no_mock_mode_when_keys_missing(monkeypatch, tmp_path):
    target_dir = tmp_path / "test_target"
    target_dir.mkdir()

    monkeypatch.setenv("NVIDIA_API_KEY", "")
    monkeypatch.setenv("PINECONE_API_KEY", "")
    monkeypatch.setenv("TARGET_PROJECT_PATH", str(target_dir))

    dummy_env = tmp_path / ".env"
    dummy_env.write_text("")

    with pytest.raises(ConfigError):
        load_settings(env_file_path=dummy_env)
