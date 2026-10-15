import os
import sys
from pathlib import Path
from openai import OpenAI
import litellm

# Ensure codelore root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from code_helper.settings import load_settings


def smoke_test():
    settings = load_settings()
    print("=== SMOKE TEST: API SANITY CHECK ===")

    # (a) Embedding call via openai client
    print("\n--- Test (a): NVIDIA NIM Embedding Call ---")
    embed_client = OpenAI(
        base_url=settings.nvidia_base_url,
        api_key=settings.nvidia_api_key,
    )
    embed_resp = embed_client.embeddings.create(
        input=["hello world"],
        model=settings.nvidia_embed_model,
        extra_body={"input_type": "query"},
    )
    vec = embed_resp.data[0].embedding
    print(f"Embedding Model: {settings.nvidia_embed_model}")
    print(f"Embedding Vector Length: {len(vec)}")

    # (b) LiteLLM chat completion call
    print("\n--- Test (b): LiteLLM Chat Completion ---")
    model_name = f"nvidia_nim/{settings.nvidia_chat_model}"
    chat_resp = litellm.completion(
        model=model_name,
        messages=[{"role": "user", "content": "Reply with the word OK"}],
        api_base=settings.nvidia_base_url,
        api_key=settings.nvidia_api_key,
        temperature=0.0,
    )
    raw_content = chat_resp.choices[0].message.content or ""
    # Print only first 50 chars, sanitized
    print(f"Chat Model: {model_name}")
    print(f"Reply Content (first 50 chars): {repr(raw_content[:50])}")

    # (c) LiteLLM Tool-Calling Check
    print("\n--- Test (c): LiteLLM Tool Calling Check ---")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Returns the current UTC time.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
    ]
    tool_resp = litellm.completion(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": "What is the current time? Call the get_current_time function.",
            }
        ],
        tools=tools,
        tool_choice="auto",
        api_base=settings.nvidia_base_url,
        api_key=settings.nvidia_api_key,
        temperature=0.0,
    )
    msg = tool_resp.choices[0].message
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls and len(tool_calls) > 0:
        fn_name = tool_calls[0].function.name
        print(f"Tool Calling Result: SUCCESS (Model returned tool call: '{fn_name}')")
    else:
        print(f"Tool Calling Result: FAILED (Model responded with text instead: {repr((msg.content or '')[:80])})")


if __name__ == "__main__":
    smoke_test()
