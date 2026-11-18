"""Transparent, bounded response planning (not a hidden chain-of-thought store)."""
from __future__ import annotations

def build_plan(user_text: str, understanding: dict, history: list[dict] | None = None) -> dict:
    return {
        "intent": understanding.get("intent", "conversation"),
        "language": understanding.get("language", "auto"),
        "needs_clarification": len((user_text or "").strip()) < 2,
        "context_messages": min(len(history or []), 12),
        "instruction": "Answer the actual request, preserve context, and ask one concise clarification only when necessary."
    }
