"""Reply validation and personality composition."""
from __future__ import annotations
from .personality import apply_personality, fallback
def compose_reply(answer: str, language: str = "unknown") -> str:
    value=(answer or "").strip()
    if not value: value=fallback(language)
    return apply_personality(value[:12000],language)
