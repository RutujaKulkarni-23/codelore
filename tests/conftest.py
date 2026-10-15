"""
Global pytest configuration for CodeLore offline test suite.
Injects fake environment configuration BEFORE any code_helper module import,
ensuring offline tests can import code_helper without requiring a real .env.
"""
import os
from pathlib import Path
import pytest

# Fixture project directory for offline test runs
SAMPLE_PROJECT = Path(__file__).resolve().parent / "fixtures" / "sample_project"
REAL_TARGET = Path("D:/CodeLore/targets/Naive_RAG")

# Use real target if present (so tool tests targeting Naive_RAG pass), else sample fixture
TARGET = REAL_TARGET if REAL_TARGET.exists() else SAMPLE_PROJECT

# If a real code_helper/.env exists, do not inject fake values so live tests can run.
# If .env is absent (e.g. offline CI), inject fake values so modules import cleanly.
if os.environ.get("RUN_LIVE") != "1":
    if "NVIDIA_API_KEY" not in os.environ:
        os.environ["NVIDIA_API_KEY"] = "nvapi-" + "fake_nvidia_test_key_offline"
    if "NVIDIA_NIM_API_KEY" not in os.environ:
        os.environ["NVIDIA_NIM_API_KEY"] = "nvapi-" + "fake_nvidia_test_key_offline"
    if "NVIDIA_BASE_URL" not in os.environ:
        os.environ["NVIDIA_BASE_URL"] = "https://integrate.api.nvidia.com/v1"
    if "NVIDIA_CHAT_MODEL" not in os.environ:
        os.environ["NVIDIA_CHAT_MODEL"] = "meta/llama-3.2-11b-vision-instruct"
    if "NVIDIA_EMBED_MODEL" not in os.environ:
        os.environ["NVIDIA_EMBED_MODEL"] = "nvidia/llama-3.2-nv-embedqa-1b-v2"
    if "PINECONE_API_KEY" not in os.environ:
        os.environ["PINECONE_API_KEY"] = "pcsk_" + "fake_pinecone_test_key_offline"
    if "PINECONE_INDEX_NAME" not in os.environ:
        os.environ["PINECONE_INDEX_NAME"] = "test-code-helper"
    if "PINECONE_CLOUD" not in os.environ:
        os.environ["PINECONE_CLOUD"] = "aws"
    if "PINECONE_REGION" not in os.environ:
        os.environ["PINECONE_REGION"] = "us-east-1"
    if "PINECONE_NAMESPACE" not in os.environ:
        os.environ["PINECONE_NAMESPACE"] = "test-namespace"
    if "TARGET_PROJECT_PATH" not in os.environ:
        os.environ["TARGET_PROJECT_PATH"] = str(TARGET)
