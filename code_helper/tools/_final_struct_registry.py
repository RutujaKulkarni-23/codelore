"""
Thread-safe store for temp:final_struct so it can be reliably captured
by the SSE runner in server/app.py even if ADK trims temp state.
"""
from typing import Any

_LAST_STRUCT: dict[str, dict[str, Any]] = {}
_CURRENT_STRUCT: dict[str, Any] | None = None


def set_last_final_struct(struct: dict[str, Any], session_id: str | None = None) -> None:
    global _CURRENT_STRUCT
    _CURRENT_STRUCT = struct
    if session_id:
        _LAST_STRUCT[session_id] = struct


def get_and_clear_final_struct(session_id: str | None = None) -> dict[str, Any] | None:
    global _CURRENT_STRUCT
    val = None
    if session_id and session_id in _LAST_STRUCT:
        val = _LAST_STRUCT.pop(session_id)
    if val is None:
        val = _CURRENT_STRUCT
    _CURRENT_STRUCT = None
    return val
