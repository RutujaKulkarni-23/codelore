from code_helper.rag.secrets_mask import mask_secrets


def test_mask_secrets_nvidia_key():
    # Dynamically build secret pattern to avoid literal string in test file
    fake_nv_key = "nvapi" + "-" + "A" * 32
    sample = f"NVIDIA_API_KEY = '{fake_nv_key}'\nprint('ready')"
    masked, count = mask_secrets(sample)
    assert count == 1
    assert fake_nv_key not in masked
    assert "<REDACTED>" in masked


def test_mask_secrets_pinecone_key():
    fake_pc_key = "pcsk" + "_" + "B" * 32
    sample = f"PINECONE_API_KEY='{fake_pc_key}'"
    masked, count = mask_secrets(sample)
    assert count >= 1
    assert fake_pc_key not in masked
    assert "<REDACTED>" in masked


def test_mask_secrets_openai_key():
    fake_sk_key = "sk" + "-" + "C" * 28
    sample = f"OPENAI_KEY = '{fake_sk_key}'"
    masked, count = mask_secrets(sample)
    assert count >= 1
    assert fake_sk_key not in masked
    assert "<REDACTED>" in masked


def test_mask_secrets_aws_key():
    fake_aws_key = "AKIA" + "1234567890ABCDEF"
    sample = f"aws_id = '{fake_aws_key}'"
    masked, count = mask_secrets(sample)
    assert count == 1
    assert fake_aws_key not in masked
    assert "<REDACTED>" in masked


def test_mask_secrets_pem_private_key():
    pem = (
        "-----BEGIN" + " RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0fakecontent...\n"
        "-----END" + " RSA PRIVATE KEY-----"
    )
    sample = f"tls_cert = '''{pem}'''"
    masked, count = mask_secrets(sample)
    assert count == 1
    assert "MIIEow" not in masked
    assert "<REDACTED>" in masked


def test_mask_clean_text():
    sample = "def calculate_sum(a, b):\n    return a + b\n"
    masked, count = mask_secrets(sample)
    assert count == 0
    assert masked == sample
