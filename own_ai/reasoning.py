"""Bounded response planning; this stores plans, not private chain-of-thought."""
from __future__ import annotations
def build_plan(user_text: str, understanding: dict, history: list[dict] | None = None,
               preferences: dict | None = None) -> dict:
    intent = understanding.get("intent","conversation")
    return {"intent":intent,"language":understanding.get("language","unknown"),
            "needs_clarification":bool(understanding.get("needs_clarification")),
            "context_messages":min(len(history or []),24),
            "response_style":(preferences or {}).get("style","natural_concise"),
            "steps":["identify the request","use relevant conversation context",
                     "check uncertainty and safety","answer in the user's language"],
            "instruction":"Answer the current request directly. Use context only when relevant. "
                          "State uncertainty honestly; do not expose internal reasoning."}
