import re

# Compiled regex patterns for credential detection
SECRET_PATTERNS = [
    # NVIDIA NIM API Keys
    re.compile(r"nvapi-[A-Za-z0-9_-]+"),
    # Pinecone API Keys
    re.compile(r"pcsk_[A-Za-z0-9_-]+"),
    # OpenAI and generic API Keys
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    # AWS Access Key IDs
    re.compile(r"AKIA[0-9A-Z]{16}"),
    # PEM Private Key Blocks
    re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"),
    # Long string literals assigned to variables with suspicious names
    re.compile(
        r"""(?i)(?:api_key|apikey|secret|token|password|auth_token)\s*=\s*['"][A-Za-z0-9_\-\.]{16,}['"]"""
    ),
]


def mask_secrets(text: str) -> tuple[str, int]:
    """
    Masks potential secrets and API credentials in text before embedding or logging.

    Detection is heuristic and imperfect: it identifies common provider token prefixes
    (nvapi-, pcsk_, sk-, AKIA), private key PEM banners, and assignments to sensitive variable names.
    It should not be relied upon as a substitute for keeping secrets out of code and repositories.

    Returns:
        tuple[str, int]: (masked_text, total_replacement_count)
    """
    masked_text = text
    total_count = 0

    for pattern in SECRET_PATTERNS:
        matches = list(pattern.finditer(masked_text))
        if matches:
            total_count += len(matches)
            masked_text = pattern.sub("<REDACTED>", masked_text)

    return masked_text, total_count
